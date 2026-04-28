"""
Workflow stream adapter.

Converts workflow StreamEvent objects to SSE format for frontend compatibility.
Reuses StreamProcessor for handling <file> markers in text content.
"""

import asyncio
import contextlib
import os
import re
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any

from utils.logger import get_logger, log_with_context

from .core.events import (
    StreamEvent as SSEEvent,
)
from .core.events import (
    agent_selected_event,
    content_end_event,
    content_event,
    content_start_event,
    done_event,
    error_event,
    file_content_end_event,
    file_content_event,
    file_created_event,
    file_edit_applied_event,
    file_edit_end_event,
    file_edit_start_event,
    iteration_exhausted_event,
    skill_matched_event,
    thinking_content_event,
    tool_call_event,
    tool_result_event,
)
from .core.stream_processor import StreamProcessor, StreamResult
from .llm.anthropic_client import StreamEvent as WorkflowStreamEvent
from .llm.anthropic_client import StreamEventType

logger = get_logger(__name__)


def _get_positive_float_env(name: str, default: float) -> float:
    """Read a positive float env var with safe fallback."""
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        value = float(raw)
    except ValueError:
        return default
    return value if value > 0 else default


STREAM_FILE_SAVE_TIMEOUT_S = _get_positive_float_env(
    "AGENT_STREAM_FILE_SAVE_TIMEOUT_S",
    15.0,
)
STREAM_SKILL_USAGE_RECORD_TIMEOUT_S = _get_positive_float_env(
    "AGENT_STREAM_SKILL_USAGE_RECORD_TIMEOUT_S",
    5.0,
)

# Regex pattern for skill usage marker: [使用技能: xxx]
SKILL_USAGE_PATTERN = re.compile(r"\[使用技能:\s*(.+?)\]")


@dataclass
class StreamAdapterConfig:
    """Configuration for StreamAdapter."""

    project_id: str = ""
    user_id: str | None = None
    # Whether to process <file> markers in text content
    process_file_markers: bool = True


@dataclass
class PendingFileWrite:
    """Tracks a pending file write operation."""

    file_id: str
    file_type: str
    title: str


