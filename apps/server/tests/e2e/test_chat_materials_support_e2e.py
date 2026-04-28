"""
Request-driven chat feedback and materials internal download e2e workflows.
"""

from __future__ import annotations

import json
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlmodel import Session

from models import ChatMessage, ChatSession, Project, User
from services.core.auth_service import hash_password

pytestmark = pytest.mark.e2e


def _identity(prefix: str) -> tuple[str, str]:
    suffix = uuid4().hex[:8]
    username = f"{prefix}_{suffix}"
    return username, f"{username}@example.com"


async def _create_user(
    db_session: Session,
    *,
    prefix: str,
    password: str = "password123",
) -> User:
    username, email = _identity(prefix)
    user = User(
        username=username,
        email=email,
        hashed_password=hash_password(password),
        email_verified=True,
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


async def _login(client: AsyncClient, *, identifier: str, password: str = "password123") -> dict:
    response = await client.post(
        "/api/auth/login",
        data={"username": identifier, "password": password},
    )
    assert response.status_code == 200
    return response.json()


def _auth_headers(access_token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {access_token}"}


@pytest.mark.asyncio
async def test_chat_feedback_roundtrip_updates_recent_history_metadata(
    client: AsyncClient,
    db_session: Session,
):
    user = await _create_user(db_session, prefix="chat_feedback")
    login_payload = await _login(client, identifier=user.username)
    headers = _auth_headers(login_payload["access_token"])

    project = Project(
        owner_id=user.id,
        name="Chat Feedback Project",
        description="Chat feedback e2e",
    )
    db_session.add(project)
    db_session.commit()
    db_session.refresh(project)

    session = ChatSession(
        user_id=user.id,
        project_id=project.id,
        title="Feedback Session",
        is_active=True,
        message_count=1,
    )
    db_session.add(session)
    db_session.commit()
    db_session.refresh(session)

    message = ChatMessage(
        session_id=session.id,
        role="assistant",
        content="请给这条回复打分",
        message_metadata=json.dumps({"source": "e2e"}, ensure_ascii=False),
    )
    db_session.add(message)
    db_session.commit()
    db_session.refresh(message)

    feedback_response = await client.post(
        f"/api/v1/chat/messages/{message.id}/feedback",
        json={"vote": "up", "preset": "helpful", "comment": "很有帮助"},
        headers=headers,
    )
    assert feedback_response.status_code == 200
    feedback_payload = feedback_response.json()
    assert feedback_payload["message_id"] == message.id
    assert feedback_payload["feedback"]["vote"] == "up"

    recent_response = await client.get(
        f"/api/v1/chat/session/{project.id}/recent?limit=5",
        headers=headers,
    )
    assert recent_response.status_code == 200
    recent_payload = recent_response.json()
    assert len(recent_payload) == 1
    metadata = json.loads(recent_payload[0]["metadata"])
    assert metadata["source"] == "e2e"
    assert metadata["feedback"]["vote"] == "up"
    assert metadata["feedback"]["preset"] == "helpful"
    assert metadata["feedback"]["comment"] == "很有帮助"


@pytest.mark.asyncio
async def test_materials_internal_worker_download_roundtrip(
    client: AsyncClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
):
    from config.material_settings import material_settings

    user = await _create_user(db_session, prefix="internal_materials")
    monkeypatch.setenv("MATERIAL_INTERNAL_TOKEN", "worker-token")
    monkeypatch.setattr(material_settings, "UPLOAD_FOLDER", str(tmp_path))

    filename = f"{user.id}_20260405_test.txt"
    file_path = tmp_path / filename
    file_path.write_text("internal worker download content", encoding="utf-8")

    response = await client.get(
        f"/api/v1/materials/internal/system/files/{filename}",
        params={"user_id": user.id},
        headers={"X-Internal-Token": "worker-token"},
    )

    assert response.status_code == 200
    assert response.text == "internal worker download content"
