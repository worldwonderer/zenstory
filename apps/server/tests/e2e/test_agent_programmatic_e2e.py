"""
Request-driven programmatic agent API e2e workflows.

These tests bridge user-managed Agent API keys with the external agent API
surface that authenticates via X-Agent-API-Key.
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlmodel import Session

from models import User
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
async def test_agent_api_key_management_roundtrip_create_list_update_regenerate_and_delete(
    client: AsyncClient,
    db_session: Session,
):
    user = await _create_user(db_session, prefix="agent_key_flow")
    login_payload = await _login(client, identifier=user.username)
    headers = _auth_headers(login_payload["access_token"])

    create_response = await client.post(
        "/api/v1/agent-api-keys",
        json={
            "name": "Programmatic Key",
            "description": "e2e key",
            "scopes": ["read", "write"],
            "project_ids": ["project-alpha"],
        },
        headers=headers,
    )
    assert create_response.status_code == 201
    created_key = create_response.json()
    assert created_key["name"] == "Programmatic Key"
    assert created_key["key"].startswith("eg_")

    list_response = await client.get("/api/v1/agent-api-keys", headers=headers)
    assert list_response.status_code == 200
    list_payload = list_response.json()
    assert list_payload["total"] == 1
    assert list_payload["keys"][0]["id"] == created_key["id"]

    get_response = await client.get(f"/api/v1/agent-api-keys/{created_key['id']}", headers=headers)
    assert get_response.status_code == 200
    assert get_response.json()["project_ids"] == ["project-alpha"]

    update_response = await client.put(
        f"/api/v1/agent-api-keys/{created_key['id']}",
        json={"name": "Updated Programmatic Key", "is_active": False},
        headers=headers,
    )
    assert update_response.status_code == 200
    assert update_response.json()["name"] == "Updated Programmatic Key"
    assert update_response.json()["is_active"] is False

    reactivate_response = await client.put(
        f"/api/v1/agent-api-keys/{created_key['id']}",
        json={"is_active": True},
        headers=headers,
    )
    assert reactivate_response.status_code == 200
    assert reactivate_response.json()["is_active"] is True

    regenerate_response = await client.post(
        f"/api/v1/agent-api-keys/{created_key['id']}/regenerate",
        headers=headers,
    )
    assert regenerate_response.status_code == 200
    assert regenerate_response.json()["key"].startswith("eg_")
    assert regenerate_response.json()["key"] != created_key["key"]

    delete_response = await client.delete(f"/api/v1/agent-api-keys/{created_key['id']}", headers=headers)
    assert delete_response.status_code == 200

    list_after_delete = await client.get("/api/v1/agent-api-keys", headers=headers)
    assert list_after_delete.status_code == 200
    assert list_after_delete.json()["total"] == 0


@pytest.mark.asyncio
async def test_agent_programmatic_projects_and_files_roundtrip_honors_project_restrictions(
    client: AsyncClient,
    db_session: Session,
):
    user = await _create_user(db_session, prefix="agent_api_flow")
    login_payload = await _login(client, identifier=user.email)
    user_headers = _auth_headers(login_payload["access_token"])

    create_alpha = await client.post(
        "/api/v1/projects",
        json={"name": "Alpha Project", "project_type": "novel"},
        headers=user_headers,
    )
    create_beta = await client.post(
        "/api/v1/projects",
        json={"name": "Beta Project", "project_type": "novel"},
        headers=user_headers,
    )
    assert create_alpha.status_code == 200
    assert create_beta.status_code == 200
    alpha_project = create_alpha.json()
    beta_project = create_beta.json()

    key_response = await client.post(
        "/api/v1/agent-api-keys",
        json={
            "name": "Scoped Programmatic Key",
            "scopes": ["read", "write"],
            "project_ids": [alpha_project["id"]],
        },
        headers=user_headers,
    )
    assert key_response.status_code == 201
    scoped_key = key_response.json()["key"]
    agent_headers = {"X-Agent-API-Key": scoped_key}

    projects_response = await client.get("/api/v1/agent/projects", headers=agent_headers)
    assert projects_response.status_code == 200
    projects_payload = projects_response.json()
    assert len(projects_payload) == 1
    assert projects_payload[0]["id"] == alpha_project["id"]

    create_file_response = await client.post(
        f"/api/v1/agent/projects/{alpha_project['id']}/files",
        json={"title": "Agent Draft", "file_type": "draft", "content": "Agent-created content"},
        headers=agent_headers,
    )
    assert create_file_response.status_code == 200
    created_file = create_file_response.json()
    assert created_file["title"] == "Agent Draft"

    get_file_response = await client.get(
        f"/api/v1/agent/files/{created_file['id']}",
        headers=agent_headers,
    )
    assert get_file_response.status_code == 200
    assert get_file_response.json()["content"] == "Agent-created content"

    update_file_response = await client.put(
        f"/api/v1/agent/files/{created_file['id']}",
        json={"content": "Agent-updated content"},
        headers=agent_headers,
    )
    assert update_file_response.status_code == 200
    assert update_file_response.json()["content"] == "Agent-updated content"

    forbidden_project_response = await client.get(
        f"/api/v1/agent/projects/{beta_project['id']}",
        headers=agent_headers,
    )
    assert forbidden_project_response.status_code == 403

    delete_file_response = await client.delete(
        f"/api/v1/agent/files/{created_file['id']}",
        headers=agent_headers,
    )
    assert delete_file_response.status_code == 200

    missing_after_delete = await client.get(
        f"/api/v1/agent/files/{created_file['id']}",
        headers=agent_headers,
    )
    assert missing_after_delete.status_code == 404
