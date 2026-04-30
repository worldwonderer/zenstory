"""
Tests for SessionLoader compaction integration.
"""

import json
from datetime import datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlmodel import Session, select

from agent.context.compaction import CompactionResult
from agent.core.session_loader import SessionLoader
from models import AgentArtifactLedger, ChatMessage, ChatSession, Project, User


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
class TestSessionLoaderCompaction:
    """Tests for applying compaction results to session history."""

    def test_apply_compaction_falls_back_to_messages_removed_without_ids(self):
        """Should cut by messages_removed when history messages do not include IDs."""
        loader = SessionLoader(project_id="proj-1", user_id="user-1")
        messages = [
            {"role": "user", "content": "msg-0"},
            {"role": "assistant", "content": "msg-1"},
            {"role": "user", "content": "msg-2"},
            {"role": "assistant", "content": "msg-3"},
        ]
        compaction_result = CompactionResult(
            summary="summary text",
            first_kept_message_id="",
            tokens_before=1000,
            tokens_after=400,
            messages_removed=2,
        )

        compacted = loader._apply_compaction(messages, compaction_result)

        assert compacted[0]["metadata"]["type"] == "compaction_summary"
        assert compacted[0]["metadata"]["semantic_role"] == "system_memory"
        assert compacted[0]["role"] == "assistant"
        assert compacted[0]["content"][0]["type"] == "text"
        assert [m["content"] for m in compacted[1:]] == ["msg-2", "msg-3"]

    def test_apply_compaction_prefers_first_kept_message_id_when_available(self):
        """Should use first_kept_message_id over fallback cut index when IDs exist."""
        loader = SessionLoader(project_id="proj-1", user_id="user-1")
        messages = [
            {"id": "m0", "role": "user", "content": "msg-0"},
            {"id": "m1", "role": "assistant", "content": "msg-1"},
            {"id": "m2", "role": "user", "content": "msg-2"},
            {"id": "m3", "role": "assistant", "content": "msg-3"},
        ]
        compaction_result = CompactionResult(
            summary="summary text",
            first_kept_message_id="m1",
            tokens_before=1000,
            tokens_after=800,
            messages_removed=3,
        )

        compacted = loader._apply_compaction(messages, compaction_result)

        assert compacted[0]["metadata"]["type"] == "compaction_summary"
        assert compacted[0]["metadata"]["semantic_role"] == "system_memory"
        assert compacted[0]["role"] == "assistant"
        assert compacted[0]["content"][0]["type"] == "text"
        assert [m["content"] for m in compacted[1:]] == ["msg-1", "msg-2", "msg-3"]

    def test_load_previous_compaction_summary_from_artifact_ledger(
        self,
        db_session: Session,
        session_loader_test_data,
    ):
        """Should read latest compaction summary checkpoint from artifact ledger."""
        chat_session = session_loader_test_data["chat_session"]
        project = session_loader_test_data["project"]
        user = session_loader_test_data["user"]

        db_session.add(
            AgentArtifactLedger(
                project_id=project.id,
                session_id=chat_session.id,
                user_id=user.id,
                action="compaction_summary",
                tool_name="context_compaction",
                artifact_ref=f"compaction:{chat_session.id}",
                payload=json.dumps({"summary": "older-summary"}),
                created_at=datetime.utcnow() - timedelta(minutes=1),
            )
        )
        db_session.add(
            AgentArtifactLedger(
                project_id=project.id,
                session_id=chat_session.id,
                user_id=user.id,
                action="compaction_summary",
                tool_name="context_compaction",
                artifact_ref=f"compaction:{chat_session.id}",
                payload=json.dumps({"summary": "latest-summary"}),
                created_at=datetime.utcnow(),
            )
        )
        db_session.commit()

        loader = SessionLoader(project_id=project.id, user_id=user.id)
        summary = loader._load_previous_compaction_summary(db_session, chat_session.id)
        assert summary == "latest-summary"

    def test_load_previous_compaction_summary_falls_back_when_latest_payload_invalid(
        self,
        db_session: Session,
        session_loader_test_data,
    ):
        """Should fall back to older valid checkpoint if latest payload cannot provide summary."""
        chat_session = session_loader_test_data["chat_session"]
        project = session_loader_test_data["project"]
        user = session_loader_test_data["user"]

        db_session.add(
            AgentArtifactLedger(
                project_id=project.id,
                session_id=chat_session.id,
                user_id=user.id,
                action="compaction_summary",
                tool_name="context_compaction",
                artifact_ref=f"compaction:{chat_session.id}",
                payload=json.dumps({"summary": "older-valid-summary"}),
                created_at=datetime.utcnow() - timedelta(minutes=1),
            )
        )
        db_session.add(
            AgentArtifactLedger(
                project_id=project.id,
                session_id=chat_session.id,
                user_id=user.id,
                action="compaction_summary",
                tool_name="context_compaction",
                artifact_ref=f"compaction:{chat_session.id}",
                payload="{}",
                created_at=datetime.utcnow(),
            )
        )
        db_session.commit()

        loader = SessionLoader(project_id=project.id, user_id=user.id)
        summary = loader._load_previous_compaction_summary(db_session, chat_session.id)
        assert summary == "older-valid-summary"

    def test_load_previous_compaction_summary_skips_unsupported_schema_version(
        self,
        db_session: Session,
        session_loader_test_data,
    ):
        """Should skip rows with unknown schema_version and use latest supported checkpoint."""
        chat_session = session_loader_test_data["chat_session"]
        project = session_loader_test_data["project"]
        user = session_loader_test_data["user"]

        db_session.add(
            AgentArtifactLedger(
                project_id=project.id,
                session_id=chat_session.id,
                user_id=user.id,
                action="compaction_summary",
                tool_name="context_compaction",
                artifact_ref=f"compaction:{chat_session.id}",
                payload=json.dumps({"schema_version": 1, "summary": "supported-summary"}),
                created_at=datetime.utcnow() - timedelta(minutes=1),
            )
        )
        db_session.add(
            AgentArtifactLedger(
                project_id=project.id,
                session_id=chat_session.id,
                user_id=user.id,
                action="compaction_summary",
                tool_name="context_compaction",
                artifact_ref=f"compaction:{chat_session.id}",
                payload=json.dumps({"schema_version": 2, "summary": "future-summary"}),
                created_at=datetime.utcnow(),
            )
        )
        db_session.commit()

        loader = SessionLoader(project_id=project.id, user_id=user.id)
        summary = loader._load_previous_compaction_summary(db_session, chat_session.id)
        assert summary == "supported-summary"

    @pytest.mark.asyncio
    async def test_load_session_with_compaction_uses_previous_summary_and_persists_checkpoint(
        self,
        db_session: Session,
        session_loader_test_data,
        monkeypatch,
    ):
        """
        Incremental compaction chain:
        - load previous summary from ledger
        - pass it into compact_context(previous_summary=...)
        - persist new checkpoint after compaction
        """
        chat_session = session_loader_test_data["chat_session"]
        project = session_loader_test_data["project"]
        user = session_loader_test_data["user"]

        _add_chat_messages(
            db_session,
            chat_session.id,
            [
                {"role": "user", "content": "old-message-1"},
                {"role": "assistant", "content": "old-message-2"},
            ],
        )

        db_session.add(
            AgentArtifactLedger(
                project_id=project.id,
                session_id=chat_session.id,
                user_id=user.id,
                action="compaction_summary",
                tool_name="context_compaction",
                artifact_ref=f"compaction:{chat_session.id}",
                payload=json.dumps({"summary": "previous-ledger-summary"}),
            )
        )
        db_session.commit()

        monkeypatch.setattr(
            "agent.context.compaction.should_compact",
            lambda *_args, **_kwargs: True,
        )

        captured: dict[str, str | None] = {"previous_summary": None}
        expected_result = CompactionResult(
            summary="new-compaction-summary",
            first_kept_message_id="",
            tokens_before=120000,
            tokens_after=24000,
            messages_removed=1,
        )

        async def _fake_compact_context(
            messages,  # noqa: ANN001
            settings,  # noqa: ANN001
            previous_summary=None,  # noqa: ANN001
            context_window=0,  # noqa: ANN001
        ):
            _ = messages, settings, context_window
            captured["previous_summary"] = previous_summary
            return expected_result

        monkeypatch.setattr(
            "agent.context.compaction.compact_context",
            _fake_compact_context,
        )

        loader = SessionLoader(project_id=project.id, user_id=user.id)
        session_data = await loader.load_session_with_compaction(
            session=db_session,
            context_assembler=SimpleNamespace(
                assemble=lambda **_kwargs: SimpleNamespace(
                    context="",
                    items=[],
                    refs=[],
                    token_estimate=0,
                    original_item_count=0,
                    trimmed_item_count=0,
                    budget_used={},
                )
            ),
            query="please continue",
            enable_compaction=True,
        )

        assert captured["previous_summary"] == "previous-ledger-summary"
        assert session_data.compaction_result is not None
        assert session_data.compaction_result.summary == "new-compaction-summary"

        db_session.commit()
        rows = db_session.exec(
            select(AgentArtifactLedger).where(
                AgentArtifactLedger.project_id == project.id,
                AgentArtifactLedger.session_id == chat_session.id,
                AgentArtifactLedger.action == "compaction_summary",
            )
        ).all()
        payload_summaries = []
        new_payload: dict[str, str | int] | None = None
        for row in rows:
            if not row.payload:
                continue
            payload = json.loads(row.payload)
            payload_summaries.append(payload.get("summary"))
            if payload.get("summary") == "new-compaction-summary":
                new_payload = payload

        assert "previous-ledger-summary" in payload_summaries
        assert "new-compaction-summary" in payload_summaries
        assert new_payload is not None
        assert new_payload.get("schema_version") == 1

    def test_persist_compaction_summary_checkpoint_prunes_stale_rows(
        self,
        db_session: Session,
        session_loader_test_data,
        monkeypatch,
    ):
        """Should keep only latest N checkpoints according to retention setting."""
        chat_session = session_loader_test_data["chat_session"]
        project = session_loader_test_data["project"]
        user = session_loader_test_data["user"]

        base_time = datetime.utcnow()
        for idx in range(3):
            db_session.add(
                AgentArtifactLedger(
                    project_id=project.id,
                    session_id=chat_session.id,
                    user_id=user.id,
                    action="compaction_summary",
                    tool_name="context_compaction",
                    artifact_ref=f"compaction:{chat_session.id}",
                    payload=json.dumps({"summary": f"old-{idx + 1}"}),
                    created_at=base_time - timedelta(minutes=3 - idx),
                )
            )
        db_session.commit()

        monkeypatch.setattr(
            "agent.core.session_loader.AGENT_COMPACTION_CHECKPOINT_RETENTION",
            2,
        )

        loader = SessionLoader(project_id=project.id, user_id=user.id)
        loader._persist_compaction_summary_checkpoint(
            session=db_session,
            session_id=chat_session.id,
            summary="new-summary",
            tokens_before=100,
            tokens_after=20,
            messages_removed=2,
        )
        db_session.commit()

        rows = db_session.exec(
            select(AgentArtifactLedger)
            .where(
                AgentArtifactLedger.project_id == project.id,
                AgentArtifactLedger.session_id == chat_session.id,
                AgentArtifactLedger.action == "compaction_summary",
            )
            .order_by(AgentArtifactLedger.created_at.desc())
        ).all()
        assert len(rows) == 2

        summaries = [
            json.loads(row.payload).get("summary")
            for row in rows
            if row.payload
        ]
        assert "new-summary" in summaries
        assert "old-3" in summaries


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
        monkeypatch.setattr("agent.core.session_loader.AGENT_CHAT_HISTORY_TOKEN_BUDGET", 12)
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
        """Assistant metadata should be hydrated into history messages for compaction math."""
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
