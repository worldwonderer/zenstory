"""
Tests for StreamAdapter - SSE streaming adapter for LangGraph events.

Comprehensive tests covering:
- SSE event formatting
- Streaming lifecycle
- Error handling
- Event types conversion
- File marker processing
- Tool result handling
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agent.core.events import (
    EventType,
    compaction_done_event,
    parallel_end_event,
    session_started_event,
    steering_received_event,
)
from agent.core.stream_processor import StreamState, normalize_file_markers
from agent.llm.anthropic_client import StreamEvent as LangGraphStreamEvent
from agent.llm.anthropic_client import StreamEventType
from agent.stream_adapter import (
    PendingFileWrite,
    StreamAdapter,
    StreamAdapterConfig,
    create_stream_adapter,
)


@pytest.fixture
def adapter_config():
    """Create test adapter configuration."""
    return StreamAdapterConfig(
        project_id="test-project-id",
        user_id="test-user-id",
        process_file_markers=True,
    )


@pytest.fixture
def adapter(adapter_config):
    """Create test stream adapter."""
    return StreamAdapter(adapter_config)


@pytest.fixture
def adapter_no_file_markers():
    """Create adapter with file marker processing disabled."""
    config = StreamAdapterConfig(
        project_id="test-project-id",
        user_id="test-user-id",
        process_file_markers=False,
    )
    return StreamAdapter(config)


class TestStreamAdapterConfig:
    """Tests for StreamAdapterConfig."""

    def test_default_config(self):
        """Test default configuration values."""
        config = StreamAdapterConfig()
        assert config.project_id == ""
        assert config.user_id is None
        assert config.process_file_markers is True

    def test_custom_config(self):
        """Test custom configuration values."""
        config = StreamAdapterConfig(
            project_id="project-123",
            user_id="user-456",
            process_file_markers=False,
        )
        assert config.project_id == "project-123"
        assert config.user_id == "user-456"
        assert config.process_file_markers is False


class TestPendingFileWrite:
    """Tests for PendingFileWrite dataclass."""

    def test_pending_file_write_creation(self):
        """Test creating a pending file write."""
        pending = PendingFileWrite(
            file_id="file-123",
            file_type="draft",
            title="Chapter 1",
        )
        assert pending.file_id == "file-123"
        assert pending.file_type == "draft"
        assert pending.title == "Chapter 1"


class TestStreamAdapterInit:
    """Tests for StreamAdapter initialization."""

    def test_init_with_config(self, adapter_config):
        """Test initialization with custom config."""
        adapter = StreamAdapter(adapter_config)
        assert adapter.config.project_id == "test-project-id"
        assert adapter.config.user_id == "test-user-id"
        assert adapter._pending_file_write is None
        assert adapter._content_started is False
        assert adapter._current_tool_calls == {}
        assert adapter._last_message_stop_reason is None
        assert adapter._last_message_usage is None
        assert adapter._accumulated_text == ""

    def test_init_without_config(self):
        """Test initialization with default config."""
        adapter = StreamAdapter()
        assert adapter.config.project_id == ""
        assert adapter.config.user_id is None

    def test_reset(self, adapter):
        """Test reset clears all state."""
        # Set some state
        adapter._content_started = True
        adapter._accumulated_text = "some text"
        adapter._current_tool_calls["tool-1"] = {"name": "test"}
        adapter._last_message_stop_reason = "end_turn"
        adapter._last_message_usage = {"input_tokens": 1}
        adapter._pending_file_write = PendingFileWrite(
            file_id="file-1", file_type="draft", title="Test"
        )

        # Reset
        adapter.reset()

        # Verify all state cleared
        assert adapter._content_started is False
        assert adapter._accumulated_text == ""
        assert adapter._current_tool_calls == {}
        assert adapter._last_message_stop_reason is None
        assert adapter._last_message_usage is None
        assert adapter._pending_file_write is None
        assert adapter._stream_processor.state == StreamState.IDLE

    def test_get_last_message_metadata_defaults(self, adapter):
        """Should return empty metadata values before any message_end."""
        metadata = adapter.get_last_message_metadata()
        assert metadata["stop_reason"] is None
        assert metadata["usage"] is None


class TestSetPendingFileWrite:
    """Tests for set_pending_file_write method."""

    def test_set_pending_file_write(self, adapter):
        """Test setting pending file write."""
        adapter.set_pending_file_write(
            file_id="file-123",
            file_type="draft",
            title="Chapter 1",
        )

        assert adapter._pending_file_write is not None
        assert adapter._pending_file_write.file_id == "file-123"
        assert adapter._pending_file_write.file_type == "draft"
        assert adapter._pending_file_write.title == "Chapter 1"

        # Verify stream processor is in waiting state
        assert adapter._stream_processor.state == StreamState.WAITING_START
        assert adapter._stream_processor.file_id == "file-123"


class TestProcessEventText:
    """Tests for processing TEXT events."""

    @pytest.mark.asyncio
    async def test_text_event_starts_content(self, adapter):
        """Test text event triggers content_start."""
        event = LangGraphStreamEvent(
            type=StreamEventType.TEXT,
            data={"text": "Hello world"},
        )

        events = []
        async for sse_event in adapter._process_langgraph_event(event):
            events.append(sse_event)

        # Should emit content_start and content events
        assert len(events) == 2
        assert events[0].type == EventType.CONTENT_START
        assert events[1].type == EventType.CONTENT
        assert events[1].data["text"] == "Hello world"

    @pytest.mark.asyncio
    async def test_multiple_text_events(self, adapter):
        """Test multiple text events only emit one content_start."""
        event1 = LangGraphStreamEvent(
            type=StreamEventType.TEXT,
            data={"text": "Hello"},
        )
        event2 = LangGraphStreamEvent(
            type=StreamEventType.TEXT,
            data={"text": " world"},
        )

        events = []
        async for sse_event in adapter._process_langgraph_event(event1):
            events.append(sse_event)
        async for sse_event in adapter._process_langgraph_event(event2):
            events.append(sse_event)

        # Should have 3 events: content_start, content, content
        assert len(events) == 3
        assert events[0].type == EventType.CONTENT_START
        assert events[1].type == EventType.CONTENT
        assert events[1].data["text"] == "Hello"
        assert events[2].type == EventType.CONTENT
        assert events[2].data["text"] == " world"

    @pytest.mark.asyncio
    async def test_text_accumulates_for_skill_detection(self, adapter):
        """Test text is accumulated for skill usage detection."""
        event1 = LangGraphStreamEvent(
            type=StreamEventType.TEXT,
            data={"text": "[使用技能: "},
        )
        event2 = LangGraphStreamEvent(
            type=StreamEventType.TEXT,
            data={"text": "大纲规划师]"},
        )

        async for _ in adapter._process_langgraph_event(event1):
            pass
        async for _ in adapter._process_langgraph_event(event2):
            pass

        assert adapter._accumulated_text == "[使用技能: 大纲规划师]"


class TestProcessEventThinking:
    """Tests for processing THINKING events."""

    @pytest.mark.asyncio
    async def test_thinking_event(self, adapter):
        """Test thinking event emits thinking_content."""
        event = LangGraphStreamEvent(
            type=StreamEventType.THINKING,
            data={"thinking": "Let me think about this..."},
        )

        events = []
        async for sse_event in adapter._process_langgraph_event(event):
            events.append(sse_event)

        assert len(events) == 1
        assert events[0].type == EventType.THINKING_CONTENT
        assert events[0].data["content"] == "Let me think about this..."
        assert events[0].data["is_complete"] is False

    @pytest.mark.asyncio
    async def test_empty_thinking_event(self, adapter):
        """Test empty thinking event emits nothing."""
        event = LangGraphStreamEvent(
            type=StreamEventType.THINKING,
            data={"thinking": ""},
        )

        events = []
        async for sse_event in adapter._process_langgraph_event(event):
            events.append(sse_event)

        assert len(events) == 0


class TestProcessEventMessageEnd:
    """Tests for processing MESSAGE_END events metadata capture."""

    @pytest.mark.asyncio
    async def test_message_end_captures_metadata(self, adapter):
        """MESSAGE_END should update adapter metadata for persistence."""
        event = LangGraphStreamEvent(
            type=StreamEventType.MESSAGE_END,
            data={
                "stop_reason": "tool_use",
                "usage": {"input_tokens": 10, "output_tokens": 5},
            },
        )

        events = []
        async for sse_event in adapter._process_langgraph_event(event):
            events.append(sse_event)

        assert events == []
        metadata = adapter.get_last_message_metadata()
        assert metadata["stop_reason"] == "tool_use"
        assert metadata["usage"]["input_tokens"] == 10


class TestProcessEventToolUse:
    """Tests for processing TOOL_USE events."""

    @pytest.mark.asyncio
    async def test_tool_use_start(self, adapter):
        """Test tool use start event."""
        event = LangGraphStreamEvent(
            type=StreamEventType.TOOL_USE,
            data={
                "status": "start",
                "id": "tool-123",
                "name": "create_file",
            },
        )

        events = []
        async for sse_event in adapter._process_langgraph_event(event):
            events.append(sse_event)

        # Start event doesn't emit SSE event, just tracks state
        assert len(events) == 0
        assert "tool-123" in adapter._current_tool_calls
        assert adapter._current_tool_calls["tool-123"]["name"] == "create_file"

    @pytest.mark.asyncio
    async def test_tool_use_delta(self, adapter):
        """Test tool use delta accumulates JSON."""
        # Start first
        adapter._current_tool_calls["tool-1"] = {
            "name": "edit_file",
            "input_json": "",
        }

        event = LangGraphStreamEvent(
            type=StreamEventType.TOOL_USE,
            data={
                "status": "delta",
                "partial_json": '{"file_id": "f1"',
            },
        )

        events = []
        async for sse_event in adapter._process_langgraph_event(event):
            events.append(sse_event)

        # Delta doesn't emit SSE event
        assert len(events) == 0
        assert adapter._current_tool_calls["tool-1"]["input_json"] == '{"file_id": "f1"'

    @pytest.mark.asyncio
    async def test_tool_use_stop_with_input(self, adapter):
        """Test tool use stop emits tool_call event with input."""
        event = LangGraphStreamEvent(
            type=StreamEventType.TOOL_USE,
            data={
                "status": "stop",
                "id": "tool-1",
                "name": "create_file",
                "input": {"title": "Chapter 1", "file_type": "draft"},
            },
        )

        events = []
        async for sse_event in adapter._process_langgraph_event(event):
            events.append(sse_event)

        assert len(events) == 1
        assert events[0].type == EventType.TOOL_CALL
        assert events[0].data["tool_use_id"] == "tool-1"
        assert events[0].data["tool_name"] == "create_file"
        assert events[0].data["arguments"]["title"] == "Chapter 1"

    @pytest.mark.asyncio
    async def test_tool_use_stop_with_accumulated_json(self, adapter):
        """Test tool use stop with accumulated JSON."""
        # Set up accumulated JSON
        adapter._current_tool_calls["tool-1"] = {
            "name": "edit_file",
            "input_json": '{"file_id": "f123", "edits": []}',
        }

        event = LangGraphStreamEvent(
            type=StreamEventType.TOOL_USE,
            data={
                "status": "stop",
                "id": "tool-1",
                "name": "edit_file",
            },
        )

        events = []
        async for sse_event in adapter._process_langgraph_event(event):
            events.append(sse_event)

        assert len(events) == 1
        assert events[0].type == EventType.TOOL_CALL
        assert events[0].data["tool_use_id"] == "tool-1"
        assert events[0].data["tool_name"] == "edit_file"
        assert events[0].data["arguments"]["file_id"] == "f123"

        # Should clean up tracked tool call
        assert "tool-1" not in adapter._current_tool_calls

    @pytest.mark.asyncio
    async def test_tool_use_complete(self, adapter):
        """Test tool use complete event."""
        event = LangGraphStreamEvent(
            type=StreamEventType.TOOL_USE,
            data={
                "status": "complete",
                "name": "query_files",
                "input": {"query": "chapter"},
            },
        )

        events = []
        async for sse_event in adapter._process_langgraph_event(event):
            events.append(sse_event)

        assert len(events) == 1
        assert events[0].type == EventType.TOOL_CALL
        assert events[0].data["tool_use_id"] is None
        assert events[0].data["tool_name"] == "query_files"


class TestProcessEventToolResult:
    """Tests for processing TOOL_RESULT events."""

    @pytest.mark.asyncio
    async def test_tool_result_success(self, adapter):
        """Test successful tool result."""
        result_json = json.dumps({
            "status": "success",
            "data": {"id": "f1", "title": "Test"}
        })
        event = LangGraphStreamEvent(
            type=StreamEventType.TOOL_RESULT,
            data={
                "name": "create_file",
                "result": {
                    "content": [{"text": result_json}]
                },
            },
        )

        events = []
        async for sse_event in adapter._process_langgraph_event(event):
            events.append(sse_event)

        assert len(events) >= 1
        assert events[0].type == EventType.TOOL_RESULT
        assert events[0].data["tool_use_id"] is None
        assert events[0].data["tool_name"] == "create_file"
        assert events[0].data["status"] == "success"

    @pytest.mark.asyncio
    async def test_tool_result_error(self, adapter):
        """Test error tool result."""
        result_json = json.dumps({
            "status": "error",
            "error": "File not found"
        })
        event = LangGraphStreamEvent(
            type=StreamEventType.TOOL_RESULT,
            data={
                "name": "update_file",
                "result": {
                    "content": [{"text": result_json}]
                },
            },
        )

        events = []
        async for sse_event in adapter._process_langgraph_event(event):
            events.append(sse_event)

        assert len(events) >= 1
        assert events[0].type == EventType.TOOL_RESULT
        assert events[0].data["status"] == "error"
        assert events[0].data["error"] == "File not found"

    @pytest.mark.asyncio
    async def test_tool_result_error_without_status_field(self, adapter):
        """Test backward-compatible error parsing when payload only has error field."""
        result_json = json.dumps({
            "error": "Unknown tool: bad_tool"
        })
        event = LangGraphStreamEvent(
            type=StreamEventType.TOOL_RESULT,
            data={
                "name": "bad_tool",
                "result": {
                    "content": [{"text": result_json}]
                },
            },
        )

        events = []
        async for sse_event in adapter._process_langgraph_event(event):
            events.append(sse_event)

        assert len(events) >= 1
        assert events[0].type == EventType.TOOL_RESULT
        assert events[0].data["status"] == "error"
        assert events[0].data["error"] == "Unknown tool: bad_tool"

    @pytest.mark.asyncio
    async def test_tool_result_with_invalid_json(self, adapter):
        """Test tool result with invalid JSON."""
        event = LangGraphStreamEvent(
            type=StreamEventType.TOOL_RESULT,
            data={
                "name": "query_files",
                "result": {
                    "content": [{"text": "not valid json"}]
                },
            },
        )

        events = []
        async for sse_event in adapter._process_langgraph_event(event):
            events.append(sse_event)

        # Should handle gracefully
        assert len(events) >= 1
        assert events[0].type == EventType.TOOL_RESULT

    @pytest.mark.asyncio
    async def test_tool_result_with_non_dict_result_shape(self, adapter):
        """Non-MCP result shapes should not break tool_result SSE emission."""
        event = LangGraphStreamEvent(
            type=StreamEventType.TOOL_RESULT,
            data={
                "name": "query_files",
                "result": "plain text payload",
            },
        )

        events = []
        async for sse_event in adapter._process_langgraph_event(event):
            events.append(sse_event)

        assert len(events) == 1
        assert events[0].type == EventType.TOOL_RESULT
        assert events[0].data["status"] == "success"
        assert events[0].data["data"]["raw"] == "plain text payload"

    @pytest.mark.asyncio
    async def test_tool_result_handoff_status_is_normalized_to_success(self, adapter):
        """Control-tool statuses should map to frontend-compatible success/error."""
        result_json = json.dumps({
            "status": "handoff",
            "target_agent": "quality_reviewer",
            "reason": "质量审查",
        })
        event = LangGraphStreamEvent(
            type=StreamEventType.TOOL_RESULT,
            data={
                "name": "handoff_to_agent",
                "result": {"content": [{"text": result_json}]},
            },
        )

        events = []
        async for sse_event in adapter._process_langgraph_event(event):
            events.append(sse_event)

        assert len(events) == 1
        assert events[0].type == EventType.TOOL_RESULT
        assert events[0].data["status"] == "success"

    @pytest.mark.asyncio
    async def test_tool_result_edit_file_with_non_dict_data_is_tolerated(self, adapter):
        """edit_file extra events should be skipped (not crashed) when data is truncated/non-dict."""
        result_json = json.dumps({
            "status": "success",
            "data": "truncated",
            "truncated": True,
            "max_chars": 100,
            "original_length": 999,
        })
        event = LangGraphStreamEvent(
            type=StreamEventType.TOOL_RESULT,
            data={
                "name": "edit_file",
                "result": {"content": [{"text": result_json}]},
            },
        )

        events = []
        async for sse_event in adapter._process_langgraph_event(event):
            events.append(sse_event)

        # Only tool_result should be emitted; edit detail events are skipped safely.
        assert len(events) == 1
        assert events[0].type == EventType.TOOL_RESULT
        assert events[0].data["status"] == "success"

    @pytest.mark.asyncio
    async def test_stream_continues_after_malformed_tool_result(self, adapter):
        """Malformed tool_result parsing should not interrupt subsequent SSE events."""

        async def mock_events():
            yield LangGraphStreamEvent(
                type=StreamEventType.TOOL_RESULT,
                data={
                    "name": "query_files",
                    "result": {
                        "content": ["bad-shape"],  # invalid MCP content item shape
                    },
                },
            )
            yield LangGraphStreamEvent(
                type=StreamEventType.TEXT,
                data={"text": "still running"},
            )

        events = []
        async for sse_event in adapter.process_langgraph_events(mock_events()):
            events.append(sse_event)

        event_types = [event.type for event in events]
        assert EventType.TOOL_RESULT in event_types
        assert EventType.CONTENT in event_types
        assert EventType.DONE in event_types


class TestProcessEventAgentSelected:
    """Tests for processing AGENT_SELECTED events."""

    @pytest.mark.asyncio
    async def test_agent_selected_event(self, adapter):
        """Test agent selected event."""
        event = LangGraphStreamEvent(
            type=StreamEventType.AGENT_SELECTED,
            data={
                "agent_type": "planner",
                "agent_name": "大纲规划师",
                "iteration": 1,
                "max_iterations": 5,
                "remaining": 4,
            },
        )

        events = []
        async for sse_event in adapter._process_langgraph_event(event):
            events.append(sse_event)

        assert len(events) == 1
        assert events[0].type == EventType.AGENT_SELECTED
        assert events[0].data["agent_type"] == "planner"
        assert events[0].data["agent_name"] == "大纲规划师"
        assert events[0].data["iteration"] == 1
        assert events[0].data["max_iterations"] == 5
        assert events[0].data["remaining"] == 4


class TestProcessEventIterationExhausted:
    """Tests for processing ITERATION_EXHAUSTED events."""

    @pytest.mark.asyncio
    async def test_iteration_exhausted_event(self, adapter):
        """Test iteration exhausted event."""
        event = LangGraphStreamEvent(
            type=StreamEventType.ITERATION_EXHAUSTED,
            data={
                "layer": "tool_call",
                "iterations_used": 10,
                "max_iterations": 10,
                "reason": "Maximum tool call iterations reached",
                "last_agent": "writer",
            },
        )

        events = []
        async for sse_event in adapter._process_langgraph_event(event):
            events.append(sse_event)

        assert len(events) == 1
        assert events[0].type == EventType.ITERATION_EXHAUSTED
        assert events[0].data["layer"] == "tool_call"
        assert events[0].data["iterations_used"] == 10
        assert events[0].data["last_agent"] == "writer"


class TestProcessEventPassthrough:
    """Tests for passthrough LangGraph events."""

    @pytest.mark.asyncio
    async def test_handoff_event_passthrough(self, adapter):
        """Test handoff event is mapped to a valid SSE event type."""
        event = LangGraphStreamEvent(
            type=StreamEventType.HANDOFF,
            data={"from_agent": "planner", "to_agent": "writer"},
        )

        events = []
        async for sse_event in adapter._process_langgraph_event(event):
            events.append(sse_event)

        assert len(events) == 1
        assert events[0].type == EventType.HANDOFF
        assert events[0].data["from_agent"] == "planner"
        assert events[0].data["to_agent"] == "writer"

    @pytest.mark.asyncio
    async def test_core_steering_received_event_passthrough(self, adapter):
        """Test core steering_received event is passed through by value."""
        event = steering_received_event(
            message_id="steer-1",
            preview="请聚焦第二章",
        )

        events = []
        async for sse_event in adapter._process_langgraph_event(event):
            events.append(sse_event)

        assert len(events) == 1
        assert events[0].type == EventType.STEERING_RECEIVED
        assert events[0].data["message_id"] == "steer-1"

    @pytest.mark.asyncio
    async def test_core_session_started_event_passthrough(self, adapter):
        """Test core session_started event is passed through by value."""
        event = session_started_event("session-123")

        events = []
        async for sse_event in adapter._process_langgraph_event(event):
            events.append(sse_event)

        assert len(events) == 1
        assert events[0].type == EventType.SESSION_STARTED
        assert events[0].data["session_id"] == "session-123"

    @pytest.mark.asyncio
    async def test_core_parallel_end_event_passthrough(self, adapter):
        """Test core parallel_end event is passed through by value."""
        event = parallel_end_event(
            execution_id="exec-1",
            total_tasks=4,
            completed=3,
            failed=1,
            duration_ms=1200,
        )

        events = []
        async for sse_event in adapter._process_langgraph_event(event):
            events.append(sse_event)

        assert len(events) == 1
        assert events[0].type == EventType.PARALLEL_END
        assert events[0].data["execution_id"] == "exec-1"
        assert events[0].data["total_tasks"] == 4

    @pytest.mark.asyncio
    async def test_core_compaction_done_event_passthrough(self, adapter):
        """Test core compaction_done event is passed through by value."""
        event = compaction_done_event(
            tokens_after=2300,
            messages_removed=12,
            summary_preview="压缩摘要",
        )

        events = []
        async for sse_event in adapter._process_langgraph_event(event):
            events.append(sse_event)

        assert len(events) == 1
        assert events[0].type == EventType.COMPACTION_DONE
        assert events[0].data["messages_removed"] == 12


class TestProcessEventError:
    """Tests for processing ERROR events."""

    @pytest.mark.asyncio
    async def test_error_event(self, adapter):
        """Test error event."""
        event = LangGraphStreamEvent(
            type=StreamEventType.ERROR,
            data={"error": "API rate limit exceeded"},
        )

        events = []
        async for sse_event in adapter._process_langgraph_event(event):
            events.append(sse_event)

        assert len(events) == 1
        assert events[0].type == EventType.ERROR
        assert events[0].data["message"] == "API rate limit exceeded"

    @pytest.mark.asyncio
    async def test_error_event_with_default_message(self, adapter):
        """Test error event with default message."""
        event = LangGraphStreamEvent(
            type=StreamEventType.ERROR,
            data={},
        )

        events = []
        async for sse_event in adapter._process_langgraph_event(event):
            events.append(sse_event)

        assert len(events) == 1
        assert events[0].data["message"] == "Unknown error"


class TestProcessLangGraphEvents:
    """Tests for the main process_langgraph_events method."""

    @pytest.mark.asyncio
    async def test_stream_lifecycle(self, adapter):
        """Test complete streaming lifecycle."""
        async def mock_events():
            yield LangGraphStreamEvent(
                type=StreamEventType.TEXT,
                data={"text": "Hello"},
            )
            yield LangGraphStreamEvent(
                type=StreamEventType.TEXT,
                data={"text": " world"},
            )
            yield LangGraphStreamEvent(
                type=StreamEventType.MESSAGE_END,
                data={},
            )

        events = []
        async for sse_event in adapter.process_langgraph_events(mock_events()):
            events.append(sse_event)

        # Should have: content_start, content, content, content_end, done
        assert len(events) == 5
        assert events[0].type == EventType.CONTENT_START
        assert events[1].type == EventType.CONTENT
        assert events[2].type == EventType.CONTENT
        assert events[3].type == EventType.CONTENT_END
        assert events[4].type == EventType.DONE

    @pytest.mark.asyncio
    async def test_stream_ensures_content_end(self, adapter):
        """Test content_end is emitted even if not in events."""
        async def mock_events():
            yield LangGraphStreamEvent(
                type=StreamEventType.TEXT,
                data={"text": "Text"},
            )
            # No MESSAGE_END, just stop

        events = []
        async for sse_event in adapter.process_langgraph_events(mock_events()):
            events.append(sse_event)

        # Should still have content_end and done
        event_types = [e.type for e in events]
        assert EventType.CONTENT_END in event_types
        assert EventType.DONE in event_types

    @pytest.mark.asyncio
    async def test_stream_without_content(self, adapter):
        """Test stream without any content events."""
        async def mock_events():
            yield LangGraphStreamEvent(
                type=StreamEventType.AGENT_SELECTED,
                data={"agent_type": "writer"},
            )
            yield LangGraphStreamEvent(
                type=StreamEventType.MESSAGE_END,
                data={},
            )

        events = []
        async for sse_event in adapter.process_langgraph_events(mock_events()):
            events.append(sse_event)

        # Should have agent_selected and done (no content_end)
        event_types = [e.type for e in events]
        assert EventType.AGENT_SELECTED in event_types
        assert EventType.DONE in event_types
        assert EventType.CONTENT_END not in event_types

    @pytest.mark.asyncio
    async def test_stream_auto_completes_file_when_end_marker_missing(self, adapter):
        """Test stream end auto-completes file write when </file> is missing."""
        adapter.set_pending_file_write("file-1", "draft", "Chapter 1")
        adapter._save_file_content = AsyncMock()

        async def mock_events():
            yield LangGraphStreamEvent(
                type=StreamEventType.TEXT,
                data={"text": "<file>Hello world"},
            )
            yield LangGraphStreamEvent(
                type=StreamEventType.MESSAGE_END,
                data={},
            )

        events = []
        async for sse_event in adapter.process_langgraph_events(mock_events()):
            events.append(sse_event)

        event_types = [e.type for e in events]
        assert EventType.CONTENT_START in event_types
        assert EventType.FILE_CONTENT in event_types
        assert EventType.FILE_CONTENT_END in event_types
        assert EventType.CONTENT_END in event_types
        assert EventType.DONE in event_types
        adapter._save_file_content.assert_awaited_once_with("file-1", "Hello world")

    @pytest.mark.asyncio
    async def test_stream_save_failure_emits_error_without_done(self, adapter):
        """Persist failure should emit error and skip file_content_end/done."""
        adapter.set_pending_file_write("file-1", "draft", "Chapter 1")
        adapter._save_file_content = AsyncMock(return_value=False)

        async def mock_events():
            yield LangGraphStreamEvent(
                type=StreamEventType.TEXT,
                data={"text": "<file>Hello</file>"},
            )
            yield LangGraphStreamEvent(
                type=StreamEventType.MESSAGE_END,
                data={},
            )

        events = []
        async for sse_event in adapter.process_langgraph_events(mock_events()):
            events.append(sse_event)

        event_types = [e.type for e in events]
        assert EventType.ERROR in event_types
        assert EventType.FILE_CONTENT_END not in event_types
        assert EventType.DONE not in event_types

    @pytest.mark.asyncio
    async def test_stream_error_event_emits_content_end_without_done(self, adapter):
        """Workflow error events should terminate the stream without emitting done."""

        async def mock_events():
            yield LangGraphStreamEvent(
                type=StreamEventType.TEXT,
                data={"text": "Partial response"},
            )
            yield LangGraphStreamEvent(
                type=StreamEventType.ERROR,
                data={"error": "Workflow exploded"},
            )

        events = []
        async for sse_event in adapter.process_langgraph_events(mock_events()):
            events.append(sse_event)

        event_types = [e.type for e in events]
        assert EventType.ERROR in event_types
        assert EventType.CONTENT_END in event_types
        assert EventType.DONE not in event_types


class TestHandleTextContent:
    """Tests for _handle_text_content method."""

    @pytest.mark.asyncio
    async def test_text_without_file_markers(self, adapter_no_file_markers):
        """Test text content without file marker processing."""
        events = []
        async for sse_event in adapter_no_file_markers._handle_text_content("Hello"):
            events.append(sse_event)

        assert len(events) == 1
        assert events[0].type == EventType.CONTENT
        assert events[0].data["text"] == "Hello"

    @pytest.mark.asyncio
    async def test_text_with_file_markers(self, adapter):
        """Test text content with file markers."""
        # Set up pending file write
        adapter.set_pending_file_write("file-1", "draft", "Chapter 1")

        events = []
        # First chunk before marker
        async for sse_event in adapter._handle_text_content("Before "):
            events.append(sse_event)

        # Send file marker and content
        async for sse_event in adapter._handle_text_content("<file>Content"):
            events.append(sse_event)

        # Should have conversation content before marker
        assert any(e.type == EventType.CONTENT for e in events)

    @pytest.mark.asyncio
    async def test_file_markers_in_single_chunk(self, adapter):
        """Test processing <file>...</file> within a single text chunk."""
        adapter.set_pending_file_write("file-1", "draft", "Chapter 1")
        adapter._save_file_content = AsyncMock()

        events = []
        async for sse_event in adapter._handle_text_content("<file>Hello</file>after"):
            events.append(sse_event)

        assert len(events) == 3
        assert events[0].type == EventType.FILE_CONTENT
        assert events[0].data["chunk"] == "Hello"
        assert events[1].type == EventType.FILE_CONTENT_END
        assert events[2].type == EventType.CONTENT
        assert events[2].data["text"] == "after"
        adapter._save_file_content.assert_awaited_once_with("file-1", "Hello")

    @pytest.mark.asyncio
    async def test_text_accumulates(self, adapter):
        """Test text accumulation for skill detection."""
        # _handle_text_content is an async generator, need to consume it
        async for _ in adapter._handle_text_content("[使用技能: "):
            pass
        async for _ in adapter._handle_text_content("大纲规划师]"):
            pass

        assert adapter._accumulated_text == "[使用技能: 大纲规划师]"


class TestHandleCreateFileResult:
    """Tests for _handle_create_file_result method."""

    @pytest.mark.asyncio
    async def test_create_file_with_content(self, adapter):
        """Test create file result with content doesn't set pending."""
        result_data = {
            "id": "file-1",
            "file_type": "draft",
            "title": "Chapter 1",
            "content": "Some content",
        }

        await adapter._handle_create_file_result(result_data)

        # Should NOT set pending file write because content exists
        assert adapter._pending_file_write is None

    @pytest.mark.asyncio
    async def test_create_file_empty(self, adapter):
        """Test create file result with empty content sets pending."""
        result_data = {
            "id": "file-1",
            "file_type": "draft",
            "title": "Chapter 1",
            "content": "",
        }

        await adapter._handle_create_file_result(result_data)

        # Should set pending file write
        assert adapter._pending_file_write is not None
        assert adapter._pending_file_write.file_id == "file-1"


