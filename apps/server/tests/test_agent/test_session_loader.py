"""
Tests for SessionLoader history loading and token-budget windowing.
"""

import json
from datetime import datetime, timedelta
from uuid import uuid4

import pytest
from sqlmodel import Session, select

from agent.core.session_loader import SessionLoader
from models import ChatMessage, ChatSession, Project, User


@pytest.fixture
def session_loader_test_data(db_session: Session):
    """Create user/project/chat session for session loader tests."""
    suffix = uuid4().hex[:8]
    user = User(
        email=f"session-loader-{suffix}@example.com",
        username=f"session_loader_{suffix}",
        hashed_password="hashed",
        name="Session Loader Test User",
        email_verified=True,
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    project = Project(
        name=f"Session Loader Project {suffix}",
        owner_id=user.id,
        project_type="novel",
    )
    db_session.add(project)
    db_session.commit()
    db_session.refresh(project)

    chat_session = ChatSession(
        user_id=user.id,
        project_id=project.id,
        title="Session Loader Test Chat",
        is_active=True,
        message_count=0,
    )
    db_session.add(chat_session)
    db_session.commit()
    db_session.refresh(chat_session)

    return {
        "user": user,
        "project": project,
        "chat_session": chat_session,
    }


def _add_chat_messages(
    db_session: Session,
    chat_session_id: str,
    messages: list[dict[str, str | None]],
) -> None:
    """Insert ordered chat messages with explicit timestamps."""
    base_time = datetime.utcnow()
    for index, message in enumerate(messages):
        db_session.add(
            ChatMessage(
                session_id=chat_session_id,
                role=message["role"] or "user",
                content=message["content"] or "",
                reasoning_content=message.get("reasoning_content"),
                created_at=base_time + timedelta(seconds=index),
            )
        )
    db_session.commit()


@pytest.mark.unit
class TestSessionLoaderHistoryBudget:
    """Tests for token-budget sliding window when loading chat history."""

    def test_load_chat_session_keeps_all_messages_within_budget(
        self,
        db_session: Session,
        session_loader_test_data,
        monkeypatch,
    ):
        """Should keep full history when total tokens are below budget."""
        monkeypatch.setattr("agent.core.session_loader.AGENT_CHAT_HISTORY_TOKEN_BUDGET", 20)
        _add_chat_messages(
            db_session,
            session_loader_test_data["chat_session"].id,
            [
                {"role": "user", "content": "u" * 12},
                {"role": "assistant", "content": "a" * 12},
                {"role": "user", "content": "v" * 12},
            ],
        )

        loader = SessionLoader(
            project_id=session_loader_test_data["project"].id,
            user_id=session_loader_test_data["user"].id,
        )
        session_data = loader.load_chat_session(db_session)

        assert [msg["content"] for msg in session_data.history_messages] == [
            "u" * 12,
            "a" * 12,
            "v" * 12,
        ]

    def test_load_chat_session_truncates_oldest_messages_when_budget_exceeded(
        self,
        db_session: Session,
        session_loader_test_data,
        monkeypatch,
    ):
        """Should keep newest messages and preserve chronological order after truncation."""
        monkeypatch.setattr("agent.core.session_loader.AGENT_CHAT_HISTORY_TOKEN_BUDGET", 40)
        _add_chat_messages(
            db_session,
            session_loader_test_data["chat_session"].id,
            [
                {"role": "user", "content": "m1" * 8},
                {"role": "assistant", "content": "m2" * 8},
                {"role": "user", "content": "m3" * 8},
                {
                    "role": "assistant",
                    "content": "m4" * 8,
                    "reasoning_content": "kept reasoning",
                },
            ],
        )

        loader = SessionLoader(
            project_id=session_loader_test_data["project"].id,
            user_id=session_loader_test_data["user"].id,
        )
        session_data = loader.load_chat_session(db_session)

        assert len(session_data.history_messages) == 2
        assert session_data.history_messages[0]["content"] == "m3" * 8

        # Assistant with reasoning_content is formatted as structured content blocks
        assistant_content = session_data.history_messages[1]["content"]
        assert isinstance(assistant_content, list)
        assert assistant_content[0] == {"type": "thinking", "thinking": "kept reasoning"}
        assert assistant_content[1] == {"type": "text", "text": "m4" * 8}

    def test_load_chat_session_returns_empty_history_for_no_messages(
        self,
        db_session: Session,
        session_loader_test_data,
        monkeypatch,
    ):
        """Should return empty history when session has no chat messages."""
        monkeypatch.setattr("agent.core.session_loader.AGENT_CHAT_HISTORY_TOKEN_BUDGET", 8)

        loader = SessionLoader(
            project_id=session_loader_test_data["project"].id,
            user_id=session_loader_test_data["user"].id,
        )
        session_data = loader.load_chat_session(db_session)

        assert session_data.history_messages == []

    def test_load_chat_session_keeps_single_message_with_zero_budget(
        self,
        db_session: Session,
        session_loader_test_data,
        monkeypatch,
    ):
        """Should keep the newest single message even if budget is non-positive."""
        monkeypatch.setattr("agent.core.session_loader.AGENT_CHAT_HISTORY_TOKEN_BUDGET", 0)
        _add_chat_messages(
            db_session,
            session_loader_test_data["chat_session"].id,
            [
                {"role": "user", "content": "single message content"},
            ],
        )

        loader = SessionLoader(
            project_id=session_loader_test_data["project"].id,
            user_id=session_loader_test_data["user"].id,
        )
        session_data = loader.load_chat_session(db_session)

        assert [msg["content"] for msg in session_data.history_messages] == ["single message content"]

    def test_load_chat_session_includes_usage_and_stop_reason_from_metadata(
        self,
        db_session: Session,
        session_loader_test_data,
        monkeypatch,
    ):
        """Assistant metadata should be hydrated into history messages for token math."""
        monkeypatch.setattr("agent.core.session_loader.AGENT_CHAT_HISTORY_TOKEN_BUDGET", 100)
        chat_session_id = session_loader_test_data["chat_session"].id

        db_session.add(
            ChatMessage(
                session_id=chat_session_id,
                role="user",
                content="hello",
            )
        )
        db_session.add(
            ChatMessage(
                session_id=chat_session_id,
                role="assistant",
                content="world",
                message_metadata=json.dumps({
                    "stop_reason": "end_turn",
                    "usage": {
                        "input_tokens": 321,
                        "output_tokens": 123,
                        "total_tokens": 444,
                    },
                }),
            )
        )
        db_session.commit()

        loader = SessionLoader(
            project_id=session_loader_test_data["project"].id,
            user_id=session_loader_test_data["user"].id,
        )
        session_data = loader.load_chat_session(db_session)

        assistant_msg = session_data.history_messages[-1]
        assert assistant_msg["role"] == "assistant"
        assert assistant_msg["stop_reason"] == "end_turn"
        assert assistant_msg["usage"]["total_tokens"] == 444

    def test_load_chat_session_synthesizes_status_only_assistant_turns_into_history_content(
        self,
        db_session: Session,
        session_loader_test_data,
        monkeypatch,
    ):
        """Status-only assistant turns should remain visible in model history after reload."""
        monkeypatch.setattr("agent.core.session_loader.AGENT_CHAT_HISTORY_TOKEN_BUDGET", 100)
        chat_session_id = session_loader_test_data["chat_session"].id

        db_session.add(
            ChatMessage(
                session_id=chat_session_id,
                role="user",
                content="继续",
            )
        )
        db_session.add(
            ChatMessage(
                session_id=chat_session_id,
                role="assistant",
                content="",
                message_metadata=json.dumps({
                    "status_cards": [
                        {
                            "type": "workflow_stopped",
                            "reason": "clarification_needed",
                            "question": "请确认主角姓名",
                            "details": ["主角姓名", "时代背景"],
                        }
                    ],
                }),
            )
        )
        db_session.commit()

        loader = SessionLoader(
            project_id=session_loader_test_data["project"].id,
            user_id=session_loader_test_data["user"].id,
        )
        session_data = loader.load_chat_session(db_session)

        assistant_msg = session_data.history_messages[-1]
        assert assistant_msg["role"] == "assistant"
        assert assistant_msg["content"]
        assert "clarification_needed" in assistant_msg["content"]
        assert "请确认主角姓名" in assistant_msg["content"]

    def test_load_chat_session_prefers_latest_active_and_deactivates_stale(
        self,
        db_session: Session,
        session_loader_test_data,
        monkeypatch,
    ):
        """Should deterministically keep latest active session and deactivate stale ones."""
        monkeypatch.setattr("agent.core.session_loader.AGENT_CHAT_HISTORY_TOKEN_BUDGET", 100)
        user = session_loader_test_data["user"]
        project = session_loader_test_data["project"]
        original_session = session_loader_test_data["chat_session"]

        original_session.updated_at = datetime.utcnow() - timedelta(hours=2)
        db_session.add(original_session)

        newer_session = ChatSession(
            user_id=user.id,
            project_id=project.id,
            title="Newest session",
            is_active=True,
            message_count=0,
            created_at=datetime.utcnow() - timedelta(minutes=30),
            updated_at=datetime.utcnow(),
        )
        older_session = ChatSession(
            user_id=user.id,
            project_id=project.id,
            title="Older stale session",
            is_active=True,
            message_count=0,
            created_at=datetime.utcnow() - timedelta(hours=1),
            updated_at=datetime.utcnow() - timedelta(hours=1),
        )
        db_session.add(newer_session)
        db_session.add(older_session)
        db_session.commit()
        db_session.refresh(newer_session)
        db_session.refresh(older_session)

        _add_chat_messages(
            db_session,
            newer_session.id,
            [
                {"role": "user", "content": "newer-user"},
                {"role": "assistant", "content": "newer-assistant"},
            ],
        )
        _add_chat_messages(
            db_session,
            older_session.id,
            [
                {"role": "user", "content": "older-user"},
            ],
        )

        loader = SessionLoader(project_id=project.id, user_id=user.id)
        session_data = loader.load_chat_session(db_session)

        assert session_data.session_id == newer_session.id
        assert [msg["content"] for msg in session_data.history_messages] == [
            "newer-user",
            "newer-assistant",
        ]

        refreshed = db_session.exec(
            select(ChatSession).where(
                ChatSession.project_id == project.id,
                ChatSession.user_id == user.id,
            )
        ).all()
        active_sessions = [row for row in refreshed if row.is_active]
        assert len(active_sessions) == 1
        assert active_sessions[0].id == newer_session.id

    def test_load_chat_session_handles_long_history_over_100_turns(
        self,
        db_session: Session,
        session_loader_test_data,
        monkeypatch,
    ):
        """
        Long sessions (100+ turns) should still return a stable, chronological
        sliding window under token budget.
        """
        monkeypatch.setattr("agent.core.session_loader.AGENT_CHAT_HISTORY_TOKEN_BUDGET", 70)
        chat_session_id = session_loader_test_data["chat_session"].id

        base_time = datetime.utcnow()
        for i in range(120):
            role = "user" if i % 2 == 0 else "assistant"
            content = f"turn-{i:03d}-" + ("x" * 32)
            db_session.add(
                ChatMessage(
                    session_id=chat_session_id,
                    role=role,
                    content=content,
                    created_at=base_time + timedelta(seconds=i),
                )
            )
        db_session.commit()

        loader = SessionLoader(
            project_id=session_loader_test_data["project"].id,
            user_id=session_loader_test_data["user"].id,
        )
        session_data = loader.load_chat_session(db_session)

        contents = [msg["content"] for msg in session_data.history_messages]
        assert len(contents) > 0
        assert len(contents) < 120  # sliding window trimmed old history
        assert contents[-1].startswith("turn-119-")  # newest turn preserved
        # remaining window should stay chronological
        turn_indexes = [int(text.split("-")[1]) for text in contents]
        assert turn_indexes == sorted(turn_indexes)

    def test_tool_call_turn_replays_as_text_breadcrumb(
        self,
        db_session: Session,
        session_loader_test_data,
        monkeypatch,
    ):
        """A prior tool-call turn should replay as a plain-text breadcrumb naming the file id."""
        monkeypatch.setattr("agent.core.session_loader.AGENT_CHAT_HISTORY_TOKEN_BUDGET", 500)
        chat_session_id = session_loader_test_data["chat_session"].id

        db_session.add(
            ChatMessage(
                session_id=chat_session_id,
                role="user",
                content="帮我创建第一章大纲",
            )
        )
        db_session.add(
            ChatMessage(
                session_id=chat_session_id,
                role="assistant",
                content="好的，已经为你建立大纲。",
                tool_calls=json.dumps(
                    [
                        {
                            "id": "call_1",
                            "name": "create_file",
                            "arguments": {"title": "第一章大纲", "file_type": "outline"},
                            "status": "success",
                            "result": {"id": "file-abc-123", "title": "第一章大纲"},
                            "error": None,
                        }
                    ]
                ),
            )
        )
        db_session.commit()

        loader = SessionLoader(
            project_id=session_loader_test_data["project"].id,
            user_id=session_loader_test_data["user"].id,
        )
        session_data = loader.load_chat_session(db_session)

        assistant_msg = session_data.history_messages[-1]
        assert assistant_msg["role"] == "assistant"

        content = assistant_msg["content"]
        content_text = (
            content
            if isinstance(content, str)
            else "\n".join(
                block.get("text", "")
                for block in content
                if isinstance(block, dict) and block.get("type") == "text"
            )
        )

        # Breadcrumb is plain TEXT and names the created file by id.
        assert "已创建文件" in content_text
        assert "file-abc-123" in content_text
        assert "第一章大纲" in content_text
        # The original prose reply is preserved alongside the breadcrumb.
        assert "已经为你建立大纲" in content_text

    def test_tool_call_breadcrumb_emits_no_raw_tool_blocks(
        self,
        db_session: Session,
        session_loader_test_data,
        monkeypatch,
    ):
        """Replayed history must never contain raw tool_use/tool_result blocks or orphaned tool_call_id."""
        from agent.openai_agents.runner import normalize_messages_for_openai_agents

        monkeypatch.setattr("agent.core.session_loader.AGENT_CHAT_HISTORY_TOKEN_BUDGET", 500)
        chat_session_id = session_loader_test_data["chat_session"].id

        db_session.add(
            ChatMessage(
                session_id=chat_session_id,
                role="user",
                content="把第二章删掉",
            )
        )
        db_session.add(
            ChatMessage(
                session_id=chat_session_id,
                role="assistant",
                content="",
                tool_calls=json.dumps(
                    [
                        {
                            "id": "call_del_1",
                            "name": "delete_file",
                            "arguments": {"id": "file-del-9"},
                            "status": "success",
                            "result": {"id": "file-del-9", "title": "第二章"},
                            "error": None,
                        }
                    ]
                ),
            )
        )
        db_session.commit()

        loader = SessionLoader(
            project_id=session_loader_test_data["project"].id,
            user_id=session_loader_test_data["user"].id,
        )
        session_data = loader.load_chat_session(db_session)

        # Even with empty prose, the breadcrumb keeps the turn visible.
        assistant_msg = session_data.history_messages[-1]
        breadcrumb_content = assistant_msg["content"]
        breadcrumb_text = (
            breadcrumb_content
            if isinstance(breadcrumb_content, str)
            else json.dumps(breadcrumb_content, ensure_ascii=False)
        )
        assert "已删除文件" in breadcrumb_text
        assert "file-del-9" in breadcrumb_text

        # Normalizing for the SDK must produce ONLY plain user/assistant text —
        # no tool_use / tool_result blocks and therefore no orphaned tool_call_id.
        normalized = normalize_messages_for_openai_agents(session_data.history_messages)
        for message in normalized:
            assert set(message.keys()) == {"role", "content"}
            assert message["role"] in {"user", "assistant"}
            assert isinstance(message["content"], str)
            assert "tool_use" not in message["content"]
            assert "tool_result" not in message["content"]
            assert "tool_call_id" not in message["content"]
            assert "call_del_1" not in message["content"]

    def test_failed_tool_call_turn_emits_no_breadcrumb(
        self,
        db_session: Session,
        session_loader_test_data,
        monkeypatch,
    ):
        """A failed tool call should not synthesize a misleading 'created file' breadcrumb."""
        monkeypatch.setattr("agent.core.session_loader.AGENT_CHAT_HISTORY_TOKEN_BUDGET", 500)
        chat_session_id = session_loader_test_data["chat_session"].id

        db_session.add(
            ChatMessage(
                session_id=chat_session_id,
                role="user",
                content="创建文件",
            )
        )
        db_session.add(
            ChatMessage(
                session_id=chat_session_id,
                role="assistant",
                content="抱歉，创建失败了。",
                tool_calls=json.dumps(
                    [
                        {
                            "id": "call_err",
                            "name": "create_file",
                            "arguments": {"title": "失败文件"},
                            "status": "error",
                            "result": None,
                            "error": "permission denied",
                        }
                    ]
                ),
            )
        )
        db_session.commit()

        loader = SessionLoader(
            project_id=session_loader_test_data["project"].id,
            user_id=session_loader_test_data["user"].id,
        )
        session_data = loader.load_chat_session(db_session)

        assistant_msg = session_data.history_messages[-1]
        assert assistant_msg["content"] == "抱歉，创建失败了。"
        assert "已创建文件" not in str(assistant_msg["content"])

    def test_load_chat_session_allows_superuser_cross_project(
        self,
        db_session: Session,
        session_loader_test_data,
        monkeypatch,
    ):
        """Superuser should be able to load chat session for projects they do not own."""
        monkeypatch.setattr("agent.core.session_loader.AGENT_CHAT_HISTORY_TOKEN_BUDGET", 100)
        project = session_loader_test_data["project"]
        suffix = uuid4().hex[:8]
        superuser = User(
            email=f"session-loader-admin-{suffix}@example.com",
            username=f"session_loader_admin_{suffix}",
            hashed_password="hashed",
            name="Session Loader Admin",
            email_verified=True,
            is_active=True,
            is_superuser=True,
        )
        db_session.add(superuser)
        db_session.commit()
        db_session.refresh(superuser)

        admin_chat_session = ChatSession(
            user_id=superuser.id,
            project_id=project.id,
            title="Admin session",
            is_active=True,
            message_count=0,
        )
        db_session.add(admin_chat_session)
        db_session.commit()
        db_session.refresh(admin_chat_session)

        _add_chat_messages(
            db_session,
            admin_chat_session.id,
            [
                {"role": "user", "content": "admin-user"},
                {"role": "assistant", "content": "admin-assistant"},
            ],
        )

        loader = SessionLoader(project_id=project.id, user_id=superuser.id)
        session_data = loader.load_chat_session(db_session)

        assert session_data.session_id == admin_chat_session.id
        assert [msg["content"] for msg in session_data.history_messages] == [
            "admin-user",
            "admin-assistant",
        ]
