"""Regression tests for NFKC-expansion boundary handling in fuzzy matching.

NFKC normalization can expand one original character into several normalized
characters (Ⅻ→xii, ﬁ→fi, ㎞→km); index_map maps all of them back to the same
original index. A fuzzy span that starts or ends in the middle of such an
expansion must be rejected (or shrunk, for approximate matching) instead of
swallowing the whole original character including its unmatched remainder.
"""

from agent.tools.file_ops.text_matching import (
    find_approximate_match,
    find_fuzzy_spans,
)

CONTENT = "他们说序章完毕。第Ⅻ章开始了……"


def test_pattern_ending_mid_expansion_is_rejected():
    """LLM 把 Ⅻ 误写成 x：span 终点落在展开字符中间，必须拒绝而非吞掉整个 Ⅻ。"""
    stats: dict[str, int] = {}
    spans = find_fuzzy_spans(CONTENT, "序章完毕第x", stats=stats)
    assert spans == []
    assert stats["boundary_rejected"] == 1


def test_pattern_starting_mid_expansion_is_rejected():
    """span 起点落在展开字符中间同样必须拒绝。"""
    stats: dict[str, int] = {}
    spans = find_fuzzy_spans(CONTENT, "ii章开始了", stats=stats)
    assert spans == []
    assert stats["boundary_rejected"] == 1


def test_pattern_covering_full_expansion_still_matches():
    """覆盖完整展开序列（xii）的 pattern 仍应正常匹配到整个 Ⅻ。"""
    spans = find_fuzzy_spans(CONTENT, "序章完毕第xii")
    assert len(spans) == 1
    start, end = spans[0]
    assert CONTENT[start:end] == "序章完毕。第Ⅻ"


def test_stats_report_zero_when_no_boundary_issue():
    stats: dict[str, int] = {}
    spans = find_fuzzy_spans(CONTENT, "章开始了", stats=stats)
    # 归一化后不足 min_normalized_len 也不应误报 boundary_rejected
    assert stats["boundary_rejected"] == 0
    assert spans == []


def test_approximate_match_shrinks_partial_expansion():
    """近似匹配窗口终点落在展开字符中间时，应收缩到对齐边界而非吞掉 Ⅻ。"""
    content = "他们说的序章今天完毕。第Ⅻ章开始了。"
    pattern = "他们说的序章今天完毕第x"
    match = find_approximate_match(content, pattern, max_error_rate=0.2, min_pattern_len=10)
    assert match is not None
    start, end, _score, matched_text = match
    assert "Ⅻ" not in matched_text
    assert end <= content.index("Ⅻ")
    assert 0 <= start < end
