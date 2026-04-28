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

        return StreamResult(conversation_content=content)

    def _process_waiting_start(self, content: str) -> StreamResult:
        """Process content while waiting for <file> marker."""
        self.temp_buffer += content

        if FILE_START_MARKER in self.temp_buffer:
            # Found start marker - split content
            before_marker, after_marker = self.temp_buffer.split(FILE_START_MARKER, 1)

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

        # 检测嵌套的 <file> 标记（异常情况）
        # 这可能是 LLM 幻觉或用户在内容中讨论 XML 标签
        if FILE_START_MARKER in self.temp_buffer:
            nested_count = self.temp_buffer.count(FILE_START_MARKER)
            log_with_context(
                logger,
                30,  # WARNING
                "Detected nested <file> markers in content, escaping them",
                count=nested_count,
                project_id=self.project_id,
                user_id=self.user_id,
                file_id=self.file_id,
            )
            # 替换所有嵌套的开始标记（不带 count 参数会替换所有）
            self.temp_buffer = self.temp_buffer.replace(FILE_START_MARKER, '&lt;file&gt;')

        if FILE_END_MARKER in self.temp_buffer:
            return self._handle_end_marker()

        # No end marker yet - check if we have safe content to send
        marker_len = len(FILE_END_MARKER)
        if len(self.temp_buffer) > marker_len:
            return self._send_safe_content(marker_len)

        # Buffer too small, just accumulate
        return StreamResult()

    def _handle_end_marker(self) -> StreamResult:
        """Handle finding the </file> end marker."""
        before_marker, after_marker = self.temp_buffer.split(FILE_END_MARKER, 1)

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

    def _send_safe_content(self, marker_len: int) -> StreamResult:
        """Send content that's safe (not potentially part of end marker)."""
        safe_content = self.temp_buffer[:-marker_len]

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
            # Return what we have and reset
            final_content = self.content_buffer + safe_content
            content_length = len(final_content)
            file_id = self.file_id

            self.reset()

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
        self.temp_buffer = self.temp_buffer[-marker_len:]

        return StreamResult(
            file_content=safe_content,
            file_id=self.file_id,
        )

    def finalize_on_stream_end(self) -> StreamResult:
        """
        Finalize buffered content when upstream stream ends.

        Behavior:
        - WAITING_START: flush buffered text back to conversation
        - WRITING: auto-complete file content even without </file>
        """
        if self.state == StreamState.IDLE:
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
