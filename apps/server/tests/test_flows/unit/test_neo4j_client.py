from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from flows.utils.clients import neo4j as neo_mod


class _FakeSession:
    def __init__(self, should_fail=False):
        self.calls = []
        self.should_fail = should_fail

    def run(self, query, **params):
        self.calls.append((query, params))
        if self.should_fail:
            raise RuntimeError("db fail")


class _FakeSessionCtx:
    def __init__(self, session):
        self.session = session

    def __enter__(self):
        return self.session

    def __exit__(self, exc_type, exc, tb):
        return False


class _FakeDriver:
    def __init__(self, session):
        self._session = session
        self.closed = False

    def session(self):
        return _FakeSessionCtx(self._session)

    def close(self):
        self.closed = True


class TestNeo4jClient:
    def test_persist_relationships_skips_when_unavailable(self, monkeypatch):
        monkeypatch.setattr(neo_mod, "get_run_logger", lambda: MagicMock())
        client = neo_mod.Neo4jClient.__new__(neo_mod.Neo4jClient)
        client.driver = None

        result = client.persist_chapter_relationships(1, 2, [{"character_a_id": 1, "character_b_id": 2}])

        assert result["skip"] is True
        assert result["reason"] == "neo4j_unavailable"
        assert result["written"] == 0

    def test_persist_relationships_writes_only_valid_edges(self, monkeypatch):
        monkeypatch.setattr(neo_mod, "get_run_logger", lambda: MagicMock())

        session = _FakeSession()
        client = neo_mod.Neo4jClient.__new__(neo_mod.Neo4jClient)
        client.driver = _FakeDriver(session)
        client.ensure_constraints = lambda: None

        relationships = [
            {"character_a_id": 2, "character_b_id": 1, "character_a": "B", "character_b": "A"},
            {"character_a_id": 3, "character_b_id": 3},  # self-loop, skip
            {"character_a_id": "x", "character_b_id": 4},  # invalid id, skip
        ]

        result = client.persist_chapter_relationships(10, 20, relationships)

        assert result["skip"] is False
        assert result["written"] == 1
        assert result["novel_id"] == 10
        assert result["chapter_id"] == 20
        assert any("HAS_CHAPTER" in call[0] for call in session.calls)

    def test_persist_relationships_returns_write_error_on_session_failure(self, monkeypatch):
        monkeypatch.setattr(neo_mod, "get_run_logger", lambda: MagicMock())

        session = _FakeSession(should_fail=True)
        client = neo_mod.Neo4jClient.__new__(neo_mod.Neo4jClient)
        client.driver = _FakeDriver(session)
        client.ensure_constraints = lambda: None

        result = client.persist_chapter_relationships(1, 1, [])

        assert result["skip"] is True
        assert result["reason"] == "write_error"

    def test_close_closes_driver(self):
        session = _FakeSession()
        driver = _FakeDriver(session)
        client = neo_mod.Neo4jClient.__new__(neo_mod.Neo4jClient)
        client.driver = driver

        client.close()

        assert driver.closed is True
