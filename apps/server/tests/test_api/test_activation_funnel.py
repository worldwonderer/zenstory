"""
Integration tests for activation funnel tracking.
"""

import pytest
from httpx import AsyncClient
from sqlmodel import Session, select

from models import (
    ACTIVATION_EVENT_FIRST_AI_ACTION_ACCEPTED,
    ACTIVATION_EVENT_FIRST_FILE_SAVED,
    ACTIVATION_EVENT_PROJECT_CREATED,
    ACTIVATION_EVENT_SIGNUP_SUCCESS,
    ActivationEvent,
    User,
)
from services.core.auth_service import hash_password
from services.features.activation_event_service import activation_event_service


async def _create_user(
    db_session: Session,
    *,
    username: str,
    email: str,
    password: str = "password123",
    is_superuser: bool = False,
) -> User:
    user = User(
        username=username,
        email=email,
        hashed_password=hash_password(password),
        email_verified=True,
        is_active=True,
        is_superuser=is_superuser,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


async def _login(client: AsyncClient, username: str, password: str = "password123") -> str:
    response = await client.post(
        "/api/auth/login",
        data={"username": username, "password": password},
    )
    assert response.status_code == 200
    return response.json()["access_token"]


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.integration
async def test_register_records_signup_activation_event(client: AsyncClient, db_session: Session, monkeypatch):
    monkeypatch.setenv("AUTH_REGISTER_INVITE_CODE_OPTIONAL", "true")

    async def _fake_send_verification_code(_email: str, language: str = "zh"):
        return True, None

    monkeypatch.setattr("api.auth.send_verification_code", _fake_send_verification_code)

    response = await client.post(
        "/api/auth/register",
        json={
            "username": "new_activation_user",
            "email": "new_activation_user@example.com",
            "password": "password123",
        },
    )
    assert response.status_code == 200

    user = db_session.exec(
        select(User).where(User.username == "new_activation_user")
    ).first()
    assert user is not None

    signup_event = db_session.exec(
        select(ActivationEvent).where(
            ActivationEvent.user_id == user.id,
            ActivationEvent.event_name == ACTIVATION_EVENT_SIGNUP_SUCCESS,
        )
    ).first()
    assert signup_event is not None


@pytest.mark.integration
async def test_project_and_file_updates_record_activation_events(client: AsyncClient, db_session: Session):
    await _create_user(
        db_session,
        username="activation_flow_user",
        email="activation_flow_user@example.com",
    )
    token = await _login(client, "activation_flow_user")
    headers = _auth_headers(token)

    project_resp = await client.post(
        "/api/v1/projects",
        json={"name": "Activation Project", "project_type": "novel"},
        headers=headers,
    )
    assert project_resp.status_code == 200
    project_id = project_resp.json()["id"]

    file_resp = await client.post(
        f"/api/v1/projects/{project_id}/files",
        json={"title": "Chapter 1", "file_type": "draft", "content": ""},
        headers=headers,
    )
    assert file_resp.status_code == 200
    file_id = file_resp.json()["id"]

    save_resp = await client.put(
        f"/api/v1/files/{file_id}",
        json={"content": "first save from user"},
        headers=headers,
    )
    assert save_resp.status_code == 200

    ai_accept_resp = await client.put(
        f"/api/v1/files/{file_id}",
        json={
            "content": "first save from user with ai accepted change",
            "change_type": "ai_edit",
            "change_source": "ai",
            "change_summary": "review accepted",
        },
        headers=headers,
    )
    assert ai_accept_resp.status_code == 200

    # Repeat user save should not create duplicate first_file_saved event.
    second_save_resp = await client.put(
        f"/api/v1/files/{file_id}",
        json={"content": "second user save", "change_type": "edit", "change_source": "user"},
        headers=headers,
    )
    assert second_save_resp.status_code == 200

    events = db_session.exec(
        select(ActivationEvent).where(ActivationEvent.project_id == project_id)
    ).all()
    names = [event.event_name for event in events]

    assert ACTIVATION_EVENT_PROJECT_CREATED in names
    assert ACTIVATION_EVENT_FIRST_FILE_SAVED in names
    assert ACTIVATION_EVENT_FIRST_AI_ACTION_ACCEPTED in names
    assert names.count(ACTIVATION_EVENT_FIRST_FILE_SAVED) == 1


@pytest.mark.integration
async def test_admin_activation_funnel_returns_step_counts(client: AsyncClient, db_session: Session):
    await _create_user(
        db_session,
        username="activation_admin",
        email="activation_admin@example.com",
        is_superuser=True,
    )
    user_a = await _create_user(
        db_session,
        username="activation_user_a",
        email="activation_user_a@example.com",
    )
    user_b = await _create_user(
        db_session,
        username="activation_user_b",
        email="activation_user_b@example.com",
    )

    activation_event_service.record_once(
        db_session, user_id=user_a.id, event_name=ACTIVATION_EVENT_SIGNUP_SUCCESS
    )
    activation_event_service.record_once(
        db_session, user_id=user_a.id, event_name=ACTIVATION_EVENT_PROJECT_CREATED
    )
    activation_event_service.record_once(
        db_session, user_id=user_a.id, event_name=ACTIVATION_EVENT_FIRST_FILE_SAVED
    )
    activation_event_service.record_once(
        db_session, user_id=user_a.id, event_name=ACTIVATION_EVENT_FIRST_AI_ACTION_ACCEPTED
    )
    activation_event_service.record_once(
        db_session, user_id=user_b.id, event_name=ACTIVATION_EVENT_SIGNUP_SUCCESS
    )

    admin_token = await _login(client, "activation_admin")

    response = await client.get(
        "/api/admin/dashboard/activation-funnel?days=30",
        headers=_auth_headers(admin_token),
    )
    assert response.status_code == 200
    data = response.json()

    assert data["window_days"] == 30
    assert 0 <= data["activation_rate"] <= 1

    steps = data["steps"]
    assert [step["event_name"] for step in steps] == [
        ACTIVATION_EVENT_SIGNUP_SUCCESS,
        ACTIVATION_EVENT_PROJECT_CREATED,
        ACTIVATION_EVENT_FIRST_FILE_SAVED,
        ACTIVATION_EVENT_FIRST_AI_ACTION_ACCEPTED,
    ]
    # In xdist runs, other workers may add events into the shared SQLite DB.
    # Ensure this test's events are reflected without assuming global exclusivity.
    assert steps[0]["users"] >= 2
    assert steps[1]["users"] >= 1
    assert steps[2]["users"] >= 1
    assert steps[3]["users"] >= 1


@pytest.mark.integration
async def test_activation_guide_defaults_to_next_project_step(client: AsyncClient, db_session: Session):
    await _create_user(
        db_session,
        username="activation_guide_user",
        email="activation_guide_user@example.com",
    )
    token = await _login(client, "activation_guide_user")

    response = await client.get(
        "/api/v1/activation/guide",
        headers=_auth_headers(token),
    )
    assert response.status_code == 200
    data = response.json()

    assert data["total_steps"] == 4
    assert data["completed_steps"] >= 1
    assert data["next_event_name"] == ACTIVATION_EVENT_PROJECT_CREATED
    assert data["next_action"] == "/dashboard"
    assert data["is_activated"] is False


@pytest.mark.integration
async def test_activation_guide_marks_user_activated_after_all_milestones(client: AsyncClient, db_session: Session):
    await _create_user(
        db_session,
        username="activation_guide_user_done",
        email="activation_guide_user_done@example.com",
    )
    token = await _login(client, "activation_guide_user_done")
    headers = _auth_headers(token)

    project_resp = await client.post(
        "/api/v1/projects",
        json={"name": "Guide Project", "project_type": "novel"},
        headers=headers,
    )
    assert project_resp.status_code == 200
    project_id = project_resp.json()["id"]

    file_resp = await client.post(
        f"/api/v1/projects/{project_id}/files",
        json={"title": "Guide Chapter", "file_type": "draft", "content": ""},
        headers=headers,
    )
    assert file_resp.status_code == 200
    file_id = file_resp.json()["id"]

    first_save = await client.put(
        f"/api/v1/files/{file_id}",
        json={"content": "first save"},
        headers=headers,
    )
    assert first_save.status_code == 200

    ai_accept = await client.put(
        f"/api/v1/files/{file_id}",
        json={
            "content": "first ai accepted",
            "change_type": "ai_edit",
            "change_source": "ai",
            "change_summary": "accepted",
        },
        headers=headers,
    )
    assert ai_accept.status_code == 200

    response = await client.get(
        "/api/v1/activation/guide",
        headers=headers,
    )
    assert response.status_code == 200
    data = response.json()

    assert data["completed_steps"] == data["total_steps"] == 4
    assert data["completion_rate"] == 1.0
    assert data["is_activated"] is True
    assert data["next_event_name"] is None
    assert data["next_action"] is None
