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

from models.file_model import FILE_TYPE_FOLDER
from utils.logger import get_logger, log_with_context

from .constants import coerce_bool
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
from .core.workflow_events import StreamEvent as WorkflowStreamEvent
from .core.workflow_events import StreamEventType

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

# [使用技能: X] 是纯控制信号（用来发 skill_matched 事件），不属于用户可见正文。
# 模型被要求写在回复最开头，但 delta 可能把它拆成 "[使用技" + "能: 悬念大师]"
# 两段，所以要在流头部缓冲一小段再判定。下面是标记的固定前缀与缓冲上限。
SKILL_MARKER_HEAD = "[使用技能:"
SKILL_MARKER_MAX_BUFFER = 64


def is_folder_file_type(raw: Any) -> bool:
    """判断一个 file_type 值是否是文件夹（strip + lower 归一化，容忍 None/非字符串）。

    与 mcp_tools 的 pending-empty-file 守卫必须用同一套判定：一处放行、一处
    拦截会让 folder 只在其中一条路径上被排除（本次 C2 缺口的成因）。
    """
    return isinstance(raw, str) and raw.strip().lower() == FILE_TYPE_FOLDER


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
    # 目标文件在本次流式写入之前已有的正文长度。create_file 的幂等复用分支
    # （剧本分集重复创建）会返回一个**已经写满正文**的文件，此时任何"没等到
    # </file> 的自动补全"都不能整体覆盖它——那会用几百字残稿抹掉整集。
    original_content_length: int = 0


