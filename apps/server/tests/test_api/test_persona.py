"""Integration tests for persona onboarding server-side APIs."""

from __future__ import annotations

from datetime import datetime
from datetime import timedelta

import pytest
from httpx import AsyncClient
from sqlmodel import Session

from config.datetime_utils import utcnow
from models import User
from services.core.auth_service import hash_password


async def _create_user(
    db_session: Session,
    *,
    username: str,
    email: str,
    created_at: datetime,
    password: str = "password123",
) -> User:
    user = User(
        username=username,
        email=email,
        hashed_password=hash_password(password),
        email_verified=True,
        is_active=True,
        created_at=created_at,
        updated_at=created_at,
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
async def test_persona_onboarding_required_for_new_user(client: AsyncClient, db_session: Session, monkeypatch):
    rollout_at = (utcnow() - timedelta(days=2)).isoformat().replace("+00:00", "Z")
    monkeypatch.setenv("PERSONA_ONBOARDING_ROLLOUT_AT", rollout_at)
    monkeypatch.setenv("PERSONA_ONBOARDING_NEW_USER_WINDOW_DAYS", "7")

    await _create_user(
        db_session,
        username="persona_new_user",
        email="persona_new_user@example.com",
        created_at=utcnow() - timedelta(days=1),
    )
    token = await _login(client, "persona_new_user")

    response = await client.get(
        "/api/v1/persona/onboarding",
        headers=_auth_headers(token),
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["required"] is True
    assert payload["profile"] is None


@pytest.mark.integration
async def test_persona_onboarding_can_be_saved_and_returns_recommendations(
    client: AsyncClient,
    db_session: Session,
):
    await _create_user(
        db_session,
        username="persona_save_user",
        email="persona_save_user@example.com",
        created_at=datetime(2026, 3, 6, 0, 0, 0),
    )
    token = await _login(client, "persona_save_user")

    save_response = await client.put(
        "/api/v1/persona/onboarding",
        headers=_auth_headers(token),
        json={
            "selected_personas": ["serial", "professional"],
            "selected_goals": ["improveQuality", "monetize"],
            "experience_level": "advanced",
            "skipped": False,
        },
    )
    assert save_response.status_code == 200
    payload = save_response.json()
    assert payload["required"] is False
    assert payload["profile"] is not None
    assert payload["profile"]["selected_personas"] == ["serial", "professional"]
    assert payload["profile"]["selected_goals"] == ["improveQuality", "monetize"]
    assert payload["profile"]["experience_level"] == "advanced"
    assert len(payload["recommendations"]) >= 1

    recommendations_response = await client.get(
        "/api/v1/persona/recommendations",
        headers=_auth_headers(token),
    )
    assert recommendations_response.status_code == 200
    recommendations = recommendations_response.json()["recommendations"]
    assert len(recommendations) >= 1


@pytest.mark.integration
async def test_persona_onboarding_not_required_for_pre_rollout_user(
    client: AsyncClient,
    db_session: Session,
    monkeypatch,
):
    monkeypatch.setenv("PERSONA_ONBOARDING_ROLLOUT_AT", "2026-03-05T16:00:00Z")

    await _create_user(
        db_session,
        username="persona_old_user",
        email="persona_old_user@example.com",
        created_at=datetime(2026, 2, 20, 0, 0, 0),
    )
    token = await _login(client, "persona_old_user")

    response = await client.get(
        "/api/v1/persona/onboarding",
        headers=_auth_headers(token),
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["required"] is False
    assert payload["profile"] is None
