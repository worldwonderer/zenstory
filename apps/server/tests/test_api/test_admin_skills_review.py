"""
Tests for admin community skill review endpoints.
"""

from datetime import timedelta

import pytest
from httpx import AsyncClient
from sqlmodel import Session

from config.datetime_utils import utcnow
from models import PublicSkill, User, UserSkill
from services.core.auth_service import hash_password


async def create_user(
    db_session: Session,
    username: str,
    email: str,
    password: str = "password123",
    is_superuser: bool = False,
) -> User:
    """Create and persist a user for tests."""
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
    """Login and return an access token."""
    response = await client.post(
        "/api/auth/login",
        data={"username": username, "password": password},
    )
    assert response.status_code == 200
    return response.json()["access_token"]


def auth_headers(token: str) -> dict[str, str]:
    """Authorization headers helper."""
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.integration
async def test_get_pending_skills_returns_pending_only_with_author_name_and_order(
    client: AsyncClient,
    db_session: Session,
):
    """List endpoint should return only pending skills ordered by created_at asc."""
    admin = await create_user(db_session, "admin_skill_1", "admin_skill_1@example.com", is_superuser=True)
    author = await create_user(db_session, "skill_author_1", "skill_author_1@example.com")

    older_pending = PublicSkill(
        name="Older pending",
        description="desc",
        instructions="do older",
        category="writing",
        source="community",
        status="pending",
        author_id=author.id,
        created_at=utcnow() - timedelta(days=1),
    )
    approved = PublicSkill(
        name="Approved skill",
        description="desc",
        instructions="skip me",
        category="writing",
        source="community",
        status="approved",
        author_id=author.id,
        created_at=utcnow() - timedelta(hours=12),
    )
    newer_pending = PublicSkill(
        name="Newer pending",
        description="desc",
        instructions="do newer",
        category="character",
        source="community",
        status="pending",
        created_at=utcnow(),
    )
    db_session.add(older_pending)
    db_session.add(approved)
    db_session.add(newer_pending)
    db_session.commit()

    token = await login_user(client, admin.username)
    response = await client.get("/api/admin/skills/pending", headers=auth_headers(token))

    assert response.status_code == 200
    data = response.json()
    assert [item["id"] for item in data] == [older_pending.id, newer_pending.id]
    assert data[0]["author_name"] == author.username
    assert data[1]["author_name"] is None


