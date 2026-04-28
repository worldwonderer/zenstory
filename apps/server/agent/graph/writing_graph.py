"""
Writing workflow for zenstory.

Provides streaming multi-agent orchestration with router, planner, writer, and quality reviewer.
"""

import os
from collections.abc import AsyncIterator
from typing import Any

from agent.graph.nodes import (
    detect_task_complete,
    evaluate_agent_output,
    run_streaming_agent,
)
from agent.graph.router import get_next_node, router_node
from agent.graph.state import WritingState
from agent.llm.anthropic_client import StreamEvent, StreamEventType
from agent.tools.mcp_tools import ToolContext, update_project
from config.agent_runtime import (
    AGENT_AUTO_REVIEW_THRESHOLD_CHARS,
    AGENT_COLLABORATION_MAX_ITERATIONS,
    AGENT_ENABLE_GRAPH_AUTO_REVIEW,
    AGENT_ROUTER_STRATEGY,
    AGENT_TOOL_CALL_MAX_ITERATIONS,
)
from utils.logger import get_logger, log_with_context

logger = get_logger(__name__)


def _extract_review_payload(agent_content: str) -> str:
    """
    Prefer reviewing the concrete draft payload.

    When the writer follows the "<file>...</file>" streaming protocol, extract file blocks.
    Otherwise, fall back to the full agent text.
    """
    raw = (agent_content or "").strip()
    if not raw:
        return ""

    if "<file" not in raw.lower():
        return raw

    # Normalize file marker variants (best-effort). We reuse the same normalization
    # logic as StreamProcessor so reviewer extraction is consistent with file writes.
    normalized = raw
    try:
        from agent.core.stream_processor import normalize_file_markers

        normalized = normalize_file_markers(raw)
    except Exception:
        normalized = raw

    start_tag = "<file>"
    end_tag = "</file>"
    if start_tag not in normalized or end_tag not in normalized:
        return raw

    blocks: list[str] = []
    cursor = 0
    while True:
        start = normalized.find(start_tag, cursor)
        if start == -1:
            break
        start += len(start_tag)
        end = normalized.find(end_tag, start)
        if end == -1:
            break
        block = normalized[start:end].strip()
        if block:
            blocks.append(block)
        cursor = end + len(end_tag)

    return "\n\n".join(blocks).strip() if blocks else raw


def _format_review_payload(text: str, *, max_chars: int = 9000) -> str:
    """Trim extremely long draft content while keeping head+tail for reviewer context."""
    normalized = (text or "").strip()
    if not normalized:
        return ""
    if max_chars <= 0 or len(normalized) <= max_chars:
        return normalized

    head_chars = int(max_chars * 0.7)
    tail_chars = max_chars - head_chars
    head = normalized[:head_chars].rstrip()
    tail = normalized[-tail_chars:].lstrip() if tail_chars > 0 else ""
    omitted = len(normalized) - len(head) - len(tail)
    omitted_hint = f"\n\n...[中间省略 {omitted} 字]...\n\n" if omitted > 0 else "\n\n"
    return f"{head}{omitted_hint}{tail}".strip()


def _format_file_inventory(inventory: dict[str, list[dict[str, Any]]]) -> str:
    """格式化文件清单为可读字符串。"""
    parts = []
    type_names = {
        "outline": "大纲",
        "draft": "正文",
        "character": "角色",
        "lore": "设定",
    }

    for file_type, files in inventory.items():
        if files and file_type in type_names:
            items = [f"{f['title']}(id={f['id']})" for f in files]
            parts.append(f"{type_names[file_type]}: {', '.join(items)}")

    return "\n".join(parts) if parts else ""


def _build_completion_task_payload(tasks: list[dict[str, Any]]) -> list[dict[str, Any]] | None:
    """将任务板中的 in_progress 任务标记为 done。"""
    updated_tasks: list[dict[str, Any]] = []
    has_updates = False

    for task in tasks:
        if not isinstance(task, dict):
            continue

        normalized_task = dict(task)
        if normalized_task.get("status") == "in_progress":
            normalized_task["status"] = "done"
            has_updates = True
        updated_tasks.append(normalized_task)

    return updated_tasks if has_updates else None


