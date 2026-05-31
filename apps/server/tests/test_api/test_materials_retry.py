from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlmodel import select

import api.materials.upload as materials_upload_api
from models import User
from models.material_models import IngestionJob, Novel
from models.subscription import SubscriptionPlan, UsageQuota, UserSubscription
from services.core.auth_service import hash_password


@pytest.fixture(autouse=True)
def stub_retry_flow_dispatch(monkeypatch):
    async def _fake_start_flow_deployment(*args, **kwargs):
        return "flow-run-test"

    monkeypatch.setattr(
        materials_upload_api,
        "_start_flow_deployment",
        _fake_start_flow_deployment,
    )


async def _create_test_user_and_token(
    client: AsyncClient,
    db_session,
    username: str,
) -> tuple[User, str]:
    user = User(
        username=username,
        email=f"{username}@example.com",
        hashed_password=hash_password("password123"),
        email_verified=True,
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()

    paid_plan = db_session.exec(
        select(SubscriptionPlan).where(SubscriptionPlan.name == "pro")
    ).first()
    if paid_plan is None:
        paid_plan = SubscriptionPlan(
            name="pro",
            display_name="Pro",
            display_name_en="Pro",
            price_monthly_cents=4900,
            price_yearly_cents=39900,
            features={
                "materials_library_access": True,
                "material_uploads": 5,
                "material_decompositions": 5,
                "ai_conversations_per_day": -1,
                "max_projects": -1,
            },
            is_active=True,
        )
        db_session.add(paid_plan)
        db_session.commit()
        db_session.refresh(paid_plan)

    existing_subscription = db_session.exec(
        select(UserSubscription).where(UserSubscription.user_id == user.id)
    ).first()
    if existing_subscription is None:
        now = datetime.utcnow()
        db_session.add(
            UserSubscription(
                user_id=user.id,
                plan_id=paid_plan.id,
                status="active",
                current_period_start=now,
                current_period_end=now + timedelta(days=30),
            )
        )
        db_session.commit()

    login_response = await client.post(
        "/api/auth/login",
        data={"username": username, "password": "password123"},
    )
    assert login_response.status_code == 200
    token = login_response.json()["access_token"]
    return user, token


@pytest.mark.integration
async def test_retry_material_job_rejects_running_job(client: AsyncClient, db_session):
    user, token = await _create_test_user_and_token(client, db_session, "retrybusy1")

    novel = Novel(user_id=user.id, title="Retry Busy Novel", author="Tester")
    db_session.add(novel)
    db_session.commit()
    db_session.refresh(novel)

    running_job = IngestionJob(
        novel_id=novel.id,
        source_path="/tmp/test.txt",
        status="processing",
        total_chapters=10,
        processed_chapters=1,
    )
    db_session.add(running_job)
    db_session.commit()

    response = await client.post(
        f"/api/v1/materials/{novel.id}/retry",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 409


@pytest.mark.integration
async def test_retry_material_job_requires_paid_materials_access(client: AsyncClient, db_session):
    free_user = User(
        username="retryfree1",
        email="retryfree1@example.com",
        hashed_password=hash_password("password123"),
        email_verified=True,
        is_active=True,
    )
    db_session.add(free_user)
    db_session.commit()
    db_session.refresh(free_user)

    novel = Novel(user_id=free_user.id, title="Retry Free Novel", author="Tester")
    db_session.add(novel)
    db_session.commit()
    db_session.refresh(novel)

    failed_job = IngestionJob(
        novel_id=novel.id,
        source_path="/tmp/test.txt",
        status="failed",
        total_chapters=10,
        processed_chapters=0,
        error_message="boom",
    )
    db_session.add(failed_job)
    db_session.commit()

    login_response = await client.post(
        "/api/auth/login",
        data={"username": free_user.username, "password": "password123"},
    )
    assert login_response.status_code == 200
    token = login_response.json()["access_token"]

    response = await client.post(
        f"/api/v1/materials/{novel.id}/retry",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 402
    assert response.json()["error_code"] == "ERR_FEATURE_NOT_INCLUDED"


@pytest.mark.integration
async def test_retry_material_job_consumes_quota_for_regular_failed_jobs(client: AsyncClient, db_session):
    user, token = await _create_test_user_and_token(client, db_session, "retryquota1")

    now = datetime.utcnow()
    quota = UsageQuota(
        user_id=user.id,
        period_start=now,
        period_end=now + timedelta(days=30),
        ai_conversations_used=0,
        material_decompositions_used=4,
        monthly_period_start=now - timedelta(days=1),
        monthly_period_end=now + timedelta(days=30),
        last_reset_at=now,
    )
    db_session.add(quota)
    db_session.commit()

    novel = Novel(user_id=user.id, title="Retry Charged Novel", author="Tester")
    db_session.add(novel)
    db_session.commit()
    db_session.refresh(novel)

    failed_job = IngestionJob(
        novel_id=novel.id,
        source_path="/tmp/test.txt",
        status="failed",
        total_chapters=10,
        processed_chapters=0,
        error_message="flow failed",
        error_details='{"stage":"flow","message":"flow failed"}',
    )
    db_session.add(failed_job)
    db_session.commit()

    response = await client.post(
        f"/api/v1/materials/{novel.id}/retry",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    db_session.refresh(quota)
    assert quota.material_decompositions_used == 5


@pytest.mark.integration
async def test_retry_material_job_does_not_consume_quota_when_dispatch_fails(
    client: AsyncClient, db_session, monkeypatch
):
    async def _failed_start_flow_deployment(*args, **kwargs):
        return None

    monkeypatch.setattr(
        materials_upload_api,
        "_start_flow_deployment",
        _failed_start_flow_deployment,
    )

    user, token = await _create_test_user_and_token(client, db_session, "retrydispatchfail")

    now = datetime.utcnow()
    quota = UsageQuota(
        user_id=user.id,
        period_start=now,
        period_end=now + timedelta(days=30),
        ai_conversations_used=0,
        material_decompositions_used=4,
        monthly_period_start=now - timedelta(days=1),
        monthly_period_end=now + timedelta(days=30),
        last_reset_at=now,
    )
    db_session.add(quota)
    db_session.commit()

    novel = Novel(user_id=user.id, title="Retry Dispatch Failure Novel", author="Tester")
    db_session.add(novel)
    db_session.commit()
    db_session.refresh(novel)

    failed_job = IngestionJob(
        novel_id=novel.id,
        source_path="/tmp/test.txt",
        status="failed",
        total_chapters=10,
        processed_chapters=0,
        error_message="flow failed",
        error_details='{"stage":"flow","message":"flow failed"}',
    )
    db_session.add(failed_job)
    db_session.commit()

    response = await client.post(
        f"/api/v1/materials/{novel.id}/retry",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 503
    db_session.refresh(quota)
    assert quota.material_decompositions_used == 4

    latest_job = db_session.exec(
        select(IngestionJob)
        .where(IngestionJob.novel_id == novel.id)
        .order_by(IngestionJob.created_at.desc())
    ).first()
    assert latest_job is not None
    assert latest_job.status == "failed"


@pytest.mark.integration
async def test_retry_material_job_does_not_consume_quota_for_compensatory_failures(
    client: AsyncClient, db_session
):
    user, token = await _create_test_user_and_token(client, db_session, "retryquota2")

    now = datetime.utcnow()
    quota = UsageQuota(
        user_id=user.id,
        period_start=now,
        period_end=now + timedelta(days=30),
        ai_conversations_used=0,
        material_decompositions_used=5,
        monthly_period_start=now - timedelta(days=1),
        monthly_period_end=now + timedelta(days=30),
        last_reset_at=now,
    )
    db_session.add(quota)
    db_session.commit()

    novel = Novel(user_id=user.id, title="Retry Compensated Novel", author="Tester")
    db_session.add(novel)
    db_session.commit()
    db_session.refresh(novel)

    failed_job = IngestionJob(
        novel_id=novel.id,
        source_path="/tmp/test.txt",
        status="failed",
        total_chapters=10,
        processed_chapters=0,
        error_message="deployment startup failed",
        error_details='{"stage":"deployment_start","message":"deployment startup failed"}',
    )
    db_session.add(failed_job)
    db_session.commit()

    response = await client.post(
        f"/api/v1/materials/{novel.id}/retry",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    db_session.refresh(quota)
    assert quota.material_decompositions_used == 5


@pytest.mark.integration
async def test_retry_material_job_rejects_when_quota_cannot_be_consumed(
    client: AsyncClient, db_session, monkeypatch
):
    """If quota consumption fails, retry must reject (402) and must NOT proceed
    to dispatch or refund quota it never consumed.

    Regression: when consume_quota returned False but a concurrent decrement
    made check_feature_quota report allowed=True, the old code fell through to
    dispatch without charging quota, and a dispatch failure then refunded a unit
    that was never consumed (refund-leak / free decomposition).
    """
    user, token = await _create_test_user_and_token(client, db_session, "retryconsumefail")

    now = datetime.utcnow()
    quota = UsageQuota(
        user_id=user.id,
        period_start=now,
        period_end=now + timedelta(days=30),
        ai_conversations_used=0,
        material_decompositions_used=5,
        monthly_period_start=now - timedelta(days=1),
        monthly_period_end=now + timedelta(days=30),
        last_reset_at=now,
    )
    db_session.add(quota)
    db_session.commit()

    novel = Novel(user_id=user.id, title="Retry Consume Fail Novel", author="Tester")
    db_session.add(novel)
    db_session.commit()
    db_session.refresh(novel)

    failed_job = IngestionJob(
        novel_id=novel.id,
        source_path="/tmp/test.txt",
        status="failed",
        total_chapters=10,
        processed_chapters=0,
        error_message="flow failed",
        error_details='{"stage":"flow","message":"flow failed"}',
    )
    db_session.add(failed_job)
    db_session.commit()

    # Simulate the race: the pre-check passes, consume_quota fails, but a
    # concurrent decrement makes check_feature_quota report allowed=True.
    monkeypatch.setattr(materials_upload_api, "check_quota", lambda *a, **k: None)
    monkeypatch.setattr(materials_upload_api, "consume_quota", lambda *a, **k: False)
    monkeypatch.setattr(
        materials_upload_api.quota_service,
        "check_feature_quota",
        lambda *a, **k: (True, 4, 5),
    )

    release_calls: list[int] = []
    monkeypatch.setattr(
        materials_upload_api.quota_service,
        "release_feature_quota",
        lambda *a, **k: release_calls.append(1),
    )

    dispatch_calls: list[int] = []

    async def _tracking_dispatch(*args, **kwargs):
        dispatch_calls.append(1)
        return "flow-run-test"

    monkeypatch.setattr(materials_upload_api, "_start_flow_deployment", _tracking_dispatch)

    response = await client.post(
        f"/api/v1/materials/{novel.id}/retry",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 402
    assert dispatch_calls == []  # never proceeded to dispatch
    assert release_calls == []  # never refunded quota it did not consume
    db_session.refresh(quota)
    assert quota.material_decompositions_used == 5  # unchanged
