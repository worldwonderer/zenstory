"""
Agent nodes for the writing workflow.

Implements the graph-facing streaming agent entrypoint and output evaluation
helpers. The model/tool loop is provided by agent.openai_agents.
"""

from collections.abc import AsyncIterator
from typing import Any, NamedTuple

from agent.core.workflow_events import StreamEvent, StreamEventType
from agent.graph.state import WritingState
from agent.openai_agents.runner import run_openai_agents_streaming_agent
from agent.prompts.subagents import (
    HOOK_DESIGNER_PROMPT,
    PLANNER_PROMPT,
    QUALITY_REVIEWER_PROMPT,
    WRITER_PROMPT,
)
from utils.logger import get_logger, log_with_context

logger = get_logger(__name__)


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

    base_prompt = state.get("system_prompt", "")

    # Combine base prompt with specialized agent prompt
    specialized = specialized_prompts.get(agent_type, "")
    if base_prompt and specialized:
        system_prompt = f"{base_prompt}\n\n## 当前角色：{agent_type}\n\n{specialized}"
    elif specialized:
        system_prompt = specialized
    else:
        system_prompt = base_prompt

    try:
        async for event in run_openai_agents_streaming_agent(
            state=state,
            agent_type=agent_type,
            system_prompt=system_prompt,
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

    # Explicit [TASK_COMPLETE] marker is the ONLY completion signal.
    # Chinese substring heuristics (任务已完成, 已完成, etc.) are intentionally
    # removed: they produced false positives whenever those phrases appeared
    # mid-text.  Mirror the clarification approach: structured signal only.
    has_complete_marker = lowered.endswith("[task_complete]")
    complete_score = 1.0 if has_complete_marker else 0.0
    clarification_score = 0.0

    should_clarify = False
    should_complete = has_complete_marker and not should_clarify

    # Lightweight consistency score for observability/debugging
    consistency_score = max(0.0, 1.0 - abs(complete_score - clarification_score))

    reason = "explicit_complete_marker" if has_complete_marker else "insufficient_signal"

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