async def _auto_finalize_task_board_on_completion() -> list[StreamEvent]:
    """
    在 workflow 完成时自动补一次 update_project(tasks=[...])。

    仅将 in_progress 任务改为 done，避免误改 pending 任务。
    """
    session_id = ToolContext.get_session_id()
    if not session_id:
        return []

    user_id = ToolContext.get_user_id()
    project_id = ToolContext.get_project_id()

    try:
        from services.infra.task_board_service import task_board_service

        current_tasks = task_board_service.get_tasks(
            session_id,
            user_id=user_id,
            project_id=project_id,
        ) or []
        completion_tasks = _build_completion_task_payload(current_tasks)
        if not completion_tasks:
            return []

        tool_result = await update_project({"tasks": completion_tasks})
        tool_use_id = "workflow_auto_completion"
        return [
            StreamEvent(
                type=StreamEventType.TOOL_USE,
                data={
                    "id": tool_use_id,
                    "name": "update_project",
                    "status": "complete",
                    "input": {"tasks": completion_tasks},
                },
            ),
            StreamEvent(
                type=StreamEventType.TOOL_RESULT,
                data={
                    "tool_use_id": tool_use_id,
                    "name": "update_project",
                    "result": tool_result,
                },
            ),
        ]
    except Exception as e:
        log_with_context(
            logger,
            30,  # WARNING
            "Auto finalize task board failed",
            error=str(e),
            error_type=type(e).__name__,
            session_id=session_id,
            user_id=user_id,
            project_id=project_id,
        )
        return []


# =============================================================================
# Streaming Workflow Execution
# =============================================================================


