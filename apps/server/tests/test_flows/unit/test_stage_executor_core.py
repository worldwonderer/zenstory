from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

from flows.pipelines.stages import stage_executor as se_mod
from tests.test_flows.conftest import FakeTask


class _DummyPublisher:
    def __init__(self, _correlation_id, _logger):
        self.events = []
        self.completions = []

    def publish(self, event_type: str, **kwargs):
        self.events.append((event_type, kwargs))

    def publish_completion(self, novel_id, chapter_ids, result):
        self.completions.append((novel_id, chapter_ids, result))


class _FakeCheckpointManager:
    def __init__(self, checkpoints=None):
        self.checkpoints = checkpoints or {}
        self.completed_calls = []
        self.update_calls = []

    def get_checkpoint(self, stage: str):
        return self.checkpoints.get(stage)

    def mark_stage_completed(self, stage: str, data):
        self.completed_calls.append((stage, data))

    def update_checkpoint(self, stage: str, status=None, data=None, error=None):
        self.update_calls.append((stage, status, data, error))


class TestStageExecutorCore:
    def test_parse_cp_data_handles_variants(self):
        assert se_mod._parse_cp_data(None) == {}
        assert se_mod._parse_cp_data(SimpleNamespace(checkpoint_data={"a": 1})) == {"a": 1}
        assert se_mod._parse_cp_data(SimpleNamespace(checkpoint_data='{"a": 1}')) == {"a": 1}
        assert se_mod._parse_cp_data(SimpleNamespace(checkpoint_data="bad-json")) == {}

    def test_check_stage2_completion_with_feature_flags(self, monkeypatch):
        monkeypatch.setattr(se_mod, "get_run_logger", lambda: MagicMock())
        monkeypatch.setattr(se_mod, "ProgressPublisher", _DummyPublisher)

        checkpoints = {
            "stage2a": SimpleNamespace(stage_status="completed", checkpoint_data={"synopsis_generated": True, "stories_count": 2, "storylines_count": 1}),
            "stage2b": SimpleNamespace(stage_status="completed", checkpoint_data={"relationships_count": 2, "neo4j_persisted": True}),
            "stage2c": SimpleNamespace(stage_status="completed", checkpoint_data={"characters_built": True}),
        }
        cp = _FakeCheckpointManager(checkpoints)

        monkeypatch.setattr(se_mod.settings, "ENABLE_NOVEL_SYNOPSIS", True)
        monkeypatch.setattr(se_mod.settings, "ENABLE_STORY_AGGREGATION", True)
        monkeypatch.setattr(se_mod.settings, "ENABLE_STORYLINE_GENERATION", True)
        monkeypatch.setattr(se_mod.settings, "ENABLE_RELATIONSHIP_EXTRACTION", True)
        monkeypatch.setattr(se_mod.settings, "ENABLE_NEO4J_STORAGE", True)

        executor = se_mod.StageExecutor(1, [1, 2], cp, None)
        assert executor._check_stage2_completion() == (True, True, True)

    def test_check_stage2_completion_allows_zero_count_completed_checkpoints(self, monkeypatch):
        monkeypatch.setattr(se_mod, "get_run_logger", lambda: MagicMock())
        monkeypatch.setattr(se_mod, "ProgressPublisher", _DummyPublisher)

        checkpoints = {
            "stage2a": SimpleNamespace(stage_status="completed", checkpoint_data={"stories_count": 0, "storylines_count": 0}),
            "stage2b": SimpleNamespace(stage_status="completed", checkpoint_data={"relationships_count": 0, "neo4j_persisted": False}),
            "stage2c": SimpleNamespace(stage_status="completed", checkpoint_data={"characters_built": True}),
        }
        cp = _FakeCheckpointManager(checkpoints)

        monkeypatch.setattr(se_mod.settings, "ENABLE_NOVEL_SYNOPSIS", False)
        monkeypatch.setattr(se_mod.settings, "ENABLE_STORY_AGGREGATION", True)
        monkeypatch.setattr(se_mod.settings, "ENABLE_STORYLINE_GENERATION", True)
        monkeypatch.setattr(se_mod.settings, "ENABLE_RELATIONSHIP_EXTRACTION", True)
        monkeypatch.setattr(se_mod.settings, "ENABLE_NEO4J_STORAGE", True)

        executor = se_mod.StageExecutor(1, [1, 2], cp, None)
        assert executor._check_stage2_completion() == (True, True, True)

    def test_execute_parallel_stages_runs_subflows_when_not_done(self, monkeypatch):
        monkeypatch.setattr(se_mod, "get_run_logger", lambda: MagicMock())
        monkeypatch.setattr(se_mod, "ProgressPublisher", _DummyPublisher)
        monkeypatch.setattr(se_mod.settings, "ENABLE_ENTITY_EXTRACTION", True)

        story_task = FakeTask({"stories_count": 2, "storylines_count": 1, "synopsis_generated": True})
        character_task = FakeTask({"created_count": 4, "updated_count": 1, "failed_count": 0})
        monkeypatch.setattr(se_mod, "_task_run_story_aggregate", story_task)
        monkeypatch.setattr(se_mod, "_task_run_character_entity_build", character_task)

        executor = se_mod.StageExecutor(9, [11, 12], _FakeCheckpointManager(), "cid")
        story_result, character_result = executor._execute_parallel_stages(False, False)

        assert story_result["stories_count"] == 2
        assert character_result["created_count"] == 4
        assert len(story_task.submit_calls) == 1
        assert len(character_task.submit_calls) == 1

    def test_execute_parallel_stages_uses_checkpoint_when_done(self, monkeypatch):
        monkeypatch.setattr(se_mod, "get_run_logger", lambda: MagicMock())
        monkeypatch.setattr(se_mod, "ProgressPublisher", _DummyPublisher)

        checkpoints = {
            "stage2a": SimpleNamespace(stage_status="completed", checkpoint_data={"synopsis_generated": True, "stories_count": 3, "storylines_count": 5, "status": "completed"}),
            "stage2c": SimpleNamespace(stage_status="completed", checkpoint_data={"created_count": 1, "updated_count": 2, "failed_count": 0, "failed_characters": [], "status": "completed"}),
        }
        executor = se_mod.StageExecutor(1, [1], _FakeCheckpointManager(checkpoints), None)

        story_result, character_result = executor._execute_parallel_stages(True, True)

        assert story_result["stories_count"] == 3
        assert character_result["updated_count"] == 2

    def test_execute_relationship_stage_uses_subflow_or_checkpoint(self, monkeypatch):
        monkeypatch.setattr(se_mod, "get_run_logger", lambda: MagicMock())
        monkeypatch.setattr(se_mod, "ProgressPublisher", _DummyPublisher)

        relation_task = FakeTask({"relationships_count": 6, "neo4j_persisted": False, "neo4j_failed_chapters": [], "status": "completed"})
        monkeypatch.setattr(se_mod, "_task_run_relationship", relation_task)

        checkpoints = {
            "stage2b": SimpleNamespace(stage_status="completed", checkpoint_data={"relationships_count": 9, "neo4j_persisted": True, "neo4j_failed_chapters": [2], "status": "completed_with_errors"})
        }
        executor = se_mod.StageExecutor(1, [1, 2], _FakeCheckpointManager(checkpoints), None)

        fresh = executor._execute_relationship_stage(False)
        resumed = executor._execute_relationship_stage(True)

        assert fresh["relationships_count"] == 6
        assert resumed["relationships_count"] == 9

    def test_update_stage2_checkpoints_writes_all_stages(self, monkeypatch):
        monkeypatch.setattr(se_mod, "get_run_logger", lambda: MagicMock())
        monkeypatch.setattr(se_mod, "ProgressPublisher", _DummyPublisher)

        cp = _FakeCheckpointManager()
        executor = se_mod.StageExecutor(1, [1, 2], cp, None)
        executor._update_stage2_checkpoints(
            {"synopsis_generated": True, "stories_count": 2, "storylines_count": 3, "failed_stories": [], "status": "completed"},
            {"relationships_count": 4, "neo4j_persisted": False, "neo4j_failed_chapters": [2], "status": "completed_with_errors"},
            {"created_count": 5, "updated_count": 1, "failed_count": 0, "failed_characters": [], "status": "completed"},
        )

        stages = [s for s, _ in cp.completed_calls]
        assert stages == ["stage2a", "stage2b", "stage2c", "stage2"]

    def test_save_final_checkpoint_collects_final_metrics(self, monkeypatch):
        monkeypatch.setattr(se_mod, "get_run_logger", lambda: MagicMock())
        monkeypatch.setattr(se_mod, "ProgressPublisher", _DummyPublisher)

        cp = _FakeCheckpointManager()
        executor = se_mod.StageExecutor(3, [10, 20], cp, None)
        executor._save_final_checkpoint(
            stage1_result={"summaries_count": 2, "plots_count": 7, "mentions_extracted": True, "failed_count": 1, "failed_chapters": [9], "failed_mention_chapters": [10]},
            story_result={"synopsis_generated": True, "stories_count": 2, "storylines_count": 1, "failed_stories": ["s1"]},
            relationship_result={"relationships_count": 4, "neo4j_persisted": True, "neo4j_failed_chapters": [2]},
            character_entity_result={"created_count": 6, "updated_count": 2, "failed_count": 1, "failed_characters": ["赵四"]},
        )

        assert cp.completed_calls
        stage, payload = cp.completed_calls[0]
        assert stage == "completed"
        assert payload["novel_id"] == 3
        assert payload["chapters_count"] == 2
        assert payload["characters_created"] == 6
        assert payload["failed_chapters"] == [9]
        assert payload["neo4j_failed_chapters"] == [2]

    def test_derive_final_status_marks_completed_with_errors(self, monkeypatch):
        monkeypatch.setattr(se_mod, "get_run_logger", lambda: MagicMock())
        monkeypatch.setattr(se_mod, "ProgressPublisher", _DummyPublisher)

        executor = se_mod.StageExecutor(3, [10, 20], _FakeCheckpointManager(), None)
        status = executor._derive_final_status(
            {"failed_count": 1},
            {"failed_stories": []},
            {"neo4j_failed_chapters": []},
            {"failed_count": 0},
        )

        assert status == "completed_with_errors"

    def test_update_job_status_uses_completed_with_errors(self, monkeypatch):
        monkeypatch.setattr(se_mod, "get_run_logger", lambda: MagicMock())
        monkeypatch.setattr(se_mod, "ProgressPublisher", _DummyPublisher)

        captured = {}

        class _Svc:
            def get_latest_by_novel(self, _session, _novel_id):
                return SimpleNamespace(id=42)

            def update_processed(self, _session, job_id, **kwargs):
                captured["job_id"] = job_id
                captured["kwargs"] = kwargs

        class _SessionCtx:
            def __enter__(self):
                return SimpleNamespace(commit=lambda: None)

            def __exit__(self, exc_type, exc, tb):
                return False

        monkeypatch.setattr(se_mod, "get_prefect_db_session", lambda: _SessionCtx())
        monkeypatch.setitem(__import__("sys").modules, "services.material.ingestion_jobs_service", SimpleNamespace(IngestionJobsService=_Svc))

        executor = se_mod.StageExecutor(3, [10, 20], _FakeCheckpointManager(), None)
        executor._update_job_status(
            "completed_with_errors",
            {"failed_count": 2, "failed_chapters": [1], "failed_mention_chapters": [2]},
            {"failed_stories": ["story-1"]},
            {"neo4j_failed_chapters": [3]},
            {"failed_count": 1, "failed_characters": ["赵四"]},
        )

        assert captured["job_id"] == 42
        assert captured["kwargs"]["status"] == "completed_with_errors"
