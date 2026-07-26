"""Streaming runner that adapts openai-agents-python to ZenStory workflow events."""

from __future__ import annotations

import asyncio
import contextlib
import json
from collections.abc import AsyncIterator, Callable
from typing import Any

from agent.core.progress_channel import reset_progress_emitter, set_progress_emitter
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

# 控制流工具：调用成功即表示「本次 SDK run 到此为止」——
# handoff_to_agent 把控制权交给下一个 agent，request_clarification 把控制权交回用户。
# 工具名与 agent/tools/registry.py 的注册名一致（tools_adapter 原样透传给 SDK）。
CONTROL_FLOW_TOOL_NAMES: tuple[str, ...] = ("handoff_to_agent", "request_clarification")

# 控制流工具「调用成功」的判定：只有返回这些 status 才算真的要停下。
# 参数非法时（invalid target_agent / self handoff / question is required）工具返回 error，
# 此时必须让模型看到错误并在同一个 run 内自行纠正，绝不能把 run 截断掉。
_CONTROL_FLOW_STOP_STATUS: dict[str, str] = {
    "handoff_to_agent": "handoff",
    "request_clarification": "clarification_needed",
}


def _control_flow_status_of(tool_name: str, output_text: str) -> bool:
    """判断某次工具输出是否是「生效的控制流结果」。"""
    expected = _CONTROL_FLOW_STOP_STATUS.get(tool_name)
    if expected is None:
        return False
    try:
        payload = json.loads(output_text) if output_text else {}
    except (json.JSONDecodeError, TypeError):
        return False
    return isinstance(payload, dict) and payload.get("status") == expected


def _stop_run_on_control_flow_tool(_ctx: Any, tool_results: list[Any]) -> Any:
    """SDK 的 tool_use_behavior 回调：控制流工具生效后立即结束当前 run。

    为什么不能只靠 result.cancel(mode="after_turn")：cancel 是异步落地的——
    SDK run-loop 把 tool_output 放进自己的 _event_queue，经 _pump_sdk_events 转发到
    run_queue，本模块的消费循环才读到并 cancel；等标志位落地时 run-loop 早已发起了
    下一次模型调用，那一轮的正文会被推给前端、工具（create_file/edit_file/delete_file）
    会被真实执行——「工作流已暂停」却仍在改用户的文件。
    这里改用 SDK 在 turn 内同步检查的 tool_use_behavior（turn_resolution.py
    check_for_final_output_from_tools），控制流工具一返回就把本轮当作 final output，
    run-loop 不会再发起下一次模型调用。

    用可调用对象而非 StopAtTools(dict) 的原因：StopAtTools 只看工具名，
    控制流工具报错（例如 target_agent 非法）时也会把 run 掐断，模型将失去在同一个
    run 内纠错的机会；这里按返回 status 精确判定。
    """
    from agents.agent import ToolsToFinalOutputResult

    for tool_result in tool_results or []:
        tool_name = str(getattr(getattr(tool_result, "tool", None), "name", "") or "")
        if tool_name not in CONTROL_FLOW_TOOL_NAMES:
            continue
        output = getattr(tool_result, "output", "")
        output_text = output if isinstance(output, str) else str(output)
        if _control_flow_status_of(tool_name, output_text):
            return ToolsToFinalOutputResult(is_final_output=True, final_output=output_text)

    return ToolsToFinalOutputResult(is_final_output=False, final_output=None)


def _is_new_model_turn_event(sdk_event: Any) -> bool:
    """事件是否意味着「模型又开了新的一轮」。

    单个 turn 内，模型响应流（raw_response_event）先跑完，SDK 才执行工具并发出
    tool_output；因此控制流工具的 tool_output 之后再出现任何 raw_response_event，
    或再出现 tool_called，都只能来自新的一轮模型调用。
    """
    event_type = str(getattr(sdk_event, "type", "") or "")
    if event_type == "raw_response_event":
        return True
    return event_type == "run_item_stream_event" and getattr(sdk_event, "name", "") == "tool_called"


def _safe_cancel(result: Any, mode: str) -> None:
    """调用 SDK 的 cancel，忽略实现差异/已结束 run 带来的异常。"""
    cancel = getattr(result, "cancel", None)
    if not callable(cancel):
        return
    with contextlib.suppress(Exception):
        cancel(mode=mode)


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