async def run_writing_workflow_streaming(
    state: WritingState,
    thread_id: str | None = None,
    max_iterations: int = AGENT_COLLABORATION_MAX_ITERATIONS,
    auto_review_threshold: int = AGENT_AUTO_REVIEW_THRESHOLD_CHARS,
    get_steering_messages: Any | None = None,
) -> AsyncIterator[StreamEvent]:
    """
    Execute the writing workflow with true streaming output and agent collaboration.

    Uses router to determine initial agent and workflow plan, then streams from agents.
    Supports both planned workflows and dynamic agent handoffs.

    Args:
        state: Initial workflow state
        thread_id: Optional thread ID for logging
        max_iterations: Maximum number of agent handoffs (default 5)
        auto_review_threshold: Character count threshold for auto-triggering quality reviewer
        get_steering_messages: Optional async callback to retrieve steering messages

    Yields:
        StreamEvent objects for real-time streaming
    """
    log_with_context(
        logger,
        20,  # INFO
        "Starting streaming writing workflow with collaboration",
        user_message_preview=state.get("user_message", "")[:50],
        thread_id=thread_id,
    )

    agent_names = {
        "planner": "大纲规划师",
        "hook_designer": "爽点设计师",
        "writer": "内容创作者",
        "quality_reviewer": "质量审稿人",
    }

    iteration = 0
    current_agent_type: str | None = None
    handoff_context: str = ""
    workflow_agents: list[str] = []  # Planned agents to execute after initial
    accumulated_content: str = ""  # Track content for auto-review threshold
    review_round: int = 0  # 跟踪 writer-quality_reviewer 循环次数
    previous_agent: str | None = None  # 跟踪上一个 agent

    try:
        generation_mode = str(state.get("generation_mode") or "").strip().lower()
        if generation_mode not in {"fast", "quality"}:
            generation_mode = ""

        # Step 1: Run router to determine initial agent and workflow plan
        yield StreamEvent(
            type=StreamEventType.ROUTER_THINKING,
            data={
                "message": (
                    "快速模式：直接进入生成..."
                    if generation_mode == "fast"
                    else "高质量模式：正在规划工作流..."
                    if generation_mode == "quality"
                    else "Router 正在选择处理方式..."
                ),
            },
        )

        router_strategy = (os.getenv("AGENT_ROUTER_STRATEGY") or AGENT_ROUTER_STRATEGY).strip().lower()
        if router_strategy not in {"llm", "off"}:
            router_strategy = AGENT_ROUTER_STRATEGY

        enable_graph_auto_review = (
            os.getenv("AGENT_ENABLE_GRAPH_AUTO_REVIEW")
            if os.getenv("AGENT_ENABLE_GRAPH_AUTO_REVIEW") is not None
            else str(AGENT_ENABLE_GRAPH_AUTO_REVIEW)
        ).strip().lower() in {"1", "true", "yes", "y", "on"}

        # Per-request override (driven by frontend generation_mode UI).
        if generation_mode == "fast":
            router_strategy = "off"
            enable_graph_auto_review = False
        elif generation_mode == "quality":
            router_strategy = "llm"
            enable_graph_auto_review = True

        try:
            if router_strategy == "off":
                router_result = {
                    "current_agent": "writer",
                    "workflow_plan": "quick",
                    "workflow_agents": [],
                    "routing_metadata": {
                        "agent_type": "writer",
                        "workflow_type": "quick",
                        "reason": "generation_mode_fast" if generation_mode == "fast" else "router_off",
                        "confidence": 0.0,
                    },
                }
            else:
                router_result = await router_node(state)

            current_agent_type = get_next_node(router_result)
            workflow_agents = list(router_result.get("workflow_agents", []))
            workflow_plan = router_result.get("workflow_plan", "quick")
            routing_metadata = router_result.get("routing_metadata", {})
        except (ValueError, KeyError) as validation_error:
            # 可恢复的验证错误 - 使用 fallback
            log_with_context(
                logger,
                30,  # WARNING
                "Router validation failed, using fallback",
                error=str(validation_error),
                error_type=type(validation_error).__name__,
            )
            current_agent_type = "writer"
            workflow_agents = []
            workflow_plan = "quick"
            routing_metadata = {
                "agent_type": "writer",
                "workflow_type": "quick",
                "reason": "router_validation_fallback",
                "confidence": 0.0,
            }
        except Exception as router_error:
            # 其他错误 - 记录并使用 fallback
            log_with_context(
                logger,
                40,  # ERROR
                "Router failed, using fallback",
                error=str(router_error),
                error_type=type(router_error).__name__,
            )
            current_agent_type = "writer"
            workflow_agents = []
            workflow_plan = "quick"
            routing_metadata = {
                "agent_type": "writer",
                "workflow_type": "quick",
                "reason": "router_exception_fallback",
                "confidence": 0.0,
            }

        yield StreamEvent(
            type=StreamEventType.ROUTER_DECIDED,
            data={
                "initial_agent": current_agent_type,
                "workflow_plan": workflow_plan,
                "workflow_agents": workflow_agents.copy(),
                "routing_metadata": routing_metadata,
            },
        )

        log_with_context(
            logger,
            20,
            "Router determined workflow",
            initial_agent=current_agent_type,
            workflow_plan=workflow_plan,
            workflow_agents=workflow_agents,
            router_strategy=router_strategy,
            enable_graph_auto_review=enable_graph_auto_review,
        )

        while current_agent_type and iteration < max_iterations:
            iteration += 1
            ToolContext.set_current_agent(current_agent_type)

            log_with_context(
                logger,
                20,
                f"Agent collaboration iteration {iteration}",
                agent_type=current_agent_type,
                remaining_workflow_agents=workflow_agents,
            )

            # Emit agent_selected event with iteration status
            yield StreamEvent(
                type=StreamEventType.AGENT_SELECTED,
                data={
                    "agent_type": current_agent_type,
                    "agent_name": agent_names.get(current_agent_type, current_agent_type),
                    "iteration": iteration,
                    "max_iterations": max_iterations,
                    "remaining": max_iterations - iteration,
                },
            )

            # 构建最后一轮提示（如果是最后一轮）
            is_last_iteration = iteration == max_iterations
            last_iteration_hint = ""
            if is_last_iteration:
                last_iteration_hint = (
                    f"\n\n[重要提示] 这是最后一轮协作（第 {iteration}/{max_iterations} 轮），"
                    "请直接完成当前任务并输出最终结果，不要交接给其他 Agent。"
                )

            # If there's handoff context, add it to the state
            if handoff_context:
                modified_state = dict(state)
                original_msg = modified_state.get("user_message", "")

                # 检测 writer-quality_reviewer 循环
                is_reviewer = current_agent_type == "quality_reviewer"
                is_from_writer = previous_agent == "writer"
                if is_reviewer and is_from_writer:
                    review_round += 1
                    log_with_context(
                        logger, 20, "Writer-quality_reviewer cycle detected",
                        review_round=review_round,
                    )

                # 刷新文件清单
                inventory_text = ""
                try:
                    refreshed = ToolContext.refresh_file_inventory()
                    if refreshed:
                        inventory_text = _format_file_inventory(refreshed)
                        if inventory_text:
                            inventory_text = f"\n\n[当前项目文件清单]:\n{inventory_text}"
                except Exception as e:
                    log_with_context(
                        logger, 30, "Failed to refresh file inventory", error=str(e)
                    )

                # 对 Reviewer 使用专门的消息格式，不传递原始用户请求
                # 避免 Reviewer 误以为自己需要创作
                if is_reviewer:
                    # 构建审查轮次提示
                    # review_round=1 是第一次审查，不需要提示
                    # review_round=2 是第二次审查（第一次循环）
                    # review_round>=3 是第三次及以上审查
                    round_hint = ""
                    if review_round >= 3:
                        round_hint = (
                            f"\n\n[重要提示] 这是第 {review_round} 轮审查，已经过多轮修改。"
                            "除非有严重的质量问题（如明显的逻辑错误、角色崩坏），"
                            "否则应该通过审查，避免无限循环修改。"
                            "追更指数达到 5 分以上即可通过。"
                        )
                    elif review_round == 2:
                        round_hint = "\n\n[提示] 这是第 2 轮审查，请重点关注之前提出的问题是否已修复。"

                    modified_state["user_message"] = (
                        f"[质量检查任务]\n\n请审查上一个 Agent 完成的内容。\n\n"
                        f"交接信息: {handoff_context}{inventory_text}{round_hint}{last_iteration_hint}"
                    )
                else:
                    modified_state["user_message"] = (
                        f"{original_msg}\n\n[来自上一个Agent的交接信息]: "
                        f"{handoff_context}{inventory_text}{last_iteration_hint}"
                    )
            else:
                # 即使没有 handoff_context，也需要注入最后一轮提示
                if last_iteration_hint:
                    modified_state = dict(state)
                    original_msg = modified_state.get("user_message", "")
                    modified_state["user_message"] = f"{original_msg}{last_iteration_hint}"
                else:
                    modified_state = state

            # Stream from the current agent
            next_agent: str | None = None
            agent_content: str = ""  # Track this agent's output
            handoff_packet: dict[str, Any] | None = None
            explicit_handoff_event_data: dict[str, Any] | None = None
            clarification_stopped = False
            tool_call_exhausted = False
            invalid_handoff_stopped = False
            writer_used_write_tools = False
            writer_emitted_file_markers = False

            async for event in run_streaming_agent(
                modified_state, current_agent_type, get_steering_messages=get_steering_messages
            ):
                # Track text content for auto-review threshold
                if event.type == StreamEventType.TEXT:
                    text = event.data.get("text", "")
                    agent_content += text
                    accumulated_content += text

                if (
                    current_agent_type == "writer"
                    and event.type == StreamEventType.TOOL_USE
                    and event.data.get("status") == "complete"
                ):
                    tool_name = str(event.data.get("name") or "").strip()
                    if tool_name in {"create_file", "edit_file"}:
                        writer_used_write_tools = True

                # Check for handoff event
                if event.type == StreamEventType.HANDOFF:
                    next_agent = event.data.get("target_agent")
                    if next_agent == current_agent_type:
                        invalid_handoff_stopped = True
                        yield StreamEvent(
                            type=StreamEventType.WORKFLOW_STOPPED,
                            data={
                                "reason": "invalid_handoff",
                                "agent_type": current_agent_type,
                                "message": (
                                    f"无效交接：{current_agent_type} 不能交接给自己。"
                                    "请直接完成当前任务或交接给其他 Agent。"
                                ),
                                "target_agent": next_agent,
                            },
                        )
                        continue

                    handoff_context = event.data.get("context", "")
                    handoff_packet = event.data.get("handoff_packet")
                    if not isinstance(handoff_packet, dict):
                        handoff_packet = {
                            "target_agent": next_agent or "",
                            "reason": event.data.get("reason", ""),
                            "context": handoff_context,
                            "completed": [],
                            "todo": [],
                            "evidence": [],
                        }
                    reason = event.data.get("reason", "")

                    log_with_context(
                        logger,
                        20,
                        "Agent requested handoff",
                        from_agent=current_agent_type,
                        to_agent=next_agent,
                        reason=reason,
                    )

                    explicit_handoff_event_data = {
                        "target_agent": next_agent,
                        "reason": reason,
                        "context": handoff_context,
                        "handoff_packet": handoff_packet,
                    }
                elif (
                    event.type == StreamEventType.WORKFLOW_STOPPED
                    and event.data.get("reason") == "clarification_needed"
                ):
                    clarification_stopped = True
                    yield event
                elif (
                    event.type == StreamEventType.ITERATION_EXHAUSTED
                    and event.data.get("layer") == "tool_call"
                ):
                    tool_call_exhausted = True
                    yield event
                else:
                    yield event

            # Carry forward conversation evolution from this agent turn so that
            # downstream agents can see full assistant/tool history.
            updated_messages = modified_state.get("messages")
            if isinstance(updated_messages, list):
                state["messages"] = updated_messages

            if current_agent_type == "writer" and agent_content:
                lowered = agent_content.lower()
                if "<file" in lowered or "</file" in lowered:
                    writer_emitted_file_markers = True

            # Structured clarification stop is canonical and must block planned/auto handoff.
            if clarification_stopped:
                break
            # Invalid explicit handoff should stop collaboration to prevent self-loop.
            if invalid_handoff_stopped:
                break
            # Tool-call exhaustion should stop workflow; never continue with planned/auto handoff.
            if tool_call_exhausted:
                break

            # Determine upcoming handoff after stop checks.
            # Explicit handoff requests still take precedence over completion checks.
            has_pending_handoff = False
            has_explicit_handoff = False
            pending_next_agent: str | None = None
            pending_handoff_event_data: dict[str, Any] | None = None

            if next_agent:
                # Agent explicitly requested handoff
                has_pending_handoff = True
                has_explicit_handoff = True
                pending_next_agent = next_agent
                pending_handoff_event_data = explicit_handoff_event_data
                # Remove from workflow_agents if it was planned
                if next_agent in workflow_agents:
                    workflow_agents.remove(next_agent)
                if handoff_packet and handoff_packet.get("context"):
                    handoff_context = str(handoff_packet.get("context", ""))
            elif workflow_agents:
                # Follow planned workflow
                has_pending_handoff = True
                next_planned = workflow_agents.pop(0)
                if next_planned == current_agent_type:
                    yield StreamEvent(
                        type=StreamEventType.WORKFLOW_STOPPED,
                        data={
                            "reason": "invalid_handoff",
                            "agent_type": current_agent_type,
                            "message": (
                                f"无效自动交接：{current_agent_type} 不能交接给自己。"
                            ),
                            "target_agent": next_planned,
                        },
                    )
                    break
                handoff_context = f"按照工作流计划，从 {current_agent_type} 自动交接"
                handoff_packet = {
                    "target_agent": next_planned,
                    "reason": "工作流自动交接",
                    "context": handoff_context,
                    "completed": [],
                    "todo": [],
                    "evidence": [f"workflow_plan={workflow_plan}"],
                }

                log_with_context(
                    logger,
                    20,
                    "Following planned workflow",
                    from_agent=current_agent_type,
                    to_agent=next_planned,
                )

                pending_handoff_event_data = {
                    "target_agent": next_planned,
                    "reason": "工作流自动交接",
                    "context": handoff_context,
                    "handoff_packet": handoff_packet,
                }

                pending_next_agent = next_planned
            elif (
                enable_graph_auto_review
                and
                current_agent_type == "writer"
                and len(agent_content) >= auto_review_threshold
                and (writer_emitted_file_markers or writer_used_write_tools)
            ):
                # Auto-trigger quality_reviewer for long content
                has_pending_handoff = True
                log_with_context(
                    logger,
                    20,
                    "Auto-triggering quality_reviewer due to content length",
                    content_length=len(agent_content),
                    threshold=auto_review_threshold,
                )

                handoff_event_context = f"内容长度 {len(agent_content)} 字，自动触发质量检查"
                handoff_context = handoff_event_context
                handoff_packet = {
                    "target_agent": "quality_reviewer",
                    "reason": "自动质量门控",
                    "context": handoff_event_context,
                    "completed": [],
                    "todo": ["执行质量审查并返回问题清单"],
                    "evidence": [f"content_length={len(agent_content)}"],
                }

                pending_handoff_event_data = {
                    "target_agent": "quality_reviewer",
                    "reason": "自动质量门控",
                    "context": handoff_event_context,
                    "handoff_packet": handoff_packet,
                }

                pending_next_agent = "quality_reviewer"

            if (
                pending_next_agent == "quality_reviewer"
                and current_agent_type == "writer"
                and agent_content.strip()
            ):
                event_context = ""
                if pending_handoff_event_data is not None:
                    event_context = str(pending_handoff_event_data.get("context") or "").strip()
                base_context = (handoff_context or event_context).strip()
                original_request = str(state.get("router_message") or state.get("user_message") or "").strip()
                review_payload = _format_review_payload(_extract_review_payload(agent_content))
                handoff_context = (
                    f"{base_context}\n\n"
                    f"[原始用户需求]\n{original_request}\n\n"
                    f"[待审查内容]\n{review_payload}"
                ).strip()

            # 检测任务完成。
            # - 显式 handoff 优先级最高（继续协作，不触发 stop/complete）。
            # - planned/auto handoff 仅在显式完成标记时允许打断。
            # - 无待交接时允许启发式完成。
            if agent_content:
                evaluation = evaluate_agent_output(agent_content, current_agent_type)
                complete_result = detect_task_complete(agent_content, current_agent_type)

                explicit_complete = complete_result.reason == "explicit_complete_marker"

                if has_explicit_handoff:
                    can_stop_for_completion = False
                else:
                    can_stop_for_completion = complete_result.is_complete and (
                        explicit_complete or not has_pending_handoff
                    )

                if can_stop_for_completion:
                    log_with_context(
                        logger,
                        20,
                        "Agent marked task as complete, stopping workflow",
                        agent_type=current_agent_type,
                        confidence=complete_result.confidence,
                    )

                    # Best-effort: 自动补发一次 update_project(tasks) 把 in_progress 任务收尾。
                    auto_task_update_events = await _auto_finalize_task_board_on_completion()
                    for auto_task_update_event in auto_task_update_events:
                        yield auto_task_update_event

                    # 发送工作流完成事件
                    yield StreamEvent(
                        type=StreamEventType.WORKFLOW_COMPLETE,
                        data={
                            "reason": "task_complete",
                            "agent_type": current_agent_type,
                            "message": "任务已完成",
                            "confidence": complete_result.confidence,
                            "evaluation": {
                                "complete_score": evaluation.complete_score,
                                "clarification_score": evaluation.clarification_score,
                                "consistency_score": evaluation.consistency_score,
                                "decision_reason": evaluation.reason,
                            },
                        },
                    )

                    # 终止工作流
                    break

            if pending_handoff_event_data is not None:
                yield StreamEvent(
                    type=StreamEventType.HANDOFF,
                    data=pending_handoff_event_data,
                )

            # 保存当前 agent 类型，用于下一轮循环检测
            previous_agent = current_agent_type

            # Apply next agent decision
            current_agent_type = pending_next_agent or None

        ToolContext.set_current_agent(None)

        if iteration >= max_iterations:
            log_with_context(
                logger,
                30,  # WARNING
                "Max collaboration iterations reached",
                iterations=iteration,
            )
            # Notify frontend that collaboration iterations are exhausted
            yield StreamEvent(
                type=StreamEventType.ITERATION_EXHAUSTED,
                data={
                    "layer": "collaboration",
                    "iterations_used": iteration,
                    "max_iterations": max_iterations,
                    "reason": (
                        f"已达到 Agent 协作轮数上限（{max_iterations} 轮）。"
                        f"这是 Agent 之间交接的次数限制，与单个 Agent 的工具调用次数（{AGENT_TOOL_CALL_MAX_ITERATIONS} 次）独立。"
                        "任务可能未完全完成，您可以继续对话让 AI 完成剩余工作。"
                    ),
                    "last_agent": previous_agent,
                },
            )

    except Exception as e:
        log_with_context(
            logger,
            40,  # ERROR
            "Streaming workflow error",
            error=str(e),
            error_type=type(e).__name__,
        )
        yield StreamEvent(
            type=StreamEventType.ERROR,
            data={"error": str(e), "error_type": type(e).__name__},
        )

    log_with_context(
        logger,
        20,  # INFO
        "Streaming writing workflow completed",
        total_iterations=iteration,
        total_content_length=len(accumulated_content),
    )
