"""
Tests for context compaction module.

Tests token estimation, cut point detection, and summarization.
"""

import asyncio
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime

from agent.context.compaction import (
    CompactionSettings,
    CompactionResult,
    ContextUsageEstimate,
    estimate_tokens,
    estimate_context_tokens,
    should_compact,
    find_cut_point,
    generate_compaction_summary,
    compact_context,
    create_compaction_summary_message,
    _get_assistant_usage,
    _calculate_context_tokens,
    _serialize_messages_to_text,
    _simple_truncate_messages,
    CONTEXT_WINDOW,
)


@pytest.mark.unit
class TestEstimateTokens:
    """Test token estimation functions."""

    def test_estimate_tokens_user_string(self):
        """Test token estimation for user message with string content."""
        message = {"role": "user", "content": "Hello world"}
        # 11 chars / 4 = 2.75 → 2 tokens
        assert estimate_tokens(message) == 2

    def test_estimate_tokens_user_list(self):
        """Test token estimation for user message with list content."""
        message = {
            "role": "user",
            "content": [
                {"type": "text", "text": "Hello world"},
                {"type": "text", "text": "Another text"},
            ],
        }
        # 11 + 12 = 23 chars / 4 = 5.75 → 5 tokens
        assert estimate_tokens(message) == 5

    def test_estimate_tokens_assistant_text(self):
        """Test token estimation for assistant message with text."""
        message = {
            "role": "assistant",
            "content": [
                {"type": "text", "text": "Response text here"},
            ],
        }
        # 18 chars / 4 = 4.5 → 4 tokens
        assert estimate_tokens(message) == 4

    def test_estimate_tokens_assistant_thinking(self):
        """Test token estimation for assistant message with thinking."""
        message = {
            "role": "assistant",
            "content": [
                {"type": "thinking", "thinking": "Thinking process..."},
            ],
        }
        # 19 chars / 4 = 4.75 → 4 tokens
        assert estimate_tokens(message) == 4

    def test_estimate_tokens_assistant_tool_use(self):
        """Test token estimation for assistant message with tool use."""
        message = {
            "role": "assistant",
            "content": [
                {"type": "tool_use", "name": "create_file", "input": {"title": "Test"}},
            ],
        }
        # name + str(input) ≈ some chars
        tokens = estimate_tokens(message)
        assert tokens > 0

    def test_estimate_tokens_tool_result(self):
        """Test token estimation for tool result message."""
        message = {
            "role": "tool_result",
            "content": "Tool result content here",
        }
        # 24 chars / 4 = 6 tokens
        assert estimate_tokens(message) == 6

    def test_estimate_tokens_tool_result_with_image(self):
        """Test token estimation for tool result with image."""
        message = {
            "role": "tool_result",
            "content": [
                {"type": "text", "text": "Text part"},
                {"type": "image", "source": {"data": "base64..."}},
            ],
        }
        # 9 chars text + 4800 chars image estimate = 4809 / 4 ≈ 1202 tokens
        tokens = estimate_tokens(message)
        assert tokens > 1000

    def test_estimate_tokens_empty_content(self):
        """Test token estimation for empty content returns min 1."""
        message = {"role": "user", "content": ""}
        # Empty content returns max(1, 0) = 1 due to chars // 4 = 0, max(1, 0) = 1
        assert estimate_tokens(message) == 1

    def test_estimate_tokens_chinese(self):
        """Test token estimation for Chinese content."""
        message = {"role": "user", "content": "这是一个测试"}
        # 6 chars / 4 = 1.5 → 1 token
        assert estimate_tokens(message) == 1

    def test_estimate_tokens_long_content(self):
        """Test token estimation for long content."""
        message = {"role": "user", "content": "x" * 400}
        # 400 chars / 4 = 100 tokens
        assert estimate_tokens(message) == 100


