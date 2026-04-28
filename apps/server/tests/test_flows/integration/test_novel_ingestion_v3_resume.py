from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from flows.pipelines import novel_ingestion_v3_flow as flow_mod


class _FakeSession:
    def __init__(self):
        self.flush_calls = 0
        self.commit_calls = 0

    def flush(self):
        self.flush_calls += 1

    def commit(self):
        self.commit_calls += 1


class _FakeSessionCtx:
    def __init__(self, session):
        self.session = session

    def __enter__(self):
        return self.session

    def __exit__(self, exc_type, exc, tb):
        return False


@pytest.mark.integration
class TestNovelIngestionResume:
    def test_check_and_resume_returns_incomplete_when_no_existing_novel(self, monkeypatch, fake_logger):
        session = _FakeSession()
        monkeypatch.setattr(flow_mod, "get_prefect_db_session", lambda: _FakeSessionCtx(session))

        import services.material.novels_service as novels_mod

        class FakeNovelsService:
            def get_by_content_hash(self, _session, _content_hash, _user_id):
                return None

        monkeypatch.setattr(novels_mod, "NovelsService", FakeNovelsService)

        result = flow_mod._check_and_resume_from_checkpoint(
            content_hash="abc",
            user_id="u1",
            novel_id=None,
            correlation_id=None,
            flow_start=0.0,
            logger=fake_logger,
            publisher=MagicMock(),
        )

        assert result == {"completed": False}

    def test_check_and_resume_returns_completed_when_latest_checkpoint_completed(
        self, monkeypatch, fake_logger, fake_checkpoint_record_factory
    ):
        session = _FakeSession()
        monkeypatch.setattr(flow_mod, "get_prefect_db_session", lambda: _FakeSessionCtx(session))

        import services.material.novels_service as novels_mod

        class FakeNovelsService:
            def get_by_content_hash(self, _session, _content_hash, _user_id):
                return SimpleNamespace(id=99)

            def list_chapter_ids(self, _session, _novel_id):
                return [1, 2, 3]

        monkeypatch.setattr(novels_mod, "NovelsService", FakeNovelsService)

        cp_mgr = MagicMock()
        cp_mgr.get_latest_checkpoint.return_value = fake_checkpoint_record_factory(
            {}, stage="completed", stage_status="completed"
        )
        monkeypatch.setattr(flow_mod, "create_checkpoint_manager", lambda _novel_id: cp_mgr)

        result = flow_mod._check_and_resume_from_checkpoint(
            content_hash="abc",
            user_id="u1",
            novel_id=None,
            correlation_id=None,
            flow_start=0.0,
            logger=fake_logger,
            publisher=MagicMock(),
        )

        assert result["completed"] is True
        assert result["result"]["novel_id"] == 99
        assert result["result"]["status"] == "already_completed"

    def test_check_and_resume_executes_stage1_and_stage2_when_resume_stage1(self, monkeypatch, fake_logger):
        session = _FakeSession()
        monkeypatch.setattr(flow_mod, "get_prefect_db_session", lambda: _FakeSessionCtx(session))

        import services.material.novels_service as novels_mod

        class FakeNovelsService:
            def get_by_content_hash(self, _session, _content_hash, _user_id):
                return SimpleNamespace(id=88)

            def list_chapter_ids(self, _session, _novel_id):
                return [7, 8]

        monkeypatch.setattr(novels_mod, "NovelsService", FakeNovelsService)

        cp_mgr = MagicMock()
        cp_mgr.get_latest_checkpoint.return_value = None
        cp_mgr.can_resume.return_value = True
        cp_mgr.get_resume_point.return_value = {"stage": "stage1", "status": "processing"}
        monkeypatch.setattr(flow_mod, "create_checkpoint_manager", lambda _novel_id: cp_mgr)

        calls = {"stage1": 0, "stage2": 0}

        class FakeExecutor:
            def __init__(self, **kwargs):
                self.kwargs = kwargs

            def execute_stage1(self):
                calls["stage1"] += 1
                return {"summaries_count": 2}

            def execute_stage2(self, stage1_result, _flow_start):
                calls["stage2"] += 1
                assert stage1_result == {"summaries_count": 2}
                return {"novel_id": 88, "status": "completed"}

        monkeypatch.setattr(flow_mod, "StageExecutor", FakeExecutor)

        result = flow_mod._check_and_resume_from_checkpoint(
            content_hash="abc",
            user_id="u1",
            novel_id=None,
            correlation_id="cid",
            flow_start=0.0,
            logger=fake_logger,
            publisher=MagicMock(),
        )

        assert result["completed"] is True
        assert result["result"]["novel_id"] == 88
        assert calls == {"stage1": 1, "stage2": 1}

    def test_check_and_resume_returns_incomplete_when_resume_not_allowed(self, monkeypatch, fake_logger):
        session = _FakeSession()
        monkeypatch.setattr(flow_mod, "get_prefect_db_session", lambda: _FakeSessionCtx(session))

        import services.material.novels_service as novels_mod

        class FakeNovelsService:
            def get_by_content_hash(self, _session, _content_hash, _user_id):
                return SimpleNamespace(id=77)

            def list_chapter_ids(self, _session, _novel_id):
                return [1]

        monkeypatch.setattr(novels_mod, "NovelsService", FakeNovelsService)

        cp_mgr = MagicMock()
        cp_mgr.get_latest_checkpoint.return_value = None
        cp_mgr.can_resume.return_value = False
        monkeypatch.setattr(flow_mod, "create_checkpoint_manager", lambda _novel_id: cp_mgr)

        result = flow_mod._check_and_resume_from_checkpoint(
            content_hash="abc",
            user_id="u1",
            novel_id=None,
            correlation_id="cid",
            flow_start=0.0,
            logger=fake_logger,
            publisher=MagicMock(),
        )

        assert result == {"completed": False, "novel_id": 77}
        cp_mgr.get_resume_point.assert_not_called()

    def test_check_and_resume_executes_stage2_only_when_resume_stage2(self, monkeypatch, fake_logger):
        session = _FakeSession()
        monkeypatch.setattr(flow_mod, "get_prefect_db_session", lambda: _FakeSessionCtx(session))

        import services.material.novels_service as novels_mod

        class FakeNovelsService:
            def get_by_content_hash(self, _session, _content_hash, _user_id):
                return SimpleNamespace(id=55)

            def list_chapter_ids(self, _session, _novel_id):
                return [3, 4]

        monkeypatch.setattr(novels_mod, "NovelsService", FakeNovelsService)

        cp_mgr = MagicMock()
        cp_mgr.get_latest_checkpoint.return_value = None
        cp_mgr.can_resume.return_value = True
        cp_mgr.get_resume_point.return_value = {"stage": "stage2", "status": "processing"}
        monkeypatch.setattr(flow_mod, "create_checkpoint_manager", lambda _novel_id: cp_mgr)

        calls = {"stage1": 0, "stage2": 0}

        class FakeExecutor:
            def __init__(self, **kwargs):
                self.kwargs = kwargs

            def execute_stage1(self):
                calls["stage1"] += 1
                raise AssertionError("stage2 恢复路径不应执行 stage1")

            def execute_stage2(self, stage1_result, _flow_start):
                calls["stage2"] += 1
                assert stage1_result is None
                return {"novel_id": 55, "status": "completed"}

        monkeypatch.setattr(flow_mod, "StageExecutor", FakeExecutor)

        result = flow_mod._check_and_resume_from_checkpoint(
            content_hash="abc",
            user_id="u1",
            novel_id=None,
            correlation_id="cid",
            flow_start=0.0,
            logger=fake_logger,
            publisher=MagicMock(),
        )

        assert result["completed"] is True
        assert result["result"]["novel_id"] == 55
        assert calls == {"stage1": 0, "stage2": 1}

    def test_check_and_resume_treats_unknown_stage_as_fresh_start(self, monkeypatch, fake_logger):
        session = _FakeSession()
        monkeypatch.setattr(flow_mod, "get_prefect_db_session", lambda: _FakeSessionCtx(session))

        import services.material.novels_service as novels_mod

        class FakeNovelsService:
            def get_by_content_hash(self, _session, _content_hash, _user_id):
                return SimpleNamespace(id=44)

            def list_chapter_ids(self, _session, _novel_id):
                return [9]

        monkeypatch.setattr(novels_mod, "NovelsService", FakeNovelsService)

        cp_mgr = MagicMock()
        cp_mgr.get_latest_checkpoint.return_value = None
        cp_mgr.can_resume.return_value = True
        cp_mgr.get_resume_point.return_value = {"stage": "weird_stage", "status": "processing"}
        monkeypatch.setattr(flow_mod, "create_checkpoint_manager", lambda _novel_id: cp_mgr)
        monkeypatch.setattr(flow_mod, "StageExecutor", lambda **kwargs: (_ for _ in ()).throw(AssertionError("不应创建执行器")))

        result = flow_mod._check_and_resume_from_checkpoint(
            content_hash="abc",
            user_id="u1",
            novel_id=None,
            correlation_id="cid",
            flow_start=0.0,
            logger=fake_logger,
            publisher=MagicMock(),
        )

        assert result == {"completed": False, "novel_id": 44}

    def test_check_and_resume_cleans_failed_stage(self, monkeypatch, fake_logger):
        session = _FakeSession()
        monkeypatch.setattr(flow_mod, "get_prefect_db_session", lambda: _FakeSessionCtx(session))

        import services.material.checkpoint_service as cp_service_mod
        import services.material.ingestion_jobs_service as jobs_mod
        import services.material.novels_service as novels_mod

        class FakeNovelsService:
            def get_by_content_hash(self, _session, _content_hash, _user_id):
                return SimpleNamespace(id=66)

            def list_chapter_ids(self, _session, _novel_id):
                return [1]

        class FakeCheckpointService:
            def __init__(self):
                self.deleted = []

            def delete_all(self, _session, novel_id):
                self.deleted.append(novel_id)

        old_job = SimpleNamespace(status="failed")

        class FakeIngestionJobsService:
            def get_latest_by_novel(self, _session, _novel_id):
                return old_job

        monkeypatch.setattr(novels_mod, "NovelsService", FakeNovelsService)
        fake_cp_service = FakeCheckpointService()
        monkeypatch.setattr(cp_service_mod, "CheckpointService", lambda: fake_cp_service)
        monkeypatch.setattr(jobs_mod, "IngestionJobsService", FakeIngestionJobsService)

        cp_mgr = MagicMock()
        cp_mgr.get_latest_checkpoint.return_value = None
        cp_mgr.can_resume.return_value = True
        cp_mgr.get_resume_point.return_value = {"stage": "failed", "status": "failed"}
        monkeypatch.setattr(flow_mod, "create_checkpoint_manager", lambda _novel_id: cp_mgr)

        result = flow_mod._check_and_resume_from_checkpoint(
            content_hash="abc",
            user_id="u1",
            novel_id=None,
            correlation_id=None,
            flow_start=0.0,
            logger=fake_logger,
            publisher=MagicMock(),
        )

        assert result == {"completed": False, "novel_id": 66}
        assert old_job.status == "abandoned"
        assert session.flush_calls == 1
        assert session.commit_calls == 1
        assert fake_cp_service.deleted == [66]


