from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

from flows.utils.helpers import checkpoint_manager as cm_mod


class _FakeSessionCtx:
    def __init__(self, session_obj):
        self.session_obj = session_obj

    def __enter__(self):
        return self.session_obj

    def __exit__(self, exc_type, exc, tb):
        return False


class _FakeCheckpointService:
    def __init__(self):
        self.upsert_calls = []

    def upsert(self, session, novel_id, stage, data, status=None, job_id=None, error=None):
        self.upsert_calls.append(
            {
                "session": session,
                "novel_id": novel_id,
                "stage": stage,
                "data": data,
                "status": status,
                "job_id": job_id,
                "error": error,
            }
        )
        return SimpleNamespace(stage_status=status or "processing")

    def get(self, _session, _novel_id, _stage):
        return None

    def get_latest(self, _session, _novel_id):
        return None

    def delete_all(self, _session, _novel_id):
        return None


class TestCheckpointManager:
    def test_update_checkpoint_passes_none_data_verbatim(self, monkeypatch):
        fake_service = _FakeCheckpointService()
        fake_session = MagicMock()

        monkeypatch.setattr(cm_mod, "CheckpointService", lambda: fake_service)
        monkeypatch.setattr(cm_mod, "get_run_logger", lambda: MagicMock())

        import flows.database_session as dbs

        monkeypatch.setattr(dbs, "get_prefect_db_session", lambda: _FakeSessionCtx(fake_session))

        manager = cm_mod.CheckpointManager(novel_id=1, job_id=9)
        manager.update_checkpoint("stage1", status="processing", data=None)

        assert len(fake_service.upsert_calls) == 1
        call = fake_service.upsert_calls[0]
        assert call["data"] is None
        assert call["stage"] == "stage1"
        assert call["status"] == "processing"
        assert call["job_id"] == 9

    def test_parse_checkpoint_data_handles_json_and_invalid(self, monkeypatch):
        monkeypatch.setattr(cm_mod, "get_run_logger", lambda: MagicMock())
        manager = cm_mod.CheckpointManager(novel_id=1)

        valid = SimpleNamespace(checkpoint_data='{"a": 1}')
        invalid = SimpleNamespace(checkpoint_data="not-json")

        assert manager._parse_checkpoint_data(valid) == {"a": 1}
        assert manager._parse_checkpoint_data(invalid) == {}
        assert manager._parse_checkpoint_data(None) == {}

    def test_can_resume_only_processing_or_failed(self, monkeypatch):
        monkeypatch.setattr(cm_mod, "get_run_logger", lambda: MagicMock())
        manager = cm_mod.CheckpointManager(novel_id=1)

        manager.get_latest_checkpoint = lambda: SimpleNamespace(stage_status="processing")
        assert manager.can_resume() is True

        manager.get_latest_checkpoint = lambda: SimpleNamespace(stage_status="failed")
        assert manager.can_resume() is True

        manager.get_latest_checkpoint = lambda: SimpleNamespace(stage_status="completed")
        assert manager.can_resume() is False

    def test_get_pending_chapters_excludes_completed_and_failed(self, monkeypatch):
        monkeypatch.setattr(cm_mod, "get_run_logger", lambda: MagicMock())
        manager = cm_mod.CheckpointManager(novel_id=1)

        manager.get_completed_chapters = lambda _stage: [1, 2]
        manager.get_failed_chapters = lambda _stage: [4]

        pending = manager.get_pending_chapters("stage1", [1, 2, 3, 4, 5])
        assert pending == [3, 5]
