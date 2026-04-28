"""
Agent nodes for the writing workflow.

Implements streaming agent execution with tool calling support.
"""

import json
from collections.abc import AsyncIterator, Callable
from typing import Any, NamedTuple

from agent.core.metrics import (
    AGENT_CLARIFICATION_TOTAL,
    TOOL_CALLS_DURATION_MS,
    TOOL_CALLS_ERRORS,
    TOOL_CALLS_TOTAL,
    get_metrics_collector,
)
from agent.graph.state import WritingState
from agent.llm.anthropic_client import (
    StreamEvent,
    StreamEventType,
    get_anthropic_client,
)
from agent.prompts.subagents import (
    HOOK_DESIGNER_PROMPT,
    PLANNER_PROMPT,
    QUALITY_REVIEWER_PROMPT,
    WRITER_PROMPT,
)
from agent.tools.registry import (
    TOOL_FUNCTIONS,
    get_agent_tools,
)
from config.agent_runtime import (
    AGENT_COLLABORATION_MAX_ITERATIONS,
    AGENT_TOOL_CALL_MAX_ITERATIONS,
)
from utils.logger import get_logger, log_with_context

logger = get_logger(__name__)


# =============================================================================
# Tool Execution Helper
# =============================================================================

def _resolve_tool_input_schema(
    tool_name: str,
    tools: list[dict[str, Any]] | None,
) -> dict[str, Any] | None:
    """
    Best-effort resolve a tool's input_schema for schema-guided JSON repair.

    Preference order:
    1) The schema list passed into run_agent_loop_streaming (most accurate for this call)
    2) Global registry fallback (keeps tests/dev calls robust even when tools=[])
    """
    if tools:
        for tool in tools:
            if tool.get("name") != tool_name:
                continue
            schema = tool.get("input_schema")
            if isinstance(schema, dict):
                return schema

    try:
        from agent.tools.anthropic_tools import get_tool_by_name

        tool_def = get_tool_by_name(tool_name)
        if tool_def:
            schema = tool_def.get("input_schema")
            if isinstance(schema, dict):
                return schema
    except Exception:
        # Optional dependency path; never fail tool execution because schema lookup failed.
        return None

    return None


def _parse_tool_input_json(
    tool_input_json: str,
    *,
    tool_name: str,
    tools: list[dict[str, Any]] | None,
) -> tuple[dict[str, Any], str | None, dict[str, Any]]:
    """
    Parse tool input JSON with best-effort repair.

    Returns:
        (parsed_input_dict, parse_error, metadata)

    Notes:
        - Only JSON objects are accepted as tool inputs; arrays/strings are rejected.
        - Repair is only attempted when strict json.loads() fails.
    """
    if not tool_input_json:
        return {}, None, {"strategy": "empty"}

    try:
        parsed = json.loads(tool_input_json)
        if isinstance(parsed, dict):
            return parsed, None, {"strategy": "json"}
        return {}, f"tool_input must be a JSON object, got {type(parsed).__name__}", {"strategy": "json"}
    except json.JSONDecodeError as exc:
        schema = _resolve_tool_input_schema(tool_name, tools)
        parse_error = str(exc)

        try:
            from json_repair import loads as json_repair_loads

            repaired_obj, repair_log = json_repair_loads(
                tool_input_json,
                skip_json_loads=True,
                logging=True,
                stream_stable=True,
                schema=schema,
            )
            if isinstance(repaired_obj, dict):
                return repaired_obj, None, {
                    "strategy": "json_repair",
                    "repair_actions": len(repair_log),
                }
            return {}, parse_error, {
                "strategy": "json_repair",
                "repair_actions": len(repair_log),
                "repaired_type": type(repaired_obj).__name__,
            }
        except Exception as repair_exc:
            return {}, parse_error, {
                "strategy": "json_repair_failed",
                "repair_error": f"{type(repair_exc).__name__}: {repair_exc}",
            }