@pytest.mark.integration
class TestMarkJobAsFailed:
    def test_mark_job_as_failed_publishes_even_without_novel(self, fake_logger):
        publisher = MagicMock()
        flow_mod._mark_job_as_failed(
            novel_id=None,
            _correlation_id=None,
            error="err",
            flow_start=0.0,
            logger=fake_logger,
            publisher=publisher,
        )

        publisher.publish.assert_called_once()

    def test_mark_job_as_failed_updates_job_and_checkpoint(self, monkeypatch, fake_logger):
        session = _FakeSession()
        monkeypatch.setattr(flow_mod, "get_prefect_db_session", lambda: _FakeSessionCtx(session))

        import services.material.ingestion_jobs_service as jobs_mod

        class FakeIngestionJobsService:
            def get_latest_by_novel(self, _session, _novel_id):
                return SimpleNamespace(id=123)

            def update_processed(
                self,
                _session,
                job_id,
                *,
                status,
                stage,
                stage_status,
                stage_data,
                error_message,
                error_details,
            ):
                assert job_id == 123
                assert status == "failed"
                assert stage == "failed"
                assert stage_status == "failed"
                assert isinstance(stage_data.get("elapsed_ms"), int)
                assert stage_data["elapsed_ms"] >= 0
                assert error_message == "fatal"
                assert error_details["stage"] == "flow"

        monkeypatch.setattr(jobs_mod, "IngestionJobsService", FakeIngestionJobsService)

        cp_mgr = MagicMock()
        monkeypatch.setattr(flow_mod, "create_checkpoint_manager", lambda _novel_id: cp_mgr)

        publisher = MagicMock()
        flow_mod._mark_job_as_failed(
            novel_id=5,
            _correlation_id=None,
            error="fatal",
            flow_start=0.0,
            logger=fake_logger,
            publisher=publisher,
        )

        assert session.commit_calls == 1
        cp_mgr.mark_stage_failed.assert_called_once_with("failed", "fatal")
        publisher.publish.assert_called_once()
