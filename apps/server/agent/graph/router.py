"""
Router node for the writing workflow.

Uses Anthropic API to classify user intent and route to the appropriate agent.
Supports workflow planning for multi-agent collaboration.
"""

import json
import re
from typing import Any, Literal

from pydantic import BaseModel, Field, ValidationError

from agent.graph.state import WritingState
from agent.llm.anthropic_client import StreamEventType, get_router_client
from agent.prompts.subagents import ROUTER_PROMPT
from utils.logger import get_logger, log_with_context

logger = get_logger(__name__)

# Valid agent types for routing
AgentType = Literal["planner", "hook_designer", "writer", "quality_reviewer"]

# Workflow type definitions
WorkflowType = Literal["quick", "standard", "full", "hook_focus", "review_only"]

# Workflow type to agent sequence mapping
# 每个工作流定义了初始 Agent 之后的 Agent 序列
WORKFLOW_AGENTS: dict[str, list[str]] = {
    "quick": [],  # writer only (review is triggered explicitly or via auto-review gate)
    "standard": ["writer"],  # planner -> writer
    "full": ["hook_designer", "writer"],  # planner -> hook_designer -> writer
    "hook_focus": ["writer"],  # hook_designer -> writer
    "review_only": [],  # quality_reviewer only
}


class RouterDecision(BaseModel):
    """Structured routing decision with schema validation."""

    agent_type: AgentType
    workflow_type: WorkflowType
    reason: str = ""
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)


async def router_node(state: WritingState) -> dict:
    """
    Route user message to appropriate agent based on intent.

    Uses Anthropic API to classify the user's intent and determine
    which agent (planner/writer/quality_reviewer) should handle the request.
    Also plans the workflow path for multi-agent collaboration.

    Args:
        state: Current workflow state containing user_message

    Returns:
        Dict with current_agent, workflow_plan, workflow_agents, routing_metadata
    """
    user_message = state.get("router_message") or state.get("user_message", "")

    log_with_context(
        logger,
        20,  # INFO
        "Router node processing message",
        message_preview=user_message[:100] if user_message else "",
    )

    if not user_message:
        log_with_context(logger, 30, "Empty user message, defaulting to writer")
        return {
            "current_agent": "writer",
            "workflow_plan": "quick",
            "workflow_agents": [],
            "routing_metadata": {
                "agent_type": "writer",
                "workflow_type": "quick",
                "reason": "empty_user_message",
                "confidence": 0.0,
            },
        }

    try:
        client = get_router_client()

        # Call Anthropic API for intent classification and workflow planning
        response = await _route_with_streaming(client, user_message)

        # Extract structured decision from response
        decision = _parse_router_response(response)
        workflow_agents = WORKFLOW_AGENTS.get(decision.workflow_type, [])

        log_with_context(
            logger,
            20,  # INFO
            "Router determined agent and workflow",
            agent_type=decision.agent_type,
            workflow_type=decision.workflow_type,
            workflow_agents=workflow_agents,
            confidence=decision.confidence,
            user_message_preview=user_message[:50],
        )

        return {
            "current_agent": decision.agent_type,
            "workflow_plan": decision.workflow_type,
            "workflow_agents": workflow_agents,
            "routing_metadata": decision.model_dump(),
        }

    except Exception as e:
        log_with_context(
            logger,
            40,  # ERROR
            "Router error, defaulting to writer with quick workflow",
            error=str(e),
            error_type=type(e).__name__,
        )
        # Default to writer on error (review is triggered explicitly or via auto-review gate)
        return {
            "current_agent": "writer",
            "workflow_plan": "quick",
            "workflow_agents": [],
            "routing_metadata": {
                "agent_type": "writer",
                "workflow_type": "quick",
                "reason": "router_fallback",
                "confidence": 0.0,
            },
        }


async def _route_with_streaming(client: Any, user_message: str) -> dict[str, list[dict[str, str]]]:
    """
    Route using streaming API and aggregate text deltas into a router response.

    This avoids long-request failures on non-streaming endpoints while keeping
    existing parser behavior unchanged.
    """
    text_parts: list[str] = []

    async for event in client.stream_message(
        messages=[{"role": "user", "content": user_message}],
        system_prompt=ROUTER_PROMPT,
    ):
        event_type = getattr(event, "type", None)

        if event_type in (StreamEventType.TEXT, StreamEventType.TEXT.value):
            text = event.data.get("text", "")
            if text:
                text_parts.append(text)
            continue

        if event_type in (StreamEventType.ERROR, StreamEventType.ERROR.value):
            error_message = event.data.get("error", "Unknown router streaming error")
            raise ValueError(error_message)

    return {
        "content": [
            {
                "type": "text",
                "text": "".join(text_parts),
            }
        ]
    }