def _normalize_str_list(value: Any) -> list[str]:
    """Normalize optional list-like input to a clean list[str]."""
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _merge_unique_strings(*groups: list[str]) -> list[str]:
    """Merge list[str] groups while preserving order and removing duplicates."""
    merged: list[str] = []
    seen: set[str] = set()
    for group in groups:
        for item in group:
            if item in seen:
                continue
            seen.add(item)
            merged.append(item)
    return merged


def _build_handoff_packet(
    result_data: dict[str, Any],
    artifact_refs: list[str] | None = None,
) -> dict[str, Any]:
    """Build a structured handoff packet from tool result payload."""
    target_agent = str(result_data.get("target_agent", "")).strip()
    reason = str(result_data.get("reason", "")).strip()
    context = str(result_data.get("context", "")).strip()
    completed = _normalize_str_list(result_data.get("completed"))
    todo = _normalize_str_list(result_data.get("todo"))
    evidence = _normalize_str_list(result_data.get("evidence"))
    payload_refs = _normalize_str_list(result_data.get("artifact_refs"))
    merged_refs = _merge_unique_strings(payload_refs, artifact_refs or [])
    overflow_backfill = result_data.get("overflow_backfill")
    normalized_overflow_backfill = (
        [item for item in overflow_backfill if isinstance(item, dict)]
        if isinstance(overflow_backfill, list)
        else []
    )

    return {
        "target_agent": target_agent,
        "reason": reason,
        "context": context,
        "completed": completed,
        "todo": todo,
        "evidence": evidence,
        "artifact_refs": merged_refs,
        "overflow_backfill": normalized_overflow_backfill,
    }


def _extract_artifact_refs(
    tool_name: str,
    result_text: str,
    tool_input: dict[str, Any] | None = None,
) -> list[str]:
    """Extract lightweight artifact refs from tool success payload."""
    if not result_text:
        return []

    try:
        payload = json.loads(result_text)
    except json.JSONDecodeError:
        return []

    refs: list[str] = []
    overflow_ref = payload.get("overflow_ref")
    if isinstance(overflow_ref, str) and overflow_ref.strip():
        refs.append(overflow_ref.strip())

    if payload.get("status") != "success":
        return _merge_unique_strings(refs)

    data = payload.get("data")

    if tool_name in {"create_file", "edit_file"} and isinstance(data, dict):
        file_id = data.get("id")
        if isinstance(file_id, str) and file_id.strip():
            refs.append(file_id.strip())
    elif tool_name == "delete_file":
        deleted_id = data.get("id") if isinstance(data, dict) else None
        if not isinstance(deleted_id, str):
            deleted_id = (tool_input or {}).get("id")
        if isinstance(deleted_id, str) and deleted_id.strip():
            refs.append(deleted_id.strip())
    elif tool_name == "update_project":
        if isinstance(data, dict):
            project_id = data.get("project_id")
            if isinstance(project_id, str) and project_id.strip():
                refs.append(f"project:{project_id.strip()}")

    return _merge_unique_strings(refs)


def _tool_error_result(error: str) -> dict[str, Any]:
    """Build a standardized error payload for tool execution failures."""
    return {
        "content": [
            {
                "type": "text",
                "text": json.dumps({
                    "status": "error",
                    "error": error,
                }),
            }
        ]
    }


async def execute_tool(name: str, args: dict[str, Any]) -> dict[str, Any]:
    """Execute a tool by name and return the result."""
    metrics = get_metrics_collector()
    metrics.increment_counter(TOOL_CALLS_TOTAL)
    with metrics.time_histogram(TOOL_CALLS_DURATION_MS):
        tool_func = TOOL_FUNCTIONS.get(name)
        if tool_func is None:
            metrics.increment_counter(TOOL_CALLS_ERRORS)
            return _tool_error_result(f"Unknown tool: {name}")

        try:
            result = await tool_func(args)
            return result
        except Exception as e:
            metrics.increment_counter(TOOL_CALLS_ERRORS)
            log_with_context(
                logger,
                40,  # ERROR
                "Tool execution error",
                tool_name=name,
                error=str(e),
            )
            return _tool_error_result(str(e))


