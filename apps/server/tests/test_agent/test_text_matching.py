"""Regression tests for approximate text matching safety.

Covers:
- The work-budget guard that stops find_approximate_match from spinning the
  CPU (and blocking the event loop) on large chapters.
- The ambiguity guard that refuses to auto-apply a merely-similar window when a
  different, distant passage scores nearly as high.
- Preservation of the legitimate word-error match on reasonably-sized content.
"""

import time

from agent.tools.file_ops.text_matching import (
    MAX_APPROX_CONTENT_LEN,
    find_approximate_match,
)


def test_word_error_match_still_found():
    """A near-duplicate (minor drift) should still match on small content."""
    content = "他缓缓转过身，看着窗外的大雨，心中一片茫然。"
    pattern = "他缓缓转过身看着窗外的大雨心中一片茫然"  # punctuation/word drift
    match = find_approximate_match(content, pattern, max_error_rate=0.25, min_pattern_len=8)
    assert match is not None
    start, end, score, _matched = match
    assert score >= 0.75
    assert 0 <= start < end <= len(content)


def test_ambiguous_match_is_rejected():
    """Two similar, distant passages must be treated as ambiguous (return None)."""
    content = "她缓缓转过身，看着门外的细雨。\n\n" + ("x" * 40) + "\n\n他缓缓转过身，看着窗外的大雨。"
    pattern = "缓缓转过身看着外的雨天气不错"
    assert find_approximate_match(content, pattern, max_error_rate=0.25, min_pattern_len=8) is None


def test_large_content_is_guarded_and_fast():
    """Oversized content must bail out quickly instead of scanning (no hang)."""
    big = "这是一个测试段落，用于验证性能守卫是否生效。" * 500
    assert len(big) > MAX_APPROX_CONTENT_LEN
    start = time.time()
    result = find_approximate_match(
        big,
        "一个并不存在于文中的很长很长的锚点句子写在这里现在结束",
        max_error_rate=0.25,
        min_pattern_len=8,
    )
    elapsed = time.time() - start
    assert result is None
    # The guard should return effectively immediately (generously bounded).
    assert elapsed < 1.0


def test_short_pattern_is_ignored():
    """Patterns below min_pattern_len are not matched approximately."""
    assert find_approximate_match("some content here", "abc", min_pattern_len=8) is None
