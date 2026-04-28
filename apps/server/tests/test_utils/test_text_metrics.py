"""Tests for shared text metrics helpers."""

from utils.text_metrics import count_words


def test_count_words_ignores_pure_numbers():
    """Numeric-only tokens should not count as words."""
    assert count_words("123 456 7890") == 0


def test_count_words_counts_latin_words_and_chinese_chars():
    """Latin words and Chinese chars should both be counted."""
    assert count_words("hello 你好 world 世界 123") == 6
