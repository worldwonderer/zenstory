"""
Stream processor for file content streaming.

Handles the state machine for streaming file content from LLM output
to the database. Manages <file> and </file> marker parsing and
buffer size limits.

State transitions:
    IDLE -> WAITING_START (when pending_file_write is set)
    WAITING_START -> WRITING (when <file> marker is found)
    WRITING -> IDLE (when </file> marker is found, buffer limit exceeded, or stream ends)
"""

import re
from dataclasses import dataclass
from enum import StrEnum

from utils.logger import get_logger, log_with_context

logger = get_logger(__name__)

# Streaming markers
FILE_START_MARKER = "<file>"
FILE_END_MARKER = "</file>"

# Upper bound on the length of a (whitespace/case) marker variant, e.g.
# "<  /  file  >". We retain this many trailing chars as "possibly part of an
# end marker" so a variant split across stream chunks is never flushed as file
# content before it can be reassembled and matched.
MAX_MARKER_LEN = 32

# 容错正则表达式 - 匹配各种 <file> 变体（避免误匹配 <filex>/<filename>）
FILE_START_PATTERN = re.compile(
    r'<\s*[Ff][Ii][Ll][Ee]\b(?:\s+[^>]*)?>',
    re.IGNORECASE
)
FILE_END_PATTERN = re.compile(
    r'<\s*/\s*[Ff][Ii][Ll][Ee]\b\s*>',
    re.IGNORECASE
)

# 边界情况：内容中合法包含 <file> 文本的模式
ESCAPED_FILE_PATTERNS = [
    r'`<\s*/?\s*[Ff][Ii][Ll][Ee]\b[^>]*>`',  # 行内代码
    r'```[\s\S]*?<\s*/?\s*[Ff][Ii][Ll][Ee]\b[^>]*>[\s\S]*?```',  # 代码块
    r'&lt;file&gt;',       # HTML 转义
]

# Buffer size limit (1MB)
BUFFER_MAX_SIZE = 1024 * 1024

# Turn-control / workflow markers that belong to the model's chat narration and
# must never be persisted as file content. If an unterminated <file> body carries
# one of these, it means chat text (handoff summaries, a trailing [TASK_COMPLETE],
# cross-agent narration) leaked into the file-write state instead of real prose.
CONTROL_MARKERS: tuple[str, ...] = (
    "[task_complete]",
    "[workflow_stopped]",
    "[clarification_needed]",
)


def _contains_control_marker(text: str) -> bool:
    """True when text carries a turn-control marker (i.e. chat narration, not prose)."""
    lowered = text.lower()
    return any(marker in lowered for marker in CONTROL_MARKERS)


def normalize_file_markers(content: str) -> str:
    """
    将各种 <file> 变体标准化为正确格式。

    处理的变体：
    - <File>, <FILE> -> <file>
    - < file >, <  file  > -> <file>
    - <file name="xxx"> -> <file>
    - </File>, </FILE> -> </file>

    边界情况处理：
    - 代码块中的 <file> 不处理
    - 行内代码中的 `<file>` 不处理
    """
    original = content

    # 1. 保护需要保留的内容（用占位符替换）
    placeholders = {}
    placeholder_idx = 0

    for pattern in ESCAPED_FILE_PATTERNS:
        for match in re.finditer(pattern, content):
            placeholder = f"__FILE_PLACEHOLDER_{placeholder_idx}__"
            placeholders[placeholder] = match.group(0)
            content = content.replace(match.group(0), placeholder, 1)
            placeholder_idx += 1

    # 2. 标准化开始和结束标记
    content = FILE_START_PATTERN.sub('<file>', content)
    content = FILE_END_PATTERN.sub('</file>', content)

    # 3. 恢复被保护的内容
    for placeholder, original_text in placeholders.items():
        content = content.replace(placeholder, original_text)

    # 4. 记录变体情况
    if content != original:
        log_with_context(
            logger,
            30,  # WARNING
            "Normalized non-standard file markers",
            original_snippet=original[:100],
        )

    return content