def _int_attr(source: Any, name: str) -> int:
    """读取 usage 上的整数字段，缺失/None/非法一律按 0 处理。"""
    value = getattr(source, name, 0)
    if value is None:
        return 0
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _usage_dict_from_result(result: Any) -> dict[str, int]:
    """汇总本次 SDK run 全部模型响应的 token 用量。

    cache_read_tokens：DeepSeek 的 prompt cache 命中量（OpenAI 兼容字段
    prompt_tokens_details.cached_tokens，SDK 映射为 input_tokens_details.cached_tokens）。
    它是 prompt_tokens 的**子集**，而 writing_stats_service 的计价公式是
    input * 输入价 + cache_read * 缓存价（相加），所以这里必须把命中缓存的部分从
    input_tokens 里扣掉，否则同一批 token 会被按输入价和缓存价重复计费。
    """
    totals = {
        "input_tokens": 0,
        "output_tokens": 0,
        "total_tokens": 0,
        "cache_read_tokens": 0,
    }
    raw_responses = getattr(result, "raw_responses", None)
    if not isinstance(raw_responses, list):
        return {}

    for raw_response in raw_responses:
        response_usage = getattr(raw_response, "usage", None)
        if response_usage is None:
            continue

        input_tokens = _int_attr(response_usage, "input_tokens")
        cached_tokens = _int_attr(
            getattr(response_usage, "input_tokens_details", None), "cached_tokens"
        )
        cached_tokens = max(0, min(cached_tokens, input_tokens))

        totals["input_tokens"] += input_tokens - cached_tokens
        totals["cache_read_tokens"] += cached_tokens
        totals["output_tokens"] += _int_attr(response_usage, "output_tokens")
        totals["total_tokens"] += _int_attr(response_usage, "total_tokens")

    # 保持「无用量时返回空 dict」的既有契约：下游用非空判断是否拿到真实 usage。
    return {key: value for key, value in totals.items() if value}


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
            # include_usage 决定请求体里是否带 stream_options={"include_usage": true}。
            # SDK 的默认值只在 client 指向 api.openai.com 时才是 True
            # （chatcmpl_helpers.get_stream_options_param），而本项目走 api.deepseek.com，
            # 不显式打开的话 OpenAI 兼容流式接口不会补发带 usage 的末尾 chunk，
            # MESSAGE_END 的 usage 恒为空，用量统计只能退化成「字符数/4」的估算。
            include_usage=True,
        ),
        tools=build_agent_function_tools(agent_type),
        # 控制流工具生效即结束 run，避免 SDK 在「工作流已暂停」之后再跑一整轮
        # 模型调用并真实执行其工具（详见 _stop_run_on_control_flow_tool）。
        tool_use_behavior=_stop_run_on_control_flow_tool,
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


async def _consume_boundary_steering(
    collected: list[str],
    get_steering_messages: Callable[[], Any] | None,
) -> AsyncIterator[StreamEvent]:
    """Consume steering that arrived while the SDK run is executing.

    openai-agents 不支持向进行中的 run 注入消息，工具输出边界只做消费与
    前端确认；内容暂存 collected，run 结束后写回 state.messages，由 graph
    决定是否追加一轮 writer 让引导在本次请求内生效。
    """
    if get_steering_messages is None:
        return
    try:
        steering_msgs = await get_steering_messages()
    except Exception as exc:
        log_with_context(
            logger,
            40,  # ERROR
            "Failed to retrieve steering messages at tool boundary",
            error=str(exc),
            error_type=type(exc).__name__,
        )
        return
    for msg in steering_msgs or []:
        content = str(msg.get("content") or "") if isinstance(msg, dict) else ""
        if not content:
            continue
        collected.append(content)
        from agent.core.events import steering_received_event

        yield steering_received_event(
            message_id=str(msg.get("id") or "") if isinstance(msg, dict) else "",
            preview=content[:50],
        )


