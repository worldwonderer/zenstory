"""
Router node for the writing workflow.

Uses DeepSeek's OpenAI-compatible Chat Completions API to classify user
intent and route to the appropriate writing agent.
"""

import json
import re
from typing import Literal

from pydantic import BaseModel, Field, ValidationError

from agent.core.deepseek_client import get_deepseek_client
from agent.graph.state import WritingState
from agent.openai_agents.events import parse_json_object
from agent.openai_agents.model import DEEPSEEK_WRITING_MODEL
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

    Uses DeepSeek Chat Completions to classify the user's intent and determine
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
        # Route via DeepSeek Chat Completions + tolerant JSON parser. (An SDK
        # output_type=RouterDecision path was evaluated and removed: DeepSeek
        # rejects response_format json_schema, so it could never succeed.)
        response = await _route_with_deepseek_chat(user_message)
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


async def _route_with_deepseek_chat(user_message: str) -> dict[str, list[dict[str, str]]]:
    """Route using DeepSeek's OpenAI-compatible Chat Completions endpoint."""
    client = get_deepseek_client()
    response = await client.chat.completions.create(
        model=DEEPSEEK_WRITING_MODEL,
        messages=[
            {"role": "system", "content": ROUTER_PROMPT},
            {"role": "user", "content": user_message},
        ],
        temperature=0.0,
        # deepseek-v4-flash is a reasoning model: chain-of-thought reasoning_tokens count
        # against completion tokens. A tight budget can be fully consumed by reasoning,
        # leaving an empty JSON answer and forcing a silent fallback to writer/quick.
        # Keep a generous budget so the short routing JSON always fits after reasoning.
        max_tokens=2048,
    )
    text = response.choices[0].message.content or ""
    return {
        "content": [
            {
                "type": "text",
                "text": text,
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


_ROUTER_KEYS: frozenset[str] = frozenset(
    {"agent_type", "agent", "target_agent", "workflow_type", "workflow", "workflow_plan"}
)


def _extract_router_payload(text: str) -> dict[str, object]:
    """
    Extract payload from router raw text.

    Parsing order:
    1) Strict JSON (fast path — no repair needed)
    2) Shared JSON-repair via parse_json_object (handles markdown fences, truncation, etc.)
       If the repaired result lacks routing keys, scan per-fragment for a better match.
    3) Legacy two-line text fallback (agent\\nworkflow)
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

    # 2) Shared JSON-repair path (delegates to json_repair library when available).
    #    If parse_json_object succeeds and the result has routing keys, use it.
    #    Otherwise scan per-fragment (raw_decode at each '{') to prefer a fragment
    #    that contains routing keys — this handles text with multiple JSON objects
    #    where json_repair returns the first/wrong one (or a non-dict like a list).
    repaired, _err, _meta = parse_json_object(text, tool_name="router")
    if repaired and any(key in repaired for key in _ROUTER_KEYS):
        return repaired

    # Per-fragment scan: prefer any fragment with routing keys, keep first as fallback.
    fallback_object: dict[str, object] | None = repaired if repaired else None
    for candidate in _iter_json_object_candidates(text):
        try:
            candidate_obj = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if not isinstance(candidate_obj, dict):
            continue
        if any(key in candidate_obj for key in _ROUTER_KEYS):
            return candidate_obj
        if fallback_object is None:
            fallback_object = candidate_obj

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
