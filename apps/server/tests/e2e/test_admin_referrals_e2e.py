"""
Request-driven admin referrals e2e workflows.
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlmodel import Session

from models import User
from models.referral import InviteCode, Referral, UserReward
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
    is_superuser: bool = False,
    password: str = "password123",
) -> User:
    username, email = _identity(prefix)
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
async def test_admin_referrals_roundtrip_covers_stats_invites_and_rewards(
    client: AsyncClient,
    db_session: Session,
):
    admin = await _create_user(db_session, prefix="admin_referrals", is_superuser=True)
    inviter = await _create_user(db_session, prefix="ref_inviter")
    invitee = await _create_user(db_session, prefix="ref_invitee")

    admin_login = await _login(client, identifier=admin.username)
    headers = _auth_headers(admin_login["access_token"])

    create_invite_response = await client.post("/api/admin/invites", headers=headers)
    assert create_invite_response.status_code == 201
    created_invite = create_invite_response.json()
    assert created_invite["owner_id"] == admin.id

    inviter_code = InviteCode(
        code=f"REF-{uuid4().hex[:8].upper()}",
        owner_id=inviter.id,
        max_uses=5,
        current_uses=1,
        is_active=True,
    )
    db_session.add(inviter_code)
    db_session.commit()
    db_session.refresh(inviter_code)

    referral = Referral(
        inviter_id=inviter.id,
        invitee_id=invitee.id,
        invite_code_id=inviter_code.id,
        status="COMPLETED",
        inviter_rewarded=False,
        invitee_rewarded=False,
    )
    db_session.add(referral)
    db_session.commit()
    db_session.refresh(referral)

    reward = UserReward(
        user_id=inviter.id,
        reward_type="points",
        amount=30,
        source="referral",
        referral_id=referral.id,
        is_used=False,
    )
    db_session.add(reward)
    db_session.commit()

    stats_response = await client.get("/api/admin/referrals/stats", headers=headers)
    assert stats_response.status_code == 200
    stats_payload = stats_response.json()
    assert stats_payload["total_codes"] == 2
    assert stats_payload["active_codes"] == 2
    assert stats_payload["total_referrals"] == 1
    assert stats_payload["successful_referrals"] == 1
    assert stats_payload["pending_rewards"] == 1
    assert stats_payload["total_points_awarded"] == 30

    invites_response = await client.get(
        "/api/admin/invites?page=1&page_size=100&is_active=true",
        headers=headers,
    )
    assert invites_response.status_code == 200
    invites_payload = invites_response.json()
    assert invites_payload["total"] == 2
    assert any(item["id"] == created_invite["id"] for item in invites_payload["items"])

    rewards_response = await client.get(
        "/api/admin/referrals/rewards?page=1&page_size=100",
        headers=headers,
    )
    assert rewards_response.status_code == 200
    rewards_payload = rewards_response.json()
    assert rewards_payload["total"] == 1
    reward_item = next(item for item in rewards_payload["items"] if item["id"] == reward.id)
    assert reward_item["username"] == inviter.username
    assert reward_item["referral_id"] == referral.id
