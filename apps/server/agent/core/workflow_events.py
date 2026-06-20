"""Workflow streaming event types for the writing graph.

These events are the internal graph/runner contract consumed by the SSE
stream adapter. They are provider-neutral and must not depend on any LLM SDK.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class StreamEventType(Enum):
    """Types of internal workflow streaming events."""

    TEXT = "text"
    THINKING = "thinking"
    TOOL_USE = "tool_use"
    TOOL_RESULT = "tool_result"
    MESSAGE_START = "message_start"
    MESSAGE_END = "message_end"
    ERROR = "error"
    AGENT_SELECTED = "agent_selected"
    HANDOFF = "handoff"
    ITERATION_EXHAUSTED = "iteration_exhausted"
    ROUTER_THINKING = "router_thinking"
    ROUTER_DECIDED = "router_decided"
    WORKFLOW_STOPPED = "workflow_stopped"
    WORKFLOW_COMPLETE = "workflow_complete"
    STEERING_RECEIVED = "steering_received"


@dataclass
class StreamEvent:
    """Internal workflow streaming event."""

    type: StreamEventType
    data: dict[str, Any] = field(default_factory=dict)
