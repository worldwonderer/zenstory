from __future__ import annotations

import importlib
from unittest.mock import MagicMock

import pytest

summary_mod = importlib.import_module(
    "flows.atomic_tasks.narrative.summary_based_aggregation"
)
decorator_mod = importlib.import_module("flows.utils.decorators.prefect")
chapters_mod = importlib.import_module("services.material.chapters_service")


class _FakeSessionCtx:
    def __enter__(self):
        return object()

    def __exit__(self, exc_type, exc, tb):
        return False


@pytest.mark.integration
def test_identify_story_frameworks_accepts_novel_id_keyword(monkeypatch):
    """
    Regression:
    Prefect task invocation passes `novel_id=...`.
    The task function must accept this keyword without TypeError.
    """

    class _FakeChaptersService:
        def list_by_novel_ordered(self, _db, _novel_id, _chapter_ids=None):
            return []

    monkeypatch.setattr(decorator_mod, "get_run_logger", lambda: MagicMock())
    monkeypatch.setattr(summary_mod, "get_run_logger", lambda: MagicMock())
    monkeypatch.setattr(summary_mod, "get_db_session", lambda: _FakeSessionCtx())
    monkeypatch.setattr(chapters_mod, "ChaptersService", _FakeChaptersService)

    result = summary_mod.identify_story_frameworks_from_summaries.fn(
        novel_id=42,
        chapter_ids=[1, 2, 3],
    )

    assert result == {"story_frameworks": [], "novel_id": 42}


@pytest.mark.integration
def test_summary_based_aggregation_accepts_novel_id_keyword(monkeypatch):
    monkeypatch.setattr(decorator_mod, "get_run_logger", lambda: MagicMock())
    monkeypatch.setattr(summary_mod, "get_run_logger", lambda: MagicMock())
    monkeypatch.setattr(
        summary_mod,
        "identify_story_frameworks_from_summaries",
        lambda **kwargs: {"story_frameworks": [], "novel_id": kwargs["novel_id"]},
    )

    result = summary_mod.summary_based_story_aggregation.fn(
        novel_id=77,
        chapter_ids=[10, 11],
    )

    assert result == {
        "novel_id": 77,
        "stories_count": 0,
        "storylines_count": 0,
    }
