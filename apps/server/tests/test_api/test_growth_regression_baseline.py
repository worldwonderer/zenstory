"""Regression baseline for key growth journey: register -> create project -> upgrade -> export."""

from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlmodel import Session, select

from models import UpgradeFunnelEvent, User


@pytest.mark.integration
async def test_growth_regression_baseline_register_project_upgrade_export(
    client: AsyncClient,
    db_session: Session,
    monkeypatch,
):
    """Keep a stable baseline for growth journey regressions."""
    monkeypatch.setenv("AUTH_REGISTER_INVITE_CODE_OPTIONAL", "true")

    async def _fake_send_verification_code(_email: str, language: str = "zh"):
        return True, None

    monkeypatch.setattr("api.auth.send_verification_code", _fake_send_verification_code)

    suffix = uuid4().hex[:8]
    username = f"growth_baseline_{suffix}"
    email = f"{username}@example.com"
    password = "Password123!"

    register_response = await client.post(
        "/api/auth/register",
        json={
            "username": username,
            "email": email,
            "password": password,
        },
    )
    assert register_response.status_code == 200

    user = db_session.exec(select(User).where(User.username == username)).first()
    assert user is not None

    # Registration keeps email unverified by default; mark verified for login in integration baseline.
    user.email_verified = True
    db_session.add(user)
    db_session.commit()

    login_response = await client.post(
        "/api/auth/login",
        data={"username": username, "password": password},
    )
    assert login_response.status_code == 200
    token = login_response.json()["access_token"]
    auth_headers = {"Authorization": f"Bearer {token}"}

    project_response = await client.post(
        "/api/v1/projects",
        headers=auth_headers,
        json={
            "name": "Growth Baseline Project",
            "project_type": "novel",
        },
    )
    assert project_response.status_code == 200
    project_id = project_response.json()["id"]

    create_file_response = await client.post(
        f"/api/v1/projects/{project_id}/files",
        headers=auth_headers,
        json={
            "title": "第一章",
            "file_type": "draft",
            "content": "这是关键增长链路的导出回归基线内容。",
        },
    )
    assert create_file_response.status_code == 200

    upgrade_event_response = await client.post(
        "/api/v1/subscription/upgrade-funnel-events",
        headers=auth_headers,
        json={
            "action": "click",
            "source": "dashboard_today_action",
            "surface": "page",
            "cta": "direct",
            "destination": "billing",
            "meta": {"baseline": "growth_journey"},
        },
    )
    assert upgrade_event_response.status_code == 201
    assert upgrade_event_response.json() == {"success": True}

    export_response = await client.get(
        f"/api/v1/projects/{project_id}/export/drafts",
        headers=auth_headers,
    )
    assert export_response.status_code == 200
    assert "attachment" in export_response.headers.get("content-disposition", "")
    exported_content = export_response.content.decode("utf-8-sig")
    assert "关键增长链路的导出回归基线内容" in exported_content

    event = db_session.exec(
        select(UpgradeFunnelEvent).where(
            UpgradeFunnelEvent.user_id == user.id,
            UpgradeFunnelEvent.source == "dashboard_today_action",
        )
    ).first()
    assert event is not None
    assert event.destination == "billing"

