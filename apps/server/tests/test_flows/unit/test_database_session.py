from __future__ import annotations

import pytest

from flows import database_session as dbs


class _FakeSessionObj:
    def __init__(self):
        self.commit_calls = 0
        self.rollback_calls = 0

    def commit(self):
        self.commit_calls += 1

    def rollback(self):
        self.rollback_calls += 1


class _FakeSessionCtx:
    def __init__(self, session_obj: _FakeSessionObj):
        self.session_obj = session_obj

    def __enter__(self):
        return self.session_obj

    def __exit__(self, exc_type, exc, tb):
        return False


class TestDatabaseSession:
    def test_get_prefect_db_session_commits_on_success(self, monkeypatch):
        session = _FakeSessionObj()
        monkeypatch.setattr(dbs, "Session", lambda _engine: _FakeSessionCtx(session))

        with dbs.get_prefect_db_session() as got:
            assert got is session

        assert session.commit_calls == 1
        assert session.rollback_calls == 0

    def test_get_prefect_db_session_rolls_back_on_error(self, monkeypatch):
        session = _FakeSessionObj()
        monkeypatch.setattr(dbs, "Session", lambda _engine: _FakeSessionCtx(session))

        with pytest.raises(RuntimeError, match="boom"):
            with dbs.get_prefect_db_session():
                raise RuntimeError("boom")

        assert session.commit_calls == 0
        assert session.rollback_calls == 1