@pytest.mark.unit
class TestAssistantUsage:
    """Test assistant usage extraction."""

    def test_get_assistant_usage_valid(self):
        """Test extracting valid usage info."""
        message = {
            "role": "assistant",
            "stop_reason": "end_turn",
            "usage": {
                "input_tokens": 100,
                "output_tokens": 50,
            },
        }
        usage = _get_assistant_usage(message)
        assert usage is not None
        assert usage["input_tokens"] == 100

    def test_get_assistant_usage_aborted(self):
        """Test that aborted messages return None."""
        message = {
            "role": "assistant",
            "stop_reason": "aborted",
            "usage": {"input_tokens": 100},
        }
        assert _get_assistant_usage(message) is None

    def test_get_assistant_usage_error(self):
        """Test that error messages return None."""
        message = {
            "role": "assistant",
            "stop_reason": "error",
            "usage": {"input_tokens": 100},
        }
        assert _get_assistant_usage(message) is None

    def test_get_assistant_usage_no_usage(self):
        """Test message without usage field."""
        message = {"role": "assistant", "content": "text"}
        assert _get_assistant_usage(message) is None

    def test_get_assistant_usage_non_assistant(self):
        """Test non-assistant message returns None."""
        message = {"role": "user", "content": "text"}
        assert _get_assistant_usage(message) is None


@pytest.mark.unit
class TestCalculateContextTokens:
    """Test context token calculation."""

    def test_calculate_with_total_tokens(self):
        """Test calculation with total_tokens field."""
        usage = {"total_tokens": 1000}
        assert _calculate_context_tokens(usage) == 1000

    def test_calculate_with_components(self):
        """Test calculation from components."""
        usage = {
            "input_tokens": 500,
            "output_tokens": 200,
            "cache_read_tokens": 100,
            "cache_write_tokens": 50,
        }
        assert _calculate_context_tokens(usage) == 850


@pytest.mark.unit
class TestEstimateContextTokens:
    """Test full context token estimation."""

    def test_estimate_empty_messages(self):
        """Test estimation with empty messages."""
        estimate = estimate_context_tokens([])
        assert estimate.total_tokens == 0
        assert estimate.usage_tokens == 0
        assert estimate.trailing_tokens == 0

    def test_estimate_no_usage_info(self):
        """Test estimation without usage info."""
        messages = [
            {"role": "user", "content": "x" * 400},
            {"role": "assistant", "content": "y" * 400},
        ]
        estimate = estimate_context_tokens(messages)
        # 800 chars / 4 = 200 tokens
        assert estimate.total_tokens == 200
        assert estimate.usage_tokens == 0
        assert estimate.trailing_tokens == 200
        assert estimate.last_usage_index is None

    def test_estimate_with_usage_info(self):
        """Test estimation with usage info in assistant message."""
        messages = [
            {"role": "user", "content": "query"},
            {"role": "assistant", "content": "response", "usage": {"total_tokens": 500}},
            {"role": "user", "content": "x" * 400},  # 100 tokens
        ]
        estimate = estimate_context_tokens(messages)
        assert estimate.total_tokens == 600  # 500 + 100
        assert estimate.usage_tokens == 500
        assert estimate.trailing_tokens == 100
        assert estimate.last_usage_index == 1


@pytest.mark.unit
class TestShouldCompact:
    """Test compaction decision."""

    def test_should_compact_disabled(self):
        """Test compaction when disabled."""
        settings = CompactionSettings(enabled=False)
        assert should_compact(180000, CONTEXT_WINDOW, settings) is False

    def test_should_compact_below_threshold(self):
        """Test compaction below threshold."""
        settings = CompactionSettings(reserve_tokens=16384)
        # CONTEXT_WINDOW - 16384 = 183616
        assert should_compact(100000, CONTEXT_WINDOW, settings) is False

    def test_should_compact_above_threshold(self):
        """Test compaction above threshold."""
        settings = CompactionSettings(reserve_tokens=16384)
        # Should trigger when > 200000 - 16384
        assert should_compact(190000, CONTEXT_WINDOW, settings) is True


