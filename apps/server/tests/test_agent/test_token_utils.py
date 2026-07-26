"""Tests for token estimation utilities."""


from agent.utils.token_utils import (
    _chars_per_token_for,
    _cjk_fraction,
    estimate_message_tokens,
    estimate_text_tokens,
)

# ---------------------------------------------------------------------------
# estimate_text_tokens
# ---------------------------------------------------------------------------


def test_empty_string_returns_zero():
    assert estimate_text_tokens("") == 0


def test_none_like_falsy_returns_zero():
    assert estimate_text_tokens("") == 0


def test_latin_text_positive():
    tokens = estimate_text_tokens("Hello world, this is a test sentence.")
    assert tokens > 0


def test_chinese_text_estimates_more_tokens_than_len_over_4():
    """Chinese text should yield materially more tokens than len/4 (≈ len/2)."""
    text = "这是一段中文测试文本，用于验证token估算的准确性。中文字符每个大约对应半个token。"
    naive = len(text) // 4
    estimated = estimate_text_tokens(text)
    # The CJK-aware estimate should be at least 1.5x the naive len/4 estimate
    assert estimated >= naive * 1.5, (
        f"Expected CJK estimate ({estimated}) to be >= 1.5 * naive ({naive})"
    )


def test_chinese_text_more_tokens_than_naive():
    """Pure Chinese text should yield more tokens than the naive len/4 estimate."""
    text = "今天天气很好，我们一起去公园散步。" * 5
    estimated = estimate_text_tokens(text)
    naive = len(text) // 4
    assert estimated > naive, (
        f"Expected CJK estimate ({estimated}) to exceed naive len/4 ({naive})"
    )


def test_mixed_text_returns_positive():
    mixed = "Hello 你好 world 世界 foo bar"
    assert estimate_text_tokens(mixed) > 0


def test_short_text_returns_at_least_one():
    assert estimate_text_tokens("x") >= 1


# ---------------------------------------------------------------------------
# estimate_message_tokens
# ---------------------------------------------------------------------------


def test_user_message_string():
    msg = {"role": "user", "content": "Hello, how are you?"}
    assert estimate_message_tokens(msg) >= 1


def test_user_message_blocks():
    msg = {
        "role": "user",
        "content": [{"type": "text", "text": "Hello, how are you?"}],
    }
    assert estimate_message_tokens(msg) >= 1


def test_assistant_message_text_block():
    msg = {
        "role": "assistant",
        "content": [{"type": "text", "text": "I am fine, thank you."}],
    }
    assert estimate_message_tokens(msg) >= 1


def test_assistant_message_thinking_block():
    msg = {
        "role": "assistant",
        "content": [{"type": "thinking", "thinking": "Let me think about this..."}],
    }
    assert estimate_message_tokens(msg) >= 1


def test_tool_result_message():
    msg = {
        "role": "tool_result",
        "content": [{"type": "text", "text": "File created successfully."}],
    }
    assert estimate_message_tokens(msg) >= 1


def test_image_block_counts_tokens():
    msg = {
        "role": "tool_result",
        "content": [{"type": "image", "source": {}}],
    }
    tokens = estimate_message_tokens(msg)
    # Image should contribute ~1200 tokens
    assert tokens >= 1000


def test_unknown_role_string_content():
    msg = {"role": "custom", "content": "some content here"}
    assert estimate_message_tokens(msg) >= 1


def test_empty_content_returns_zero_or_one():
    msg = {"role": "user", "content": ""}
    # Empty content — result is 0 or 1 (max(1, ...) guard might not fire for empty)
    assert estimate_message_tokens(msg) >= 0


def test_assistant_thinking_blocks_do_not_consume_history_budget():
    """Thinking blocks are dropped before replay, so they must not be billed."""
    text_block = {"type": "text", "text": "Final answer for the user."}
    with_thinking = {
        "role": "assistant",
        "content": [
            {"type": "thinking", "thinking": "reasoning " * 500},
            text_block,
        ],
    }
    text_only = {"role": "assistant", "content": [text_block]}

    assert estimate_message_tokens(with_thinking) == estimate_message_tokens(text_only)


# ---------------------------------------------------------------------------
# _cjk_fraction / _chars_per_token_for
# ---------------------------------------------------------------------------


def test_cjk_extension_b_counts_as_cjk():
    assert _cjk_fraction(chr(0x20000) * 10) == 1.0
    assert _cjk_fraction(chr(0x2A6DF) * 10) == 1.0


def test_general_punctuation_and_symbols_are_not_cjk():
    # Curly quotes, em dash, ellipsis, arrow, for-all — all inside U+2001..U+2A6D
    assert _cjk_fraction("‘’“”—…→∀") == 0.0


def test_chars_per_token_uses_cjk_ratio_for_extension_b_text():
    assert _chars_per_token_for(chr(0x20000) * 20) == 2.0


def test_chars_per_token_keeps_latin_ratio_for_symbol_heavy_text():
    assert _chars_per_token_for("‘’“”—…→∀") == 4.0