async def _pump_sdk_events(result: Any, run_queue: asyncio.Queue[tuple[str, Any]]) -> None:
    """Forward SDK stream events onto the shared run queue, tagged by kind.

    Runs as a background task so the consumer can interleave live in-tool
    progress events (pushed onto the same queue via the progress channel) with
    the SDK's own events. The SDK parks ``stream_events()`` while a tool's
    callback runs, so without this pump those progress events could not be
    surfaced until the tool returned.

    Terminal protocol: on a stream exception, emits ``("error", exc)`` so the
    consumer can re-raise it in the original control flow; ``("done", None)`` is
    always emitted last so the consumer's drain loop can terminate.
    """
    try:
        async for sdk_event in result.stream_events():
            run_queue.put_nowait(("sdk", sdk_event))
    except asyncio.CancelledError:
        raise
    except BaseException as exc:  # noqa: BLE001 — forwarded to consumer for unified handling
        run_queue.put_nowait(("error", exc))
    finally:
        run_queue.put_nowait(("done", None))


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
    mid_run_steering: list[str] = []
    artifact_refs_accumulated: list[str] = []
    handoff_event_data: dict[str, Any] | None = None
    clarification_event_data: dict[str, Any] | None = None
    # 控制流工具已生效：本 run 不应再有新的模型轮次（见 _is_new_model_turn_event）。
    control_flow_stopped = False

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

    # Shared queue interleaving SDK events (via _pump_sdk_events) with live
    # in-tool progress events (via the progress channel emitter installed below).
    run_queue: asyncio.Queue[tuple[str, Any]] = asyncio.Queue()
    pump_task: asyncio.Task[None] | None = None
    try:
        from agents import RunConfig, Runner, ToolExecutionConfig
        from agents.exceptions import MaxTurnsExceeded

        from .intra_run_trimmer import IntraRunToolOutputTrimmer

        sdk_agent = _build_agent(agent_type, system_prompt)
        # Install the progress emitter only across run_streamed. The SDK creates
        # its background task synchronously inside run_streamed, copying the
        # current context (with the emitter) into it; that snapshot is
        # independent of ours, so we reset immediately afterwards to keep this
        # generator's context clean and avoid cross-yield contextvar tokens.
        emitter_token = set_progress_emitter(
            lambda event: run_queue.put_nowait(("progress", event))
        )
        try:
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
        finally:
            reset_progress_emitter(emitter_token)

        pump_task = asyncio.create_task(_pump_sdk_events(result, run_queue))

        try:
            while True:
                kind, payload = await run_queue.get()
                if kind == "progress":
                    # Pre-built workflow/SSE event emitted from inside a tool call
                    # (e.g. parallel_execute sub-task progress). Forward as-is.
                    yield payload
                    continue
                if kind == "done":
                    break
                if kind == "error":
                    raise payload
                sdk_event = payload
                if control_flow_stopped and _is_new_model_turn_event(sdk_event):
                    # 兜底护栏：正常情况下 tool_use_behavior 已经让 run-loop 在控制流
                    # 工具返回的那一刻结束，走不到这里。一旦走到（工具改名、SDK 行为
                    # 变化等），说明 SDK 又开了新的一轮——立即硬取消并截断消费循环，
                    # 绝不把暂停之后的正文/工具调用透给前端或写回 state.messages。
                    log_with_context(
                        logger,
                        30,  # WARNING
                        "Control-flow tool did not stop the SDK run; truncating extra turn",
                        agent_type=agent_type,
                        sdk_event_type=str(getattr(sdk_event, "type", "") or ""),
                    )
                    _safe_cancel(result, "immediate")
                    break
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

                    if tool_name == "handoff_to_agent" and result_data.get("status") == _CONTROL_FLOW_STOP_STATUS["handoff_to_agent"]:
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
                        # 「停下」由 Agent(tool_use_behavior=_stop_run_on_control_flow_tool)
                        # 在 SDK turn 内同步完成，run-loop 不会再发起下一次模型调用。
                        # 这里的 cancel(mode="after_turn") 只是第二道保险（万一 SDK 侧的
                        # 截断未生效，至少不让它跨过下一个 turn 边界）；历史上仅靠它是
                        # 不够的——cancel 标志异步落地，模型早已跑完并执行了额外的工具。
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
                        control_flow_stopped = True
                        _safe_cancel(result, "after_turn")
                    elif tool_name == "request_clarification" and result_data.get("status") == _CONTROL_FLOW_STOP_STATUS["request_clarification"]:
                        clarification_event_data = {
                            "reason": "clarification_needed",
                            "agent_type": agent_type,
                            "message": result_data.get("question", "等待您的回复"),
                            "question": result_data.get("question", ""),
                            "context": result_data.get("context", ""),
                            "details": normalize_str_list(result_data.get("details")),
                        }
                        control_flow_stopped = True
                        _safe_cancel(result, "after_turn")

                    # 工具输出边界是 run 内唯一能消费 steering 的时机（SDK 事件
                    # 消费循环的其余位置都在等模型流式输出）。
                    async for steering_event in _consume_boundary_steering(
                        mid_run_steering, get_steering_messages
                    ):
                        yield steering_event
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
        # Stop the SDK pump if it is still running (e.g. the consumer aborted
        # early before the stream drained), so it cannot outlive this run.
        if pump_task is not None and not pump_task.done():
            pump_task.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await pump_task
        _append_assistant_turn_to_state_messages(
            state,
            api_messages,
            assistant_text="".join(assistant_text_parts),
            thinking_text="".join(thinking_text_parts),
            tool_uses=tool_uses,
        )
        if mid_run_steering:
            # 工具边界消费的 steering 作为用户消息进入后续迭代的输入
            # （本次 SDK run 已经无法注入）。
            state["messages"] = list(state.get("messages") or []) + [
                {"role": "user", "content": content} for content in mid_run_steering
            ]