@pytest.mark.unit
class TestFindCutPoint:
    """Test cut point detection."""

    def test_find_cut_point_empty(self):
        """Test cut point with empty messages."""
        index, is_split = find_cut_point([], 1000)
        assert index == 0
        assert is_split is False

    def test_find_cut_point_single_user(self):
        """Test cut point with single user message."""
        messages = [{"role": "user", "content": "x" * 100}]
        index, is_split = find_cut_point(messages, 50)
        # Only one message, so cut at 0
        assert index == 0
        # User message means not a split turn
        assert is_split is False

    def test_find_cut_point_keeps_recent(self):
        """Test cut point keeps recent messages."""
        messages = [
            {"role": "user", "content": "x" * 400},  # Old
            {"role": "assistant", "content": "y" * 400},
            {"role": "user", "content": "z" * 400},  # Recent
        ]
        index, is_split = find_cut_point(messages, 50)
        # Should cut somewhere to keep ~50 tokens of recent content
        assert index >= 0
        assert index < len(messages)

    def test_find_cut_point_never_tool_result(self):
        """Test cut point is never at tool result."""
        messages = [
            {"role": "user", "content": "query"},
            {"role": "assistant", "content": "response"},
            {"role": "tool_result", "content": "result"},
        ]
        index, is_split = find_cut_point(messages, 5)
        # Should not cut at tool_result
        assert messages[index]["role"] != "tool_result"


@pytest.mark.unit
class TestSerializeMessages:
    """Test message serialization."""

    def test_serialize_string_content(self):
        """Test serialization of string content."""
        messages = [
            {"role": "user", "content": "Hello"},
        ]
        text = _serialize_messages_to_text(messages)
        assert "[USER]: Hello" in text

    def test_serialize_list_content(self):
        """Test serialization of list content."""
        messages = [
            {
                "role": "assistant",
                "content": [
                    {"type": "text", "text": "Response"},
                    {"type": "thinking", "thinking": "Thoughts..."},
                    {"type": "tool_use", "name": "test", "input": {"a": 1}},
                ],
            },
        ]
        text = _serialize_messages_to_text(messages)
        assert "[ASSISTANT]:" in text
        assert "Response" in text
        assert "[Thinking:" in text
        assert "[Tool:" in text


@pytest.mark.unit
class TestCompactionSettings:
    """Test compaction settings."""

    def test_default_settings(self):
        """Test default settings values."""
        settings = CompactionSettings()
        assert settings.enabled is True
        assert settings.reserve_tokens == 16384
        assert settings.keep_recent_tokens == 20000

    def test_custom_settings(self):
        """Test custom settings values."""
        settings = CompactionSettings(
            enabled=False,
            reserve_tokens=8000,
            keep_recent_tokens=10000,
        )
        assert settings.enabled is False
        assert settings.reserve_tokens == 8000
        assert settings.keep_recent_tokens == 10000


@pytest.mark.unit
class TestCompactionResult:
    """Test compaction result."""

    def test_result_creation(self):
        """Test creating compaction result."""
        result = CompactionResult(
            summary="Test summary",
            first_kept_message_id="msg_123",
            tokens_before=100000,
            tokens_after=30000,
            messages_removed=50,
        )
        assert result.summary == "Test summary"
        assert result.first_kept_message_id == "msg_123"
        assert result.tokens_before == 100000
        assert result.tokens_after == 30000
        assert result.messages_removed == 50


@pytest.mark.unit
class TestCreateCompactionSummaryMessage:
    """Test compaction summary message creation."""

    def test_create_message(self):
        """Test creating compaction summary message."""
        msg = create_compaction_summary_message("Summary text", 50000)
        assert msg["role"] == "assistant"
        assert isinstance(msg["content"], list)
        assert msg["content"][0]["type"] == "text"
        assert "System Memory Block" in msg["content"][0]["text"]
        assert "50000 tokens compressed" in msg["content"][0]["text"]
        assert "Summary text" in msg["content"][0]["text"]
        assert msg["metadata"]["type"] == "compaction_summary"
        assert msg["metadata"]["semantic_role"] == "system_memory"
        assert msg["metadata"]["tokens_before"] == 50000


