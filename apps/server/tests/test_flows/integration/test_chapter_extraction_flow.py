from __future__ import annotations

import importlib
from unittest.mock import MagicMock

import pytest

from tests.test_flows.conftest import FakeFuture, FakeMonitor, FakeTask

chapter_mod = importlib.import_module("flows.pipelines.subflows.chapter_extraction_flow")


class _FakeCheckpointManager:
    def __init__(self):
        self.update_calls = []

    def get_pending_chapters(self, _stage: str, all_chapter_ids: list[int]):
        return all_chapter_ids

    def update_checkpoint(self, stage, status=None, data=None):
        self.update_calls.append((stage, status, data))


@pytest.mark.integration
class TestChapterExtractionFlow:
    def test_flow_with_all_feature_flags_disabled(self, monkeypatch):
        monkeypatch.setattr(chapter_mod, "get_run_logger", lambda: MagicMock())
        monkeypatch.setattr(chapter_mod, "create_performance_monitor", lambda _name: FakeMonitor())
        monkeypatch.setattr(chapter_mod, "create_checkpoint_manager", lambda _novel_id: _FakeCheckpointManager())

        monkeypatch.setattr(chapter_mod.settings, "ENABLE_CHAPTER_SUMMARIES", False)
        monkeypatch.setattr(chapter_mod.settings, "ENABLE_PLOT_EXTRACTION", False)
        monkeypatch.setattr(chapter_mod.settings, "ENABLE_ENTITY_EXTRACTION", False)

        result = chapter_mod.chapter_extraction_flow.fn(novel_id=1, chapter_ids=[10, 20])

        assert result["novel_id"] == 1
        assert result["summaries_count"] == 0
        assert result["plots_count"] == 0
        assert result["mentions_extracted"] is False
        assert result["status"] == "completed"

    def test_flow_extracts_mentions_when_enabled(self, monkeypatch):
        monkeypatch.setattr(chapter_mod, "get_run_logger", lambda: MagicMock())
        monkeypatch.setattr(chapter_mod, "create_performance_monitor", lambda _name: FakeMonitor())
        monkeypatch.setattr(chapter_mod, "create_checkpoint_manager", lambda _novel_id: _FakeCheckpointManager())

        monkeypatch.setattr(chapter_mod.settings, "ENABLE_CHAPTER_SUMMARIES", False)
        monkeypatch.setattr(chapter_mod.settings, "ENABLE_PLOT_EXTRACTION", False)
        monkeypatch.setattr(chapter_mod.settings, "ENABLE_ENTITY_EXTRACTION", True)
        monkeypatch.setattr(chapter_mod.settings, "MAX_CONCURRENT_CHAPTERS", 3)

        mention_task = FakeTask({"chapter_id": 10, "mentions": ["A"]})
        monkeypatch.setattr(chapter_mod, "extract_character_mentions_task", mention_task)

        result = chapter_mod.chapter_extraction_flow.fn(novel_id=2, chapter_ids=[10, 20])

        assert result["mentions_extracted"] is True
        assert result["failed_count"] == 0
        assert len(mention_task.submit_calls) == 2

    def test_flow_counts_failed_mentions_in_failed_count(self, monkeypatch):
        monkeypatch.setattr(chapter_mod, "get_run_logger", lambda: MagicMock())
        monkeypatch.setattr(chapter_mod, "create_performance_monitor", lambda _name: FakeMonitor())
        monkeypatch.setattr(chapter_mod, "create_checkpoint_manager", lambda _novel_id: _FakeCheckpointManager())

        monkeypatch.setattr(chapter_mod.settings, "ENABLE_CHAPTER_SUMMARIES", False)
        monkeypatch.setattr(chapter_mod.settings, "ENABLE_PLOT_EXTRACTION", False)
        monkeypatch.setattr(chapter_mod.settings, "ENABLE_ENTITY_EXTRACTION", True)
        monkeypatch.setattr(chapter_mod.settings, "MAX_CONCURRENT_CHAPTERS", 3)

        class _MentionTask:
            def submit(self, chapter_id):
                if chapter_id == 10:
                    return FakeFuture({"chapter_id": chapter_id, "mentions": ["A"]})
                return FakeFuture(error=RuntimeError("mention fail"))

        monkeypatch.setattr(chapter_mod, "extract_character_mentions_task", _MentionTask())

        result = chapter_mod.chapter_extraction_flow.fn(novel_id=3, chapter_ids=[10, 20])

        assert result["mentions_extracted"] is True
        assert result["failed_count"] == 1
        assert result["failed_mention_chapters"] == [20]
        assert result["status"] == "completed_with_errors"
