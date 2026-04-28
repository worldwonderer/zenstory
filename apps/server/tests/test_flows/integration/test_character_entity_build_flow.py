from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from flows.pipelines.subflows import character_entity_build_flow as char_mod
from tests.test_flows.conftest import FakeFuture, FakeMonitor


class _FakeSessionCtx:
    def __init__(self, session):
        self.session = session

    def __enter__(self):
        return self.session

    def __exit__(self, exc_type, exc, tb):
        return False


class _SequenceTask:
    def __init__(self, results):
        self.results = list(results)
        self.calls = []

    def submit(self, novel_id: int, character_name: str):
        self.calls.append((novel_id, character_name))
        next_result = self.results.pop(0)
        return FakeFuture(next_result)


@pytest.mark.integration
class TestCharacterEntityBuildFlow:
    def test_flow_returns_zero_when_no_mentions(self, monkeypatch):
        monkeypatch.setattr(char_mod, "get_run_logger", lambda: MagicMock())
        monkeypatch.setattr(char_mod, "create_performance_monitor", lambda _name: FakeMonitor())

        import flows.database_session as dbs
        import services.material.character_mentions_service as mentions_mod

        monkeypatch.setattr(dbs, "get_db_session", lambda: _FakeSessionCtx(MagicMock()))

        class FakeCharacterMentionsService:
            def get_by_novel(self, _db, _novel_id):
                return []

        monkeypatch.setattr(mentions_mod, "CharacterMentionsService", FakeCharacterMentionsService)

        result = char_mod.character_entity_build_flow.fn(novel_id=1)

        assert result["created_count"] == 0
        assert result["updated_count"] == 0
        assert result["total_count"] == 0

    def test_flow_builds_entities_for_selected_characters(self, monkeypatch):
        monkeypatch.setattr(char_mod, "get_run_logger", lambda: MagicMock())
        monkeypatch.setattr(char_mod, "create_performance_monitor", lambda _name: FakeMonitor())
        monkeypatch.setattr(char_mod.settings, "MAX_CONCURRENT_CHAPTERS", 4)

        import flows.database_session as dbs
        import services.material.character_mentions_service as mentions_mod

        monkeypatch.setattr(dbs, "get_db_session", lambda: _FakeSessionCtx(MagicMock()))

        mentions = [
            SimpleNamespace(character_name="Alice", importance="major"),
            SimpleNamespace(character_name="Bob", importance="supporting"),
            SimpleNamespace(character_name="Alice", importance="major"),
        ]

        class FakeCharacterMentionsService:
            def get_by_novel(self, _db, _novel_id):
                return mentions

        monkeypatch.setattr(mentions_mod, "CharacterMentionsService", FakeCharacterMentionsService)

        task = _SequenceTask([
            {"status": "created", "character_name": "Alice"},
            {"status": "updated", "character_name": "Bob"},
        ])
        monkeypatch.setattr(char_mod, "build_character_entity_task", task)

        result = char_mod.character_entity_build_flow.fn(novel_id=7)

        assert result["selected_characters"] == 2
        assert result["created_count"] == 1
        assert result["updated_count"] == 1
        assert result["failed_count"] == 0
        assert result["total_count"] == 2
        assert len(task.calls) == 2
