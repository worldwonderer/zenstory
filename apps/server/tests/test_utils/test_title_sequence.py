import pytest

from utils.title_sequence import (
    build_sequence_sort_key,
    extract_chapter_like_sequence_number,
    extract_sequence_number,
    extract_sequence_number_from_metadata,
    extract_title_first_sequence_number,
    has_sequence_locked_order,
    normalize_explicit_sequence_order,
    resolve_persisted_sequence_order,
)


@pytest.mark.unit
def test_extract_chapter_like_sequence_number_supports_chapter_patterns():
    assert extract_chapter_like_sequence_number("第十章：冲突升级") == 10
    assert extract_chapter_like_sequence_number("第12集 终章") == 12
    assert extract_chapter_like_sequence_number("Chapter 7 - Twist") == 7


@pytest.mark.unit
def test_extract_chapter_like_sequence_number_ignores_leading_number_only():
    title = "2026-03-20 写作日志"
    assert extract_chapter_like_sequence_number(title) is None
    assert extract_sequence_number(title) == 2026


@pytest.mark.unit
def test_extract_sequence_number_from_metadata_prefers_numeric_hints():
    assert extract_sequence_number_from_metadata({"chapter_number": 58}) == 58
    assert extract_sequence_number_from_metadata({"episode_number": "12"}) == 12
    assert extract_sequence_number_from_metadata({"section_number": " 7 "}) == 7


@pytest.mark.unit
def test_extract_title_first_sequence_number_prefers_visible_title_over_metadata():
    assert (
        extract_title_first_sequence_number(
            "第58章 真相",
            {"chapter_number": 99},
        )
        == 58
    )


@pytest.mark.unit
def test_normalize_explicit_sequence_order_collapses_trailing_zero_typos():
    assert normalize_explicit_sequence_order(580, sequence_number=58) == 58
    assert normalize_explicit_sequence_order(5800, sequence_number=58) == 58
    assert normalize_explicit_sequence_order(59, sequence_number=58) == 59


@pytest.mark.unit
def test_build_sequence_sort_key_normalizes_suspicious_order_mismatch():
    assert build_sequence_sort_key(580, title="第58章 真相") == (58, 58)
    assert build_sequence_sort_key(0, title="第58章 真相") == (58, 58)


@pytest.mark.unit
def test_build_sequence_sort_key_locks_chapter_like_drafts_to_title_sequence():
    assert build_sequence_sort_key(
        1,
        title="第58章 真相",
        file_type="draft",
    ) == (58, 58)


@pytest.mark.unit
def test_build_sequence_sort_key_does_not_lock_non_chapter_like_numbered_drafts():
    assert build_sequence_sort_key(
        1,
        title="2026-03-20 写作日志",
        file_type="draft",
    ) == (1, 2026)


@pytest.mark.unit
def test_has_sequence_locked_order_only_for_writing_file_types():
    assert has_sequence_locked_order("draft", sequence_number=58) is True
    assert has_sequence_locked_order("outline", sequence_number=58) is True
    assert has_sequence_locked_order("script", sequence_number=58) is True
    assert has_sequence_locked_order("character", sequence_number=58) is False


@pytest.mark.unit
def test_resolve_persisted_sequence_order_prefers_title_sequence_for_chapter_files():
    assert resolve_persisted_sequence_order(
        1,
        title="第58章 真相",
        file_type="draft",
    ) == 58
    assert resolve_persisted_sequence_order(
        1,
        title="角色设定 1",
        file_type="character",
    ) == 1
    assert resolve_persisted_sequence_order(
        1,
        title="剧情大纲",
        metadata={"chapter_number": 58},
        file_type="draft",
    ) == 1
