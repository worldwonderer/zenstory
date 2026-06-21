"""Streaming runner that adapts openai-agents-python to ZenStory workflow events."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator, Callable
from typing import Any

from agent.core.workflow_events import StreamEvent, StreamEventType
from agent.graph.state import WritingState
from agent.openai_agents.events import (
    build_handoff_packet,
    extract_artifact_refs,
    mcp_text_result,
    merge_unique_strings,
    normalize_str_list,
    parse_json_object,
)
from agent.openai_agents.model import DEEPSEEK_WRITING_MODEL, get_deepseek_chat_model
from agent.openai_agents.tools_adapter import build_agent_function_tools
from config.agent_runtime import (
    AGENT_COLLABORATION_MAX_ITERATIONS,
    AGENT_OPENAI_AGENTS_MAX_OUTPUT_TOKENS,
    AGENT_TOOL_CALL_MAX_ITERATIONS,
)
from utils.logger import get_logger, log_with_context

logger = get_logger(__name__)

MessageList = list[dict[str, Any]]


def extract_text_from_message_content(content: Any) -> str:
    """Convert persisted mixed content blocks to plain text for Chat Completions input."""
    if isinstance(content, str):
        return content

    if not isinstance(content, list):
        return "" if content is None else str(content)

    parts: list[str] = []
    for block in content:
        if isinstance(block, str):
            if block.strip():
                parts.append(block)
            continue
        if not isinstance(block, dict):
            continue

        block_type = block.get("type")
        if block_type == "text":
            text = block.get("text")
            if isinstance(text, str) and text.strip():
                parts.append(text)
        # tool_use / tool_result blocks are intentionally omitted from replay. The SDK owns
        # the live tool-call loop within a single agent run; re-serializing a prior turn's
        # tool calls/results as plain prose would inject raw tool JSON (file ids, arguments)
        # into the next agent as if the *user* had said it, degrading instruction-following.
        # Cross-agent continuity is instead carried by the structured handoff packet
        # (context / completed / artifact_refs) and the refreshed file inventory, which also
        # avoids any orphaned-tool_call_id risk from replaying partial structured tool turns.
        # thinking/reasoning blocks are likewise omitted (persisted for UI/history only).

    return "\n".join(part for part in parts if part.strip())


def normalize_messages_for_openai_agents(messages: MessageList) -> MessageList:
    """Normalize project chat history to SDK easy-input messages."""
    normalized: MessageList = []
    for message in messages:
        if not isinstance(message, dict):
            continue
        role = str(message.get("role") or "").strip().lower()
        if role not in {"user", "assistant", "system", "developer"}:
            continue

        text = extract_text_from_message_content(message.get("content"))
        if not text.strip():
            continue

        normalized.append({"role": role, "content": text})

    return normalized


def should_append_user_message(messages: MessageList, user_message: str) -> bool:
    """Return True when the current user message is not already the last message."""
    if not user_message:
        return False
    if not messages:
        return True
    last = messages[-1]
    return last.get("role") != "user" or str(last.get("content") or "") != user_message


def build_history_messages(state: WritingState) -> MessageList:
    """Build normalized SDK input messages from workflow state."""
    api_messages = normalize_messages_for_openai_agents(list(state.get("messages", []) or []))
    user_message = str(state.get("user_message") or "")
    if should_append_user_message(api_messages, user_message):
        api_messages.append({"role": "user", "content": user_message})
    return api_messages


def _append_assistant_turn_to_state_messages(
    state: WritingState,
    api_messages: MessageList,
    *,
    assistant_text: str,
    thinking_text: str,
    tool_uses: list[dict[str, Any]],
) -> None:
    """Persist the SDK run progression for downstream graph agents."""
    updated: MessageList = list(api_messages)

    assistant_content: list[dict[str, Any]] = []
    if thinking_text.strip():
        assistant_content.append({"type": "thinking", "thinking": thinking_text})
    if assistant_text.strip():
        assistant_content.append({"type": "text", "text": assistant_text})
    for tool_use in tool_uses:
        assistant_content.append(
            {
                "type": "tool_use",
                "id": tool_use.get("id", ""),
                "name": tool_use.get("name", ""),
                "input": tool_use.get("input", {}),
            }
        )

    if assistant_content:
        updated.append({"role": "assistant", "content": assistant_content})

    tool_results = []
    for tool_use in tool_uses:
        if tool_use.get("result") is None:
            continue
        tool_results.append(
            {
                "type": "tool_result",
                "tool_use_id": tool_use.get("id", ""),
                "content": tool_use.get("result", ""),
            }
        )
    if tool_results:
        updated.append({"role": "user", "content": tool_results})

    state["messages"] = updated


def _raw_event_type(raw_event: Any) -> str:
    return str(getattr(raw_event, "type", "") or "")


def _raw_event_delta(raw_event: Any) -> str:
    delta = getattr(raw_event, "delta", "")
    return delta if isinstance(delta, str) else str(delta or "")


def _raw_item_value(raw_item: Any, key: str, default: Any = None) -> Any:
    if isinstance(raw_item, dict):
        return raw_item.get(key, default)
    return getattr(raw_item, key, default)


def _tool_call_payload(item: Any) -> tuple[str, str, dict[str, Any]]:
    tool_name = getattr(item, "tool_name", None) or _raw_item_value(getattr(item, "raw_item", None), "name", "")
    call_id = getattr(item, "call_id", None) or _raw_item_value(getattr(item, "raw_item", None), "call_id", "")
    raw_arguments = _raw_item_value(getattr(item, "raw_item", None), "arguments", "")
    if raw_arguments is None:
        raw_arguments = ""
    parsed, parse_error, _metadata = parse_json_object(str(raw_arguments), tool_name=str(tool_name or ""))
    if parse_error is not None:
        parsed = {}
    return str(tool_name or ""), str(call_id or ""), parsed


def _tool_output_payload(item: Any) -> tuple[str, str]:
    call_id = getattr(item, "call_id", None) or _raw_item_value(getattr(item, "raw_item", None), "call_id", "")
    output = getattr(item, "output", "")
    return str(call_id or ""), output if isinstance(output, str) else str(output)


def _usage_dict_from_result(result: Any) -> dict[str, int]:
    usage: dict[str, int] = {}
    raw_responses = getattr(result, "raw_responses", None)
    if not isinstance(raw_responses, list):
        return usage

    for raw_response in raw_responses:
        response_usage = getattr(raw_response, "usage", None)
        if response_usage is None:
            continue
        for source_attr, target_key in (
            ("input_tokens", "input_tokens"),
            ("output_tokens", "output_tokens"),
            ("total_tokens", "total_tokens"),
        ):
            value = getattr(response_usage, source_attr, 0) or 0
            if value:
                usage[target_key] = usage.get(target_key, 0) + int(value)
    return usage


def _build_agent(agent_type: str, system_prompt: str) -> Any:
    # NOTE — Agent.as_tool was evaluated and rejected.
    # Agent.as_tool wraps an agent as a callable tool for a parent agent, which
    # would collapse each sub-agent's SSE events into a single opaque tool result
    # and eliminate the per-agent streaming visibility the UI depends on.  It would
    # also merge the two independent iteration budgets (AGENT_TOOL_CALL_MAX_ITERATIONS
    # per agent, AGENT_COLLABORATION_MAX_ITERATIONS across the graph) into one, making
    # it impossible to surface per-agent exhaustion cleanly.  The current explicit
    # graph loop + handoff packet approach is intentional; do not replace with as_tool.
    #
    # NOTE — reasoning lever (not yet activated).
    # ModelSettings also accepts a ``reasoning`` field (maps to the model's reasoning-effort
    # parameter) and an ``extra_body`` dict for provider-specific kwargs.  DeepSeek's
    # Chat Completions API does not document a first-class reasoning-effort parameter for
    # deepseek-chat / deepseek-v4-flash (it is a feature of the separate /beta/reasoner
    # endpoint).  Activating it without confirmation risks a 400/422 from the API.
    # When DeepSeek confirms the parameter for the chat endpoint, add:
    #   model_settings=ModelSettings(..., reasoning={"effort": "medium"})
    # or route through extra_body if the SDK does not yet expose it natively.
    # Until then, do NOT set reasoning here.
    from agents import Agent, ModelSettings

    return Agent(
        name=agent_type,
        instructions=system_prompt,
        model=get_deepseek_chat_model(),
        model_settings=ModelSettings(
            temperature=1.0,
            top_p=0.95,
            max_tokens=AGENT_OPENAI_AGENTS_MAX_OUTPUT_TOKENS,
        ),
        tools=build_agent_function_tools(agent_type),
    )


async def _inject_initial_steering(
    api_messages: MessageList,
    get_steering_messages: Callable[[], Any] | None,
) -> AsyncIterator[StreamEvent]:
    if get_steering_messages is None:
        return

    try:
        steering_msgs = await get_steering_messages()
        for msg in steering_msgs or []:
            content = str(msg.get("content") or "") if isinstance(msg, dict) else ""
            if not content:
                continue
            api_messages.append({"role": "user", "content": content})
            from agent.core.events import steering_received_event

            yield steering_received_event(
                message_id=str(msg.get("id") or "") if isinstance(msg, dict) else "",
                preview=content[:50],
            )
    except Exception as exc:
        log_with_context(
            logger,
            40,  # ERROR
            "Failed to retrieve steering messages for OpenAI Agents run",
            error=str(exc),
            error_type=type(exc).__name__,
        )


async def run_openai_agents_streaming_agent(
    state: WritingState,
    agent_type: str,
    system_prompt: str,
    get_steering_messages: Callable[[], Any] | None = None,
) -> AsyncIterator[StreamEvent]:
    """Run one writing agent via openai-agents-python and yield workflow events."""
    api_messages = build_history_messages(state)
    assistant_text_parts: list[str] = []
    thinking_text_parts: list[str] = []
    tool_uses: list[dict[str, Any]] = []
    tool_inputs_by_call_id: dict[str, dict[str, Any]] = {}
    tool_names_by_call_id: dict[str, str] = {}
    artifact_refs_accumulated: list[str] = []
    handoff_event_data: dict[str, Any] | None = None
    clarification_event_data: dict[str, Any] | None = None

    # Read-only co-call instrumentation (item 1.4).
    # Approximation: within a single assistant turn, the SDK emits all tool_called events
    # first, then tool_output events (even with max_function_tool_concurrency=1, which
    # serialises *execution* but not the event ordering for calls batched in one response).
    # We track per-turn how many read-only tool calls appear before the first tool_output
    # of that turn; when ≥2 are observed we record a co-call event.  A new "turn" begins
    # after every tool_output (the model produced a fresh response with new tool requests).
    _READONLY_TOOLS: frozenset[str] = frozenset({"query_files", "hybrid_search"})
    _turn_readonly_pending: int = 0   # read-only calls seen since last tool_output
    _turn_has_output: bool = False    # whether the current turn has received any tool_output

    async for steering_event in _inject_initial_steering(api_messages, get_steering_messages):
        yield steering_event

    yield StreamEvent(
        type=StreamEventType.MESSAGE_START,
        data={"model": DEEPSEEK_WRITING_MODEL, "agent_type": agent_type},
    )

    try:
        from agents import RunConfig, Runner, ToolExecutionConfig
        from agents.exceptions import MaxTurnsExceeded

        from .intra_run_trimmer import IntraRunToolOutputTrimmer

        sdk_agent = _build_agent(agent_type, system_prompt)
        result = Runner.run_streamed(
            sdk_agent,
            input=api_messages,
            max_turns=AGENT_TOOL_CALL_MAX_ITERATIONS,
            # When DeepSeek emits multiple tool_calls in one turn, the SDK would run them
            # concurrently (asyncio.create_task). Project tools share a single SQLAlchemy
            # Session via ToolContext, which is NOT safe for concurrent use. Serialize tool
            # execution to preserve the previous sequential contract and avoid Session races.
            run_config=RunConfig(
                tool_execution=ToolExecutionConfig(max_function_tool_concurrency=1),
                # Preview stale intra-run retrieval outputs (query_files / hybrid_search)
                # so a long multi-tool run doesn't re-send every bulky search dump on each
                # subsequent model call. Keeps the freshest outputs full; control-flow tool
                # outputs are never touched. See intra_run_trimmer for why the stock SDK
                # ToolOutputTrimmer is a no-op for this project's history shape.
                call_model_input_filter=IntraRunToolOutputTrimmer(),
            ),
        )

        try:
            async for sdk_event in result.stream_events():
                event_type = getattr(sdk_event, "type", "")

                if event_type == "raw_response_event":
                    raw = getattr(sdk_event, "data", None)
                    raw_type = _raw_event_type(raw)
                    if raw_type == "response.output_text.delta":
                        text = _raw_event_delta(raw)
                        if text:
                            assistant_text_parts.append(text)
                            yield StreamEvent(type=StreamEventType.TEXT, data={"text": text})
                    elif raw_type in {
                        "response.reasoning_text.delta",
                        "response.reasoning_summary_text.delta",
                    }:
                        thinking = _raw_event_delta(raw)
                        if thinking:
                            thinking_text_parts.append(thinking)
                            yield StreamEvent(type=StreamEventType.THINKING, data={"thinking": thinking})
                    continue

                if event_type != "run_item_stream_event":
                    continue

                event_name = getattr(sdk_event, "name", "")
                item = getattr(sdk_event, "item", None)
                if event_name == "tool_called":
                    tool_name, call_id, tool_input = _tool_call_payload(item)
                    if call_id:
                        tool_names_by_call_id[call_id] = tool_name
                        tool_inputs_by_call_id[call_id] = tool_input
                    tool_uses.append(
                        {
                            "id": call_id,
                            "name": tool_name,
                            "input": tool_input,
                            "result": None,
                        }
                    )
                    # Read-only co-call tracking: count read-only calls before outputs arrive.
                    # A tool_called arriving after a turn's outputs starts a NEW turn, so
                    # reset the per-turn tracking here (not in the tool_output block) — that
                    # keeps the turn guard set for the whole turn and avoids counting every
                    # tool_output as a separate turn.
                    if _turn_has_output:
                        _turn_has_output = False
                        _turn_readonly_pending = 0
                    if tool_name in _READONLY_TOOLS:
                        _turn_readonly_pending += 1
                    yield StreamEvent(
                        type=StreamEventType.TOOL_USE,
                        data={
                            "id": call_id,
                            "name": tool_name,
                            "status": "complete",
                            "input": tool_input,
                        },
                    )
                elif event_name == "tool_output":
                    # First tool_output of this turn: flush the pending read-only count.
                    # The guard stays set for the rest of the turn; the next tool_called
                    # batch resets it. This counts each turn exactly once (the previous
                    # in-block reset made it count every tool_output as a turn).
                    if not _turn_has_output:
                        _turn_has_output = True
                        from agent.core.metrics import (
                            TOOL_READONLY_COCALL_TOTAL,
                            TOOL_READONLY_TURNS_TOTAL,
                            get_metrics_collector,
                        )
                        _mc = get_metrics_collector()
                        _mc.increment_counter(TOOL_READONLY_TURNS_TOTAL)
                        if _turn_readonly_pending >= 2:
                            _mc.increment_counter(TOOL_READONLY_COCALL_TOTAL)
                    call_id, result_text = _tool_output_payload(item)
                    tool_name = tool_names_by_call_id.get(call_id, "")
                    tool_input = tool_inputs_by_call_id.get(call_id, {})
                    if tool_uses:
                        for tool_use in reversed(tool_uses):
                            if tool_use.get("id") == call_id:
                                tool_use["result"] = result_text
                                break
                    result_payload = mcp_text_result(result_text)

                    artifact_refs_accumulated = merge_unique_strings(
                        artifact_refs_accumulated,
                        extract_artifact_refs(tool_name, result_text, tool_input=tool_input),
                    )

                    yield StreamEvent(
                        type=StreamEventType.TOOL_RESULT,
                        data={
                            "tool_use_id": call_id,
                            "name": tool_name,
                            "result": result_payload,
                        },
                    )

                    try:
                        result_data = json.loads(result_text) if result_text else {}
                    except json.JSONDecodeError:
                        result_data = {}

                    if tool_name == "handoff_to_agent" and result_data.get("status") == "handoff":
                        # DESIGN NOTE — do not migrate to the SDK's native Agent(handoffs=[...]).
                        #
                        # The SDK's built-in handoff mechanism passes a plain text string from
                        # one agent to the next.  ZenStory's handoff carries a structured packet
                        # (completed/todo/evidence/artifact_refs) assembled here from the live
                        # tool result, plus pre-handoff narration that has already been streamed
                        # as TEXT events.  The SDK's text-passing handoff cannot express this
                        # structured context, and rebuilding it inside the SDK's callback would
                        # require duplicating the packet-assembly and event-streaming logic that
                        # lives in build_handoff_packet / extract_artifact_refs.
                        #
                        # result.cancel(mode="after_turn") lets the current SDK turn finish
                        # cleanly (so any in-flight streaming completes) before the graph picks
                        # up the handoff_event_data and routes to the next agent node.  Using
                        # "immediate" would truncate the trailing text stream; keep "after_turn".
                        packet = build_handoff_packet(
                            result_data,
                            artifact_refs=artifact_refs_accumulated,
                        )
                        handoff_event_data = {
                            "target_agent": packet["target_agent"],
                            "reason": packet["reason"],
                            "context": packet["context"],
                            "handoff_packet": packet,
                        }
                        result.cancel(mode="after_turn")
                    elif tool_name == "request_clarification" and result_data.get("status") == "clarification_needed":
                        clarification_event_data = {
                            "reason": "clarification_needed",
                            "agent_type": agent_type,
                            "message": result_data.get("question", "等待您的回复"),
                            "question": result_data.get("question", ""),
                            "context": result_data.get("context", ""),
                            "details": normalize_str_list(result_data.get("details")),
                        }
                        result.cancel(mode="after_turn")
        except MaxTurnsExceeded:
            yield StreamEvent(
                type=StreamEventType.ITERATION_EXHAUSTED,
                data={
                    "layer": "tool_call",
                    "iterations_used": AGENT_TOOL_CALL_MAX_ITERATIONS,
                    "max_iterations": AGENT_TOOL_CALL_MAX_ITERATIONS,
                    "reason": (
                        f"单个 Agent（{agent_type}）的工具调用轮数已达上限"
                        f"（{AGENT_TOOL_CALL_MAX_ITERATIONS} 轮）。"
                        f"这是单个 Agent 内的工具调用限制，与 Agent 协作轮数"
                        f"（{AGENT_COLLABORATION_MAX_ITERATIONS} 轮）独立。"
                        "当前任务可能未完全完成，您可以继续对话让 AI 完成剩余工作。"
                    ),
                    "last_agent": agent_type,
                },
            )

        if clarification_event_data is not None:
            from agent.core.metrics import AGENT_CLARIFICATION_TOTAL, get_metrics_collector

            get_metrics_collector().increment_counter(AGENT_CLARIFICATION_TOTAL)
            yield StreamEvent(type=StreamEventType.WORKFLOW_STOPPED, data=clarification_event_data)
        elif handoff_event_data is not None:
            yield StreamEvent(type=StreamEventType.HANDOFF, data=handoff_event_data)

        usage = _usage_dict_from_result(result)
        yield StreamEvent(
            type=StreamEventType.MESSAGE_END,
            data={"stop_reason": "end_turn", "usage": usage},
        )

        log_with_context(
            logger,
            20,  # INFO
            "OpenAI Agents streaming run completed",
            agent_type=agent_type,
            tool_calls=len(tool_uses),
            response_length=sum(len(part) for part in assistant_text_parts),
        )

    except Exception as exc:
        log_with_context(
            logger,
            40,  # ERROR
            "OpenAI Agents streaming run failed",
            agent_type=agent_type,
            error=str(exc),
            error_type=type(exc).__name__,
        )
        yield StreamEvent(
            type=StreamEventType.ERROR,
            data={"error": str(exc), "error_type": type(exc).__name__},
        )
    finally:
        _append_assistant_turn_to_state_messages(
            state,
            api_messages,
            assistant_text="".join(assistant_text_parts),
            thinking_text="".join(thinking_text_parts),
            tool_uses=tool_uses,
        )
