"""Tests for admin points management endpoints."""

from datetime import timedelta

import pytest
from httpx import AsyncClient
from sqlmodel import Session

from config.datetime_utils import utcnow
from core.error_codes import ErrorCode
from models import User
from models.points import PointsTransaction
from services.core.auth_service import hash_password
from services.features.points_service import points_service


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
async def test_admin_points_stats_balance_and_transactions(client: AsyncClient, db_session: Session):
    admin = await create_user(db_session, "admin_points_metrics", "admin_points_metrics@example.com", is_superuser=True)
    target = await create_user(db_session, "points_target_user", "points_target_user@example.com")
    extra_user = await create_user(db_session, "points_extra_user", "points_extra_user@example.com")

    points_service.earn_points(db_session, target.id, 120, "referral", description="seed earn")
    points_service.spend_points(db_session, target.id, 30, "redeem_pro", description="seed spend")

    now = utcnow()
    db_session.add(
        PointsTransaction(
            user_id=target.id,
            amount=50,
            balance_after=140,
            transaction_type="legacy_bonus",
            description="expired seed",
            expires_at=now - timedelta(days=1),
            is_expired=True,
            expired_at=now - timedelta(hours=1),
            created_at=now - timedelta(days=2),
        )
    )

    points_service.earn_points(db_session, extra_user.id, 10, "check_in", description="extra user seed")
    db_session.commit()

    token = await login_user(client, admin.username)

    stats_response = await client.get("/api/admin/points/stats", headers=auth_headers(token))
    assert stats_response.status_code == 200
    stats_data = stats_response.json()
    assert stats_data["total_points_issued"] >= 180
    assert stats_data["total_points_spent"] >= 30
    assert stats_data["total_points_expired"] >= 50
    assert stats_data["active_users_with_points"] >= 2

    balance_by_username = await client.get(
        f"/api/admin/points/{target.username}",
        headers=auth_headers(token),
    )
    assert balance_by_username.status_code == 200
    balance_data = balance_by_username.json()
    assert balance_data["user_id"] == target.id
    assert balance_data["username"] == target.username
    assert balance_data["email"] == target.email
    assert balance_data["available"] == 90
    assert balance_data["pending_expiration"] == 0
    assert balance_data["total_earned"] == 170
    assert balance_data["total_spent"] == 30

    tx_response = await client.get(
        f"/api/admin/points/{target.email}/transactions",
        headers=auth_headers(token),
        params={"page": 1, "page_size": 2},
    )
    assert tx_response.status_code == 200
    tx_data = tx_response.json()
    assert tx_data["page"] == 1
    assert tx_data["page_size"] == 2
    assert tx_data["total"] >= 3
    assert len(tx_data["items"]) == 2
    assert all(item["user_id"] == target.id for item in tx_data["items"])


@pytest.mark.integration
async def test_admin_adjust_points_add_deduct_and_validation(client: AsyncClient, db_session: Session):
    admin = await create_user(db_session, "admin_adjust_points", "admin_adjust_points@example.com", is_superuser=True)
    target = await create_user(db_session, "points_adjust_target", "points_adjust_target@example.com")
    points_service.earn_points(db_session, target.id, 40, "referral", description="initial balance")

    token = await login_user(client, admin.username)

    add_response = await client.post(
        f"/api/admin/points/{target.username}/adjust",
        headers=auth_headers(token),
        json={"amount": 25, "reason": "manual bonus"},
    )
    assert add_response.status_code == 200
    add_data = add_response.json()
    assert add_data["success"] is True
    assert add_data["old_balance"] == 40
    assert add_data["new_balance"] == 65
    assert add_data["transaction"]["amount"] == 25
    assert add_data["transaction"]["transaction_type"] == "admin_adjust"
    assert add_data["transaction"]["description"] == "manual bonus"

    deduct_response = await client.post(
        f"/api/admin/points/{target.email}/adjust",
        headers=auth_headers(token),
        json={"amount": -15, "reason": "manual correction"},
    )
    assert deduct_response.status_code == 200
    deduct_data = deduct_response.json()
    assert deduct_data["old_balance"] == 65
    assert deduct_data["new_balance"] == 50
    assert deduct_data["transaction"]["amount"] == -15
    assert deduct_data["transaction"]["description"] == "manual correction"

    zero_response = await client.post(
        f"/api/admin/points/{target.id}/adjust",
        headers=auth_headers(token),
        json={"amount": 0, "reason": "invalid adjustment"},
    )
    assert zero_response.status_code == 400
    zero_data = zero_response.json()
    assert zero_data["detail"] == ErrorCode.VALIDATION_ERROR
    assert zero_data["error_detail"] == "Amount cannot be zero"


