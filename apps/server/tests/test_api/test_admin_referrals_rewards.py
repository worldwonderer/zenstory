"""Tests for admin referral rewards endpoint."""

from datetime import timedelta

import pytest
from httpx import AsyncClient
from sqlmodel import Session

from config.datetime_utils import utcnow
from models import User
from models.referral import InviteCode, Referral, UserReward
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


@pytest.mark.integration
async def test_admin_create_invite_code_sets_admin_as_owner(
    client: AsyncClient,
    db_session: Session,
):
    admin = await create_user(
        db_session,
        "admin_invite_creator",
        "admin_invite_creator@example.com",
        is_superuser=True,
    )
    token = await login_user(client, admin.username)

    response = await client.post(
        "/api/admin/invites",
        headers=auth_headers(token),
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["owner_id"] == admin.id
    assert payload["owner_name"] == admin.username
    assert payload["code"]
    assert payload["is_active"] is True


@pytest.mark.integration
async def test_admin_create_invite_code_forbidden_for_non_superuser(
    client: AsyncClient,
    db_session: Session,
):
    user = await create_user(
        db_session,
        "invite_normal_user",
        "invite_normal_user@example.com",
    )
    token = await login_user(client, user.username)

    response = await client.post(
        "/api/admin/invites",
        headers=auth_headers(token),
    )

    assert response.status_code == 403


@pytest.mark.integration
async def test_admin_referral_rewards_returns_referral_only_and_enriched_user(
    client: AsyncClient,
    db_session: Session,
):
    admin = await create_user(
        db_session,
        "admin_referral_rewards",
        "admin_referral_rewards@example.com",
        is_superuser=True,
    )
    inviter = await create_user(
        db_session,
        "ref_reward_inviter",
        "ref_reward_inviter@example.com",
    )
    invitee = await create_user(
        db_session,
        "ref_reward_invitee",
        "ref_reward_invitee@example.com",
    )

    invite_code = InviteCode(
        code="RWD-1001",
        owner_id=inviter.id,
        max_uses=5,
        current_uses=1,
        is_active=True,
    )
    db_session.add(invite_code)
    db_session.commit()
    db_session.refresh(invite_code)

    referral = Referral(
        inviter_id=inviter.id,
        invitee_id=invitee.id,
        invite_code_id=invite_code.id,
        status="COMPLETED",
        inviter_rewarded=False,
    )
    db_session.add(referral)
    db_session.commit()
    db_session.refresh(referral)

    referral_reward = UserReward(
        user_id=inviter.id,
        reward_type="points",
        amount=30,
        source="referral",
        referral_id=referral.id,
        is_used=False,
        created_at=utcnow() + timedelta(days=3650),
    )
    non_referral_reward = UserReward(
        user_id=inviter.id,
        reward_type="points",
        amount=10,
        source="promotion",
        referral_id=None,
        is_used=False,
    )
    db_session.add(referral_reward)
    db_session.add(non_referral_reward)
    db_session.commit()

    token = await login_user(client, admin.username)
    response = await client.get(
        "/api/admin/referrals/rewards",
        headers=auth_headers(token),
        params={"page": 1, "page_size": 100},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["page"] == 1
    assert payload["page_size"] == 100
    assert payload["total"] >= 1

    items = payload["items"]
    assert all(item["source"] == "referral" for item in items)

    target_item = next(item for item in items if item["id"] == referral_reward.id)
    assert target_item["username"] == inviter.username
    assert target_item["referral_id"] == referral.id

    assert all(item["id"] != non_referral_reward.id for item in items)


@pytest.mark.integration
async def test_admin_referral_rewards_forbidden_for_non_superuser(
    client: AsyncClient,
    db_session: Session,
):
    user = await create_user(
        db_session,
        "referral_rewards_normal_user",
        "referral_rewards_normal_user@example.com",
    )
    token = await login_user(client, user.username)

    response = await client.get(
        "/api/admin/referrals/rewards",
        headers=auth_headers(token),
    )

    assert response.status_code == 403