class TestHandleEditFileResult:
    """Tests for _handle_edit_file_result method."""

    @pytest.mark.asyncio
    async def test_edit_file_result(self, adapter):
        """Test edit file result emits proper events."""
        result = {
            "id": "file-1",
            "title": "Chapter 1",
            "details": [
                {
                    "op": "replace",
                    "old_preview": "old text here",
                    "new_preview": "new text here",
                    "success": True,
                }
            ],
            "new_length": 1000,
        }

        events = []
        async for sse_event in adapter._handle_edit_file_result(result):
            events.append(sse_event)

        # Should emit: edit_start, edit_applied, edit_end
        assert len(events) == 3
        assert events[0].type == EventType.FILE_EDIT_START
        assert events[0].data["file_id"] == "file-1"
        assert events[0].data["total_edits"] == 1

        assert events[1].type == EventType.FILE_EDIT_APPLIED
        assert events[1].data["op"] == "replace"
        assert events[1].data["success"] is True

        assert events[2].type == EventType.FILE_EDIT_END
        assert events[2].data["edits_applied"] == 1
        assert events[2].data["new_length"] == 1000

    @pytest.mark.asyncio
    async def test_edit_file_result_propagates_file_metadata(self, adapter):
        """file_edit_start/end should include file metadata when available."""
        result = {
            "id": "file-1",
            "title": "Chapter 1",
            "file_type": "outline",
            "details": [],
            "new_length": 42,
        }

        events = []
        async for sse_event in adapter._handle_edit_file_result(result):
            events.append(sse_event)

        assert len(events) == 2
        assert events[0].type == EventType.FILE_EDIT_START
        assert events[0].data["file_type"] == "outline"
        assert events[1].type == EventType.FILE_EDIT_END
        assert events[1].data["file_type"] == "outline"
        assert events[1].data["title"] == "Chapter 1"

    @pytest.mark.asyncio
    async def test_edit_file_multiple_edits(self, adapter):
        """Test edit file result with multiple edits."""
        result = {
            "id": "file-1",
            "title": "Chapter 1",
            "details": [
                {"op": "replace", "old_preview": "a", "new_preview": "b", "success": True},
                {"op": "insert_after", "old_preview": "c", "new_preview": "d", "success": True},
            ],
            "new_length": 2000,
        }

        events = []
        async for sse_event in adapter._handle_edit_file_result(result):
            events.append(sse_event)

        # Should emit: start, 2 applied, end
        assert len(events) == 4
        assert events[0].type == EventType.FILE_EDIT_START
        assert events[0].data["total_edits"] == 2

        assert events[1].type == EventType.FILE_EDIT_APPLIED
        assert events[1].data["edit_index"] == 0

        assert events[2].type == EventType.FILE_EDIT_APPLIED
        assert events[2].data["edit_index"] == 1

        assert events[3].type == EventType.FILE_EDIT_END

    @pytest.mark.asyncio
    async def test_edit_file_failed_edit(self, adapter):
        """Test edit file result with failed edit."""
        result = {
            "id": "file-1",
            "title": "Chapter 1",
            "details": [
                {
                    "op": "replace",
                    "old_preview": "old",
                    "new_preview": "new",
                    "success": False,
                    "error": "Pattern not found",
                }
            ],
            "new_length": 500,
        }

        events = []
        async for sse_event in adapter._handle_edit_file_result(result):
            events.append(sse_event)

        assert len(events) == 3
        assert events[1].type == EventType.FILE_EDIT_APPLIED
        assert events[1].data["success"] is False
        assert events[1].data["error"] == "Pattern not found"

    @pytest.mark.asyncio
    async def test_edit_file_no_file_id(self, adapter):
        """Test edit file result without file ID."""
        result = {
            "id": "",
            "title": "Chapter 1",
            "details": [],
        }

        events = []
        async for sse_event in adapter._handle_edit_file_result(result):
            events.append(sse_event)

        # Should emit nothing
        assert len(events) == 0


