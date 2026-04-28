"""
Focused E2E contracts for auth/session and project/file-tree flows.

These tests pin the backend contracts that default auth/session/projects/smoke
browser lanes rely on:
- login + me + refresh-token rotation
- project creation/list/get/delete
- default project naming and file-tree visibility
"""

from __future__ import annotations

from typing import Any

import pytest
from httpx import AsyncClient
from sqlmodel import Session

from .test_core_api_e2e import (
    _auth_headers,
    _create_file,
    _create_project,
    _create_user,
    _login,
)

pytestmark = pytest.mark.e2e


def _collect_titles(nodes: list[dict[str, Any]]) -> list[str]:
    titles: list[str] = []
    for node in nodes:
        title = node.get("title")
        if isinstance(title, str):
            titles.append(title)
        children = node.get("children")
        if isinstance(children, list):
            titles.extend(_collect_titles(children))
    return titles


@pytest.mark.asyncio
async def test_auth_contract_supports_me_and_refresh_rotation(
    client: AsyncClient,
    db_session: Session,
):
    user = await _create_user(db_session, prefix="auth_contract")

    login_by_email = await _login(client, identifier=user.email)
    assert login_by_email["token_type"] == "bearer"
    assert login_by_email["refresh_token"]

    me_response = await client.get(
        "/api/auth/me",
        headers=_auth_headers(login_by_email["access_token"]),
    )
    assert me_response.status_code == 200
    me_payload = me_response.json()
    assert me_payload["id"] == user.id
    assert me_payload["username"] == user.username
    assert me_payload["email"] == user.email

    refresh_response = await client.post(
        "/api/auth/refresh",
        json={"refresh_token": login_by_email["refresh_token"]},
    )
    assert refresh_response.status_code == 200
    refreshed_payload = refresh_response.json()
    assert refreshed_payload["refresh_token"] != login_by_email["refresh_token"]
    assert refreshed_payload["access_token"]

    replay_response = await client.post(
        "/api/auth/refresh",
        json={"refresh_token": login_by_email["refresh_token"]},
    )
    assert replay_response.status_code == 401

    login_by_username = await _login(client, identifier=user.username)
    assert login_by_username["access_token"]


@pytest.mark.asyncio
async def test_projects_contract_supports_default_naming_list_delete_and_file_tree(
    client: AsyncClient,
    db_session: Session,
):
    user = await _create_user(db_session, prefix="projects_contract")
    login_payload = await _login(client, identifier=user.email)
    headers = _auth_headers(login_payload["access_token"])

    unnamed_response = await client.post(
        "/api/v1/projects",
        json={"description": "screenplay without explicit name", "project_type": "screenplay"},
        headers={**headers, "Accept-Language": "en-US,en;q=0.9"},
    )
    assert unnamed_response.status_code == 200
    unnamed_project = unnamed_response.json()
    assert unnamed_project["name"]
    assert unnamed_project["project_type"] == "screenplay"

    named_project = await _create_project(
        client,
        login_payload["access_token"],
        name="Contract Novel Project",
        project_type="novel",
    )

    list_response = await client.get("/api/v1/projects", headers=headers)
    assert list_response.status_code == 200
    list_payload = list_response.json()
    ids = {project["id"] for project in list_payload}
    assert unnamed_project["id"] in ids
    assert named_project["id"] in ids
    assert {project["project_type"] for project in list_payload} >= {"screenplay", "novel"}

    get_response = await client.get(f"/api/v1/projects/{named_project['id']}", headers=headers)
    assert get_response.status_code == 200
    assert get_response.json()["name"] == "Contract Novel Project"

    created_file = await _create_file(
        client,
        login_payload["access_token"],
        project_id=named_project["id"],
        title="Chapter Contract 1",
        content="contract draft body",
    )

    tree_response = await client.get(
        f"/api/v1/projects/{named_project['id']}/file-tree",
        headers=headers,
    )
    assert tree_response.status_code == 200
    tree_payload = tree_response.json()["tree"]
    assert len(tree_payload) >= 4
    root_folders = [item for item in tree_payload if item.get("file_type") == "folder"]
    assert len(root_folders) >= 4
    assert "Chapter Contract 1" in _collect_titles(tree_payload)
    assert all(node.get("content", "") == "" for node in tree_payload)

    tree_with_content = await client.get(
        f"/api/v1/projects/{named_project['id']}/file-tree?include_content=true",
        headers=headers,
    )
    assert tree_with_content.status_code == 200
    titles_to_nodes = {node["title"]: node for node in _collect_nodes(tree_with_content.json()["tree"])}
    assert titles_to_nodes["Chapter Contract 1"]["content"] == "contract draft body"
    assert titles_to_nodes["Chapter Contract 1"]["id"] == created_file["id"]

    delete_response = await client.delete(f"/api/v1/projects/{unnamed_project['id']}", headers=headers)
    assert delete_response.status_code == 200
    assert delete_response.json()["message"] == "Project deleted successfully"

    list_after_delete = await client.get("/api/v1/projects", headers=headers)
    assert list_after_delete.status_code == 200
    after_ids = {project["id"] for project in list_after_delete.json()}
    assert unnamed_project["id"] not in after_ids
    assert named_project["id"] in after_ids

    deleted_get = await client.get(f"/api/v1/projects/{unnamed_project['id']}", headers=headers)
    assert deleted_get.status_code == 404


def _collect_nodes(nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for node in nodes:
        result.append(node)
        children = node.get("children")
        if isinstance(children, list):
            result.extend(_collect_nodes(children))
    return result