class StreamAdapter:
    """
    Adapter that converts workflow events to SSE events.

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

        # Track latest model message metadata (for persistence accuracy)
        self._last_message_stop_reason: str | None = None
        self._last_message_usage: dict[str, Any] | None = None

        # Accumulate text content for skill usage detection
        self._accumulated_text: str = ""
        # 技能标记剥离：缓冲每个 agent 回复开头的少量文本，直到能判定它是不是
        # [使用技能: X]（该标记不能进入用户可见正文与落库的会话历史）
        self._skill_marker_buf: str = ""
        self._skill_marker_scan_done: bool = False
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
        self._skill_marker_buf = ""
        self._skill_marker_scan_done = False
        self._fatal_stream_error = False

    # usage 键别名 → 规范键。Chat Completions 用 prompt/completion，
    # Responses/SDK 用 input/output；两族键名若同时进同一个累加字典，
    # 就只有 total_tokens 会被相加，而下游 writing_stats_service 取
    # input_tokens 时读到的是另一族的值，别名那族被静默丢弃——
    # 结果 total_tokens ≠ input + output + cache，计价口径自相矛盾。
    _USAGE_KEY_ALIASES: dict[str, str] = {
        "prompt_tokens": "input_tokens",
        "completion_tokens": "output_tokens",
    }

    @classmethod
    def _normalize_usage_keys(cls, usage: dict[str, Any]) -> dict[str, Any]:
        """把别名键折叠到规范键上（同名冲突时数值相加）。"""
        normalized: dict[str, Any] = {}
        for key, value in usage.items():
            canonical = cls._USAGE_KEY_ALIASES.get(key, key)
            previous = normalized.get(canonical)
            if (
                isinstance(value, (int, float))
                and not isinstance(value, bool)
                and isinstance(previous, (int, float))
                and not isinstance(previous, bool)
            ):
                normalized[canonical] = previous + value
            else:
                normalized[canonical] = value
        return normalized

    @classmethod
    def _merge_usage(
        cls,
        accumulated: dict[str, Any] | None,
        incoming: Any,
    ) -> dict[str, Any] | None:
        """累加一次 MESSAGE_END / ROUTER_DECIDED 带来的 usage 统计。

        一轮请求里 router 与 planner/writer/quality_reviewer 各上报一次用量，
        每次只携带自己那部分 token 消耗。整轮的真实消耗是它们之和，
        直接赋值会让统计只剩最后一个 agent 的部分。

        规则：先把别名键归一（prompt_tokens→input_tokens、
        completion_tokens→output_tokens），再逐键相加；
        非数值字段以最新一次为准；incoming 不是字典时保留已累计的值。
        """
        if not isinstance(incoming, dict):
            return accumulated
        normalized_incoming = cls._normalize_usage_keys(incoming)
        if not isinstance(accumulated, dict):
            return normalized_incoming

        merged: dict[str, Any] = cls._normalize_usage_keys(accumulated)
        for key, value in normalized_incoming.items():
            previous = merged.get(key)
            if (
                isinstance(value, (int, float))
                and not isinstance(value, bool)
                and isinstance(previous, (int, float))
                and not isinstance(previous, bool)
            ):
                merged[key] = previous + value
            else:
                merged[key] = value
        return merged

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
        original_content_length: int = 0,
    ) -> None:
        """
        Set a pending file write operation.

        Called when create_file tool creates an empty file and
        expects content to follow with <file>...</file> markers.

        Args:
            file_id: ID of the created file
            file_type: Type of the file
            title: Title of the file
            original_content_length: 目标文件此前已有的正文长度（幂等复用分支
                会命中一个已写满的文件），>0 时禁止用截断补全的正文整体覆盖它

        Note:
            start_file_write() 会清空 StreamProcessor 的缓冲。调用方若可能在
            捕获进行中调用（正常路径就是「上一份文件还没写完又建了新档」），
            必须先用 _flush_active_capture() 把已缓冲的内容吐出去，否则那段
            叙述/正文会被静默丢弃。适配器自身的 create_file 处理已这样做。
        """
        if self.config.process_file_markers and self._stream_processor.is_active:
            log_with_context(
                logger,
                30,  # WARNING
                "Overwriting an active file capture without flushing it first",
                file_id=file_id,
                previous_state=str(self._stream_processor.state),
                previous_file_id=self._stream_processor.file_id,
            )

        self._pending_file_write = PendingFileWrite(
            file_id=file_id,
            file_type=file_type,
            title=title,
            original_content_length=max(int(original_content_length or 0), 0),
        )
        self._stream_processor.start_file_write(file_id)

        log_with_context(
            logger,
            20,  # INFO
            "Pending file write set",
            file_id=file_id,
            file_type=file_type,
            title=title,
            original_content_length=self._pending_file_write.original_content_length,
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
        try:
            async for event in events:
                if self._fatal_stream_error:
                    break
                async for sse_event in self._process_workflow_event(event):
                    yield sse_event
                    if self._fatal_stream_error:
                        break
                if self._fatal_stream_error:
                    break
        finally:
            # Deterministically close the upstream generator (e.g. when we break
            # early on a fatal stream error) so the runner's finally — which
            # cancels its background pump task — runs now instead of at GC time.
            aclose = getattr(events, "aclose", None)
            if aclose is not None:
                with contextlib.suppress(Exception):
                    await aclose()

        # 先放行技能标记缓冲里扣着的文本（它在时间上早于下面的收尾），
        # 再收尾 <file> 状态，顺序不能颠倒。
        if not self._fatal_stream_error:
            async for sse_event in self._release_skill_marker_buffer():
                yield sse_event

        # Flush pending <file> state when upstream stream ends unexpectedly.
        if (
            not self._fatal_stream_error
            and self.config.process_file_markers
            and self._stream_processor.is_active
        ):
            final_result = self._stream_processor.finalize_on_stream_end()
            async for sse_event in self._emit_stream_result(final_result):
                yield sse_event

        # An abandoned <file> write (create_file emitted an empty file but the model never
        # streamed its <file>...</file> content) leaves both the adapter tracker and the
        # ToolContext pending-empty-file guard set — finalize_on_stream_end flushes a
        # WAITING_START file as plain text without completing it, so _complete_file_write
        # (which normally clears the guard) never runs. Clear the stale state at stream end
        # so it cannot block create_file in any subsequent processing/request.
        if self._pending_file_write is not None:
            self._pending_file_write = None
            self._clear_pending_empty_file_guard()

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

                # If no input in data, try to get from accumulated JSON from streaming tool-call deltas)
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
            # 多 agent 协作时每个 agent 各发一次 MESSAGE_END：usage 必须**累加**，
            # 用后来的覆盖先前的会让整轮统计只剩最后一个 agent 的消耗（计费/
            # 配额都基于它）。非字典的 usage 不清空已累计的值。
            self._last_message_usage = self._merge_usage(
                self._last_message_usage, data.get("usage")
            )

            # 技能标记剥离缓冲按 agent 边界收口：本轮扣住的文本必须在这里放行，
            # 同时重置扫描状态，让下一个 agent 的开头也能被检查。
            async for sse_event in self._release_skill_marker_buffer():
                yield sse_event
            self._skill_marker_buf = ""
            self._skill_marker_scan_done = False

            # Agent boundary. MESSAGE_END marks the end of ONE agent's turn; the
            # same StreamAdapter/StreamProcessor is reused across the whole
            # multi-agent handoff loop. If a file write is still open here, this
            # agent created/opened a file but never closed it (no </file>), so
            # finalize it NOW — otherwise the next handed-off agent's narration
            # would keep accumulating into this agent's file and get flushed in
            # at end-of-request. finalize_on_stream_end discards control-marker
            # contaminated narration and salvages only genuine truncated prose.
            #
            # We deliberately leave the ToolContext pending-empty-file guard set:
            # it is the signal the workflow loop uses to detect an unwritten file
            # and re-run the writer to complete it (see writing_graph). It is
            # cleared on a successful <file> completion or at full stream end.
            if self.config.process_file_markers and self._stream_processor.is_active:
                boundary_result = self._stream_processor.finalize_on_stream_end()
                async for sse_event in self._emit_stream_result(boundary_result):
                    yield sse_event
                # NOTE: deliberately keep self._pending_file_write and the
                # ToolContext pending-empty-file guard set. The StreamProcessor is
                # now reset (no further cross-agent capture), but the guard remains
                # the signal the workflow loop reads to re-run the writer, and the
                # end-of-stream cleanup clears it so it cannot leak to the next
                # request.

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
        ):
            if event_type_value == StreamEventType.ROUTER_DECIDED.value:
                # 路由那次独立的（非流式）LLM 调用同样烧 token，但它不发
                # MESSAGE_END，用量只能随 ROUTER_DECIDED 捎带回来。这里汇入同一个
                # 累加器，整轮统计才是完整的。
                self._last_message_usage = self._merge_usage(
                    self._last_message_usage, data.get("routing_usage")
                )
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

            # edit_file 全部编辑都没生效时必须降级为 error，并补上人话错因。
            #
            # 注意**不能**加 `status == "success"` 前置条件：mcp_tools 的
            # _derive_edit_status 现在已经在 all_failed 时把工具层 status 直接
            # 置成 "error"，上面解析出的 status 就是 error，加了前置条件这段
            # 就成了死代码——于是 data 被置 None（status != success）、error 也
            # 还是 None（工具层没填 error 字段），前端拿到一张既没内容也没原因
            # 的空白失败卡。判据只看 all_failed。
            edit_all_failed = (
                tool_name == "edit_file"
                and isinstance(result_data, dict)
                and bool(result_data.get("all_failed"))
            )
            if edit_all_failed:
                status = "error"
                error = error or self._summarize_edit_failures(result_data)

            # 全失败的 edit_file 仍要把 data 发出去：failed_edits 是用户判断
            # 「哪几处没改成、为什么」的唯一依据，丢掉它卡片就是空白的。
            emit_data = result_data if (status == "success" or edit_all_failed) else None

            # Emit tool_result event
            yield tool_result_event(
                tool_name=tool_name,
                status=status,
                data=emit_data,
                error=error,
                tool_use_id=tool_use_id or None,
            )

            # Handle file creation
            if tool_name == "create_file" and status == "success":
                async for event in self._handle_create_file_result(result_data):
                    yield event
                file_data = result_data if isinstance(result_data, dict) else {}
                if file_data:
                    file_id = file_data.get("id", "")
                    file_type = file_data.get("file_type", "")
                    title = file_data.get("title", "")
                    if file_id:
                        yield file_created_event(file_id, file_type, title)

            # Handle file edit。即便状态被降级为 error（全部编辑失败），
            # 也要把逐条失败事件发出去，让用户看到「哪几处没改成」。
            if tool_name == "edit_file":
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

    async def _handle_create_file_result(
        self,
        result_data: Any,
    ) -> AsyncIterator[SSEEvent]:
        """Set up pending file write if a content-bearing file was created empty.

        Yields SSE events for the previous capture when a new pending write
        displaces one that is still buffering.
        """
        file_data = result_data if isinstance(result_data, dict) else {}
        if not file_data:
            return

        file_id = file_data.get("id", "")
        if not file_id:
            return

        raw_content = file_data.get("content")
        content = raw_content if isinstance(raw_content, str) else ""
        # 是否进入 <file> 捕获等待，以 create_file 的显式字段 reused_existing 为准，
        # 不再依赖"content 是否为空"这种隐式信号：剧本分集的幂等复用分支命中的是
        # 一个已经写满正文的文件，它同样需要进入捕获（模型接下来会流式写新正文），
        # 但必须把"原本非空"记下来，供截断补全时的覆盖保护使用。
        reused_existing = coerce_bool(file_data.get("reused_existing"))
        if content and not reused_existing:
            return

        original_content_length = self._resolve_original_content_length(
            file_data, content
        )

        file_type = file_data.get("file_type", "")
        # folder 是纯容器节点，永远不会收到 <file>…</file> 正文。给它开启流式
        # 捕获会把后续叙述全部扣在 WAITING_START 缓冲里（前端长时间无输出），
        # 并让流结束时的 at_eof 兜底把叙述当正文 update_file 写进文件夹行。
        # 与 mcp_tools 的 pending-empty-file 守卫保持同一套 folder 判定。
        if is_folder_file_type(file_type):
            log_with_context(
                logger,
                20,  # INFO
                "Skipping pending file write for folder node",
                file_id=file_id,
                file_type=file_type,
                title=file_data.get("title", ""),
            )
            return

        # 上一段捕获可能仍在缓冲（WAITING_START 的叙述 / WRITING 的正文）：
        # 先收尾并把内容吐出去，再切到新文件，避免 start_file_write() 清空
        # 缓冲造成静默丢失。
        async for sse_event in self._flush_active_capture():
            yield sse_event
        if self._fatal_stream_error:
            return

        self.set_pending_file_write(
            file_id,
            file_type,
            file_data.get("title", ""),
            original_content_length=original_content_length,
        )

    @staticmethod
    def _resolve_original_content_length(file_data: dict[str, Any], content: str) -> int:
        """取目标文件本次写入前的正文长度。

        优先用 create_file 返回的显式字段 original_content_length（复用分支给出），
        缺失或不合法时退回实际 content 的长度——两者都拿不到就是 0（新建空文件）。
        """
        raw = file_data.get("original_content_length")
        try:
            explicit = int(raw)
        except (TypeError, ValueError):
            explicit = 0
        return max(explicit, len(content), 0)

    async def _flush_active_capture(self) -> AsyncIterator[SSEEvent]:
        """收尾仍在进行中的流式捕获，并发出对应的 SSE 事件。

        复用 finalize_on_stream_end 的语义：WAITING_START 的缓冲原样回到对话，
        WRITING 的正文按截断补全（含 control-marker 污染守卫），DRAINING 的
        溢出尾部丢弃。
        """
        if not (self.config.process_file_markers and self._stream_processor.is_active):
            return

        result = self._stream_processor.finalize_on_stream_end()
        async for sse_event in self._emit_stream_result(result):
            yield sse_event

    async def _handle_text_content(self, text: str) -> AsyncIterator[SSEEvent]:
        """
        Handle text content, processing <file> markers if needed.

        Args:
            text: Text content chunk

        Yields:
            SSE events (content or file_content)
        """
        # Accumulate text for skill usage detection.
        # 注意：这里保留**原始**文本（含 [使用技能: X] 标记），技能匹配事件仍基于
        # 它检测；被剥离的只是下发给前端 / 落库的对话正文。
        if text:
            self._accumulated_text += text

        released = self._strip_skill_marker_prefix(text)
        if not released:
            return

        async for sse_event in self._emit_conversation_text(released):
            yield sse_event

    async def _emit_conversation_text(self, text: str) -> AsyncIterator[SSEEvent]:
        """把一段（已剥离控制标记的）文本按 <file> 协议路由成 SSE 事件。"""
        if not self.config.process_file_markers:
            # No file marker processing, just emit content
            if text:
                yield content_event(text)
            return

        # Process through StreamProcessor
        result: StreamResult = self._stream_processor.process_content(text)

        async for sse_event in self._emit_stream_result(result):
            yield sse_event

    def _strip_skill_marker_prefix(self, text: str) -> str:
        """剥离回复开头的 [使用技能: X] 控制标记，返回可以下发的文本。

        标记可能被 delta 拆开（"[使用技" + "能: 悬念大师]"），所以在判定出结果
        之前先把开头的文本扣在 _skill_marker_buf 里；一旦确定开头不可能是该标记
        （或缓冲超过上限、标记不完整），立刻把缓冲原样放行，绝不丢字。
        """
        if self._skill_marker_scan_done:
            return text

        self._skill_marker_buf += text
        buffered = self._skill_marker_buf
        candidate = buffered.lstrip()
        if not candidate:
            # 仅有空白：继续等（超过上限时按下面的兜底放行）
            if len(buffered) <= SKILL_MARKER_MAX_BUFFER:
                return ""
            return self._release_skill_marker_scan()

        if not (
            candidate.startswith(SKILL_MARKER_HEAD)
            or SKILL_MARKER_HEAD.startswith(candidate)
        ):
            # 开头不是标记，也不可能是标记的前缀 -> 立即放行
            return self._release_skill_marker_scan()

        match = SKILL_USAGE_PATTERN.match(candidate)
        if match:
            self._skill_marker_scan_done = True
            self._skill_marker_buf = ""
            skill_name = match.group(1).strip()
            log_with_context(
                logger,
                20,  # INFO
                "Stripped skill usage marker from conversation text",
                skill_name=skill_name,
                project_id=self.config.project_id,
            )
            # 标记独占一行，剥离后紧跟的换行/空白也一并去掉，避免气泡以空行开头
            return candidate[match.end():].lstrip()

        if len(buffered) > SKILL_MARKER_MAX_BUFFER:
            # 像标记开头但迟迟不闭合：不再扣着，原样放行
            return self._release_skill_marker_scan()

        return ""

    def _release_skill_marker_scan(self) -> str:
        """结束标记扫描并交还已缓冲的文本。"""
        buffered = self._skill_marker_buf
        self._skill_marker_buf = ""
        self._skill_marker_scan_done = True
        return buffered

    async def _release_skill_marker_buffer(self) -> AsyncIterator[SSEEvent]:
        """流/agent 结束时把仍扣在技能标记缓冲里的文本放行，防止内容丢失。"""
        if self._skill_marker_scan_done or not self._skill_marker_buf:
            return
        pending = self._release_skill_marker_scan()
        if not pending:
            return
        async for sse_event in self._emit_conversation_text(pending):
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
        # 覆盖保护：这次完成来自"没等到 </file> 的自动补全"，而目标文件本来
        # 就有正文（create_file 幂等复用命中的已完成分集）。补全出来的正文很
        # 可能只写了个开头，_save_file_content 又是整体替换，写下去等于用残稿
        # 抹掉整集。此处拒绝落库、保留原文，并把情况说给用户和模型听，交由
        # writing_graph 的补写纠偏走 edit_file 继续。
        if self._should_refuse_truncated_overwrite(result):
            pending = self._pending_file_write
            original_length = pending.original_content_length if pending else 0
            title = pending.title if pending else ""
            log_with_context(
                logger,
                30,  # WARNING
                "Refusing to overwrite an existing file body with auto-completed content",
                file_id=result.file_id,
                title=title,
                original_content_length=original_length,
                streamed_length=len(result.final_content),
            )
            warning_text = (
                f"\n\n[系统提醒] 《{title or result.file_id}》的流式写入没有收到结尾的 "
                f"</file>，本次只收到 {len(result.final_content)} 字，而该文件已有 "
                f"{original_length} 字正文。为避免覆盖已完成的内容，本次内容未保存，"
                "原文保持不变。请用 edit_file 继续补写，或重新完整输出并以 </file> 结尾。"
            )
            if not self._content_started:
                yield content_start_event()
                self._content_started = True
            yield content_event(warning_text)
            yield file_content_end_event(result.file_id)
            self._pending_file_write = None
            self._clear_pending_empty_file_guard(result.file_id)
            return

        # Save accumulated file content to database before emitting end event
        if result.final_content:
            saved = await self._save_file_content(result.file_id, result.final_content)
            if not saved:
                self._fatal_stream_error = True
                # Clear pending state to avoid blocking future create_file calls.
                self._pending_file_write = None
                self._clear_pending_empty_file_guard(result.file_id)
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
        self._clear_pending_empty_file_guard(result.file_id)

    def _should_refuse_truncated_overwrite(self, result: StreamResult) -> bool:
        """判断这次"截断自动补全"是否会覆盖掉目标文件原有的正文。

        三个条件同时成立才拒绝：
        1) 本次完成由流结束时的自动补全产生（没有真实的 </file>）；
        2) 该文件确实是本适配器正在等待写入的那一份；
        3) 该文件在本次写入前已有正文（幂等复用命中的已完成分集）。
        """
        if not result.auto_completed or not result.file_id:
            return False
        pending = self._pending_file_write
        if pending is None or pending.file_id != result.file_id:
            return False
        return pending.original_content_length > 0

    def _clear_pending_empty_file_guard(self, file_id: str = "") -> None:
        """清除 ToolContext 的 pending-empty-file 标记。

        传入 file_id 时只清除指向该文件的标记：一份仍在缓冲的文件被新的
        create_file 顶掉时，标记可能已经指向新建的空文件，若被上一份文件的
        收尾误清，「空文件必须被补写」的信号就丢了（writing_graph 再也不会
        安排补写）。file_id 为空表示流结束时的无条件清理，避免标记泄漏到
        下一个请求。

        实现上直接把 file_id 交给 ToolContext 做精确摘除：标记现在是集合，
        「读最近一个再无参清空」在同时存在多个待写空文件时会一次清光其余条目。
        """
        with contextlib.suppress(Exception):
            from agent.tools.mcp_tools import ToolContext

            ToolContext.clear_pending_empty_file(file_id or None)

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
        applied_edits = [e for e in edits if isinstance(e, dict)] if isinstance(edits, list) else []
        # 失败项与告警此前被整体丢弃：部分失败/全部失败的编辑在 UI 上呈现为
        # 「全部成功」，用户以为改完了就继续往下写。失败必须与成功同样上屏。
        failed_edits = self._normalize_edit_failures(result.get("failed_edits"))
        warnings = [str(w) for w in result.get("warnings") or [] if w]

        if not file_id:
            return

        # Emit edit start —— 总数必须包含失败项，否则进度条会少算
        yield file_edit_start_event(
            file_id,
            title,
            len(applied_edits) + len(failed_edits),
            file_type=file_type,
        )

        # Emit individual edit events
        for i, edit in enumerate(applied_edits):
            op = edit.get("op", "replace")
            old_preview = edit.get("old_preview", "")
            new_preview = edit.get("new_preview", "")
            # append/prepend 的 detail 没有 new_preview，只有 text_preview
            if not new_preview:
                new_preview = edit.get("text_preview", "")
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

        # 失败项紧随其后，edit_index 继续顺延（保证事件 key 唯一）
        for offset, failed in enumerate(failed_edits):
            yield file_edit_applied_event(
                file_id=file_id,
                edit_index=len(applied_edits) + offset,
                op=failed.get("op") or "replace",
                old_preview=None,
                new_preview=None,
                success=False,
                error=failed.get("error") or "编辑失败",
            )

        # Emit edit end - use new_length from result directly
        end_event = file_edit_end_event(
            file_id=file_id,
            edits_applied=len(applied_edits),
            new_length=result.get("new_length", 0),
            new_content=None,  # Content not included in executor result
            original_content=None,
            file_type=file_type,
            title=title,
            # 失败/部分成功/静默跳过的告警一并带上，前端与历史都能看到真实结果。
            # 这些已是 FileEditEndEventData 的一等字段，不再在工厂外补键。
            failed_count=len(failed_edits),
            partial_success=bool(
                result.get("partial_success") or (applied_edits and failed_edits)
            ),
            all_failed=bool(
                result.get("all_failed") or (failed_edits and not applied_edits)
            ),
            warnings=warnings,
        )
        yield end_event

    @staticmethod
    def _normalize_edit_failures(raw: Any) -> list[dict[str, Any]]:
        """把 edit_file 返回的 failed_edits 归一化成事件可用的字典列表。"""
        if not isinstance(raw, list):
            return []
        failures: list[dict[str, Any]] = []
        for item in raw:
            if isinstance(item, dict):
                failures.append(item)
            elif item:
                failures.append({"error": str(item)})
        return failures

    @classmethod
    def _summarize_edit_failures(cls, result: dict[str, Any]) -> str:
        """把全部失败的编辑汇总成一句给模型看的错误说明。"""
        failures = cls._normalize_edit_failures(result.get("failed_edits"))
        reasons = [str(item.get("error")) for item in failures if item.get("error")]
        if not reasons:
            reasons = [str(w) for w in result.get("warnings") or [] if w]
        detail = "；".join(reasons) if reasons else "未提供原因"
        return f"全部 {len(failures)} 处编辑均未生效：{detail}"

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

        # Resolve in the same precedence the injector/explicit resolver use:
        # a user's own skill (or an added public skill) that shares a builtin's
        # display name is the one that was actually injected, so it must win.
        # Builtin is the last-resort fallback.
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

        # Builtin is the last-resort fallback (a user/added skill of the same
        # display name would have matched above and correctly won).
        if not skill_id:
            for skill in get_builtin_skills_fn():
                if skill.name == skill_name:
                    skill_id = skill.id
                    skill_source = "builtin"
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
    "is_folder_file_type",
]