def _parse_router_response(response: dict) -> RouterDecision:
    """
    Parse and validate structured router decision from model response.

    Preferred format is strict JSON, with backward-compatible fallback to
    legacy two-line text format.
    """
    content_blocks = response.get("content", [])

    parse_errors: list[str] = []
    for block in content_blocks:
        if block.get("type") != "text":
            continue

        text = block.get("text", "").strip()
        payload = _extract_router_payload(text)
        normalized = _normalize_router_payload(payload)

        try:
            return RouterDecision.model_validate(normalized)
        except ValidationError as e:
            parse_errors.append(str(e))
            continue

    if parse_errors:
        raise ValueError(f"Invalid router response schema: {'; '.join(parse_errors)}")

    # No parseable text block
    return RouterDecision(
        agent_type="writer",
        workflow_type="quick",
        reason="empty_router_response",
        confidence=0.0,
    )


def _extract_router_payload(text: str) -> dict[str, object]:
    """
    Extract payload from router raw text.

    Parsing order:
    1) Strict JSON
    2) JSON object fragment inside text
    3) Legacy two-line text fallback
    """
    if not text:
        return {}

    # 1) strict JSON
    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass

    # 2) JSON fragment(s) inside wrappers (e.g. markdown)
    fallback_object: dict[str, object] | None = None
    for candidate in _iter_json_object_candidates(text):
        try:
            parsed = json.loads(candidate)
            if isinstance(parsed, dict):
                if any(
                    key in parsed
                    for key in ("agent_type", "agent", "target_agent", "workflow_type", "workflow", "workflow_plan")
                ):
                    return parsed
                fallback_object = parsed
        except json.JSONDecodeError:
            continue

    if fallback_object is not None:
        return fallback_object

    # 3) Legacy two-line fallback: line1 agent, line2 workflow
    lowered = text.lower()
    lines = [line.strip() for line in lowered.split("\n") if line.strip()]
    payload: dict[str, object] = {}
    if lines:
        payload["agent_type"] = lines[0]
    if len(lines) > 1:
        payload["workflow_type"] = lines[1]
    return payload


def _iter_json_object_candidates(text: str) -> list[str]:
    """
    Extract JSON object candidates from free-form text.

    Uses JSONDecoder.raw_decode at every '{' start index to avoid greedy regex
    over-capturing when text contains multiple objects.
    """
    decoder = json.JSONDecoder()
    candidates: list[str] = []

    for match in re.finditer(r"\{", text):
        start = match.start()
        try:
            parsed_obj, end = decoder.raw_decode(text[start:])
        except json.JSONDecodeError:
            continue
        if isinstance(parsed_obj, dict):
            candidates.append(text[start:start + end])
    return candidates


def _normalize_router_payload(payload: dict[str, object]) -> dict[str, object]:
    """Normalize router payload into RouterDecision fields."""
    agent_raw = str(
        payload.get("agent_type")
        or payload.get("agent")
        or payload.get("target_agent")
        or "writer"
    ).strip().lower()

    agent_type: AgentType = "writer"
    if "planner" in agent_raw:
        agent_type = "planner"
    elif "hook_designer" in agent_raw:
        agent_type = "hook_designer"
    elif "quality_reviewer" in agent_raw:
        agent_type = "quality_reviewer"
    elif "writer" in agent_raw:
        agent_type = "writer"

    workflow_raw = str(
        payload.get("workflow_type")
        or payload.get("workflow")
        or payload.get("workflow_plan")
        or ""
    ).strip().lower()
    if not workflow_raw:
        workflow_raw = _infer_workflow_from_agent(agent_type)

    workflow_type: WorkflowType = "quick"
    if "full" in workflow_raw:
        workflow_type = "full"
    elif "standard" in workflow_raw:
        workflow_type = "standard"
    elif "hook_focus" in workflow_raw:
        workflow_type = "hook_focus"
    elif "review_only" in workflow_raw:
        workflow_type = "review_only"
    elif "quick" in workflow_raw:
        workflow_type = "quick"

    confidence_raw = payload.get("confidence", 0.0)
    try:
        confidence = float(confidence_raw)
    except (TypeError, ValueError):
        confidence = 0.0
    confidence = max(0.0, min(1.0, confidence))

    reason = str(payload.get("reason", "")).strip()

    return {
        "agent_type": agent_type,
        "workflow_type": workflow_type,
        "reason": reason,
        "confidence": confidence,
    }


def _infer_workflow_from_agent(agent_type: AgentType) -> WorkflowType:
    """Infer default workflow type based on initial agent."""
    workflow_map = {
        "planner": "standard",  # planner -> writer -> quality_reviewer
        "hook_designer": "hook_focus",  # hook_designer -> writer -> quality_reviewer
        "writer": "quick",  # writer -> quality_reviewer
        "quality_reviewer": "review_only",  # quality_reviewer only
    }
    return workflow_map.get(agent_type, "review_only")


def get_next_node(state: WritingState) -> AgentType:
    """
    Resolve the next agent from current state.

    Returns the next node based on current_agent in state.
    """
    agent = state.get("current_agent", "writer")

    if agent in ("planner", "hook_designer", "writer", "quality_reviewer"):
        return agent  # type: ignore[return-value]

    return "writer"