# Maximum iterations for tool calling loop
MAX_TOOL_ITERATIONS = AGENT_TOOL_CALL_MAX_ITERATIONS

async def run_agent_loop_streaming(
    client: Any,
    messages: list[dict[str, Any]],
    system_prompt: str,
    tools: list[dict[str, Any]],
    agent_type: str = "unknown",  # For context in events and dynamic prompt
    get_steering_messages: Callable[[], list[dict[str, Any]]] | None = None,
) -> AsyncIterator[StreamEvent]:
    """
    Run the streaming agentic loop, yielding events as they arrive.

    Continues calling the LLM and executing tools until:
    - LLM returns end_turn (no more tool calls)
    - Maximum iterations reached

    Args:
        client: AnthropicClient instance
        messages: Initial messages list (will be modified in place)
        system_prompt: System prompt for the LLM
        tools: List of tool definitions
        agent_type: Type of agent for context in events
        get_steering_messages: Optional async callback to retrieve steering messages

    Yields:
        StreamEvent objects for text, tool_use, tool_result, etc.
    """
    iteration = 0
    stop_reason = "end_turn"  # Track last stop_reason for exhausted check
    artifact_refs_accumulated: list[str] = []

    while iteration < MAX_TOOL_ITERATIONS:
        iteration += 1
        log_with_context(logger, 20, f"Streaming agent loop iteration {iteration}")

        # Check for steering messages at start of each iteration
        if get_steering_messages:
            try:
                steering_msgs = await get_steering_messages()
                for msg in steering_msgs:
                    messages.append({
                        "role": "user",
                        "content": msg["content"],
                    })
                    # Import here to avoid circular dependency
                    from agent.core.events import steering_received_event
                    yield steering_received_event(
                        message_id=msg.get("id", ""),
                        preview=msg["content"][:50],
                    )
                    log_with_context(
                        logger,
                        20,  # INFO
                        "Steering message injected into conversation",
                        message_id=msg.get("id"),
                        iteration=iteration,
                    )
            except Exception as e:
                log_with_context(
                    logger,
                    40,  # ERROR
                    "Failed to retrieve steering messages",
                    error=str(e),
                )

        # Inject iteration context into the conversation (not system prompt)
        # to preserve DeepSeek context cache on the stable system prompt prefix.
        if iteration > 0:
            remaining = MAX_TOOL_ITERATIONS - iteration
            iteration_hint = (
                f"\n\n[工具调用状态: 第{iteration}轮/{MAX_TOOL_ITERATIONS}轮, 剩余{remaining}轮]"
                + (" 请优先完成最重要的任务，如无法完成请告知用户当前进度。" if remaining <= 2 else "")
            )
            # Append to the last message to keep system prompt stable
            # Guard: tool-result messages use list-of-blocks content, not string
            if messages and messages[-1].get("role") in ("user", "tool"):
                last_content = messages[-1].get("content", "")
                if isinstance(last_content, str):
                    messages[-1]["content"] = last_content + iteration_hint
                else:
                    messages.append({"role": "user", "content": iteration_hint})
            else:
                messages.append({"role": "user", "content": iteration_hint})

        current_system_prompt = system_prompt

        current_tool: dict[str, Any] | None = None
        tool_input_json = ""
        tool_uses_this_turn: list[dict[str, Any]] = []
        text_content_this_turn = ""
        thinking_content_this_turn = ""
        stop_reason = "end_turn"
        handoff_event_data: dict[str, Any] | None = None
        clarification_event_data: dict[str, Any] | None = None

        # Stream LLM response
        async for event in client.stream_message(
            messages=messages,
            system_prompt=current_system_prompt,  # Use dynamically updated prompt
            tools=tools,
        ):
            # Yield text events directly for real-time streaming
            if event.type == StreamEventType.TEXT:
                text_content_this_turn += event.data.get("text", "")
                yield event

            elif event.type == StreamEventType.THINKING:
                thinking_content_this_turn += event.data.get("thinking", "")
                yield event

            elif event.type == StreamEventType.TOOL_USE:
                status = event.data.get("status")

                if status == "start":
                    current_tool = {
                        "id": event.data.get("id", ""),
                        "name": event.data.get("name", ""),
                    }
                    tool_input_json = ""
                    yield event

                elif status == "delta":
                    tool_input_json += event.data.get("partial_json", "")

                elif status == "stop" and current_tool:
                    tool_input, parse_error, parse_metadata = _parse_tool_input_json(
                        tool_input_json,
                        tool_name=current_tool["name"],
                        tools=tools,
                    )

                    # Emit complete tool-use event with parsed input for downstream persistence.
                    yield StreamEvent(
                        type=StreamEventType.TOOL_USE,
                        data={
                            "id": current_tool["id"],
                            "name": current_tool["name"],
                            "status": "complete",
                            "input": tool_input,
                        },
                    )

                    if parse_error is None and parse_metadata.get("strategy") == "json_repair":
                        log_with_context(
                            logger,
                            20,  # INFO
                            "Tool input JSON repaired",
                            tool_name=current_tool["name"],
                            tool_use_id=current_tool["id"],
                            repair_actions=parse_metadata.get("repair_actions"),
                        )

                    if parse_error is not None:
                        log_with_context(
                            logger,
                            30,  # WARNING
                            "Invalid tool input JSON",
                            tool_name=current_tool["name"],
                            tool_use_id=current_tool["id"],
                            error=parse_error,
                            repair_strategy=parse_metadata.get("strategy"),
                            repair_error=parse_metadata.get("repair_error"),
                        )
                        error_payload = {
                            "status": "error",
                            "error": "Invalid tool input JSON",
                            "error_type": "invalid_tool_input_json",
                            "tool_name": current_tool["name"],
                            "details": parse_error,
                        }
                        result_text = json.dumps(error_payload, ensure_ascii=False)
                        result = {
                            "content": [{
                                "type": "text",
                                "text": result_text,
                            }]
                        }
                        tool_uses_this_turn.append({
                            "id": current_tool["id"],
                            "name": current_tool["name"],
                            "input": tool_input,
                            "result": result_text,
                        })
                        yield StreamEvent(
                            type=StreamEventType.TOOL_RESULT,
                            data={
                                "tool_use_id": current_tool["id"],
                                "name": current_tool["name"],
                                "result": result,
                            },
                        )
                        current_tool = None
                        tool_input_json = ""
                        continue

                    # Execute the tool immediately
                    result = await execute_tool(current_tool["name"], tool_input)

                    # Extract result text
                    content_list = result.get("content", [])
                    result_text = content_list[0].get("text", "") if content_list else ""
                    new_artifact_refs = _extract_artifact_refs(
                        current_tool["name"],
                        result_text,
                        tool_input=tool_input,
                    )
                    artifact_refs_accumulated = _merge_unique_strings(
                        artifact_refs_accumulated,
                        new_artifact_refs,
                    )

                    # Control tools are resolved after this turn so precedence can be applied.
                    if current_tool["name"] == "handoff_to_agent":
                        try:
                            result_data = json.loads(result_text) if result_text else {}
                            if result_data.get("status") == "handoff":
                                # Emit tool_result for frontend tool-call lifecycle completion
                                # before handing off to next agent.
                                yield StreamEvent(
                                    type=StreamEventType.TOOL_RESULT,
                                    data={
                                        "tool_use_id": current_tool["id"],
                                        "name": current_tool["name"],
                                        "result": result,
                                    },
                                )
                                packet = _build_handoff_packet(
                                    result_data,
                                    artifact_refs=artifact_refs_accumulated,
                                )
                                handoff_event_data = {
                                    "target_agent": packet["target_agent"],
                                    "reason": packet["reason"],
                                    "context": packet["context"],
                                    "handoff_packet": packet,
                                }
                                current_tool = None
                                tool_input_json = ""
                                continue
                        except json.JSONDecodeError:
                            pass
                    elif current_tool["name"] == "request_clarification":
                        try:
                            result_data = json.loads(result_text) if result_text else {}
                            if result_data.get("status") == "clarification_needed":
                                # Emit tool_result for frontend tool-call lifecycle completion
                                # before canonical clarification stop event.
                                yield StreamEvent(
                                    type=StreamEventType.TOOL_RESULT,
                                    data={
                                        "tool_use_id": current_tool["id"],
                                        "name": current_tool["name"],
                                        "result": result,
                                    },
                                )
                                clarification_event_data = {
                                    "reason": "clarification_needed",
                                    "agent_type": agent_type,
                                    "message": result_data.get("question", "等待您的回复"),
                                    "question": result_data.get("question", ""),
                                    "context": result_data.get("context", ""),
                                    "details": _normalize_str_list(result_data.get("details")),
                                }
                                current_tool = None
                                tool_input_json = ""
                                continue
                        except json.JSONDecodeError:
                            pass

                    # Track tool use for message history
                    tool_uses_this_turn.append({
                        "id": current_tool["id"],
                        "name": current_tool["name"],
                        "input": tool_input,
                        "result": result_text,
                    })

                    # Yield tool result event with MCP format
                    yield StreamEvent(
                        type=StreamEventType.TOOL_RESULT,
                        data={
                            "tool_use_id": current_tool["id"],
                            "name": current_tool["name"],
                            "result": result,
                        },
                    )

                    current_tool = None
                    tool_input_json = ""

            elif event.type == StreamEventType.MESSAGE_START:
                yield event

            elif event.type == StreamEventType.MESSAGE_END:
                stop_reason = event.data.get("stop_reason", "end_turn")
                yield event

            elif event.type == StreamEventType.ERROR:
                yield event

        # Clarification is canonical stop signal: it must win over handoff in the same turn.
        if clarification_event_data is not None:
            if clarification_event_data.get("reason") == "clarification_needed":
                get_metrics_collector().increment_counter(AGENT_CLARIFICATION_TOTAL)
            yield StreamEvent(type=StreamEventType.WORKFLOW_STOPPED, data=clarification_event_data)
            return
        if handoff_event_data is not None:
            yield StreamEvent(type=StreamEventType.HANDOFF, data=handoff_event_data)
            return

        should_continue = stop_reason == "tool_use" and bool(tool_uses_this_turn)

        # Persist this turn into conversation history so downstream agents in the
        # same workflow can always see the latest assistant output, even when
        # stop_reason=end_turn (no further tool-iteration loop).
        assistant_content: list[dict[str, Any]] = []
        if thinking_content_this_turn:
            assistant_content.append({"type": "thinking", "thinking": thinking_content_this_turn})
        if text_content_this_turn.strip():
            assistant_content.append({"type": "text", "text": text_content_this_turn})
        for tu in tool_uses_this_turn:
            assistant_content.append({
                "type": "tool_use",
                "id": tu["id"],
                "name": tu["name"],
                "input": tu["input"],
            })
        if assistant_content:
            messages.append({"role": "assistant", "content": assistant_content})

        # Persist tool results whenever tools were executed in this turn.
        if tool_uses_this_turn:
            tool_results = []
            for tu in tool_uses_this_turn:
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": tu["id"],
                    "content": tu["result"],
                })
            messages.append({"role": "user", "content": tool_results})

        # Continue only when model explicitly requests another tool iteration.
        if not should_continue:
            break

    # Only emit exhausted if we hit the limit AND the agent wanted to continue
    # This prevents false positives when agent completes normally on iteration 10
    if iteration >= MAX_TOOL_ITERATIONS and stop_reason == "tool_use":
        yield StreamEvent(
            type=StreamEventType.ITERATION_EXHAUSTED,
            data={
                "layer": "tool_call",
                "iterations_used": iteration,
                "max_iterations": MAX_TOOL_ITERATIONS,
                "reason": (
                    f"单个 Agent（{agent_type}）的工具调用次数已达上限（{MAX_TOOL_ITERATIONS} 次）。"
                    f"这是单个 Agent 内的工具调用限制，与 Agent 协作轮数（{AGENT_COLLABORATION_MAX_ITERATIONS} 轮）独立。"
                    "当前任务可能未完全完成，您可以继续对话让 AI 完成剩余工作。"
                ),
                "last_agent": agent_type,
            },
        )

    log_with_context(logger, 20, "Streaming agent loop completed", iterations=iteration)


