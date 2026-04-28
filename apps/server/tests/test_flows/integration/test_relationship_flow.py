from __future__ import annotations

import importlib
from unittest.mock import MagicMock

import pytest

from tests.test_flows.conftest import FakeFuture, FakeMonitor

rel_mod = importlib.import_module("flows.pipelines.subflows.relationship_flow")


class _FakeCheckpointManager:
    def __init__(self):
        self.update_calls = []

    def update_checkpoint(self, stage, status=None, data=None):
        self.update_calls.append((stage, status, data))


class _PersistTask:
    def __init__(self):
        self.calls = []

    def submit(self, novel_id: int, chapter_id: int):
        self.calls.append((novel_id, chapter_id))
        if chapter_id == 2:
            return FakeFuture(error=RuntimeError("neo4j fail"))
        return FakeFuture({"ok": True})


@pytest.mark.integration
class TestRelationshipFlow:
    def test_flow_with_features_disabled(self, monkeypatch):
        cp = _FakeCheckpointManager()

        monkeypatch.setattr(rel_mod, "get_run_logger", lambda: MagicMock())
        monkeypatch.setattr(rel_mod, "create_performance_monitor", lambda _name: FakeMonitor())
        monkeypatch.setattr(rel_mod, "create_checkpoint_manager", lambda _novel_id: cp)

        monkeypatch.setattr(rel_mod.settings, "ENABLE_RELATIONSHIP_EXTRACTION", False)
        monkeypatch.setattr(rel_mod.settings, "ENABLE_NEO4J_STORAGE", False)

        result = rel_mod.relationship_flow.fn(novel_id=1, chapter_ids=[1, 2])

        assert result["relationships_count"] == 0
        assert result["neo4j_persisted"] is False
        assert cp.update_calls[-1][0] == "stage2b"

    def test_flow_collects_neo4j_failed_chapters(self, monkeypatch):
        cp = _FakeCheckpointManager()
        persist_task = _PersistTask()

        monkeypatch.setattr(rel_mod, "get_run_logger", lambda: MagicMock())
        monkeypatch.setattr(rel_mod, "create_performance_monitor", lambda _name: FakeMonitor())
        monkeypatch.setattr(rel_mod, "create_checkpoint_manager", lambda _novel_id: cp)

        monkeypatch.setattr(rel_mod.settings, "ENABLE_RELATIONSHIP_EXTRACTION", True)
        monkeypatch.setattr(rel_mod.settings, "ENABLE_NEO4J_STORAGE", True)
        monkeypatch.setattr(rel_mod.settings, "MAX_CONCURRENT_CHAPTERS", 3)

        monkeypatch.setattr(
            rel_mod,
            "extract_character_relationships_task",
            lambda novel_id, chapter_ids, batch_size: {
                "relationships": [{"character_a_id": 1, "character_b_id": 2}],
                "batches_processed": 1,
            },
        )
        monkeypatch.setattr(
            rel_mod,
            "build_character_relationships_task",
            lambda novel_id, relationships_data: {"saved_count": 1},
        )
        monkeypatch.setattr(rel_mod, "persist_chapter_relationships_to_neo4j_task", persist_task)

        result = rel_mod.relationship_flow.fn(novel_id=9, chapter_ids=[1, 2, 3])

        assert result["relationships_count"] == 1
        assert result["neo4j_persisted"] is False
        assert result["neo4j_failed_chapters"] == [2]
        assert result["status"] == "completed_with_errors"
        assert len(persist_task.calls) == 3
