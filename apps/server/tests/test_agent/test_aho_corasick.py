"""Regression tests for longest-non-ambiguous match selection.

The previous running-max-end "group" merge transitively chained non-overlapping
spans through a shared neighbour, so two non-overlapping local winners could be
discarded together because of an unrelated tie in the chained group.
"""

from agent.utils.aho_corasick import (
    MatchSpan,
    select_longest_non_ambiguous_matches,
)


def _terms(spans):
    return sorted((s.term, s.start, s.end) for s in spans)


def test_non_overlapping_bridged_winners_are_both_kept():
    # A[0,6] and C[6,12] do not overlap each other but are both bridged by
    # B[3,8]. A and C are strictly longer than B, so both survive; only the
    # dominated B is dropped. (The old grouping discarded all three.)
    a = MatchSpan(term="A", start=0, end=6)
    b = MatchSpan(term="B", start=3, end=8)
    c = MatchSpan(term="C", start=6, end=12)
    kept = select_longest_non_ambiguous_matches([a, b, c])
    assert _terms(kept) == [("A", 0, 6), ("C", 6, 12)]


def test_equal_length_overlap_is_ambiguous_and_dropped():
    a = MatchSpan(term="A", start=0, end=5)
    b = MatchSpan(term="B", start=3, end=8)  # same length, overlaps A
    assert select_longest_non_ambiguous_matches([a, b]) == []


def test_nested_shorter_span_loses_to_longer():
    outer = MatchSpan(term="outer", start=0, end=10)
    inner = MatchSpan(term="inner", start=2, end=5)
    kept = select_longest_non_ambiguous_matches([outer, inner])
    assert _terms(kept) == [("outer", 0, 10)]


def test_disjoint_spans_all_kept():
    a = MatchSpan(term="a", start=0, end=3)
    b = MatchSpan(term="b", start=5, end=9)
    c = MatchSpan(term="c", start=20, end=25)
    kept = select_longest_non_ambiguous_matches([a, b, c])
    assert _terms(kept) == [("a", 0, 3), ("b", 5, 9), ("c", 20, 25)]


def test_empty_input():
    assert select_longest_non_ambiguous_matches([]) == []