# =============================================================================
# Streaming Agent Implementation
# =============================================================================

async def run_streaming_agent(
    state: WritingState,
    agent_type: str,
    get_steering_messages: Any | None = None,
) -> AsyncIterator[StreamEvent]:
    """
    Generic streaming agent that yields events in real-time.

    Args:
        state: Current workflow state
        agent_type: Type of agent (planner/writer/quality_reviewer)
        get_steering_messages: Optional async callback to retrieve steering messages

    Yields:
        StreamEvent objects for real-time streaming
    """
    # Specialized prompts from subagents.py
    specialized_prompts = {
        "planner": PLANNER_PROMPT,
        "hook_designer": HOOK_DESIGNER_PROMPT,
        "writer": WRITER_PROMPT,
        "quality_reviewer": QUALITY_REVIEWER_PROMPT,
    }

    log_with_context(logger, 20, f"Streaming {agent_type} started")

    user_message = state.get("user_message", "")
    messages = state.get("messages", [])
    base_prompt = state.get("system_prompt", "")

    # Combine base prompt with specialized agent prompt
    specialized = specialized_prompts.get(agent_type, "")
    if base_prompt and specialized:
        system_prompt = f"{base_prompt}\n\n## 当前角色：{agent_type}\n\n{specialized}"
    elif specialized:
        system_prompt = specialized
    else:
        system_prompt = base_prompt

    # Build messages for API call
    api_messages = list(messages)
    if user_message and (not api_messages or api_messages[-1].get("content") != user_message):
        api_messages.append({"role": "user", "content": user_message})

    try:
        client = get_anthropic_client()

        # 根据 agent 类型选择工具集
        tools = get_agent_tools(agent_type)

        # Run streaming agentic loop
        async for event in run_agent_loop_streaming(
            client=client,
            messages=api_messages,
            system_prompt=system_prompt,
            tools=tools,
            agent_type=agent_type,  # Pass agent type for context
            get_steering_messages=get_steering_messages,
        ):
            yield event

        log_with_context(logger, 20, f"Streaming {agent_type} completed")

    except Exception as e:
        log_with_context(
            logger, 40, f"Streaming {agent_type} error",
            error=str(e), error_type=type(e).__name__,
        )
        yield StreamEvent(
            type=StreamEventType.ERROR,
            data={"error": str(e), "error_type": type(e).__name__},
        )
    finally:
        # Persist conversation progression for downstream agents in this workflow.
        state["messages"] = api_messages