@pytest.mark.integration
async def test_admin_adjust_points_not_found_and_insufficient_balance(client: AsyncClient, db_session: Session):
    admin = await create_user(db_session, "admin_points_errors", "admin_points_errors@example.com", is_superuser=True)
    target = await create_user(db_session, "points_balance_empty", "points_balance_empty@example.com")

    token = await login_user(client, admin.username)

    insufficient_response = await client.post(
        f"/api/admin/points/{target.id}/adjust",
        headers=auth_headers(token),
        json={"amount": -10, "reason": "deduct without balance"},
    )
    assert insufficient_response.status_code == 402
    insufficient_data = insufficient_response.json()
    assert insufficient_data["detail"] == ErrorCode.QUOTA_EXCEEDED
    assert insufficient_data["error_detail"]["available"] == 0
    assert insufficient_data["error_detail"]["required"] == 10

    not_found_response = await client.get(
        "/api/admin/points/missing_user_identifier",
        headers=auth_headers(token),
    )
    assert not_found_response.status_code == 404
    not_found_data = not_found_response.json()
    assert not_found_data["detail"] == ErrorCode.NOT_FOUND
    assert not_found_data["error_detail"] == "User not found"


@pytest.mark.integration
@pytest.mark.parametrize(
    ("method", "path", "payload"),
    [
        ("GET", "/api/admin/points/stats", None),
        ("GET", "/api/admin/points/{id}", None),
        ("GET", "/api/admin/points/{id}/transactions", None),
        ("POST", "/api/admin/points/{id}/adjust", {"amount": 10, "reason": "forbidden"}),
    ],
)
async def test_admin_points_endpoints_forbidden_for_non_superuser(
    method: str,
    path: str,
    payload: dict | None,
    client: AsyncClient,
    db_session: Session,
):
    normal_user = await create_user(db_session, "points_normal_user", "points_normal_user@example.com")
    target = await create_user(db_session, "points_target_forbidden", "points_target_forbidden@example.com")
    token = await login_user(client, normal_user.username)

    final_path = path.format(id=target.id)
    if method == "GET":
        response = await client.get(final_path, headers=auth_headers(token))
    else:
        response = await client.post(final_path, headers=auth_headers(token), json=payload)

    assert response.status_code == 403


@pytest.mark.integration
async def test_admin_points_transactions_and_adjust_return_404_for_missing_user(
    client: AsyncClient,
    db_session: Session,
):
    admin = await create_user(db_session, "admin_points_missing_user", "admin_points_missing_user@example.com", is_superuser=True)
    token = await login_user(client, admin.username)

    tx_response = await client.get(
        "/api/admin/points/user-not-found-id/transactions",
        headers=auth_headers(token),
    )
    assert tx_response.status_code == 404
    assert tx_response.json()["error_detail"] == "User not found"

    adjust_response = await client.post(
        "/api/admin/points/user-not-found-id/adjust",
        headers=auth_headers(token),
        json={"amount": 10, "reason": "missing user"},
    )
    assert adjust_response.status_code == 404
    assert adjust_response.json()["error_detail"] == "User not found"
