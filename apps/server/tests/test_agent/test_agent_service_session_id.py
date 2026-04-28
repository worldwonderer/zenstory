"""
Regression tests for AgentService session-id resolution.

These cover the hotfix that ensures the session_id used by ToolContext / artifact
ledger is always backed by a real `chat_session.id` row.
"""

from __future__ import annotations

from datetime import timedelta
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from sqlmodel import Session

from agent.service import AgentService
from config.datetime_utils import utcnow
from models import ChatSession, Project, User
from services.core.auth_service import hash_password


def _create_user_and_project(db_session: Session) -> tuple[User, Project]:
    suffix = uuid4().hex[:8]
    user = User(
        email=f"agent-session-id-{suffix}@example.com",
        username=f"agent_session_id_{suffix}",
        hashed_password=hash_password("password123"),
        email_verified=True,
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    project = Project(
        name=f"Agent session id project {suffix}",
        owner_id=user.id,
        project_type="novel",
    )
    db_session.add(project)
    db_session.commit()
    db_session.refresh(project)

    return user, project


@pytest.mark.integration
class TestAgentServiceSessionIdResolution:
    def test_falls_back_to_existing_active_session_when_requested_missing(self, db_session: Session):
        user, project = _create_user_and_project(db_session)

        existing = ChatSession(
            id="existing-session",
            user_id=user.id,
            project_id=project.id,
            title="Existing",
            is_active=True,
            message_count=0,
        )
        db_session.add(existing)
        db_session.commit()

        service = AgentService(context_assembler=MagicMock())
        resolved = service._resolve_or_create_chat_session_id(
            db_session,
            project_id=project.id,
            user_id=user.id,
            requested_session_id="runtime-session-id",
        )

        assert resolved == existing.id
        assert db_session.get(ChatSession, "runtime-session-id") is None

    def test_creates_requested_session_id_when_no_active_session_exists(self, db_session: Session):
        user, project = _create_user_and_project(db_session)

        service = AgentService(context_assembler=MagicMock())
        resolved = service._resolve_or_create_chat_session_id(
            db_session,
            project_id=project.id,
            user_id=user.id,
            requested_session_id="runtime-session-id",
        )

        assert resolved == "runtime-session-id"
        created = db_session.get(ChatSession, "runtime-session-id")
        assert created is not None
        assert created.user_id == user.id
        assert created.project_id == project.id
        assert created.is_active is True

    def test_deactivates_stale_active_sessions_when_multiple_exist(self, db_session: Session):
        user, project = _create_user_and_project(db_session)

        old = ChatSession(
            id="old-session",
            user_id=user.id,
            project_id=project.id,
            title="Old",
            is_active=True,
            message_count=0,
            created_at=utcnow() - timedelta(minutes=10),
            updated_at=utcnow() - timedelta(minutes=10),
        )
        new = ChatSession(
            id="new-session",
            user_id=user.id,
            project_id=project.id,
            title="New",
            is_active=True,
            message_count=0,
            created_at=utcnow() - timedelta(minutes=1),
            updated_at=utcnow() - timedelta(minutes=1),
        )
        db_session.add_all([old, new])
        db_session.commit()

        service = AgentService(context_assembler=MagicMock())
        resolved = service._resolve_or_create_chat_session_id(
            db_session,
            project_id=project.id,
            user_id=user.id,
            requested_session_id=None,
        )

        assert resolved == new.id

        db_session.refresh(old)
        db_session.refresh(new)
        assert new.is_active is True
        assert old.is_active is False

    def test_ignores_requested_session_id_from_other_user_project(self, db_session: Session):
        user1, project1 = _create_user_and_project(db_session)
        user2, project2 = _create_user_and_project(db_session)

        foreign = ChatSession(
            id="shared-session",
            user_id=user2.id,
            project_id=project2.id,
            title="Foreign",
            is_active=True,
            message_count=0,
        )
        db_session.add(foreign)
        db_session.commit()

        service = AgentService(context_assembler=MagicMock())
        resolved = service._resolve_or_create_chat_session_id(
            db_session,
            project_id=project1.id,
            user_id=user1.id,
            requested_session_id="shared-session",
        )

        assert resolved != "shared-session"

        resolved_row = db_session.get(ChatSession, resolved)
        assert resolved_row is not None
        assert resolved_row.user_id == user1.id
        assert resolved_row.project_id == project1.id

        # Foreign session remains untouched.
        foreign_row = db_session.get(ChatSession, "shared-session")
        assert foreign_row is not None
        assert foreign_row.user_id == user2.id
        assert foreign_row.project_id == project2.id
