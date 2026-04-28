"""Additional tests for admin inspiration endpoints."""

import json

import pytest
from httpx import AsyncClient
from sqlmodel import Session, select

from models import File, Inspiration, Project, User
from services.core.auth_service import hash_password


async def create_user(
    db_session: Session,
    username: str,
    email: str,
    password: str = "password123",
    *,
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


async def login_user(client: AsyncClient, username: str, password: str = "password123") -> str:
    response = await client.post(
        "/api/auth/login",
        data={"username": username, "password": password},
    )
    assert response.status_code == 200
    return response.json()["access_token"]


def auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def create_inspiration_record(
    db_session: Session,
    *,
    name: str,
    author_id: str | None,
    status: str = "pending",
    tags: str = "[]",
    reviewed_by: str | None = None,
) -> Inspiration:
    inspiration = Inspiration(
        name=name,
        description=f"{name} description",
        project_type="novel",
        tags=tags,
        snapshot_data=json.dumps({"project_type": "novel", "files": []}, ensure_ascii=False),
        source="community",
        status=status,
        author_id=author_id,
        reviewed_by=reviewed_by,
    )
    db_session.add(inspiration)
    db_session.commit()
    db_session.refresh(inspiration)
    return inspiration


@pytest.mark.integration
async def test_admin_get_inspiration_detail_success_and_not_found(
    client: AsyncClient,
    db_session: Session,
):
    admin = await create_user(
        db_session,
        "admin_inspiration_detail",
        "admin_inspiration_detail@example.com",
        is_superuser=True,
    )
    author = await create_user(
        db_session,
        "inspiration_detail_author",
        "inspiration_detail_author@example.com",
    )

    inspiration = create_inspiration_record(
        db_session,
        name="Detail Inspiration",
        author_id=author.id,
        tags="not-a-json-array",
        reviewed_by=admin.id,
        status="approved",
    )

    token = await login_user(client, admin.username)

    detail_response = await client.get(
        f"/api/admin/inspirations/{inspiration.id}",
        headers=auth_headers(token),
    )
    assert detail_response.status_code == 200
    payload = detail_response.json()
    assert payload["id"] == inspiration.id
    assert payload["name"] == "Detail Inspiration"
    assert payload["creator_name"] == author.username
    assert payload["reviewer_name"] == admin.username
    assert payload["tags"] == []

    missing_response = await client.get(
        "/api/admin/inspirations/missing-inspiration-id",
        headers=auth_headers(token),
    )
    assert missing_response.status_code == 404


@pytest.mark.integration
async def test_admin_create_inspiration_requires_project_and_active_files(
    client: AsyncClient,
    db_session: Session,
):
    admin = await create_user(
        db_session,
        "admin_inspiration_create_guard",
        "admin_inspiration_create_guard@example.com",
        is_superuser=True,
    )
    token = await login_user(client, admin.username)

    missing_project_response = await client.post(
        "/api/admin/inspirations",
        headers=auth_headers(token),
        json={"project_id": "missing-project-id", "source": "official"},
    )
    assert missing_project_response.status_code == 404

    project = Project(
        name="No Active Files Project",
        description="all files deleted",
        owner_id=admin.id,
        project_type="novel",
    )
    db_session.add(project)
    db_session.commit()
    db_session.refresh(project)

    deleted_file = File(
        project_id=project.id,
        title="deleted",
        content="x",
        file_type="draft",
        order=0,
        is_deleted=True,
    )
    db_session.add(deleted_file)
    db_session.commit()

    no_files_response = await client.post(
        "/api/admin/inspirations",
        headers=auth_headers(token),
        json={"project_id": project.id, "source": "official"},
    )
    assert no_files_response.status_code == 400
    assert no_files_response.json()["error_detail"] == "Project has no files to include in inspiration"


@pytest.mark.integration
async def test_admin_patch_inspiration_updates_mutable_fields(
    client: AsyncClient,
    db_session: Session,
):
    admin = await create_user(
        db_session,
        "admin_inspiration_patch",
        "admin_inspiration_patch@example.com",
        is_superuser=True,
    )
    inspiration = create_inspiration_record(
        db_session,
        name="Patch Target",
        author_id=admin.id,
        tags=json.dumps(["old"], ensure_ascii=False),
        status="pending",
    )

    token = await login_user(client, admin.username)

    patch_response = await client.patch(
        f"/api/admin/inspirations/{inspiration.id}",
        headers=auth_headers(token),
        json={
            "name": "Patched Name",
            "description": "patched description",
            "cover_image": "https://example.com/cover.png",
            "tags": ["new", "tags"],
            "is_featured": True,
            "sort_order": 9,
        },
    )
    assert patch_response.status_code == 200
    patched = patch_response.json()
    assert patched["name"] == "Patched Name"
    assert patched["description"] == "patched description"
    assert patched["cover_image"] == "https://example.com/cover.png"
    assert patched["tags"] == ["new", "tags"]
    assert patched["is_featured"] is True
    assert patched["sort_order"] == 9

    refreshed = db_session.exec(select(Inspiration).where(Inspiration.id == inspiration.id)).first()
    assert refreshed is not None
    assert refreshed.tags == json.dumps(["new", "tags"], ensure_ascii=False)


@pytest.mark.integration
async def test_admin_review_and_delete_inspiration_lifecycle(
    client: AsyncClient,
    db_session: Session,
):
    admin = await create_user(
        db_session,
        "admin_inspiration_review_delete",
        "admin_inspiration_review_delete@example.com",
        is_superuser=True,
    )
    inspiration = create_inspiration_record(
        db_session,
        name="Review Me",
        author_id=admin.id,
        status="pending",
    )

    token = await login_user(client, admin.username)

    approve_response = await client.post(
        f"/api/admin/inspirations/{inspiration.id}/review",
        headers=auth_headers(token),
        json={"approve": True},
    )
    assert approve_response.status_code == 200
    assert approve_response.json()["inspiration_id"] == inspiration.id

    refreshed = db_session.exec(select(Inspiration).where(Inspiration.id == inspiration.id)).first()
    assert refreshed is not None
    assert refreshed.status == "approved"
    assert refreshed.reviewed_by == admin.id

    non_pending_response = await client.post(
        f"/api/admin/inspirations/{inspiration.id}/review",
        headers=auth_headers(token),
        json={"approve": True},
    )
    assert non_pending_response.status_code == 400
    assert non_pending_response.json()["error_detail"] == "Inspiration is not pending review"

    delete_response = await client.delete(
        f"/api/admin/inspirations/{inspiration.id}",
        headers=auth_headers(token),
    )
    assert delete_response.status_code == 200
    assert delete_response.json()["inspiration_id"] == inspiration.id

    deleted = db_session.exec(select(Inspiration).where(Inspiration.id == inspiration.id)).first()
    assert deleted is None

    delete_missing_response = await client.delete(
        f"/api/admin/inspirations/{inspiration.id}",
        headers=auth_headers(token),
    )
    assert delete_missing_response.status_code == 404


@pytest.mark.integration
async def test_admin_list_inspirations_supports_filters_lookup_and_tag_parsing(
    client: AsyncClient,
    db_session: Session,
):
    admin = await create_user(
        db_session,
        "admin_inspiration_list",
        "admin_inspiration_list@example.com",
        is_superuser=True,
    )
    author = await create_user(
        db_session,
        "inspiration_list_author",
        "inspiration_list_author@example.com",
    )
    reviewer = await create_user(
        db_session,
        "inspiration_list_reviewer",
        "inspiration_list_reviewer@example.com",
        is_superuser=True,
    )

    db_session.add(
        Inspiration(
            name="Community Pending A",
            description="community pending",
            project_type="novel",
            tags=json.dumps(["tag-a"], ensure_ascii=False),
            snapshot_data=json.dumps({"project_type": "novel", "files": []}, ensure_ascii=False),
            source="community",
            status="pending",
            author_id=author.id,
            reviewed_by=reviewer.id,
        )
    )
    db_session.add(
        Inspiration(
            name="Community Pending B",
            description="community pending 2",
            project_type="novel",
            tags=json.dumps(["tag-b"], ensure_ascii=False),
            snapshot_data=json.dumps({"project_type": "novel", "files": []}, ensure_ascii=False),
            source="community",
            status="pending",
            author_id=author.id,
        )
    )
    db_session.add(
        Inspiration(
            name="Official Approved No User",
            description="official approved",
            project_type="novel",
            tags="",
            snapshot_data=json.dumps({"project_type": "novel", "files": []}, ensure_ascii=False),
            source="official",
            status="approved",
            author_id=None,
            reviewed_by=None,
        )
    )
    db_session.commit()

    token = await login_user(client, admin.username)

    filtered_response = await client.get(
        "/api/admin/inspirations",
        headers=auth_headers(token),
        params={"status": "pending", "source": "community", "skip": 0, "limit": 2},
    )
    assert filtered_response.status_code == 200
    filtered = filtered_response.json()
    assert filtered["total"] == 2
    assert len(filtered["items"]) == 2
    assert all(item["creator_name"] == author.username for item in filtered["items"])
    assert any(item["reviewer_name"] == reviewer.username for item in filtered["items"])

    alias_status_response = await client.get(
        "/api/admin/inspirations",
        headers=auth_headers(token),
        params={"status_filter": "approved", "source": "official"},
    )
    assert alias_status_response.status_code == 200
    alias_payload = alias_status_response.json()
    assert alias_payload["total"] == 1
    assert alias_payload["items"][0]["name"] == "Official Approved No User"
    assert alias_payload["items"][0]["creator_name"] is None
    assert alias_payload["items"][0]["reviewer_name"] is None
    assert alias_payload["items"][0]["tags"] == []


@pytest.mark.integration
async def test_admin_create_inspiration_success_for_official_and_community(
    client: AsyncClient,
    db_session: Session,
):
    admin = await create_user(
        db_session,
        "admin_inspiration_create_success",
        "admin_inspiration_create_success@example.com",
        is_superuser=True,
    )
    token = await login_user(client, admin.username)

    official_project = Project(
        name="Official Source Project",
        description="official project",
        owner_id=admin.id,
        project_type="novel",
    )
    db_session.add(official_project)
    db_session.commit()
    db_session.refresh(official_project)

    db_session.add(
        File(
            project_id=official_project.id,
            title="Official File 1",
            content="official content",
            file_type="draft",
            order=0,
            is_deleted=False,
        )
    )
    db_session.commit()

    official_response = await client.post(
        "/api/admin/inspirations",
        headers=auth_headers(token),
        json={
            "project_id": official_project.id,
            "source": "official",
            "name": "Official Inspiration",
            "description": "official desc",
            "tags": ["official", "featured"],
            "is_featured": True,
        },
    )
    assert official_response.status_code == 201
    official_payload = official_response.json()
    assert official_payload["name"] == "Official Inspiration"
    assert official_payload["status"] == "approved"
    assert official_payload["tags"] == ["official", "featured"]
    assert official_payload["is_featured"] is True

    community_project = Project(
        name="Community Source Project",
        description="community project",
        owner_id=admin.id,
        project_type="novel",
    )
    db_session.add(community_project)
    db_session.commit()
    db_session.refresh(community_project)

    db_session.add(
        File(
            project_id=community_project.id,
            title="Community File 1",
            content="community content",
            file_type="draft",
            order=0,
            is_deleted=False,
        )
    )
    db_session.commit()

    community_response = await client.post(
        "/api/admin/inspirations",
        headers=auth_headers(token),
        json={
            "project_id": community_project.id,
            "source": "community",
            "name": "Community Inspiration",
            "tags": ["community"],
        },
    )
    assert community_response.status_code == 201
    community_payload = community_response.json()
    assert community_payload["name"] == "Community Inspiration"
    assert community_payload["status"] == "pending"
    assert community_payload["tags"] == ["community"]


@pytest.mark.integration
async def test_admin_patch_inspiration_rejects_status_and_not_found(
    client: AsyncClient,
    db_session: Session,
):
    admin = await create_user(
        db_session,
        "admin_inspiration_patch_errors",
        "admin_inspiration_patch_errors@example.com",
        is_superuser=True,
    )
    inspiration = create_inspiration_record(
        db_session,
        name="Patch Error Target",
        author_id=admin.id,
        status="pending",
    )
    token = await login_user(client, admin.username)

    status_response = await client.patch(
        f"/api/admin/inspirations/{inspiration.id}",
        headers=auth_headers(token),
        json={"status": "approved"},
    )
    assert status_response.status_code == 400
    assert "Status must be updated" in status_response.json()["error_detail"]

    missing_response = await client.patch(
        "/api/admin/inspirations/missing-inspiration-id",
        headers=auth_headers(token),
        json={"name": "noop"},
    )
    assert missing_response.status_code == 404


@pytest.mark.integration
async def test_admin_review_inspiration_reject_path_value_error_and_not_found(
    client: AsyncClient,
    db_session: Session,
):
    admin = await create_user(
        db_session,
        "admin_inspiration_review_reject",
        "admin_inspiration_review_reject@example.com",
        is_superuser=True,
    )
    inspiration = create_inspiration_record(
        db_session,
        name="Reject Me",
        author_id=admin.id,
        status="pending",
    )

    token = await login_user(client, admin.username)

    missing_reason_response = await client.post(
        f"/api/admin/inspirations/{inspiration.id}/review",
        headers=auth_headers(token),
        json={"approve": False},
    )
    assert missing_reason_response.status_code == 400
    assert missing_reason_response.json()["error_detail"] == "Rejection reason is required when rejecting inspiration"

    reject_response = await client.post(
        f"/api/admin/inspirations/{inspiration.id}/review",
        headers=auth_headers(token),
        json={"approve": False, "rejection_reason": "needs more detail"},
    )
    assert reject_response.status_code == 200
    assert reject_response.json()["message"] == "Inspiration rejected"

    refreshed = db_session.exec(select(Inspiration).where(Inspiration.id == inspiration.id)).first()
    assert refreshed is not None
    assert refreshed.status == "rejected"
    assert refreshed.reviewed_by == admin.id
    assert refreshed.rejection_reason == "needs more detail"

    missing_response = await client.post(
        "/api/admin/inspirations/missing-inspiration-id/review",
        headers=auth_headers(token),
        json={"approve": True},
    )
    assert missing_response.status_code == 404
