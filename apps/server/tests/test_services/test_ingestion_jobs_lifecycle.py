from __future__ import annotations

import json

import pytest
from sqlmodel import Session

from models.material_models import IngestionJob, Novel
from services.material.ingestion_jobs_service import IngestionJobsService


@pytest.fixture
def ingestion_jobs_svc() -> IngestionJobsService:
    return IngestionJobsService()


@pytest.fixture
def test_job(db_session: Session) -> IngestionJob:
    novel = Novel(user_id="job-lifecycle-user", title="Lifecycle Novel")
    db_session.add(novel)
    db_session.commit()
    db_session.refresh(novel)

    job = IngestionJob(
        novel_id=novel.id,
        source_path="/tmp/lifecycle.txt",
        status="pending",
        total_chapters=10,
        processed_chapters=0,
    )
    db_session.add(job)
    db_session.commit()
    db_session.refresh(job)
    return job


@pytest.mark.unit
def test_update_status_sets_started_and_completed_timestamps(
    db_session: Session,
    ingestion_jobs_svc: IngestionJobsService,
    test_job: IngestionJob,
) -> None:
    assert test_job.started_at is None
    assert test_job.completed_at is None

    ingestion_jobs_svc.update_status(db_session, test_job.id, "processing")
    db_session.refresh(test_job)
    assert test_job.started_at is not None
    assert test_job.completed_at is None

    ingestion_jobs_svc.update_status(db_session, test_job.id, "failed")
    db_session.refresh(test_job)
    assert test_job.completed_at is not None


@pytest.mark.unit
def test_update_processed_is_monotonic_and_writes_stage_payload(
    db_session: Session,
    ingestion_jobs_svc: IngestionJobsService,
    test_job: IngestionJob,
) -> None:
    ingestion_jobs_svc.update_processed(
        db_session,
        test_job.id,
        processed_chapters=6,
        status="processing",
        stage="stage1",
        stage_status="processing",
        stage_data={"batch": 1},
    )
    db_session.refresh(test_job)
    assert test_job.processed_chapters == 6
    assert test_job.stage_progress is not None
    stage_progress = json.loads(test_job.stage_progress)
    assert stage_progress["stage1"]["status"] == "processing"
    assert stage_progress["stage1"]["batch"] == 1

    ingestion_jobs_svc.update_processed(
        db_session,
        test_job.id,
        processed_chapters=2,
    )
    db_session.refresh(test_job)
    assert test_job.processed_chapters == 6


@pytest.mark.unit
def test_update_processed_writes_error_details(
    db_session: Session,
    ingestion_jobs_svc: IngestionJobsService,
    test_job: IngestionJob,
) -> None:
    ingestion_jobs_svc.update_processed(
        db_session,
        test_job.id,
        status="failed",
        stage="failed",
        stage_status="failed",
        error_message="boom",
        error_details={"stage": "stage1", "message": "boom"},
    )
    db_session.refresh(test_job)

    assert test_job.status == "failed"
    assert test_job.error_message == "boom"
    assert test_job.error_details is not None
    parsed = json.loads(test_job.error_details)
    assert parsed["stage"] == "stage1"