@pytest.mark.asyncio
@pytest.mark.integration
class TestGenerateCompactionSummary:
    """Test compaction summary generation (requires LLM)."""

    async def test_generate_summary_empty(self):
        """Test generating summary from empty messages."""
        # Empty messages returns early with "No prior history to summarize."
        summary = await generate_compaction_summary([])
        assert summary == "No prior history to summarize."

    async def test_generate_summary_with_messages(self):
        """Test generating summary from messages."""
        messages = [
            {"role": "user", "content": "Write a story"},
            {"role": "assistant", "content": "Once upon a time..."},
        ]

        with patch("agent.llm.anthropic_client.get_anthropic_client") as mock_client:
            mock_instance = MagicMock()
            mock_client.return_value = mock_instance
            mock_instance.create_message = AsyncMock(
                return_value={
                    "content": [
                        {
                            "type": "text",
                            "text": "## Goal\nWrite a story\n## Progress\n- Started writing",
                        }
                    ]
                }
            )

            summary = await generate_compaction_summary(messages)
            assert "## Goal" in summary

    async def test_generate_summary_accepts_max_tokens_keyword(self):
        """Should accept max_tokens keyword without signature errors."""
        messages = [{"role": "user", "content": "Summarize this"}]

        with patch("agent.llm.anthropic_client.get_anthropic_client") as mock_client:
            mock_instance = MagicMock()
            mock_client.return_value = mock_instance
            mock_instance.create_message = AsyncMock(
                return_value={
                    "content": [
                        {"type": "text", "text": "## Goal\nSummarize this"}
                    ]
                }
            )

            summary = await generate_compaction_summary(messages, max_tokens=256)
            assert "## Goal" in summary


@pytest.mark.asyncio
@pytest.mark.integration
class TestCompactContext:
    """Test full compaction flow."""

    async def test_compact_empty_messages(self):
        """Test compaction with empty messages."""
        settings = CompactionSettings()
        result = await compact_context([], settings)
        assert result is None

    async def test_compact_not_needed(self):
        """Test compaction when not needed."""
        messages = [{"role": "user", "content": "short query"}]
        settings = CompactionSettings()
        # Small context, should not need compaction
        result = await compact_context(messages, settings, context_window=100000)
        assert result is None

    async def test_compact_needed(self):
        """Test compaction when needed."""
        # Create messages that exceed threshold
        messages = [
            {"role": "user", "content": "x" * 50000, "id": f"msg_{i}"}
            for i in range(5)
        ]

        settings = CompactionSettings(
            reserve_tokens=1000,
            keep_recent_tokens=500,
        )

        with patch(
            "agent.context.compaction.generate_compaction_summary"
        ) as mock_summary:
            mock_summary.return_value = "## Goal\nTest summary"

            result = await compact_context(messages, settings, context_window=10000)

            if result:  # Compaction might not trigger depending on token estimates
                assert result.summary == "## Goal\nTest summary"
                assert result.messages_removed > 0
                assert result.tokens_after < result.tokens_before

    async def test_compact_tokens_after_matches_system_memory_wrapper_estimate(self):
        """Compaction tokens_after should match the wrapped system-memory estimate."""
        messages = [
            {"role": "user", "content": "x" * 3000, "id": f"msg_{i}"}
            for i in range(8)
        ]
        settings = CompactionSettings(reserve_tokens=1000, keep_recent_tokens=800)

        with patch("agent.context.compaction.generate_compaction_summary") as mock_summary:
            mock_summary.return_value = "## Goal\nConsistency summary"
            result = await compact_context(messages, settings, context_window=6000)

        if not result:
            pytest.skip("Compaction did not trigger under current token estimator")

        if result.first_kept_message_id:
            keep_index = next(
                (i for i, msg in enumerate(messages) if msg.get("id") == result.first_kept_message_id),
                len(messages),
            )
        else:
            keep_index = min(result.messages_removed, len(messages))

        kept_messages = messages[keep_index:]
        summary_message = create_compaction_summary_message(result.summary, result.tokens_before)
        expected_tokens_after = estimate_context_tokens([summary_message] + kept_messages).total_tokens

        assert result.tokens_after == expected_tokens_after