# =============================================================================
# Clarification Detection
# =============================================================================


class ClarificationResult(NamedTuple):
    """澄清检测结果。"""
    needs_clarification: bool
    confidence: float  # 0.0 - 1.0
    reason: str


class OutputEvaluationResult(NamedTuple):
    """Structured output evaluation result."""

    complete_score: float
    clarification_score: float
    consistency_score: float
    should_complete: bool
    should_clarify: bool
    reason: str


def evaluate_agent_output(content: str, agent_type: str = "unknown") -> OutputEvaluationResult:
    """
    Evaluate output quality signals for workflow decisions.

    Priority order:
    1) Explicit completion marker ([TASK_COMPLETE])
    2) Conservative completion heuristics
    """
    _ = agent_type
    text = (content or "").strip()
    if not text:
        return OutputEvaluationResult(
            complete_score=0.0,
            clarification_score=0.0,
            consistency_score=0.0,
            should_complete=False,
            should_clarify=False,
            reason="empty_content",
        )

    lowered = text.lower()

    # Explicit markers remain strongest signals (backward compatibility)
    has_complete_marker = lowered.endswith("[task_complete]")
    complete_score = 1.0 if has_complete_marker else 0.0
    clarification_score = 0.0

    # Conservative heuristic completion signals
    completion_phrases = (
        "任务已完成",
        "已完成",
        "最终结果",
        "总结如下",
        "修改完成",
    )
    if not has_complete_marker and any(phrase in text for phrase in completion_phrases):
        # Longer structured output is more likely to be a final answer
        complete_score = max(complete_score, 0.75 if len(text) >= 120 else 0.6)

    should_clarify = False
    should_complete = complete_score >= 0.75 and not should_clarify

    # Lightweight consistency score for observability/debugging
    consistency_score = max(0.0, 1.0 - abs(complete_score - clarification_score))

    if has_complete_marker:
        reason = "explicit_complete_marker"
    elif should_complete:
        reason = "heuristic_completion"
    else:
        reason = "insufficient_signal"

    return OutputEvaluationResult(
        complete_score=complete_score,
        clarification_score=clarification_score,
        consistency_score=consistency_score,
        should_complete=should_complete,
        should_clarify=should_clarify,
        reason=reason,
    )


