"""Tests for provider-neutral workflow streaming events."""

from agent.core.workflow_events import StreamEvent, StreamEventType


def test_stream_event_with_payload():
    event = StreamEvent(type=StreamEventType.TEXT, data={"text": "hello"})

    assert event.type == StreamEventType.TEXT
    assert event.data == {"text": "hello"}


def test_stream_event_default_data_is_empty_dict():
    event = StreamEvent(type=StreamEventType.MESSAGE_START)

    assert event.type == StreamEventType.MESSAGE_START
    assert event.data == {}


def test_stream_event_type_values_stay_stable():
    assert StreamEventType.TEXT.value == "text"
    assert StreamEventType.THINKING.value == "thinking"
    assert StreamEventType.TOOL_USE.value == "tool_use"
    assert StreamEventType.TOOL_RESULT.value == "tool_result"
    assert StreamEventType.MESSAGE_START.value == "message_start"
    assert StreamEventType.MESSAGE_END.value == "message_end"
    assert StreamEventType.ERROR.value == "error"
    assert StreamEventType.AGENT_SELECTED.value == "agent_selected"
    assert StreamEventType.HANDOFF.value == "handoff"
    assert StreamEventType.ITERATION_EXHAUSTED.value == "iteration_exhausted"
    assert StreamEventType.ROUTER_THINKING.value == "router_thinking"
    assert StreamEventType.ROUTER_DECIDED.value == "router_decided"
    assert StreamEventType.WORKFLOW_STOPPED.value == "workflow_stopped"
    assert StreamEventType.WORKFLOW_COMPLETE.value == "workflow_complete"
    assert StreamEventType.STEERING_RECEIVED.value == "steering_received"