class StreamState(StrEnum):
    """State of the stream processor."""

    IDLE = "idle"
    WAITING_START = "waiting_start"
    WRITING = "writing"
    # After a >1MB file body was force-completed we keep consuming (and
    # discarding) the rest of the body until </file>, so the overflow tail is
    # NOT rerouted into the chat transcript.
    DRAINING = "draining"


@dataclass
class StreamResult:
    """Result of processing a content chunk."""

    # Content to yield as normal conversation
    conversation_content: str = ""
    # Content to yield after file streaming is complete (preserves ordering)
    conversation_content_after_file: str = ""
    # Content to yield as file content
    file_content: str = ""
    # File ID for file content events
    file_id: str = ""
    # Whether file writing is complete
    file_complete: bool = False
    # Content length for history summary
    content_length: int = 0
    # Whether buffer limit was exceeded
    buffer_exceeded: bool = False
    # Final accumulated content (only set when file_complete=True)
    final_content: str = ""


@dataclass
class StreamProcessor:
    """
    State machine for streaming file content.

    Manages the parsing of <file> and </file> markers in LLM output
    and routes content appropriately.
    """

    project_id: str = ""
    user_id: str | None = None

    # Current state
    state: StreamState = StreamState.IDLE

    # File being written
    file_id: str = ""

    # Buffers
    content_buffer: str = ""  # Confirmed file content
    temp_buffer: str = ""  # Buffer for potential partial markers
    history_buffer: str = ""  # Content for LLM history

    def reset(self) -> None:
        """Reset processor to idle state."""
        self.state = StreamState.IDLE
        self.file_id = ""
        self.content_buffer = ""
        self.temp_buffer = ""
        self.history_buffer = ""

    def start_file_write(self, file_id: str) -> None:
        """
        Start a new file write operation.

        Called when an empty file is created and we expect
        the LLM to output content with <file>...</file> markers.
        """
        self.state = StreamState.WAITING_START
        self.file_id = file_id
        self.content_buffer = ""
        self.temp_buffer = ""
        self.history_buffer = ""

        log_with_context(
            logger,
            20,  # INFO
            "Stream processor started file write mode",
            project_id=self.project_id,
            user_id=self.user_id,
            file_id=file_id,
        )

    @property
    def is_active(self) -> bool:
        """Check if processor is actively handling file content."""
        return self.state != StreamState.IDLE

    def process_content(self, content: str) -> StreamResult:
        """
        Process a content chunk from LLM output.

        Returns a StreamResult indicating what to do with the content.
        """
        # 首先标准化 file 标记
        content = normalize_file_markers(content)

        if self.state == StreamState.IDLE:
            # Not in file writing mode - return as conversation
            return StreamResult(conversation_content=content)

        if self.state == StreamState.WAITING_START:
            return self._process_waiting_start(content)

        if self.state == StreamState.WRITING:
            return self._process_writing(content)

        if self.state == StreamState.DRAINING:
            return self._process_draining(content)

        return StreamResult(conversation_content=content)

    def _process_waiting_start(self, content: str) -> StreamResult:
        """Process content while waiting for <file> marker."""
        self.temp_buffer += content

        # Match against the accumulated buffer with the fault-tolerant regex (not
        # the exact literal), so a case/whitespace variant marker split across
        # chunks (e.g. "<FI" + "LE>") is still detected once reassembled.
        start_match = FILE_START_PATTERN.search(self.temp_buffer)
        if start_match:
            # Found start marker - split content around the matched span
            before_marker = self.temp_buffer[: start_match.start()]
            after_marker = self.temp_buffer[start_match.end():]

            # Transition to writing state
            self.state = StreamState.WRITING
            self.temp_buffer = after_marker

            log_with_context(
                logger,
                20,  # INFO
                "Found <file> marker, starting file content",
                project_id=self.project_id,
                user_id=self.user_id,
                file_id=self.file_id,
            )

            # Continue processing the remainder in the same chunk.
            # This is required for "<file>...</file>" arriving in one delta.
            result = self._process_writing("")
            if before_marker:
                result.conversation_content = before_marker + result.conversation_content
            return result

        # Check buffer size limit
        if len(self.temp_buffer) > BUFFER_MAX_SIZE:
            log_with_context(
                logger,
                40,  # ERROR
                "temp_buffer exceeded max size while waiting for <file> marker",
                project_id=self.project_id,
                user_id=self.user_id,
                buffer_size=len(self.temp_buffer),
                max_size=BUFFER_MAX_SIZE,
            )
            # Output buffered content as normal text and reset
            buffered = self.temp_buffer
            self.reset()
            return StreamResult(
                conversation_content=buffered,
                buffer_exceeded=True,
            )

        # Keep buffering
        return StreamResult()

    def _process_writing(self, content: str) -> StreamResult:
        """Process content while writing file."""
        self.temp_buffer += content

        # 检测嵌套的 <file> 标记（异常情况），容忍大小写/空白变体
        # 这可能是 LLM 幻觉或用户在内容中讨论 XML 标签
        if FILE_START_PATTERN.search(self.temp_buffer):
            nested_count = len(FILE_START_PATTERN.findall(self.temp_buffer))
            log_with_context(
                logger,
                30,  # WARNING
                "Detected nested <file> markers in content, escaping them",
                count=nested_count,
                project_id=self.project_id,
                user_id=self.user_id,
                file_id=self.file_id,
            )
            # 转义所有嵌套的开始标记变体
            self.temp_buffer = FILE_START_PATTERN.sub('&lt;file&gt;', self.temp_buffer)

        end_match = FILE_END_PATTERN.search(self.temp_buffer)
        if end_match:
            return self._handle_end_marker(end_match)

        # No end marker yet - check if we have safe content to send. Reserve a
        # full marker-variant's worth of trailing chars (not just len('</file>'))
        # so a split whitespace variant like "< /file >" is never flushed before
        # it can be reassembled and matched.
        if len(self.temp_buffer) > MAX_MARKER_LEN:
            return self._send_safe_content(MAX_MARKER_LEN)

        # Buffer too small, just accumulate
        return StreamResult()

    def _handle_end_marker(self, end_match: "re.Match[str]") -> StreamResult:
        """Handle finding the </file> end marker."""
        before_marker = self.temp_buffer[: end_match.start()]
        after_marker = self.temp_buffer[end_match.end():]

        # Add remaining content to buffers
        if before_marker:
            self.content_buffer += before_marker
            self.history_buffer += before_marker

        # Calculate final content length and save final content
        final_content = self.content_buffer
        content_length = len(final_content)
        file_id = self.file_id
        file_content = before_marker

        log_with_context(
            logger,
            20,  # INFO
            "Found </file> marker, completing file write",
            project_id=self.project_id,
            user_id=self.user_id,
            file_id=file_id,
            content_length=content_length,
        )

        # Reset state
        self.reset()

        return StreamResult(
            file_content=file_content,
            file_id=file_id,
            file_complete=True,
            content_length=content_length,
            final_content=final_content,
            conversation_content_after_file=after_marker if after_marker else "",
        )

    def _send_safe_content(self, reserve: int) -> StreamResult:
        """Send content that's safe (not potentially part of end marker)."""
        safe_content = self.temp_buffer[:-reserve]

        # Check content_buffer size limit
        new_content_size = len(self.content_buffer) + len(safe_content)
        if new_content_size > BUFFER_MAX_SIZE:
            log_with_context(
                logger,
                40,  # ERROR
                "content_buffer exceeded max size while waiting for </file> marker",
                project_id=self.project_id,
                user_id=self.user_id,
                buffer_size=new_content_size,
                max_size=BUFFER_MAX_SIZE,
            )
            # Force-complete the file at the size cap, then DRAIN the rest of the
            # body until </file> instead of resetting to IDLE — a reset would
            # reroute the (still-streaming) overflow tail into the chat transcript.
            final_content = self.content_buffer + safe_content
            content_length = len(final_content)
            file_id = self.file_id

            self._begin_draining()

            return StreamResult(
                file_content=safe_content,
                file_id=file_id,
                file_complete=True,
                content_length=content_length,
                buffer_exceeded=True,
                final_content=final_content,
            )

        # Add to buffers and keep remaining in temp
        self.content_buffer += safe_content
        self.history_buffer += safe_content
        self.temp_buffer = self.temp_buffer[-reserve:]

        return StreamResult(
            file_content=safe_content,
            file_id=self.file_id,
        )

    def _begin_draining(self) -> None:
        """Enter DRAINING after a force-completed (oversized) file.

        The file content is already persisted up to the cap; from here we only
        need enough tail buffer to detect the closing </file>.
        """
        self.state = StreamState.DRAINING
        self.content_buffer = ""
        self.history_buffer = ""
        self.temp_buffer = ""

    def _process_draining(self, content: str) -> StreamResult:
        """Swallow the overflow tail of a force-completed file until </file>.

        Content here is the discarded remainder of an oversized body; only text
        AFTER the closing </file> is surfaced as normal conversation, so nothing
        leaks into the chat transcript.
        """
        self.temp_buffer += content
        end_match = FILE_END_PATTERN.search(self.temp_buffer)
        if end_match:
            after_marker = self.temp_buffer[end_match.end():]
            self.reset()
            return StreamResult(conversation_content=after_marker or "")

        # Bound the drain buffer — only the tail is needed to spot a split </file>.
        if len(self.temp_buffer) > MAX_MARKER_LEN:
            self.temp_buffer = self.temp_buffer[-MAX_MARKER_LEN:]
        return StreamResult()

    def finalize_on_stream_end(self) -> StreamResult:
        """
        Finalize buffered content when upstream stream ends.

        Behavior:
        - WAITING_START: flush buffered text back to conversation
        - WRITING: auto-complete file content even without </file>
        """
        if self.state == StreamState.IDLE:
            return StreamResult()

        if self.state == StreamState.DRAINING:
            # File was already force-completed at the size cap; discard the
            # remaining (unterminated) overflow tail rather than leaking it.
            self.reset()
            return StreamResult()

        if self.state == StreamState.WAITING_START:
            buffered = self.temp_buffer
            log_with_context(
                logger,
                30,  # WARNING
                "Stream ended before <file> marker, flushing buffered text",
                project_id=self.project_id,
                user_id=self.user_id,
                file_id=self.file_id,
                buffered_length=len(buffered),
            )
            self.reset()
            return StreamResult(conversation_content=buffered)

        if self.state == StreamState.WRITING:
            trailing = self.temp_buffer
            if trailing:
                self.content_buffer += trailing
                self.history_buffer += trailing

            final_content = self.content_buffer
            file_id = self.file_id
            content_length = len(final_content)

            # Contamination guard: an unterminated <file> whose buffered body
            # carries turn-control markers is chat narration / cross-agent
            # handoff text that leaked into the file-write state — NOT chapter
            # prose. Surface it as conversation and leave the (empty) file
            # untouched rather than persisting the narration as the file's
            # content. Legitimately truncated prose (no control marker) is still
            # auto-completed below.
            if _contains_control_marker(final_content):
                log_with_context(
                    logger,
                    30,  # WARNING
                    "Stream ended with an unterminated <file> containing control "
                    "markers; discarding buffered narration instead of writing it "
                    "to the file",
                    project_id=self.project_id,
                    user_id=self.user_id,
                    file_id=file_id,
                    content_length=content_length,
                )
                self.reset()
                return StreamResult(conversation_content=final_content)

            log_with_context(
                logger,
                30,  # WARNING
                "Stream ended without </file>, auto-completing file write",
                project_id=self.project_id,
                user_id=self.user_id,
                file_id=file_id,
                content_length=content_length,
            )

            self.reset()
            return StreamResult(
                file_content=trailing,
                file_id=file_id,
                file_complete=True,
                content_length=content_length,
                final_content=final_content,
            )

        return StreamResult()

    def get_final_content(self) -> str:
        """Get the final accumulated file content."""
        return self.content_buffer

    def get_history_buffer(self) -> str:
        """Get the content buffer for LLM history."""
        return self.history_buffer