def detect_clarification_needed(content: str, agent_type: str = "unknown") -> ClarificationResult:
    """
    Clarification must be triggered only by structured `request_clarification` tool calls.
    Text heuristics and marker fallbacks are intentionally disabled.

    Args:
        content: Agent 输出内容（保留参数用于兼容，不参与判定）
        agent_type: Agent 类型，用于特殊处理某些 agent 的输出格式

    Returns:
        ClarificationResult with needs_clarification flag, confidence, and reason
    """
    _ = content
    # quality_reviewer 的输出是审查报告，不应触发澄清检测
    if agent_type == "quality_reviewer":
        return ClarificationResult(
            needs_clarification=False,
            confidence=0.0,
            reason="quality_reviewer_exempt",
        )

    return ClarificationResult(
        needs_clarification=False,
        confidence=0.0,
        reason="structured_tool_required",
    )


# =============================================================================
# Task Completion Detection
# =============================================================================


class TaskCompleteResult(NamedTuple):
    """任务完成检测结果。"""
    is_complete: bool
    confidence: float  # 0.0 - 1.0
    reason: str


def detect_task_complete(content: str, _agent_type: str = "unknown") -> TaskCompleteResult:
    """
    检测 Agent 输出是否标记任务完成。

    检测策略：检查输出是否以 [TASK_COMPLETE] 标记结尾。
    使用严格的末尾检测，只有标记在最后才触发。

    Args:
        content: Agent 输出内容
        agent_type: Agent 类型

    Returns:
        TaskCompleteResult with is_complete flag, confidence, and reason
    """
    evaluation = evaluate_agent_output(content, agent_type=_agent_type)
    if evaluation.should_complete:
        return TaskCompleteResult(
            is_complete=True,
            confidence=evaluation.complete_score,
            reason=evaluation.reason,
        )

    return TaskCompleteResult(
        is_complete=False,
        confidence=evaluation.complete_score,
        reason=evaluation.reason,
    )