class TestSaveFileContent:
    """Tests for _save_file_content method."""

    @pytest.mark.asyncio
    async def test_save_file_content_success(self, adapter):
        """Test successful file content save."""
        with patch("database.get_session") as mock_get_session, \
             patch("agent.tools.file_ops.FileToolExecutor") as mock_executor_class:

            # Mock session
            mock_session = MagicMock()
            mock_gen = MagicMock()
            mock_gen.__next__ = MagicMock(return_value=mock_session)
            mock_gen.__iter__ = MagicMock(return_value=iter([mock_session, None]))
            mock_get_session.return_value = mock_gen

            # Mock executor
            mock_executor = MagicMock()
            mock_executor.update_file = MagicMock()
            mock_executor_class.return_value = mock_executor

            saved = await adapter._save_file_content("file-1", "Test content")

            # Should call update_file
            mock_executor.update_file.assert_called_once_with(
                id="file-1",
                content="Test content"
            )
            assert saved is True

    @pytest.mark.asyncio
    async def test_save_file_content_error(self, adapter):
        """Test file content save with error."""
        with patch("database.get_session") as mock_get_session:
            # Mock session that raises error
            mock_get_session.side_effect = Exception("DB connection failed")

            # Should not raise, just log error and return False
            saved = await adapter._save_file_content("file-1", "Test content")
            assert saved is False