class StreamAdapter:
    """
    Adapter that converts Claude SDK events to SSE events.

    Features:
    - Converts TextBlock to content events
    - Converts ThinkingBlock to thinking_content events
    - Converts ToolUseBlock to tool_call events
    - Converts ToolResultBlock to tool_result events
    - Reuses StreamProcessor for <file> marker handling
    - Generates file_created, file_content, file_content_end events
    - Generates file_edit_start, file_edit_applied, file_edit_end events
    """

    def __init__(self, config: StreamAdapterConfig | None = None) -> None:
        """
        Initialize the adapter.

        Args:
            config: Adapter configuration
        """
        self.config = config or StreamAdapterConfig()

        # Stream processor for file content
        self._stream_processor = StreamProcessor(
            project_id=self.config.project_id,
            user_id=self.config.user_id,
        )

        # Pending file write (set when create_file tool returns empty file)
        self._pending_file_write: PendingFileWrite | None = None

        # Track content streaming state
        self._content_started = False

        # Track current tool call for result matching
        self._current_tool_calls: dict[str, dict[str, Any]] = {}

        # Track latest model message metadata (for persistence/compaction accuracy)
        self._last_message_stop_reason: str | None = None
        self._last_message_usage: dict[str, int] | None = None

        # Accumulate text content for skill usage detection
        self._accumulated_text: str = ""
        # Fatal stream error flag (e.g. file content persistence failure)
        self._fatal_stream_error = False

        log_with_context(
            logger,
            20,  # INFO
            "StreamAdapter created",
            project_id=self.config.project_id,
            user_id=self.config.user_id,
        )

    def reset(self) -> None:
        """Reset adapter state for new conversation turn."""
        self._stream_processor.reset()
        self._pending_file_write = None
        self._content_started = False
        self._current_tool_calls.clear()
        self._last_message_stop_reason = None
        self._last_message_usage = None
        self._accumulated_text = ""
        self._fatal_stream_error = False

    def get_last_message_metadata(self) -> dict[str, Any]:
        """Get latest model message metadata captured from MESSAGE_END events."""
        return {
            "stop_reason": self._last_message_stop_reason,
            "usage": self._last_message_usage,
        }

    def set_pending_file_write(
        self,
        file_id: str,
        file_type: str,
        title: str,
    ) -> None:
        """
        Set a pending file write operation.

        Called when create_file tool creates an empty file and
        expects content to follow with <file>...</file> markers.

        Args:
            file_id: ID of the created file
            file_type: Type of the file
            title: Title of the file
        """
        self._pending_file_write = PendingFileWrite(
            file_id=file_id,
            file_type=file_type,
            title=title,
        )
        self._stream_processor.start_file_write(file_id)

        log_with_context(
            logger,
            20,  # INFO
            "Pending file write set",
            file_id=file_id,
            file_type=file_type,
            title=title,
        )

    async def process_workflow_events(
        self,
        events: AsyncIterator[WorkflowStreamEvent],
    ) -> AsyncIterator[SSEEvent]:
        """
        Process workflow StreamEvent objects and yield SSE events.

        Args:
            events: AsyncIterator of workflow StreamEvent

        Yields:
            SSE StreamEvent objects for frontend consumption
        """
        async for event in events:
            if self._fatal_stream_error:
                break
            async for sse_event in self._process_workflow_event(event):
                yield sse_event
                if self._fatal_stream_error:
                    break
            if self._fatal_stream_error:
                break

        # Flush pending <file> state when upstream stream ends unexpectedly.
        if (
            not self._fatal_stream_error
            and self.config.process_file_markers
            and self._stream_processor.is_active
        ):
            final_result = self._stream_processor.finalize_on_stream_end()
            async for sse_event in self._emit_stream_result(final_result):
                yield sse_event

        # Ensure content_end is sent if content was started
        if self._content_started:
            yield content_end_event()
            self._content_started = False

        # Fatal stream errors should not be followed by done.
        if self._fatal_stream_error:
            return

        # Detect and record skill usage from accumulated text
        skill_usage = await self._detect_and_record_skill_usage()
        if skill_usage:
            yield skill_matched_event(
                skill_id=skill_usage["skill_id"],
                skill_name=skill_usage["skill_name"],
                matched_trigger=skill_usage["matched_trigger"],
            )

        # Emit done event
        yield done_event()

    async def process_langgraph_events(
        self,
        events: AsyncIterator[WorkflowStreamEvent],
    ) -> AsyncIterator[SSEEvent]:
        """Backward-compatible alias for process_workflow_events."""
        async for sse_event in self.process_workflow_events(events):
            yield sse_event

    async def _process_workflow_event(
        self,
        event: WorkflowStreamEvent,
    ) -> AsyncIterator[SSEEvent]:
        """
        Process a single workflow StreamEvent.

        Args:
            event: Workflow StreamEvent

        Yields:
            SSE StreamEvent objects
        """
        event_type = event.type
        data = event.data
        event_type_value = event_type.value if hasattr(event_type, "value") else str(event_type)

        if event_type == StreamEventType.TEXT:
            # Text content
            if not self._content_started:
                yield content_start_event()
                self._content_started = True
            async for sse_event in self._handle_text_content(data.get("text", "")):
                yield sse_event

        elif event_type == StreamEventType.THINKING:
            # Thinking content
            thinking_text = data.get("thinking", "")
            if thinking_text:
                yield thinking_content_event(thinking_text, is_complete=False)

        elif event_type == StreamEventType.TOOL_USE:
            # Tool use event
            status = data.get("status")
            if status == "start":
                tool_id = data.get("id", "")
                tool_name = data.get("name", "")
                if tool_id:
                    self._current_tool_calls[tool_id] = {
                        "name": tool_name,
                        "input_json": "",
                    }
            elif status == "delta":
                # Accumulate partial JSON for tool input
                partial_json = data.get("partial_json", "")
                # Find the tool call to update (use the most recent one)
                for tool_id in reversed(list(self._current_tool_calls.keys())):
                    self._current_tool_calls[tool_id]["input_json"] += partial_json
                    break
            elif status == "stop":
                # Emit tool_call event when complete
                tool_id = data.get("id", "")
                tool_name = data.get("name", "")

                # First try to get input directly from data (workflow can send complete input)
                tool_input = data.get("input", {})

                # If no input in data, try to get from accumulated JSON (Anthropic streaming)
                if not tool_input and tool_id and tool_id in self._current_tool_calls:
                    input_json = self._current_tool_calls[tool_id].get("input_json", "")
                    if input_json:
                        import json
                        with contextlib.suppress(json.JSONDecodeError):
                            tool_input = json.loads(input_json)
                    # Clean up
                    del self._current_tool_calls[tool_id]

                yield tool_call_event(tool_name, tool_input, tool_use_id=tool_id or None)
            elif status == "complete":
                # Complete status (has full input already)
                tool_id = data.get("id", "")
                tool_name = data.get("name", "")
                tool_input = data.get("input", {})
                yield tool_call_event(tool_name, tool_input, tool_use_id=tool_id or None)

        elif event_type == StreamEventType.TOOL_RESULT:
            # Tool result from workflow nodes
            async for sse_event in self._handle_workflow_tool_result(data):
                yield sse_event

        elif event_type == StreamEventType.MESSAGE_END:
            # Message completed - capture metadata for downstream persistence
            self._last_message_stop_reason = data.get("stop_reason")
            usage = data.get("usage")
            self._last_message_usage = usage if isinstance(usage, dict) else None

        elif event_type == StreamEventType.ERROR:
            # Error event
            error_msg = data.get("error", "Unknown error")
            self._fatal_stream_error = True
            yield error_event(message=error_msg)

        elif event_type == StreamEventType.AGENT_SELECTED:
            # Agent selected by router
            agent_type = data.get("agent_type", "")
            agent_name = data.get("agent_name", "")
            iteration = data.get("iteration")
            max_iterations = data.get("max_iterations")
            remaining = data.get("remaining")
            yield agent_selected_event(
                agent_type, agent_name, iteration, max_iterations, remaining
            )

        elif event_type == StreamEventType.ITERATION_EXHAUSTED:
            # Iteration limit reached
            yield iteration_exhausted_event(
                layer=data.get("layer", ""),
                iterations_used=data.get("iterations_used", 0),
                max_iterations=data.get("max_iterations", 0),
                reason=data.get("reason", ""),
                last_agent=data.get("last_agent"),
            )

        elif event_type_value in (
            StreamEventType.HANDOFF.value,
            StreamEventType.ROUTER_THINKING.value,
            StreamEventType.ROUTER_DECIDED.value,
            StreamEventType.WORKFLOW_STOPPED.value,
            StreamEventType.WORKFLOW_COMPLETE.value,
            StreamEventType.STEERING_RECEIVED.value,
            "session_started",
            "parallel_start",
            "parallel_task_start",
            "parallel_task_end",
            "parallel_end",
            "compaction_start",
            "compaction_done",
        ):
            # Pass through these events directly
            yield SSEEvent(type=event_type_value, data=data)

    async def _process_langgraph_event(
        self,
        event: WorkflowStreamEvent,
    ) -> AsyncIterator[SSEEvent]:
        """Backward-compatible alias for _process_workflow_event."""
        async for sse_event in self._process_workflow_event(event):
            yield sse_event

    async def _handle_workflow_tool_result(
        self,
        data: dict[str, Any],
    ) -> AsyncIterator[SSEEvent]:
        """
        Handle tool result from workflow nodes.

        Args:
            data: Tool result data

        Yields:
            SSE events for tool result and file operations
        """
        tool_name = ""
        tool_use_id = ""
        try:
            tool_name = data.get("name", "") if isinstance(data, dict) else ""
            tool_use_id = data.get("tool_use_id", "") if isinstance(data, dict) else ""
            raw_result = data.get("result", {}) if isinstance(data, dict) else {}

            parsed_result = self._parse_tool_result_payload(raw_result)

            if isinstance(parsed_result, dict) and "status" in parsed_result:
                raw_status = str(parsed_result.get("status") or "").strip().lower()
                status = "error" if raw_status in {"error", "failed", "failure"} else "success"
            elif isinstance(parsed_result, dict) and "error" in parsed_result:
                # Backward compatibility: some tool failures only return {"error": "..."}
                status = "error"
            else:
                status = "success"

            error: str | None = None
            if isinstance(parsed_result, dict) and parsed_result.get("error") is not None:
                error = str(parsed_result.get("error"))

            result_data = parsed_result.get("data", parsed_result) if isinstance(parsed_result, dict) else parsed_result

            # Emit tool_result event
            yield tool_result_event(
                tool_name=tool_name,
                status=status,
                data=result_data if status == "success" else None,
                error=error,
                tool_use_id=tool_use_id or None,
            )

            # Handle file creation
            if tool_name == "create_file" and status == "success":
                await self._handle_create_file_result(result_data)
                file_data = result_data if isinstance(result_data, dict) else {}
                if file_data:
                    file_id = file_data.get("id", "")
                    file_type = file_data.get("file_type", "")
                    title = file_data.get("title", "")
                    if file_id:
                        yield file_created_event(file_id, file_type, title)

            # Handle file edit
            if tool_name == "edit_file" and status == "success":
                async for event in self._handle_edit_file_result(result_data):
                    yield event
        except Exception as exc:
            log_with_context(
                logger,
                30,  # WARNING
                "Failed to parse workflow tool result",
                tool_name=tool_name,
                error=str(exc),
                error_type=type(exc).__name__,
            )
            yield tool_result_event(
                tool_name=tool_name,
                status="error",
                data=None,
                error=f"Malformed tool_result payload: {type(exc).__name__}",
                tool_use_id=tool_use_id or None,
            )

    async def _handle_langgraph_tool_result(
        self,
        data: dict[str, Any],
    ) -> AsyncIterator[SSEEvent]:
        """Backward-compatible alias for _handle_workflow_tool_result."""
        async for sse_event in self._handle_workflow_tool_result(data):
            yield sse_event

    def _parse_tool_result_payload(self, raw_result: Any) -> Any:
        """Parse MCP tool_result payload with defensive fallbacks."""
        import json

        # MCP canonical format: {"content":[{"type":"text","text":"...json..."}]}
        result_text = self._extract_tool_result_text(raw_result)
        if result_text:
            try:
                return json.loads(result_text)
            except json.JSONDecodeError:
                return {"raw": result_text}

        # Tolerate non-canonical payloads from workflow adapters/mocks.
        if isinstance(raw_result, dict):
            if "status" in raw_result or "error" in raw_result or "data" in raw_result:
                return raw_result
            return {}
        if raw_result is None:
            return {}

        return {"raw": str(raw_result)}

    def _extract_tool_result_text(self, raw_result: Any) -> str:
        """Extract text payload from MCP result format safely."""
        if not isinstance(raw_result, dict):
            return ""

        content_list = raw_result.get("content")
        if not isinstance(content_list, list):
            return ""

        for item in content_list:
            if isinstance(item, dict):
                text = item.get("text")
                if isinstance(text, str):
                    return text
                if text is not None:
                    return str(text)

        return ""

    async def _handle_create_file_result(self, result_data: Any) -> None:
        """Set up pending file write if file was created empty."""
        file_data = result_data if isinstance(result_data, dict) else {}
        if file_data:
            file_id = file_data.get("id", "")
            file_type = file_data.get("file_type", "")
            title = file_data.get("title", "")
            content = file_data.get("content", "")
            if not content and file_id:
                self.set_pending_file_write(file_id, file_type, title)

    async def _handle_text_content(self, text: str) -> AsyncIterator[SSEEvent]:
        """
        Handle text content, processing <file> markers if needed.

        Args:
            text: Text content chunk

        Yields:
            SSE events (content or file_content)
        """
        # Accumulate text for skill usage detection
        if text:
            self._accumulated_text += text

        if not self.config.process_file_markers:
            # No file marker processing, just emit content
            if text:
                yield content_event(text)
            return

        # Process through StreamProcessor
        result: StreamResult = self._stream_processor.process_content(text)

        async for sse_event in self._emit_stream_result(result):
            yield sse_event

    async def _emit_stream_result(self, result: StreamResult) -> AsyncIterator[SSEEvent]:
        """Emit SSE events mapped from StreamProcessor result."""
        # Emit conversation content
        if result.conversation_content:
            yield content_event(result.conversation_content)

        # Emit file content chunk
        if result.file_content and result.file_id:
            yield file_content_event(result.file_id, result.file_content)

        # Handle file completion
        if result.file_complete and result.file_id:
            async for sse_event in self._complete_file_write(result):
                yield sse_event

        # Emit any post-file conversation content after file completion.
        if result.conversation_content_after_file:
            yield content_event(result.conversation_content_after_file)

    async def _complete_file_write(self, result: StreamResult) -> AsyncIterator[SSEEvent]:
        """Persist finalized file content and emit file completion event."""
        # Save accumulated file content to database before emitting end event
        if result.final_content:
            saved = await self._save_file_content(result.file_id, result.final_content)
            if not saved:
                self._fatal_stream_error = True
                # Clear pending state to avoid blocking future create_file calls.
                self._pending_file_write = None
                with contextlib.suppress(Exception):
                    from agent.tools.mcp_tools import ToolContext
                    ToolContext.clear_pending_empty_file()
                yield error_event(
                    message="Failed to persist streamed file content",
                    code="FILE_SAVE_FAILED",
                    retryable=True,
                )
                return

        yield file_content_end_event(result.file_id)

        # Clear pending file write
        self._pending_file_write = None

        # Also clear ToolContext pending state, allowing next create_file.
        with contextlib.suppress(Exception):
            from agent.tools.mcp_tools import ToolContext
            ToolContext.clear_pending_empty_file()

    async def _save_file_content(self, file_id: str, content: str) -> bool:
        """
        Save accumulated file content to database.

        Args:
            file_id: ID of the file to update
            content: Content to save
        """
        log_with_context(
            logger,
            20,  # INFO
            "Saving file content to database",
            file_id=file_id,
            content_length=len(content),
            user_id=self.config.user_id,
        )

        try:
            return await asyncio.wait_for(
                asyncio.to_thread(
                    self._save_file_content_sync,
                    file_id,
                    content,
                ),
                timeout=STREAM_FILE_SAVE_TIMEOUT_S,
            )
        except TimeoutError:
            log_with_context(
                logger,
                40,  # ERROR
                "Timed out while saving streamed file content",
                file_id=file_id,
                timeout_s=STREAM_FILE_SAVE_TIMEOUT_S,
            )
            return False
        except Exception as e:
            log_with_context(
                logger,
                40,  # ERROR
                "Failed to save file content",
                file_id=file_id,
                error=str(e),
                error_type=type(e).__name__,
            )
            return False

    def _save_file_content_sync(self, file_id: str, content: str) -> bool:
        """Persist streamed file content with a fresh sync DB session."""
        from agent.tools.file_ops import FileToolExecutor
        from database import create_session, get_session, is_postgres

        if not is_postgres:
            session_gen = get_session()
            session = next(session_gen)
            try:
                executor = FileToolExecutor(
                    session=session,
                    user_id=self.config.user_id,
                )
                executor.update_file(id=file_id, content=content)
            finally:
                with contextlib.suppress(StopIteration):
                    next(session_gen)
        else:
            with create_session() as session:
                executor = FileToolExecutor(
                    session=session,
                    user_id=self.config.user_id,
                )
                executor.update_file(id=file_id, content=content)

        log_with_context(
            logger,
            20,  # INFO
            "File content saved successfully",
            file_id=file_id,
        )
        return True

    async def _handle_edit_file_result(
        self,
        result: Any,
    ) -> AsyncIterator[SSEEvent]:
        """
        Handle edit_file tool result, emitting edit events.

        Args:
            result: Edit file result data

        Yields:
            SSE events for file edit operations
        """
        if not isinstance(result, dict):
            return

        # FileToolExecutor returns id/title at root level, not nested in "file"
        file_id = result.get("id", "")
        title = result.get("title", "")
        file_type = result.get("file_type")
        # Edit details are in "details" field, not "edits_applied"
        edits = result.get("details", [])
        total_edits = len(edits) if isinstance(edits, list) else 0

        if not file_id:
            return

        # Emit edit start
        yield file_edit_start_event(file_id, title, total_edits, file_type=file_type)

        # Emit individual edit events
        if isinstance(edits, list):
            for i, edit in enumerate(edits):
                op = edit.get("op", "replace")
                old_preview = edit.get("old_preview", "")
                new_preview = edit.get("new_preview", "")
                success = edit.get("success", True)
                error = edit.get("error")

                yield file_edit_applied_event(
                    file_id=file_id,
                    edit_index=i,
                    op=op,
                    old_preview=old_preview[:50] if old_preview else None,
                    new_preview=new_preview[:50] if new_preview else None,
                    success=success,
                    error=error,
                )

        # Emit edit end - use new_length from result directly
        yield file_edit_end_event(
            file_id=file_id,
            edits_applied=total_edits,
            new_length=result.get("new_length", 0),
            new_content=None,  # Content not included in executor result
            original_content=None,
            file_type=file_type,
            title=title,
        )

    def get_file_content(self) -> str:
        """Get accumulated file content from StreamProcessor."""
        return self._stream_processor.get_final_content()

    def get_history_buffer(self) -> str:
        """Get content buffer for LLM history."""
        return self._stream_processor.get_history_buffer()

    async def _detect_and_record_skill_usage(self) -> dict[str, str] | None:
        """
        Detect skill usage markers in accumulated text and record to database.

        Parses [使用技能: xxx] markers and records usage statistics.
        """
        if not self._accumulated_text:
            return None

        # Only check the first 500 characters for skill marker
        text_to_check = self._accumulated_text[:500]
        match = SKILL_USAGE_PATTERN.search(text_to_check)

        if not match:
            return None

        skill_name = match.group(1).strip()
        if not skill_name:
            return None

        log_with_context(
            logger,
            20,  # INFO
            "Detected skill usage marker",
            skill_name=skill_name,
            project_id=self.config.project_id,
        )

        # Record skill usage
        return await self._record_skill_usage(skill_name)

    async def _record_skill_usage(self, skill_name: str) -> dict[str, str] | None:
        """
        Record skill usage to database.

        Looks up skill by name from builtin, user, and added skills,
        then records usage to skill_usage table.

        Args:
            skill_name: Name of the skill that was used
        """
        if not self.config.project_id:
            log_with_context(
                logger,
                30,  # WARNING
                "Cannot record skill usage: no project_id",
                skill_name=skill_name,
            )
            return None

        try:
            return await asyncio.wait_for(
                asyncio.to_thread(self._record_skill_usage_sync, skill_name),
                timeout=STREAM_SKILL_USAGE_RECORD_TIMEOUT_S,
            )
        except TimeoutError:
            log_with_context(
                logger,
                40,  # ERROR
                "Timed out while recording skill usage",
                skill_name=skill_name,
                timeout_s=STREAM_SKILL_USAGE_RECORD_TIMEOUT_S,
            )
            return None
        except Exception as e:
            log_with_context(
                logger,
                40,  # ERROR
                "Failed to record skill usage",
                skill_name=skill_name,
                error=str(e),
                error_type=type(e).__name__,
            )
            return None

    def _record_skill_usage_sync(self, skill_name: str) -> dict[str, str] | None:
        """Record skill usage using a fresh sync DB session."""
        from sqlmodel import select

        from database import create_session, get_session, is_postgres
        from models import PublicSkill, UserAddedSkill
        from services.skill_usage_service import record_skill_usage

        from .skills.loader import get_builtin_skills
        from .skills.user_skill_service import get_user_skills

        if not is_postgres:
            session_gen = get_session()
            session = next(session_gen)
            try:
                return self._record_skill_usage_with_session(
                    session,
                    skill_name,
                    select,
                    PublicSkill,
                    UserAddedSkill,
                    record_skill_usage,
                    get_builtin_skills,
                    get_user_skills,
                )
            finally:
                with contextlib.suppress(StopIteration):
                    next(session_gen)

        with create_session() as session:
            return self._record_skill_usage_with_session(
                session,
                skill_name,
                select,
                PublicSkill,
                UserAddedSkill,
                record_skill_usage,
                get_builtin_skills,
                get_user_skills,
            )

    def _record_skill_usage_with_session(
        self,
        session,
        skill_name: str,
        select_fn,
        public_skill_model,
        user_added_skill_model,
        record_skill_usage_fn,
        get_builtin_skills_fn,
        get_user_skills_fn,
    ) -> dict[str, str] | None:
        """Resolve a skill and persist usage with the provided session."""
        skill_id = None
        skill_source = "builtin"
        matched_trigger = "AI选择"

        for skill in get_builtin_skills_fn():
            if skill.name == skill_name:
                skill_id = skill.id
                skill_source = "builtin"
                break

        if not skill_id and self.config.user_id:
            user_skills = get_user_skills_fn(session, self.config.user_id)
            for skill in user_skills:
                if skill.name == skill_name:
                    skill_id = skill.id
                    skill_source = "user"
                    break

        if not skill_id and self.config.user_id:
            added_stmt = (
                select_fn(user_added_skill_model, public_skill_model)
                .join(public_skill_model, user_added_skill_model.public_skill_id == public_skill_model.id)
                .where(
                    user_added_skill_model.user_id == self.config.user_id,
                    user_added_skill_model.is_active,
                    public_skill_model.status == "approved",
                )
            )
            for added, public in session.exec(added_stmt).all():
                display_name = added.custom_name or public.name
                if display_name == skill_name:
                    skill_id = public.id
                    skill_source = "added"
                    break

        if not skill_id:
            log_with_context(
                logger,
                30,  # WARNING
                "Skill not found for usage recording",
                skill_name=skill_name,
            )
            return None

        record_skill_usage_fn(
            session=session,
            project_id=self.config.project_id,
            skill_id=skill_id,
            skill_name=skill_name,
            skill_source=skill_source,
            matched_trigger=matched_trigger,
            confidence=1.0,
            user_id=self.config.user_id,
        )

        log_with_context(
            logger,
            20,  # INFO
            "Skill usage recorded",
            skill_name=skill_name,
            skill_id=skill_id,
            skill_source=skill_source,
        )
        return {
            "skill_id": skill_id,
            "skill_name": skill_name,
            "matched_trigger": matched_trigger,
        }


def create_stream_adapter(
    project_id: str = "",
    user_id: str | None = None,
    process_file_markers: bool = True,
) -> StreamAdapter:
    """
    Factory function to create a StreamAdapter.

    Args:
        project_id: Project ID for logging
        user_id: User ID for logging
        process_file_markers: Whether to process <file> markers

    Returns:
        Configured StreamAdapter instance
    """
    config = StreamAdapterConfig(
        project_id=project_id,
        user_id=user_id,
        process_file_markers=process_file_markers,
    )
    return StreamAdapter(config)


__all__ = [
    "StreamAdapter",
    "StreamAdapterConfig",
    "PendingFileWrite",
    "create_stream_adapter",
]