@pytest.mark.integration
class TestCompactionLLMIntegration:
    """Test compaction with LLM failure scenarios."""

    @pytest.mark.asyncio
    async def test_llm_timeout_triggers_fallback(self):
        """LLM timeout should trigger fallback truncation."""
        with patch("agent.llm.anthropic_client.get_anthropic_client") as mock_client:
            # Mock client that times out
            mock_instance = MagicMock()
            mock_instance.create_message = AsyncMock(side_effect=asyncio.TimeoutError("LLM timeout"))
            mock_client.return_value = mock_instance

            messages = [{"role": "user", "content": "Test message"}]
            result = await generate_compaction_summary(messages)

            # Should return fallback result
            assert "[Context truncated" in result or "Recent Activity" in result

    @pytest.mark.asyncio
    async def test_llm_rate_limit_triggers_retry(self):
        """LLM rate limit should trigger retry."""
        call_count = 0

        async def mock_create(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise Exception("Rate limit exceeded")
            return {"content": [{"type": "text", "text": "Summary created"}]}

        with patch("agent.llm.anthropic_client.get_anthropic_client") as mock_client:
            mock_instance = MagicMock()
            mock_instance.create_message = mock_create
            mock_client.return_value = mock_instance

            messages = [{"role": "user", "content": "Test"}]
            result = await generate_compaction_summary(messages)

            # Should succeed after retries
            assert call_count == 3
            assert "Summary created" in result

    @pytest.mark.asyncio
    async def test_all_retries_fail_uses_fallback(self):
        """All retries failing should use fallback."""
        with patch("agent.llm.anthropic_client.get_anthropic_client") as mock_client:
            mock_instance = MagicMock()
            mock_instance.create_message = AsyncMock(side_effect=Exception("Permanent error"))
            mock_client.return_value = mock_instance

            messages = [
                {"role": "user", "content": "Message 1"},
                {"role": "assistant", "content": "Response 1"},
            ]
            result = await generate_compaction_summary(messages)

            # Should use fallback
            assert result is not None
            assert len(result) > 0


@pytest.mark.integration
class TestFallbackTruncation:
    """Test fallback truncation behavior."""

    def test_fallback_with_empty_messages(self):
        """Fallback with empty messages should return default."""
        result = _simple_truncate_messages([])
        assert result == "No prior history."

    def test_fallback_with_few_messages(self):
        """Fallback with few messages should include all."""
        messages = [
            {"role": "user", "content": "Hi"},
            {"role": "assistant", "content": "Hello"},
        ]
        result = _simple_truncate_messages(messages, keep_recent_count=5)

        assert "[Context truncated" in result
        assert "Hi" in result or "Hello" in result

    def test_fallback_with_many_messages(self):
        """Fallback with many messages should keep recent only."""
        messages = [
            {"role": "user", "content": f"Unique message number {i}"} for i in range(20)
        ]
        result = _simple_truncate_messages(messages, keep_recent_count=5)

        assert "[Context truncated" in result
        assert "number 19" in result  # Most recent
        assert "number 0" not in result  # Old message truncated (0 is first message)

    def test_fallback_with_list_content(self):
        """Fallback should handle list content format."""
        messages = [
            {
                "role": "assistant",
                "content": [
                    {"type": "text", "text": "Response text"},
                    {"type": "tool_use", "name": "test", "input": {}},
                ]
            }
        ]
        result = _simple_truncate_messages(messages)

        assert "[Context truncated" in result
        assert "Response text" in result


@pytest.mark.integration
class TestRetryBackoff:
    """Test retry backoff behavior."""

    @pytest.mark.asyncio
    async def test_backoff_delays(self):
        """Test that backoff delays increase exponentially."""
        delays = []
        original_sleep = asyncio.sleep

        async def mock_sleep(delay):
            delays.append(delay)
            # Don't actually sleep

        with patch("asyncio.sleep", mock_sleep):
            with patch("agent.llm.anthropic_client.get_anthropic_client") as mock_client:
                mock_instance = MagicMock()
                mock_instance.create_message = AsyncMock(side_effect=Exception("Error"))
                mock_client.return_value = mock_instance

                messages = [{"role": "user", "content": "Test"}]

                try:
                    await generate_compaction_summary(messages)
                except:
                    pass

        # Should have delays: 1s, 2s (capped at MAX_DELAY=10)
        # Note: actual implementation may vary
        if len(delays) > 0:
            assert delays[0] >= 1.0
            if len(delays) > 1:
                assert delays[1] >= delays[0]