class TestSkillUsageDetection:
    """Tests for skill usage detection."""

    @pytest.mark.asyncio
    async def test_detect_skill_usage(self, adapter):
        """Test skill usage detection from text."""
        adapter._accumulated_text = "Some text [使用技能: 大纲规划师] more text"

        with patch("database.get_session") as mock_get_session:
            mock_session = MagicMock()
            mock_gen = MagicMock()
            mock_gen.__next__ = MagicMock(return_value=mock_session)
            mock_gen.__iter__ = MagicMock(return_value=iter([mock_session, None]))
            mock_get_session.return_value = mock_gen

            with patch("agent.skills.loader.get_builtin_skills") as mock_skills, \
                 patch("services.skill_usage_service.record_skill_usage") as mock_record:

                # Mock skill with matching name
                mock_skill = MagicMock()
                mock_skill.id = "skill-1"
                mock_skill.name = "大纲规划师"
                mock_skills.return_value = [mock_skill]

                await adapter._detect_and_record_skill_usage()

                # Should record usage
                mock_record.assert_called_once()

    @pytest.mark.asyncio
    async def test_no_skill_usage_without_project(self, adapter):
        """Test skill usage not recorded without project ID."""
        adapter.config.project_id = ""
        adapter._accumulated_text = "[使用技能: 大纲规划师]"

        await adapter._detect_and_record_skill_usage()

        # Should do nothing without project_id

    @pytest.mark.asyncio
    async def test_detect_added_skill_usage(self, adapter):
        """Test usage recording works for added public skills."""
        adapter._accumulated_text = "[使用技能: 社区技能]"

        with patch("database.get_session") as mock_get_session:
            mock_session = MagicMock()
            mock_gen = MagicMock()
            mock_gen.__next__ = MagicMock(return_value=mock_session)
            mock_gen.__iter__ = MagicMock(return_value=iter([mock_session, None]))
            mock_get_session.return_value = mock_gen

            with patch("agent.skills.loader.get_builtin_skills", return_value=[]), \
                 patch("agent.skills.user_skill_service.get_user_skills", return_value=[]), \
                 patch("services.skill_usage_service.record_skill_usage") as mock_record:

                added_skill = MagicMock()
                added_skill.custom_name = "社区技能"
                public_skill = MagicMock()
                public_skill.id = "public-skill-1"
                public_skill.name = "社区技能"

                mock_exec_result = MagicMock()
                mock_exec_result.all.return_value = [(added_skill, public_skill)]
                mock_session.exec.return_value = mock_exec_result

                await adapter._detect_and_record_skill_usage()

                assert mock_record.call_count == 1
                kwargs = mock_record.call_args.kwargs
                assert kwargs["skill_id"] == "public-skill-1"
                assert kwargs["skill_source"] == "added"


