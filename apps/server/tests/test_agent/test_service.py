"""
Agent Service tests.

Unit tests for the AgentService business logic with mocked dependencies.
Tests core functionality without making real Anthropic API calls.

Updated for LangGraph architecture.
"""

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlmodel import Session, desc, select

from models import ChatMessage, ChatSession, File, Project, PublicSkill, User, UserAddedSkill, UserSkill
from services.core.auth_service import hash_password


@pytest.fixture
def test_user_with_project(db_session: Session):
    """Create a test user with project for agent service testing."""
    # Create user
    user = User(
        email="agent_service_test@example.com",
        username="agentservicetest",
        hashed_password=hash_password("password123"),
        name="Agent Service Test User",
        email_verified=True,
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    # Create project
    project = Project(
        name="Agent Service Test Project",
        description="A test project for agent service",
        owner_id=user.id,
        project_type="novel",
    )
    db_session.add(project)
    db_session.commit()
    db_session.refresh(project)

    # Create a draft file
    draft_file = File(
        title="第一章",
        content="这是第一章的内容。",
        file_type="draft",
        project_id=project.id,
        user_id=user.id,
    )
    db_session.add(draft_file)
    db_session.commit()
    db_session.refresh(draft_file)

    return {
        "user": user,
        "project": project,
        "draft_file": draft_file,
    }


@pytest.fixture
def mock_langgraph_workflow():
    """Mock the LangGraph workflow for testing."""
    from agent.llm.anthropic_client import StreamEvent, StreamEventType

    async def mock_stream():
        yield StreamEvent(type=StreamEventType.TEXT, data={"text": "Hello"})
        yield StreamEvent(type=StreamEventType.TEXT, data={"text": " World"})
        yield StreamEvent(type=StreamEventType.MESSAGE_END, data={"stop_reason": "end_turn"})

    with patch("agent.service.run_writing_workflow_streaming") as mock:
        mock.return_value = mock_stream()
        yield mock


@pytest.fixture
def mock_agent_service():
    """Create an AgentService instance with mocked dependencies."""
    with patch("agent.service.get_context_assembler") as mock_get_context:
        mock_context_assembler = MagicMock()
        mock_get_context.return_value = mock_context_assembler

        # Mock context data
        from agent.schemas.context import ContextData
        mock_context_assembler.assemble.return_value = ContextData(
            items=[],
            context="",
            token_estimate=0,
        )

        from agent.service import AgentService
        service = AgentService(
            context_assembler=mock_context_assembler,
        )

        yield service, mock_context_assembler


@pytest.mark.unit
class TestAgentServiceInit:
    """Tests for AgentService initialization."""

    def test_agent_service_init_default(self):
        """Test AgentService initialization with default dependencies."""
        with patch("agent.service.get_context_assembler") as mock_get_context:
            from agent.service import AgentService

            mock_context_assembler = MagicMock()
            mock_get_context.return_value = mock_context_assembler

            service = AgentService()

            assert service.context_assembler == mock_context_assembler
            mock_get_context.assert_called_once()

    def test_agent_service_init_with_dependencies(self):
        """Test AgentService initialization with provided dependencies."""
        mock_context_assembler = MagicMock()

        from agent.service import AgentService
        service = AgentService(
            context_assembler=mock_context_assembler,
        )

        assert service.context_assembler == mock_context_assembler




@pytest.mark.integration
class TestAgentServiceProcessStream:
    """Integration tests for process_stream method with mocked LangGraph workflow."""

    @pytest.fixture
    def mock_workflow_stream(self):
        """Create a mock LangGraph workflow stream."""
        from agent.llm.anthropic_client import StreamEvent, StreamEventType

        async def mock_stream():
            yield StreamEvent(type=StreamEventType.TEXT, data={"text": "Hello"})
            yield StreamEvent(type=StreamEventType.TEXT, data={"text": " World"})
            yield StreamEvent(type=StreamEventType.MESSAGE_END, data={"stop_reason": "end_turn"})

        return mock_stream

    async def test_process_stream_simple_response(
        self, mock_agent_service, test_user_with_project, db_session: Session, mock_workflow_stream
    ):
        """Test processing a simple user message with text response."""
        service, mock_context_assembler = mock_agent_service

        project = test_user_with_project["project"]
        user = test_user_with_project["user"]

        with patch("agent.service.run_writing_workflow_streaming") as mock_workflow:
            mock_workflow.return_value = mock_workflow_stream()

            # Collect events
            events = []
            async for event in service.process_stream(
                project_id=str(project.id),
                user_id=str(user.id),
                message="Hello",
                session=db_session,
            ):
                events.append(event)

            # Verify we got events
            assert len(events) > 0

            # Should get at least thinking and done events
            event_types = set()
            for event in events:
                if "event: thinking" in event:
                    event_types.add("thinking")
                elif "event: content" in event:
                    event_types.add("content")
                elif "event: done" in event:
                    event_types.add("done")

            assert len(event_types) > 0

    async def test_process_stream_with_chat_history(
        self, mock_agent_service, test_user_with_project, db_session: Session, mock_workflow_stream
    ):
        """Test processing message with existing chat history."""
        service, mock_context_assembler = mock_agent_service

        project = test_user_with_project["project"]
        user = test_user_with_project["user"]

        # Create existing chat session
        chat_session = ChatSession(
            user_id=str(user.id),
            project_id=str(project.id),
            title="Test Chat",
            is_active=True,
            message_count=2,
        )
        db_session.add(chat_session)
        db_session.commit()
        db_session.refresh(chat_session)

        # Add existing messages
        db_session.add(ChatMessage(
            session_id=chat_session.id,
            role="user",
            content="Previous message",
        ))
        db_session.add(ChatMessage(
            session_id=chat_session.id,
            role="assistant",
            content="Previous response",
        ))
        db_session.commit()

        with patch("agent.service.run_writing_workflow_streaming") as mock_workflow:
            mock_workflow.return_value = mock_workflow_stream()

            # Process stream
            events = []
            async for event in service.process_stream(
                project_id=str(project.id),
                user_id=str(user.id),
                message="New message",
                session=db_session,
            ):
                events.append(event)

            # Verify events received
            assert len(events) > 0

    async def test_process_stream_with_selected_text(
        self, mock_agent_service, test_user_with_project, db_session: Session, mock_workflow_stream
    ):
        """Test processing message with selected text context."""
        service, mock_context_assembler = mock_agent_service

        project = test_user_with_project["project"]
        user = test_user_with_project["user"]

        with patch("agent.service.run_writing_workflow_streaming") as mock_workflow:
            mock_workflow.return_value = mock_workflow_stream()

            selected_text = "This is the selected text"
            events = []
            async for event in service.process_stream(
                project_id=str(project.id),
                user_id=str(user.id),
                message="Explain this",
                session=db_session,
                selected_text=selected_text,
            ):
                events.append(event)

            assert len(events) > 0

    async def test_process_stream_resolves_explicit_skill_prefix_without_mutating_saved_user_message(
        self,
        mock_agent_service,
        test_user_with_project,
        db_session: Session,
        mock_workflow_stream,
    ):
        """Leading skill prefixes should become explicit skill instructions, not pollute runtime user content."""
        service, _ = mock_agent_service

        project = test_user_with_project["project"]
        user = test_user_with_project["user"]

        skill = UserSkill(
            user_id=user.id,
            name="悬念大师",
            description="增强钩子和悬念",
            triggers=json.dumps(["悬念大师"]),
            instructions="先强化钩子，再收紧悬念。",
            is_active=True,
        )
        db_session.add(skill)
        db_session.commit()

        raw_message = "悬念大师 帮我把第一段写得更有钩子"
        cleaned_message = "帮我把第一段写得更有钩子"

        with patch("agent.service.run_writing_workflow_streaming") as mock_workflow:
            mock_workflow.return_value = mock_workflow_stream()

            async for _ in service.process_stream(
                project_id=str(project.id),
                user_id=str(user.id),
                message=raw_message,
                session=db_session,
            ):
                pass

        assert mock_workflow.call_args is not None
        writing_state = mock_workflow.call_args.args[0]
        assert writing_state["router_message"] == cleaned_message
        assert writing_state["user_message"] == cleaned_message
        assert "## 用户本条消息指定技能" in writing_state["system_prompt"]
        assert "### 悬念大师" in writing_state["system_prompt"]
        assert "[使用技能: 悬念大师]" in writing_state["system_prompt"]

        latest_user_message = db_session.exec(
            select(ChatMessage)
            .join(ChatSession, ChatMessage.session_id == ChatSession.id)
            .where(ChatSession.project_id == str(project.id))
            .where(ChatMessage.role == "user")
            .order_by(desc(ChatMessage.created_at), desc(ChatMessage.id))
        ).first()
        assert latest_user_message is not None
        assert latest_user_message.content == raw_message

    async def test_process_stream_skips_forced_skill_selection_when_prefix_is_ambiguous(
        self,
        mock_agent_service,
        test_user_with_project,
        db_session: Session,
        mock_workflow_stream,
    ):
        """Ambiguous leading prefixes should fail closed and preserve the raw message."""
        service, _ = mock_agent_service

        project = test_user_with_project["project"]
        user = test_user_with_project["user"]

        db_session.add(
            UserSkill(
                user_id=user.id,
                name="悬念大师",
                description="增强钩子和悬念",
                triggers=json.dumps(["通用触发词"]),
                instructions="先强化钩子，再收紧悬念。",
                is_active=True,
            )
        )
        db_session.add(
            UserSkill(
                user_id=user.id,
                name="节奏大师",
                description="压缩拖沓段落",
                triggers=json.dumps(["通用触发词"]),
                instructions="优先压缩重复动作和解释。",
                is_active=True,
            )
        )
        db_session.commit()

        raw_message = "通用触发词 帮我处理这一段"

        with patch("agent.service.run_writing_workflow_streaming") as mock_workflow:
            mock_workflow.return_value = mock_workflow_stream()

            async for _ in service.process_stream(
                project_id=str(project.id),
                user_id=str(user.id),
                message=raw_message,
                session=db_session,
            ):
                pass

        assert mock_workflow.call_args is not None
        writing_state = mock_workflow.call_args.args[0]
        assert writing_state["router_message"] == raw_message
        assert writing_state["user_message"] == raw_message
        assert "## 用户本条消息指定技能" not in writing_state["system_prompt"]

    async def test_process_stream_resolves_added_skill_custom_name_prefix(
        self,
        mock_agent_service,
        test_user_with_project,
        db_session: Session,
        mock_workflow_stream,
    ):
        """Added public skills should resolve from the user's custom display name."""
        service, _ = mock_agent_service

        project = test_user_with_project["project"]
        user = test_user_with_project["user"]

        public_skill = PublicSkill(
            name="氛围渲染器",
            description="强化氛围和情绪",
            instructions="优先写环境与感官细节。",
            tags="[]",
            status="approved",
        )
        db_session.add(public_skill)
        db_session.commit()
        db_session.refresh(public_skill)

        db_session.add(
            UserAddedSkill(
                user_id=user.id,
                public_skill_id=public_skill.id,
                custom_name="阴影编织者",
                is_active=True,
            )
        )
        db_session.commit()

        raw_message = "阴影编织者 帮我把这场戏写得更阴冷"
        cleaned_message = "帮我把这场戏写得更阴冷"

        with patch("agent.service.run_writing_workflow_streaming") as mock_workflow:
            mock_workflow.return_value = mock_workflow_stream()

            async for _ in service.process_stream(
                project_id=str(project.id),
                user_id=str(user.id),
                message=raw_message,
                session=db_session,
            ):
                pass

        assert mock_workflow.call_args is not None
        writing_state = mock_workflow.call_args.args[0]
        assert writing_state["router_message"] == cleaned_message
        assert writing_state["user_message"] == cleaned_message
        assert "## 用户本条消息指定技能" in writing_state["system_prompt"]
        assert "### 阴影编织者" in writing_state["system_prompt"]
        assert "[使用技能: 阴影编织者]" in writing_state["system_prompt"]

    async def test_process_stream_without_user_id(
        self, mock_agent_service, test_user_with_project, db_session: Session, mock_workflow_stream
    ):
        """Test processing message without user_id (no history saved)."""
        service, mock_context_assembler = mock_agent_service

        project = test_user_with_project["project"]

        with patch("agent.service.run_writing_workflow_streaming") as mock_workflow:
            mock_workflow.return_value = mock_workflow_stream()

            events = []
            async for event in service.process_stream(
                project_id=str(project.id),
                user_id=None,  # No user_id
                message="Hello from anonymous",
                session=db_session,
            ):
                events.append(event)

            # Should still get response
            assert len(events) > 0

    async def test_process_stream_with_tool_calls(
        self, mock_agent_service, test_user_with_project, db_session: Session
    ):
        """Tool results should be associated by tool_use_id instead of append-order."""
        from agent.llm.anthropic_client import StreamEvent, StreamEventType

        service, mock_context_assembler = mock_agent_service

        project = test_user_with_project["project"]
        user = test_user_with_project["user"]

        async def mock_stream_with_tools():
            yield StreamEvent(type=StreamEventType.TEXT, data={"text": "Creating file..."})
            yield StreamEvent(
                type=StreamEventType.TOOL_USE,
                data={
                    "id": "tool-1",
                    "name": "create_file",
                    "status": "complete",
                    "input": {"title": "第一章"},
                },
            )
            yield StreamEvent(
                type=StreamEventType.TOOL_USE,
                data={
                    "id": "tool-2",
                    "name": "query_files",
                    "status": "complete",
                    "input": {"query": "大纲"},
                },
            )
            yield StreamEvent(
                type=StreamEventType.TOOL_RESULT,
                data={
                    "tool_use_id": "tool-2",
                    "name": "query_files",
                    "result": {"content": [{"type": "text", "text": '{"status": "success"}'}]},
                },
            )
            yield StreamEvent(
                type=StreamEventType.TOOL_RESULT,
                data={
                    "tool_use_id": "tool-1",
                    "name": "create_file",
                    "result": {"content": [{"type": "text", "text": '{"status": "success"}'}]},
                },
            )
            yield StreamEvent(type=StreamEventType.MESSAGE_END, data={"stop_reason": "end_turn"})

        with patch("agent.service.run_writing_workflow_streaming") as mock_workflow:
            mock_workflow.return_value = mock_stream_with_tools()

            events = []
            async for event in service.process_stream(
                project_id=str(project.id),
                user_id=str(user.id),
                message="Create a new chapter",
                session=db_session,
            ):
                events.append(event)

            assert len(events) > 0

        chat_session = db_session.exec(
            select(ChatSession)
            .where(ChatSession.project_id == str(project.id), ChatSession.user_id == str(user.id))
            .order_by(desc(ChatSession.updated_at), desc(ChatSession.created_at), desc(ChatSession.id))
        ).first()
        assert chat_session is not None

        latest_assistant = db_session.exec(
            select(ChatMessage)
            .where(ChatMessage.session_id == chat_session.id, ChatMessage.role == "assistant")
            .order_by(desc(ChatMessage.created_at), desc(ChatMessage.id))
        ).first()
        assert latest_assistant is not None
        assert latest_assistant.tool_calls is not None
        tool_calls = json.loads(latest_assistant.tool_calls)
        assert len(tool_calls) == 2

        call_by_id = {call["id"]: call for call in tool_calls}
        assert call_by_id["tool-1"]["name"] == "create_file"
        assert call_by_id["tool-1"]["status"] == "success"
        assert call_by_id["tool-2"]["name"] == "query_files"
        assert call_by_id["tool-2"]["status"] == "success"

    async def test_process_stream_with_custom_session_id(
        self, mock_agent_service, test_user_with_project, db_session: Session, mock_workflow_stream
    ):
        """Test process_stream can reuse caller-provided session ID."""
        service, _ = mock_agent_service
        project = test_user_with_project["project"]
        user = test_user_with_project["user"]
        custom_session_id = "test-session-id-123"

        with patch("agent.service.run_writing_workflow_streaming") as mock_workflow:
            mock_workflow.return_value = mock_workflow_stream()

            events = []
            async for event in service.process_stream(
                project_id=str(project.id),
                user_id=str(user.id),
                message="Hello",
                session=db_session,
                session_id=custom_session_id,
            ):
                events.append(event)

        session_started_events = [event for event in events if "event: session_started" in event]
        assert session_started_events, "Expected session_started event"
        assert custom_session_id in session_started_events[0]

    async def test_process_stream_saves_to_resolved_session_even_if_it_becomes_inactive(
        self, mock_agent_service, test_user_with_project, db_session: Session
    ):
        """Stream completion should persist to the resolved session, not whichever session is active later."""
        from agent.llm.anthropic_client import StreamEvent, StreamEventType

        service, _ = mock_agent_service
        project = test_user_with_project["project"]
        user = test_user_with_project["user"]

        target_session = ChatSession(
            id="resolved-session-id",
            user_id=str(user.id),
            project_id=str(project.id),
            title="Resolved session",
            is_active=True,
            message_count=0,
        )
        newer_session = ChatSession(
            user_id=str(user.id),
            project_id=str(project.id),
            title="New active session",
            is_active=False,
            message_count=0,
        )
        db_session.add(target_session)
        db_session.add(newer_session)
        db_session.commit()
        db_session.refresh(target_session)
        db_session.refresh(newer_session)

        async def mock_stream_switching_active_session():
            yield StreamEvent(type=StreamEventType.TEXT, data={"text": "Draft reply"})
            target_session.is_active = False
            newer_session.is_active = True
            db_session.add(target_session)
            db_session.add(newer_session)
            db_session.commit()
            yield StreamEvent(type=StreamEventType.MESSAGE_END, data={"stop_reason": "end_turn"})

        with patch("agent.service.run_writing_workflow_streaming") as mock_workflow:
            mock_workflow.return_value = mock_stream_switching_active_session()

            async for _ in service.process_stream(
                project_id=str(project.id),
                user_id=str(user.id),
                message="Persist to resolved session",
                session=db_session,
                session_id=target_session.id,
            ):
                pass

        saved_messages = db_session.exec(
            select(ChatMessage)
            .where(ChatMessage.session_id == target_session.id)
            .order_by(desc(ChatMessage.created_at), desc(ChatMessage.id))
        ).all()
        assert len(saved_messages) == 2
        assert {message.role for message in saved_messages} == {"user", "assistant"}
        assert any(message.role == "assistant" and message.content == "Draft reply" for message in saved_messages)

        newer_session_messages = db_session.exec(
            select(ChatMessage).where(ChatMessage.session_id == newer_session.id)
        ).all()
        assert newer_session_messages == []

    async def test_process_stream_passes_runtime_workflow_config(
        self, mock_agent_service, test_user_with_project, db_session: Session, mock_workflow_stream
    ):
        """Test process_stream passes centralized workflow config to writing graph."""
        from config.agent_runtime import (
            AGENT_AUTO_REVIEW_THRESHOLD_CHARS,
            AGENT_COLLABORATION_MAX_ITERATIONS,
        )

        service, _ = mock_agent_service
        project = test_user_with_project["project"]
        user = test_user_with_project["user"]

        with patch("agent.service.run_writing_workflow_streaming") as mock_workflow:
            mock_workflow.return_value = mock_workflow_stream()

            async for _ in service.process_stream(
                project_id=str(project.id),
                user_id=str(user.id),
                message="Hello",
                session=db_session,
            ):
                pass

        assert mock_workflow.call_args is not None
        _, kwargs = mock_workflow.call_args
        assert kwargs["max_iterations"] == AGENT_COLLABORATION_MAX_ITERATIONS
        assert kwargs["auto_review_threshold"] == AGENT_AUTO_REVIEW_THRESHOLD_CHARS

    async def test_process_stream_persists_stop_reason_and_usage_metadata(
        self, mock_agent_service, test_user_with_project, db_session: Session
    ):
        """Assistant chat message should persist model stop_reason/usage metadata."""
        from agent.llm.anthropic_client import StreamEvent, StreamEventType

        service, _ = mock_agent_service
        project = test_user_with_project["project"]
        user = test_user_with_project["user"]

        async def mock_stream_with_usage():
            yield StreamEvent(type=StreamEventType.TEXT, data={"text": "Answer"})
            yield StreamEvent(
                type=StreamEventType.MESSAGE_END,
                data={
                    "stop_reason": "end_turn",
                    "usage": {
                        "input_tokens": 111,
                        "output_tokens": 222,
                    },
                },
            )

        with patch("agent.service.run_writing_workflow_streaming") as mock_workflow:
            mock_workflow.return_value = mock_stream_with_usage()

            async for _ in service.process_stream(
                project_id=str(project.id),
                user_id=str(user.id),
                message="hello",
                session=db_session,
            ):
                pass

        stmt = (
            select(ChatMessage)
            .join(ChatSession, ChatMessage.session_id == ChatSession.id)
            .where(ChatSession.project_id == str(project.id))
            .where(ChatMessage.role == "assistant")
            .order_by(desc(ChatMessage.created_at))
        )
        latest_assistant = db_session.exec(stmt).first()
        assert latest_assistant is not None
        assert latest_assistant.message_metadata is not None

        metadata = json.loads(latest_assistant.message_metadata)
        assert metadata["stop_reason"] == "end_turn"
        assert metadata["usage"]["input_tokens"] == 111
        assert metadata["usage"]["output_tokens"] == 222

    async def test_process_stream_emits_done_with_persisted_assistant_message_id(
        self, mock_agent_service, test_user_with_project, db_session: Session
    ):
        """Done event should be delayed until history save succeeds and include the assistant message ID."""
        from agent.llm.anthropic_client import StreamEvent, StreamEventType

        service, _ = mock_agent_service
        project = test_user_with_project["project"]
        user = test_user_with_project["user"]

        async def mock_stream_with_clarification_stop():
            yield StreamEvent(
                type=StreamEventType.WORKFLOW_STOPPED,
                data={
                    "reason": "clarification_needed",
                    "question": "请确认主角姓名",
                },
            )
            yield StreamEvent(type=StreamEventType.MESSAGE_END, data={"stop_reason": "end_turn"})

        with patch("agent.service.run_writing_workflow_streaming") as mock_workflow:
            mock_workflow.return_value = mock_stream_with_clarification_stop()

            events: list[str] = []
            async for event in service.process_stream(
                project_id=str(project.id),
                user_id=str(user.id),
                message="需要澄清",
                session=db_session,
            ):
                events.append(event)

        done_events = [event for event in events if "event: done" in event]
        assert len(done_events) == 1
        done_payload = json.loads(done_events[0].split("data:", 1)[1].strip())
        assert done_payload["assistant_message_id"]

        saved_assistant = db_session.get(ChatMessage, done_payload["assistant_message_id"])
        assert saved_assistant is not None
        assert saved_assistant.message_metadata is not None
        metadata = json.loads(saved_assistant.message_metadata)
        assert metadata["status_cards"][0]["reason"] == "clarification_needed"

    async def test_process_stream_pg_offload_branch_initializes_message_manager_before_save(
        self, mock_agent_service, test_user_with_project, db_session: Session
    ):
        """PostgreSQL offload branch should still save history successfully."""
        from agent.core.session_loader import SessionData
        from agent.llm.anthropic_client import StreamEvent, StreamEventType
        from agent.schemas.context import ContextData

        service, _ = mock_agent_service
        project = test_user_with_project["project"]
        user = test_user_with_project["user"]

        async def mock_stream():
            yield StreamEvent(type=StreamEventType.TEXT, data={"text": "hello"})
            yield StreamEvent(type=StreamEventType.MESSAGE_END, data={"stop_reason": "end_turn"})

        session_data = SessionData(
            chat_session=None,
            session_id="sess-offload",
            history_messages=[],
            context_data=ContextData(items=[], context="", token_estimate=0),
            compaction_result=None,
        )

        with (
            patch.object(service, "_should_offload_session_work", return_value=True),
            patch.object(service, "_resolve_or_create_chat_session_id_sync", return_value="sess-offload"),
            patch.object(service, "_resolve_explicit_skill_selection_sync", return_value=None),
            patch("agent.service.SessionLoader.load_session_with_compaction", new=AsyncMock(return_value=session_data)),
            patch.object(
                service,
                "_prepare_prompt_artifacts_sync",
                return_value=(None, "hello", None, None, "system prompt"),
            ),
            patch("agent.service.run_writing_workflow_streaming", return_value=mock_stream()),
            patch("agent.service.MessageManager.save_messages", new=AsyncMock(return_value="assistant-msg-offload")),
        ):
            events: list[str] = []
            async for event in service.process_stream(
                project_id=str(project.id),
                user_id=str(user.id),
                message="hello",
                session=db_session,
            ):
                events.append(event)

        assert any("event: done" in event for event in events)
        assert not any("event: error" in event for event in events)

    async def test_process_stream_emits_error_without_done_when_history_save_fails(
        self, mock_agent_service, test_user_with_project, db_session: Session, mock_workflow_stream
    ):
        """A failed history save must not emit done before the error reaches the client."""
        service, _ = mock_agent_service
        project = test_user_with_project["project"]
        user = test_user_with_project["user"]

        with patch("agent.service.run_writing_workflow_streaming") as mock_workflow, patch(
            "agent.service.MessageManager.save_messages",
            new=AsyncMock(side_effect=RuntimeError("db unavailable")),
        ):
            mock_workflow.return_value = mock_workflow_stream()

            events: list[str] = []
            async for event in service.process_stream(
                project_id=str(project.id),
                user_id=str(user.id),
                message="hello",
                session=db_session,
            ):
                events.append(event)

        assert any("event: error" in event for event in events)
        assert not any("event: done" in event for event in events)

    async def test_process_stream_saves_partial_history_on_workflow_error(
        self, mock_agent_service, test_user_with_project, db_session: Session
    ):
        """Stream error events should persist partial history for recovery, but NOT emit done."""
        from agent.llm.anthropic_client import StreamEvent, StreamEventType

        service, _ = mock_agent_service
        project = test_user_with_project["project"]
        user = test_user_with_project["user"]

        async def mock_error_stream():
            yield StreamEvent(type=StreamEventType.TEXT, data={"text": "partial reply"})
            yield StreamEvent(type=StreamEventType.ERROR, data={"error": "workflow failed"})

        with patch("agent.service.run_writing_workflow_streaming") as mock_workflow:
            mock_workflow.return_value = mock_error_stream()

            events: list[str] = []
            async for event in service.process_stream(
                project_id=str(project.id),
                user_id=str(user.id),
                message="hello",
                session=db_session,
            ):
                events.append(event)

        assert any("event: error" in event for event in events)
        assert not any("event: done" in event for event in events)

        session_started_events = [event for event in events if "event: session_started" in event]
        assert session_started_events, "Expected session_started event"
        session_started_payload = json.loads(session_started_events[0].split("data:", 1)[1].strip())
        persisted_messages = db_session.exec(
            select(ChatMessage).where(ChatMessage.session_id == session_started_payload["session_id"])
        ).all()
        # Partial history is saved for recovery on next turn
        assert len(persisted_messages) == 2
        assert any(m.role == "user" and m.content == "hello" for m in persisted_messages)
        assert any(m.role == "assistant" and m.content == "partial reply" for m in persisted_messages)

    async def test_process_stream_schedules_background_cleanup_on_cancellation(
        self, mock_agent_service, test_user_with_project, db_session: Session
    ):
        """Cancellation should schedule steering cleanup instead of awaiting it inline."""
        from agent.llm.anthropic_client import StreamEvent, StreamEventType

        service, _ = mock_agent_service
        project = test_user_with_project["project"]
        user = test_user_with_project["user"]

        started = asyncio.Event()

        async def mock_slow_stream():
            started.set()
            yield StreamEvent(type=StreamEventType.TEXT, data={"text": "partial"})
            await asyncio.sleep(3600)

        async def consume():
            async for _event in service.process_stream(
                project_id=str(project.id),
                user_id=str(user.id),
                message="cancel me",
                session=db_session,
            ):
                pass

        with (
            patch("agent.service.run_writing_workflow_streaming", return_value=mock_slow_stream()),
            patch("agent.service.cleanup_steering_queue_async", new=AsyncMock()) as mock_cleanup,
            patch.object(service, "_schedule_background_cleanup") as mock_schedule_cleanup,
        ):
            def _consume_cleanup_coro(coro, **_kwargs):
                coro.close()

            mock_schedule_cleanup.side_effect = _consume_cleanup_coro
            task = asyncio.create_task(consume())
            await started.wait()
            await asyncio.sleep(0)
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task

        mock_cleanup.assert_not_awaited()
        assert mock_schedule_cleanup.call_count == 1
        _args, kwargs = mock_schedule_cleanup.call_args
        assert kwargs["description"] == "cleanup_steering_queue_async"

@pytest.mark.unit
class TestAgentServiceHelpers:
    """Tests for helper methods and utilities."""

    def test_get_agent_service_singleton(self):
        """Test that get_agent_service returns singleton instance."""
        with patch("agent.service.get_context_assembler"):
            import agent.service as service_module
            from agent.service import get_agent_service

            # Reset singleton
            service_module._service = None

            service1 = get_agent_service()
            service2 = get_agent_service()

            assert service1 is service2  # Same instance

            # Clean up
            service_module._service = None

    def test_agent_max_iterations_constant(self):
        """Test agent loop configuration constant."""
        from agent.service import AGENT_MAX_ITERATIONS

        assert AGENT_MAX_ITERATIONS == 15