@pytest.mark.integration
async def test_approve_pending_skill_updates_review_metadata(client: AsyncClient, db_session: Session):
    """Approve endpoint should mark skill approved and set reviewer metadata."""
    admin = await create_user(db_session, "admin_skill_2", "admin_skill_2@example.com", is_superuser=True)
    pending_skill = PublicSkill(
        name="Pending for approve",
        instructions="approve me",
        category="writing",
        source="community",
        status="pending",
    )
    db_session.add(pending_skill)
    db_session.commit()

    token = await login_user(client, admin.username)
    response = await client.post(
        f"/api/admin/skills/{pending_skill.id}/approve",
        headers=auth_headers(token),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["skill_id"] == pending_skill.id

    db_session.refresh(pending_skill)
    assert pending_skill.status == "approved"
    assert pending_skill.reviewed_by == admin.id
    assert pending_skill.reviewed_at is not None


@pytest.mark.integration
async def test_reject_pending_skill_sets_reason_and_resets_user_shared_state(
    client: AsyncClient,
    db_session: Session,
):
    """Reject endpoint should reset linked UserSkill sharing metadata."""
    admin = await create_user(db_session, "admin_skill_3", "admin_skill_3@example.com", is_superuser=True)
    author = await create_user(db_session, "skill_author_2", "skill_author_2@example.com")

    pending_skill = PublicSkill(
        name="Pending for reject",
        instructions="reject me",
        category="plot",
        source="community",
        status="pending",
        author_id=author.id,
    )
    db_session.add(pending_skill)
    db_session.commit()

    user_skill = UserSkill(
        user_id=author.id,
        name="Linked user skill",
        instructions="linked",
        triggers='["share"]',
        is_shared=True,
        shared_skill_id=pending_skill.id,
    )
    db_session.add(user_skill)
    db_session.commit()

    token = await login_user(client, admin.username)
    response = await client.post(
        f"/api/admin/skills/{pending_skill.id}/reject",
        headers=auth_headers(token),
        json={"rejection_reason": "Needs stronger quality"},
    )

    assert response.status_code == 200
    db_session.refresh(pending_skill)
    db_session.refresh(user_skill)

    assert pending_skill.status == "rejected"
    assert pending_skill.reviewed_by == admin.id
    assert pending_skill.reviewed_at is not None
    assert pending_skill.rejection_reason == "Needs stronger quality"
    assert user_skill.is_shared is False
    assert user_skill.shared_skill_id is None


@pytest.mark.integration
@pytest.mark.parametrize("endpoint, payload", [
    ("approve", None),
    ("reject", {"rejection_reason": "duplicate"}),
])
async def test_review_endpoints_return_400_for_non_pending_skill(
    client: AsyncClient,
    db_session: Session,
    endpoint: str,
    payload: dict | None,
):
    """Approve/reject should fail with validation error when skill is not pending."""
    admin = await create_user(db_session, f"admin_skill_4_{endpoint}", f"admin_skill_4_{endpoint}@example.com", is_superuser=True)
    reviewed_skill = PublicSkill(
        name="Already reviewed",
        instructions="reviewed",
        category="writing",
        source="community",
        status="approved",
    )
    db_session.add(reviewed_skill)
    db_session.commit()

    token = await login_user(client, admin.username)
    response = await client.post(
        f"/api/admin/skills/{reviewed_skill.id}/{endpoint}",
        headers=auth_headers(token),
        json=payload,
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "ERR_VALIDATION_ERROR"


@pytest.mark.integration
@pytest.mark.parametrize("endpoint, payload", [
    ("approve", None),
    ("reject", {"rejection_reason": "not found"}),
])
async def test_review_endpoints_return_404_for_missing_skill(
    client: AsyncClient,
    db_session: Session,
    endpoint: str,
    payload: dict | None,
):
    """Approve/reject should return not found for missing skill id."""
    admin = await create_user(db_session, f"admin_skill_5_{endpoint}", f"admin_skill_5_{endpoint}@example.com", is_superuser=True)
    token = await login_user(client, admin.username)

    response = await client.post(
        f"/api/admin/skills/missing-skill-id/{endpoint}",
        headers=auth_headers(token),
        json=payload,
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "ERR_NOT_FOUND"


@pytest.mark.integration
@pytest.mark.parametrize(
    "method,path_template,payload",
    [
        ("GET", "/api/admin/skills/pending", None),
        ("POST", "/api/admin/skills/{skill_id}/approve", None),
        ("POST", "/api/admin/skills/{skill_id}/reject", {"rejection_reason": "no access"}),
    ],
)
async def test_admin_skill_review_endpoints_forbidden_for_non_superuser(
    client: AsyncClient,
    db_session: Session,
    method: str,
    path_template: str,
    payload: dict | None,
):
    """All admin skill review endpoints should reject non-superusers."""
    normal_user = await create_user(db_session, "normal_skill_admin_1", "normal_skill_admin_1@example.com")
    pending_skill = PublicSkill(
        name="Pending skill",
        instructions="pending",
        category="writing",
        source="community",
        status="pending",
    )
    db_session.add(pending_skill)
    db_session.commit()

    token = await login_user(client, normal_user.username)
    path = path_template.format(skill_id=pending_skill.id)
    response = await client.request(method, path, headers=auth_headers(token), json=payload)

    assert response.status_code == 403
    assert response.json()["detail"] == "ERR_NOT_AUTHORIZED"