class TestGetFileContent:
    """Tests for get_file_content and get_history_buffer methods."""

    def test_get_file_content(self, adapter):
        """Test getting file content."""
        adapter._stream_processor.content_buffer = "Test content"
        assert adapter.get_file_content() == "Test content"

    def test_get_history_buffer(self, adapter):
        """Test getting history buffer."""
        adapter._stream_processor.history_buffer = "History content"
        assert adapter.get_history_buffer() == "History content"


class TestCreateStreamAdapter:
    """Tests for create_stream_adapter factory function."""

    def test_create_stream_adapter_defaults(self):
        """Test creating adapter with defaults."""
        adapter = create_stream_adapter()
        assert adapter.config.project_id == ""
        assert adapter.config.process_file_markers is True

    def test_create_stream_adapter_custom(self):
        """Test creating adapter with custom config."""
        adapter = create_stream_adapter(
            project_id="proj-1",
            user_id="user-1",
            process_file_markers=False,
        )
        assert adapter.config.project_id == "proj-1"
        assert adapter.config.user_id == "user-1"
        assert adapter.config.process_file_markers is False


class TestSSEFormat:
    """Tests for SSE format compliance."""

    def test_sse_event_format(self):
        """Test SSE event format structure."""
        from agent.core.events import content_event

        event = content_event("Test content")
        sse_str = event.to_sse()

        # Should have proper SSE format
        assert "event: content\n" in sse_str
        assert "data:" in sse_str
        assert sse_str.endswith("\n\n")

    def test_sse_event_json_encoding(self):
        """Test SSE event JSON encoding."""
        from agent.core.events import tool_result_event

        event = tool_result_event(
            tool_name="create_file",
            status="success",
            data={"id": "f1", "title": "测试文件"},
        )
        sse_str = event.to_sse()

        # Should handle non-ASCII characters
        assert "测试文件" in sse_str

    def test_sse_event_datetime_encoding(self):
        """Test SSE event with datetime encoding."""
        from datetime import datetime

        from agent.core.events import EventType, StreamEvent

        event = StreamEvent(
            type=EventType.CONTENT,
            data={"timestamp": datetime(2024, 1, 1, 12, 0, 0)},
        )
        sse_str = event.to_sse()

        # Should encode datetime as ISO format
        assert "2024-01-01T12:00:00" in sse_str


