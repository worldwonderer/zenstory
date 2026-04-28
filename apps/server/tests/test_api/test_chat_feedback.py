"""Chat feedback API integration tests."""

import json

import pytest
from httpx import AsyncClient
from sqlmodel import Session

from models import ChatMessage, ChatSession, Project, User
from services.core.auth_service import hash_password


@pytest.mark.integration
class TestChatFeedbackAPI:
    """Tests for message feedback API."""

    async def _login(self, client: AsyncClient, username: str, password: str) -> str:
        response = await client.post(
            "/api/auth/login",
            data={"username": username, "password": password},
        )
        assert response.status_code == 200
        return response.json()["access_token"]

    async def test_submit_feedback_success(
        self,
        client: AsyncClient,
        db_session: Session,
    ):
        """User can submit feedback for own project's assistant message."""
        user = User(
            username="feedback_user_1",
            email="feedback_user_1@example.com",
            hashed_password=hash_password("password123"),
            name="Feedback User 1",
            email_verified=True,
            is_active=True,
        )
        db_session.add(user)
        db_session.commit()

        project = Project(
            id="proj-feedback-1",
            owner_id=user.id,
            name="Feedback Project",
            description="Feedback test project",
        )
        db_session.add(project)
        db_session.commit()

        chat_session = ChatSession(
            user_id=user.id,
            project_id=project.id,
            title="Feedback Session",
            is_active=True,
            message_count=1,
        )
        db_session.add(chat_session)
        db_session.commit()

        message = ChatMessage(
            session_id=chat_session.id,
            role="assistant",
            content="这里是一条 AI 回复",
            message_metadata=json.dumps({"source": "unit-test"}, ensure_ascii=False),
        )
        db_session.add(message)
        db_session.commit()
        db_session.refresh(message)

        token = await self._login(client, "feedback_user_1", "password123")

        response = await client.post(
            f"/api/v1/chat/messages/{message.id}/feedback",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "vote": "up",
                "preset": "helpful",
                "comment": "很有帮助",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["message_id"] == message.id
        assert data["feedback"]["vote"] == "up"
        assert data["feedback"]["preset"] == "helpful"
        assert data["feedback"]["comment"] == "很有帮助"
        assert data["feedback"]["created_at"]
        assert data["feedback"]["updated_at"]
        assert data["updated_at"]

        db_session.refresh(message)
        metadata = json.loads(message.message_metadata or "{}")
        assert metadata["source"] == "unit-test"
        assert metadata["feedback"]["vote"] == "up"
        assert metadata["feedback"]["preset"] == "helpful"
        assert metadata["feedback"]["comment"] == "很有帮助"
        assert metadata["feedback"]["created_at"]
        assert metadata["feedback"]["updated_at"]

    async def test_submit_feedback_requires_project_ownership(
        self,
        client: AsyncClient,
        db_session: Session,
    ):
        """Submitting feedback for another user's project should be forbidden."""
        owner = User(
            username="feedback_owner",
            email="feedback_owner@example.com",
            hashed_password=hash_password("password123"),
            name="Feedback Owner",
            email_verified=True,
            is_active=True,
        )
        intruder = User(
            username="feedback_intruder",
            email="feedback_intruder@example.com",
            hashed_password=hash_password("password123"),
            name="Feedback Intruder",
            email_verified=True,
            is_active=True,
        )
        db_session.add(owner)
        db_session.add(intruder)
        db_session.commit()

        project = Project(
            id="proj-feedback-2",
            owner_id=owner.id,
            name="Owner Project",
            description="Owner project",
        )
        db_session.add(project)
        db_session.commit()

        chat_session = ChatSession(
            user_id=owner.id,
            project_id=project.id,
            title="Owner Session",
            is_active=True,
            message_count=1,
        )
        db_session.add(chat_session)
        db_session.commit()

        message = ChatMessage(
            session_id=chat_session.id,
            role="assistant",
            content="Owner only message",
        )
        db_session.add(message)
        db_session.commit()
        db_session.refresh(message)

        intruder_token = await self._login(client, "feedback_intruder", "password123")

        response = await client.post(
            f"/api/v1/chat/messages/{message.id}/feedback",
            headers={"Authorization": f"Bearer {intruder_token}"},
            json={"vote": "down", "comment": "不喜欢"},
        )

        assert response.status_code == 403
        data = response.json()
        assert data["error_code"] == "ERR_NOT_AUTHORIZED"

    async def test_submit_feedback_message_not_found(
        self,
        client: AsyncClient,
        db_session: Session,
    ):
        """Submitting feedback for non-existent message returns 404."""
        user = User(
            username="feedback_user_3",
            email="feedback_user_3@example.com",
            hashed_password=hash_password("password123"),
            name="Feedback User 3",
            email_verified=True,
            is_active=True,
        )
        db_session.add(user)
        db_session.commit()

        token = await self._login(client, "feedback_user_3", "password123")

        response = await client.post(
            "/api/v1/chat/messages/non-existent-message-id/feedback",
            headers={"Authorization": f"Bearer {token}"},
            json={"vote": "up"},
        )

        assert response.status_code == 404
        data = response.json()
        assert data["error_code"] == "ERR_CHAT_MESSAGE_NOT_FOUND"

    async def test_submit_feedback_rejects_non_assistant_message(
        self,
        client: AsyncClient,
        db_session: Session,
    ):
        """Feedback is only allowed on assistant-role messages."""
        user = User(
            username="feedback_user_4",
            email="feedback_user_4@example.com",
            hashed_password=hash_password("password123"),
            name="Feedback User 4",
            email_verified=True,
            is_active=True,
        )
        db_session.add(user)
        db_session.commit()

        project = Project(
            id="proj-feedback-4",
            owner_id=user.id,
            name="Feedback Project 4",
            description="Feedback test project 4",
        )
        db_session.add(project)
        db_session.commit()

        chat_session = ChatSession(
            user_id=user.id,
            project_id=project.id,
            title="Feedback Session 4",
            is_active=True,
            message_count=1,
        )
        db_session.add(chat_session)
        db_session.commit()

        user_message = ChatMessage(
            session_id=chat_session.id,
            role="user",
            content="这是一条用户消息",
        )
        db_session.add(user_message)
        db_session.commit()

        token = await self._login(client, "feedback_user_4", "password123")

        response = await client.post(
            f"/api/v1/chat/messages/{user_message.id}/feedback",
            headers={"Authorization": f"Bearer {token}"},
            json={"vote": "up"},
        )

        assert response.status_code == 400
        data = response.json()
        assert data["error_code"] == "ERR_BAD_REQUEST"

    async def test_submit_feedback_rejects_invalid_vote_payload(
        self,
        client: AsyncClient,
        db_session: Session,
    ):
        """Invalid vote value should be rejected by request validation."""
        user = User(
            username="feedback_user_5",
            email="feedback_user_5@example.com",
            hashed_password=hash_password("password123"),
            name="Feedback User 5",
            email_verified=True,
            is_active=True,
        )
        db_session.add(user)
        db_session.commit()

        token = await self._login(client, "feedback_user_5", "password123")
        response = await client.post(
            "/api/v1/chat/messages/non-existent-message-id/feedback",
            headers={"Authorization": f"Bearer {token}"},
            json={"vote": "invalid_vote"},
        )

        assert response.status_code == 422
        data = response.json()
        assert data["error_code"] == "ERR_VALIDATION_ERROR"

    async def test_recent_messages_include_feedback_metadata_after_submit(
        self,
        client: AsyncClient,
        db_session: Session,
    ):
        """Feedback written to metadata should be visible from /recent history API."""
        user = User(
            username="feedback_user_6",
            email="feedback_user_6@example.com",
            hashed_password=hash_password("password123"),
            name="Feedback User 6",
            email_verified=True,
            is_active=True,
        )
        db_session.add(user)
        db_session.commit()

        project = Project(
            id="proj-feedback-6",
            owner_id=user.id,
            name="Feedback Project 6",
            description="Feedback test project 6",
        )
        db_session.add(project)
        db_session.commit()

        chat_session = ChatSession(
            user_id=user.id,
            project_id=project.id,
            title="Feedback Session 6",
            is_active=True,
            message_count=1,
        )
        db_session.add(chat_session)
        db_session.commit()

        message = ChatMessage(
            session_id=chat_session.id,
            role="assistant",
            content="请对我评分",
        )
        db_session.add(message)
        db_session.commit()

        token = await self._login(client, "feedback_user_6", "password123")

        submit_response = await client.post(
            f"/api/v1/chat/messages/{message.id}/feedback",
            headers={"Authorization": f"Bearer {token}"},
            json={"vote": "down", "comment": "不够准确"},
        )
        assert submit_response.status_code == 200

        history_response = await client.get(
            f"/api/v1/chat/session/{project.id}/recent",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert history_response.status_code == 200
        payload = history_response.json()
        assert len(payload) == 1
        assert payload[0]["id"] == message.id
        assert payload[0]["metadata"] is not None

        metadata = json.loads(payload[0]["metadata"])
        assert metadata["feedback"]["vote"] == "down"
        assert metadata["feedback"]["comment"] == "不够准确"