class TestFileMarkerNormalization:
    """Tests for safe marker normalization behavior."""

    def test_does_not_normalize_non_file_tags(self):
        """Tags like <filex> or <filename> should remain unchanged."""
        assert normalize_file_markers("<filex>abc") == "<filex>abc"
        assert normalize_file_markers("<filename>abc") == "<filename>abc"

    def test_does_not_normalize_in_code_block(self):
        """Code block content should be preserved as-is."""
        content = "```\n<filex>\n```"
        assert normalize_file_markers(content) == content


class TestErrorHandling:
    """Tests for error handling scenarios."""

    @pytest.mark.asyncio
    async def test_handle_encoding_errors(self, adapter):
        """Test handling encoding errors in text content."""
        # Text with potential encoding issues
        event = LangGraphStreamEvent(
            type=StreamEventType.TEXT,
            data={"text": "Test with emoji 🎉 and unicode \u0000"},
        )

        # Should not raise
        events = []
        async for sse_event in adapter._process_langgraph_event(event):
            events.append(sse_event)

        assert len(events) >= 1

    @pytest.mark.asyncio
    async def test_handle_malformed_tool_result(self, adapter):
        """Test handling malformed tool result."""
        event = LangGraphStreamEvent(
            type=StreamEventType.TOOL_RESULT,
            data={
                "name": "test_tool",
                "result": {},  # Missing content
            },
        )

        # Should handle gracefully
        events = []
        async for sse_event in adapter._process_langgraph_event(event):
            events.append(sse_event)

        assert len(events) >= 1


class TestIntegration:
    """Integration tests combining multiple features."""

    @pytest.mark.asyncio
    async def test_full_conversation_flow(self, adapter):
        """Test complete conversation flow with multiple event types."""
        async def mock_events():
            yield LangGraphStreamEvent(
                type=StreamEventType.AGENT_SELECTED,
                data={"agent_type": "writer", "agent_name": "内容创作者"},
            )
            yield LangGraphStreamEvent(
                type=StreamEventType.THINKING,
                data={"thinking": "Planning the content..."},
            )
            yield LangGraphStreamEvent(
                type=StreamEventType.TEXT,
                data={"text": "Here is the content:"},
            )
            yield LangGraphStreamEvent(
                type=StreamEventType.TEXT,
                data={"text": " Chapter 1"},
            )
            yield LangGraphStreamEvent(
                type=StreamEventType.MESSAGE_END,
                data={},
            )

        events = []
        async for sse_event in adapter.process_langgraph_events(mock_events()):
            events.append(sse_event)

        # Should have all event types
        event_types = [e.type for e in events]
        assert EventType.AGENT_SELECTED in event_types
        assert EventType.THINKING_CONTENT in event_types
        assert EventType.CONTENT_START in event_types
        assert EventType.CONTENT in event_types
        assert EventType.CONTENT_END in event_types
        assert EventType.DONE in event_types

    @pytest.mark.asyncio
    async def test_tool_workflow(self, adapter):
        """Test complete tool calling workflow."""
        async def mock_events():
            # Agent selection
            yield LangGraphStreamEvent(
                type=StreamEventType.AGENT_SELECTED,
                data={"agent_type": "writer"},
            )
            # Tool call
            yield LangGraphStreamEvent(
                type=StreamEventType.TOOL_USE,
                data={
                    "status": "complete",
                    "name": "create_file",
                    "input": {"title": "Chapter 1", "file_type": "draft"},
                },
            )
            # Tool result
            result_json = json.dumps({
                "status": "success",
                "data": {"id": "f1", "title": "Chapter 1", "file_type": "draft"}
            })
            yield LangGraphStreamEvent(
                type=StreamEventType.TOOL_RESULT,
                data={
                    "name": "create_file",
                    "result": {"content": [{"text": result_json}]},
                },
            )
            # End
            yield LangGraphStreamEvent(
                type=StreamEventType.MESSAGE_END,
                data={},
            )

        events = []
        async for sse_event in adapter.process_langgraph_events(mock_events()):
            events.append(sse_event)

        # Should have tool call and result
        tool_call_events = [e for e in events if e.type == EventType.TOOL_CALL]
        tool_result_events = [e for e in events if e.type == EventType.TOOL_RESULT]

        assert len(tool_call_events) == 1
        assert len(tool_result_events) == 1
        assert EventType.DONE in [e.type for e in events]
