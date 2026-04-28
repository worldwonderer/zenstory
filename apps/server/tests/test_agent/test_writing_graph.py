"""
Tests for agent/graph/writing_graph.py
"""

import json
from unittest.mock import AsyncMock, patch

import pytest

from agent.llm.anthropic_client import StreamEvent, StreamEventType
from agent.tools.mcp_tools import ToolContext


@pytest.mark.unit
class TestWritingGraphCompletionHooks:
    """Tests for workflow completion side effects."""

    @pytest.mark.asyncio
    async def test_task_complete_triggers_update_project_for_in_progress_tasks(self):
        """Workflow completion should auto-call update_project to close in_progress tasks."""
        from agent.graph.writing_graph import run_writing_workflow_streaming

        async def fake_run_streaming_agent(*_args, **_kwargs):
            yield StreamEvent(
                type=StreamEventType.TEXT,
                data={"text": "任务完成 [TASK_COMPLETE]"},
            )

        mock_update_project = AsyncMock(
            return_value={
                "content": [{
                    "type": "text",
                    "text": json.dumps(
                        {"status": "success", "data": {"plan": {"status": "success"}}},
                        ensure_ascii=False,
                    ),
                }]
            }
        )

        state = {
            "user_message": "写一段内容",
            "messages": [],
            "system_prompt": "",
        }

        ToolContext.set_context(
            session=None,
            user_id="user-1",
            project_id="project-1",
            session_id="session-1",
        )
        try:
            with (
                patch("agent.graph.writing_graph.router_node", AsyncMock(return_value={})),
                patch("agent.graph.writing_graph.get_next_node", return_value="writer"),
                patch("agent.graph.writing_graph.run_streaming_agent", new=fake_run_streaming_agent),
                patch(
                    "services.infra.task_board_service.task_board_service.get_tasks",
                    return_value=[
                        {"task": "step-1", "status": "done"},
                        {"task": "step-2", "status": "in_progress"},
                        {"task": "step-3", "status": "pending"},
                    ],
                ),
                patch("agent.graph.writing_graph.update_project", mock_update_project),
            ):
                events = [
                    event async for event in run_writing_workflow_streaming(
                        state=state,
                        thread_id="thread-1",
                    )
                ]
        finally:
            ToolContext.clear_context()

        mock_update_project.assert_awaited_once()
        updated_tasks = mock_update_project.await_args.args[0]["tasks"]
        assert updated_tasks[0]["status"] == "done"
        assert updated_tasks[1]["status"] == "done"
        assert updated_tasks[2]["status"] == "pending"

        assert any(
            event.type == StreamEventType.TOOL_USE
            and event.data.get("name") == "update_project"
            for event in events
        )
        assert any(
            event.type == StreamEventType.TOOL_RESULT
            and event.data.get("name") == "update_project"
            for event in events
        )
        assert any(event.type == StreamEventType.WORKFLOW_COMPLETE for event in events)

    @pytest.mark.asyncio
    async def test_task_complete_without_in_progress_tasks_skips_auto_update(self):
        """No in_progress task means no auto update_project call."""
        from agent.graph.writing_graph import run_writing_workflow_streaming

        async def fake_run_streaming_agent(*_args, **_kwargs):
            yield StreamEvent(
                type=StreamEventType.TEXT,
                data={"text": "任务完成 [TASK_COMPLETE]"},
            )

        mock_update_project = AsyncMock()
        state = {
            "user_message": "写一段内容",
            "messages": [],
            "system_prompt": "",
        }

        ToolContext.set_context(
            session=None,
            user_id="user-1",
            project_id="project-1",
            session_id="session-2",
        )
        try:
            with (
                patch("agent.graph.writing_graph.router_node", AsyncMock(return_value={})),
                patch("agent.graph.writing_graph.get_next_node", return_value="writer"),
                patch("agent.graph.writing_graph.run_streaming_agent", new=fake_run_streaming_agent),
                patch(
                    "services.infra.task_board_service.task_board_service.get_tasks",
                    return_value=[
                        {"task": "step-1", "status": "done"},
                        {"task": "step-2", "status": "pending"},
                    ],
                ),
                patch("agent.graph.writing_graph.update_project", mock_update_project),
            ):
                events = [
                    event async for event in run_writing_workflow_streaming(
                        state=state,
                        thread_id="thread-2",
                    )
                ]
        finally:
            ToolContext.clear_context()

        assert mock_update_project.await_count == 0
        assert not any(
            event.type == StreamEventType.TOOL_RESULT
            and event.data.get("name") == "update_project"
            for event in events
        )
        assert any(event.type == StreamEventType.WORKFLOW_COMPLETE for event in events)


@pytest.mark.unit
class TestWritingGraphRouterFallback:
    """Tests for router fallback defaults in writing workflow."""

    @staticmethod
    async def _fake_run_streaming_agent(*_args, **_kwargs):
        yield StreamEvent(
            type=StreamEventType.TEXT,
            data={"text": "fallback done [TASK_COMPLETE]"},
        )

    @pytest.mark.asyncio
    async def test_validation_error_fallback_uses_quick_workflow_plan(self):
        """ValueError/KeyError fallback should use quick workflow naming."""
        from agent.graph.writing_graph import run_writing_workflow_streaming

        with (
            patch.dict("os.environ", {"AGENT_ROUTER_STRATEGY": "llm"}),
            patch("agent.graph.writing_graph.router_node", AsyncMock(side_effect=ValueError("invalid payload"))),
            patch("agent.graph.writing_graph.run_streaming_agent", new=self._fake_run_streaming_agent),
        ):
            events = [
                event async for event in run_writing_workflow_streaming(
                    state={"user_message": "测试", "messages": [], "system_prompt": ""},
                    thread_id="router-validation-fallback",
                )
            ]

        decided_event = next(event for event in events if event.type == StreamEventType.ROUTER_DECIDED)
        assert decided_event.data["initial_agent"] == "writer"
        assert decided_event.data["workflow_plan"] == "quick"
        assert decided_event.data["routing_metadata"]["workflow_type"] == "quick"
        assert any(event.type == StreamEventType.WORKFLOW_COMPLETE for event in events)

    @pytest.mark.asyncio
    async def test_exception_fallback_uses_quick_workflow_plan(self):
        """Generic router exception fallback should use quick workflow naming."""
        from agent.graph.writing_graph import run_writing_workflow_streaming

        with (
            patch.dict("os.environ", {"AGENT_ROUTER_STRATEGY": "llm"}),
            patch("agent.graph.writing_graph.router_node", AsyncMock(side_effect=RuntimeError("router boom"))),
            patch("agent.graph.writing_graph.run_streaming_agent", new=self._fake_run_streaming_agent),
        ):
            events = [
                event async for event in run_writing_workflow_streaming(
                    state={"user_message": "测试", "messages": [], "system_prompt": ""},
                    thread_id="router-exception-fallback",
                )
            ]

        decided_event = next(event for event in events if event.type == StreamEventType.ROUTER_DECIDED)
        assert decided_event.data["initial_agent"] == "writer"
        assert decided_event.data["workflow_plan"] == "quick"
        assert decided_event.data["routing_metadata"]["workflow_type"] == "quick"
        assert any(event.type == StreamEventType.WORKFLOW_COMPLETE for event in events)


@pytest.mark.unit
class TestWritingGraphGenerationModeOverrides:
    """Tests for per-request generation_mode overrides (fast/quality)."""

    @staticmethod
    async def _fake_run_streaming_agent(*_args, **_kwargs):
        yield StreamEvent(
            type=StreamEventType.TEXT,
            data={"text": "done [TASK_COMPLETE]"},
        )

    @pytest.mark.asyncio
    async def test_generation_mode_fast_skips_router_llm(self):
        from agent.graph.writing_graph import run_writing_workflow_streaming

        mock_router = AsyncMock(return_value={})

        with (
            patch.dict("os.environ", {"AGENT_ROUTER_STRATEGY": "llm"}),
            patch("agent.graph.writing_graph.router_node", mock_router),
            patch("agent.graph.writing_graph.run_streaming_agent", new=self._fake_run_streaming_agent),
        ):
            events = [
                event async for event in run_writing_workflow_streaming(
                    state={
                        "user_message": "测试",
                        "messages": [],
                        "system_prompt": "",
                        "generation_mode": "fast",
                    },
                    thread_id="generation-mode-fast",
                )
            ]

        assert mock_router.await_count == 0

        decided_event = next(event for event in events if event.type == StreamEventType.ROUTER_DECIDED)
        assert decided_event.data["initial_agent"] == "writer"
        assert decided_event.data["workflow_plan"] == "quick"
        assert decided_event.data["routing_metadata"]["reason"] == "generation_mode_fast"

    @pytest.mark.asyncio
    async def test_generation_mode_quality_forces_router_llm(self):
        from agent.graph.writing_graph import run_writing_workflow_streaming

        mock_router = AsyncMock(
            return_value={
                "current_agent": "writer",
                "workflow_plan": "quick",
                "workflow_agents": [],
                "routing_metadata": {
                    "agent_type": "writer",
                    "workflow_type": "quick",
                    "reason": "router_test",
                    "confidence": 1.0,
                },
            }
        )

        with (
            patch.dict("os.environ", {"AGENT_ROUTER_STRATEGY": "off"}),
            patch("agent.graph.writing_graph.router_node", mock_router),
            patch("agent.graph.writing_graph.run_streaming_agent", new=self._fake_run_streaming_agent),
        ):
            events = [
                event async for event in run_writing_workflow_streaming(
                    state={
                        "user_message": "测试",
                        "messages": [],
                        "system_prompt": "",
                        "generation_mode": "quality",
                    },
                    thread_id="generation-mode-quality",
                )
            ]

        assert mock_router.await_count == 1

        decided_event = next(event for event in events if event.type == StreamEventType.ROUTER_DECIDED)
        assert decided_event.data["initial_agent"] == "writer"
        assert decided_event.data["workflow_plan"] == "quick"
        assert decided_event.data["routing_metadata"]["reason"] == "router_test"


@pytest.mark.unit
class TestWritingGraphHandoffPriority:
    """Tests for stop/complete priority when explicit handoff exists."""

    @staticmethod
    def _router_result() -> dict[str, object]:
        return {
            "current_agent": "writer",
            "workflow_plan": "quick",
            "workflow_agents": [],
            "routing_metadata": {
                "agent_type": "writer",
                "workflow_type": "quick",
                "reason": "test",
                "confidence": 1.0,
            },
        }

    @pytest.mark.asyncio
    async def test_explicit_handoff_overrides_explicit_complete_marker(self):
        """Explicit handoff should win over [TASK_COMPLETE] in the same turn."""
        from agent.graph.writing_graph import run_writing_workflow_streaming

        async def fake_run_streaming_agent(_state, agent_type, **_kwargs):
            if agent_type == "writer":
                yield StreamEvent(
                    type=StreamEventType.TEXT,
                    data={"text": "完成初稿，交接审稿 [TASK_COMPLETE]"},
                )
                yield StreamEvent(
                    type=StreamEventType.HANDOFF,
                    data={
                        "target_agent": "quality_reviewer",
                        "reason": "继续质量审查",
                        "context": "请检查逻辑一致性",
                    },
                )
                return

            yield StreamEvent(
                type=StreamEventType.TEXT,
                data={"text": "审稿阶段处理中"},
            )

        with (
            patch("agent.graph.writing_graph.router_node", AsyncMock(return_value=self._router_result())),
            patch("agent.graph.writing_graph.get_next_node", return_value="writer"),
            patch("agent.graph.writing_graph.run_streaming_agent", new=fake_run_streaming_agent),
        ):
            events = [
                event async for event in run_writing_workflow_streaming(
                    state={"user_message": "测试", "messages": [], "system_prompt": ""},
                    thread_id="handoff-complete-priority",
                    max_iterations=3,
                )
            ]

        selected_agents = [
            event.data["agent_type"]
            for event in events
            if event.type == StreamEventType.AGENT_SELECTED
        ]
        assert selected_agents[:2] == ["writer", "quality_reviewer"]
        assert any(event.type == StreamEventType.HANDOFF for event in events)
        assert not any(event.type == StreamEventType.WORKFLOW_COMPLETE for event in events)
        assert not any(event.type == StreamEventType.WORKFLOW_STOPPED for event in events)

    @pytest.mark.asyncio
    async def test_structured_clarification_stops_planned_handoff(self):
        """Structured WORKFLOW_STOPPED clarification should block planned handoff."""
        from agent.graph.writing_graph import run_writing_workflow_streaming

        async def fake_run_streaming_agent(_state, agent_type, **_kwargs):
            if agent_type == "writer":
                yield StreamEvent(type=StreamEventType.TEXT, data={"text": "需要补充信息"})
                yield StreamEvent(
                    type=StreamEventType.WORKFLOW_STOPPED,
                    data={
                        "reason": "clarification_needed",
                        "agent_type": "writer",
                        "message": "请确认主角姓名",
                    },
                )
                return

            yield StreamEvent(
                type=StreamEventType.TEXT,
                data={"text": "审稿阶段处理中"},
            )

        router_result = self._router_result()
        router_result["workflow_agents"] = ["quality_reviewer"]

        with (
            patch("agent.graph.writing_graph.router_node", AsyncMock(return_value=router_result)),
            patch("agent.graph.writing_graph.get_next_node", return_value="writer"),
            patch("agent.graph.writing_graph.run_streaming_agent", new=fake_run_streaming_agent),
        ):
            events = [
                event async for event in run_writing_workflow_streaming(
                    state={"user_message": "测试", "messages": [], "system_prompt": ""},
                    thread_id="structured-clarify-stop",
                    max_iterations=3,
                )
            ]

        selected_agents = [
            event.data["agent_type"]
            for event in events
            if event.type == StreamEventType.AGENT_SELECTED
        ]
        assert selected_agents == ["writer"]
        assert any(event.type == StreamEventType.WORKFLOW_STOPPED for event in events)
        assert not any(event.type == StreamEventType.HANDOFF for event in events)
        assert not any(event.type == StreamEventType.WORKFLOW_COMPLETE for event in events)

    @pytest.mark.asyncio
    async def test_structured_clarification_stops_explicit_handoff_same_turn(self):
        """Structured clarification must suppress explicit handoff emitted in same turn."""
        from agent.graph.writing_graph import run_writing_workflow_streaming

        async def fake_run_streaming_agent(_state, agent_type, **_kwargs):
            if agent_type == "writer":
                yield StreamEvent(type=StreamEventType.TEXT, data={"text": "处理中"})
                yield StreamEvent(
                    type=StreamEventType.HANDOFF,
                    data={
                        "target_agent": "quality_reviewer",
                        "reason": "先审查",
                        "context": "draft done",
                        "handoff_packet": {
                            "target_agent": "quality_reviewer",
                            "reason": "先审查",
                            "context": "draft done",
                            "completed": ["初稿完成"],
                            "todo": ["审查逻辑"],
                            "evidence": ["draft/ch1.md"],
                        },
                    },
                )
                yield StreamEvent(
                    type=StreamEventType.WORKFLOW_STOPPED,
                    data={
                        "reason": "clarification_needed",
                        "agent_type": "writer",
                        "message": "请补充世界观年代",
                    },
                )
                return

            yield StreamEvent(type=StreamEventType.TEXT, data={"text": "should not run"})

        with (
            patch("agent.graph.writing_graph.router_node", AsyncMock(return_value=self._router_result())),
            patch("agent.graph.writing_graph.get_next_node", return_value="writer"),
            patch("agent.graph.writing_graph.run_streaming_agent", new=fake_run_streaming_agent),
        ):
            events = [
                event async for event in run_writing_workflow_streaming(
                    state={"user_message": "测试", "messages": [], "system_prompt": ""},
                    thread_id="explicit-handoff-clarify-stop",
                    max_iterations=3,
                )
            ]

        selected_agents = [
            event.data["agent_type"]
            for event in events
            if event.type == StreamEventType.AGENT_SELECTED
        ]
        assert selected_agents == ["writer"]
        assert any(
            event.type == StreamEventType.WORKFLOW_STOPPED
            and event.data.get("reason") == "clarification_needed"
            for event in events
        )
        assert not any(event.type == StreamEventType.HANDOFF for event in events)

    @pytest.mark.asyncio
    async def test_tool_call_exhausted_stops_planned_handoff(self):
        """Tool-call exhaustion must block any planned/auto handoff."""
        from agent.graph.writing_graph import run_writing_workflow_streaming

        async def fake_run_streaming_agent(_state, agent_type, **_kwargs):
            if agent_type == "writer":
                yield StreamEvent(type=StreamEventType.TEXT, data={"text": "处理中"})
                yield StreamEvent(
                    type=StreamEventType.ITERATION_EXHAUSTED,
                    data={
                        "layer": "tool_call",
                        "iterations_used": 10,
                        "max_iterations": 10,
                        "reason": "tool call exhausted",
                        "last_agent": "writer",
                    },
                )
                return

            yield StreamEvent(type=StreamEventType.TEXT, data={"text": "should not run"})

        router_result = self._router_result()
        router_result["workflow_agents"] = ["quality_reviewer"]

        with (
            patch("agent.graph.writing_graph.router_node", AsyncMock(return_value=router_result)),
            patch("agent.graph.writing_graph.get_next_node", return_value="writer"),
            patch("agent.graph.writing_graph.run_streaming_agent", new=fake_run_streaming_agent),
        ):
            events = [
                event async for event in run_writing_workflow_streaming(
                    state={"user_message": "测试", "messages": [], "system_prompt": ""},
                    thread_id="tool-call-exhausted-stop",
                    max_iterations=3,
                )
            ]

        selected_agents = [
            event.data["agent_type"]
            for event in events
            if event.type == StreamEventType.AGENT_SELECTED
        ]
        assert selected_agents == ["writer"]
        assert any(
            event.type == StreamEventType.ITERATION_EXHAUSTED
            and event.data.get("layer") == "tool_call"
            for event in events
        )
        assert not any(event.type == StreamEventType.HANDOFF for event in events)

    @pytest.mark.asyncio
    async def test_self_handoff_stops_workflow(self):
        """Self handoff should be rejected to avoid collaboration loops."""
        from agent.graph.writing_graph import run_writing_workflow_streaming

        async def fake_run_streaming_agent(_state, agent_type, **_kwargs):
            if agent_type == "writer":
                yield StreamEvent(type=StreamEventType.TEXT, data={"text": "修改中"})
                yield StreamEvent(
                    type=StreamEventType.HANDOFF,
                    data={
                        "target_agent": "writer",
                        "reason": "继续修改",
                        "context": "self",
                    },
                )
                return

            yield StreamEvent(type=StreamEventType.TEXT, data={"text": "should not run"})

        with (
            patch("agent.graph.writing_graph.router_node", AsyncMock(return_value=self._router_result())),
            patch("agent.graph.writing_graph.get_next_node", return_value="writer"),
            patch("agent.graph.writing_graph.run_streaming_agent", new=fake_run_streaming_agent),
        ):
            events = [
                event async for event in run_writing_workflow_streaming(
                    state={"user_message": "测试", "messages": [], "system_prompt": ""},
                    thread_id="self-handoff-stop",
                    max_iterations=3,
                )
            ]

        selected_agents = [
            event.data["agent_type"]
            for event in events
            if event.type == StreamEventType.AGENT_SELECTED
        ]
        assert selected_agents == ["writer"]
        assert any(
            event.type == StreamEventType.WORKFLOW_STOPPED
            and event.data.get("reason") == "invalid_handoff"
            for event in events
        )
        assert not any(event.type == StreamEventType.HANDOFF for event in events)

    @pytest.mark.asyncio
    async def test_task_complete_without_session_id_skips_auto_update(self):
        """Missing session_id should skip auto task-board finalize safely."""
        from agent.graph.writing_graph import run_writing_workflow_streaming

        async def fake_run_streaming_agent(*_args, **_kwargs):
            yield StreamEvent(
                type=StreamEventType.TEXT,
                data={"text": "任务完成 [TASK_COMPLETE]"},
            )

        mock_update_project = AsyncMock()
        state = {
            "user_message": "写一段内容",
            "messages": [],
            "system_prompt": "",
        }

        ToolContext.set_context(
            session=None,
            user_id="user-1",
            project_id="project-1",
            session_id=None,
        )
        try:
            with (
                patch("agent.graph.writing_graph.router_node", AsyncMock(return_value={})),
                patch("agent.graph.writing_graph.get_next_node", return_value="writer"),
                patch("agent.graph.writing_graph.run_streaming_agent", new=fake_run_streaming_agent),
                patch("agent.graph.writing_graph.update_project", mock_update_project),
            ):
                events = [
                    event async for event in run_writing_workflow_streaming(
                        state=state,
                        thread_id="thread-3",
                    )
                ]
        finally:
            ToolContext.clear_context()

        assert mock_update_project.await_count == 0
        assert any(event.type == StreamEventType.WORKFLOW_COMPLETE for event in events)


@pytest.mark.unit
class TestWritingGraphAutoReviewGate:
    """Ensure graph-level auto-review does not hijack long non-writing replies."""

    @staticmethod
    def _router_result() -> dict[str, object]:
        return {
            "current_agent": "writer",
            "workflow_plan": "quick",
            "workflow_agents": [],
            "routing_metadata": {
                "agent_type": "writer",
                "workflow_type": "quick",
                "reason": "test",
                "confidence": 1.0,
            },
        }

    @pytest.mark.asyncio
    async def test_auto_review_skipped_for_non_writing_request(self):
        from agent.graph.writing_graph import run_writing_workflow_streaming

        async def fake_run_streaming_agent(*_args, **_kwargs):
            yield StreamEvent(type=StreamEventType.TEXT, data={"text": "x" * 200})

        with (
            patch.dict("os.environ", {"AGENT_ENABLE_GRAPH_AUTO_REVIEW": "true"}),
            patch("agent.graph.writing_graph.router_node", AsyncMock(return_value=self._router_result())),
            patch("agent.graph.writing_graph.get_next_node", return_value="writer"),
            patch("agent.graph.writing_graph.run_streaming_agent", new=fake_run_streaming_agent),
        ):
            events = [
                event async for event in run_writing_workflow_streaming(
                    state={
                        "user_message": "请解释一下函数式编程的优缺点",
                        "router_message": "请解释一下函数式编程的优缺点",
                        "messages": [],
                        "system_prompt": "",
                    },
                    thread_id="auto-review-skip-non-writing",
                    max_iterations=2,
                    auto_review_threshold=50,
                )
            ]

        assert not any(event.type == StreamEventType.HANDOFF for event in events)

    @pytest.mark.asyncio
    async def test_auto_review_includes_writer_content_for_reviewer_context(self):
        from agent.graph.writing_graph import run_writing_workflow_streaming

        captured_review_task: dict[str, str] = {}

        async def fake_run_streaming_agent(state, agent_type, **_kwargs):
            if agent_type == "writer":
                # Simulate writer producing a deliverable draft via <file> streaming protocol.
                yield StreamEvent(type=StreamEventType.TEXT, data={"text": f"<file>{'a' * 200}</file>"})
                return
            if agent_type == "quality_reviewer":
                captured_review_task["user_message"] = str(state.get("user_message") or "")
                yield StreamEvent(type=StreamEventType.TEXT, data={"text": "review ok [TASK_COMPLETE]"})
                return

            yield StreamEvent(type=StreamEventType.TEXT, data={"text": "noop"})

        with (
            patch.dict("os.environ", {"AGENT_ENABLE_GRAPH_AUTO_REVIEW": "true"}),
            patch("agent.graph.writing_graph.router_node", AsyncMock(return_value=self._router_result())),
            patch("agent.graph.writing_graph.get_next_node", return_value="writer"),
            patch("agent.graph.writing_graph.run_streaming_agent", new=fake_run_streaming_agent),
        ):
            events = [
                event async for event in run_writing_workflow_streaming(
                    state={
                        "user_message": "帮我写一段小说开头",
                        "router_message": "帮我写一段小说开头",
                        "messages": [],
                        "system_prompt": "",
                    },
                    thread_id="auto-review-context-includes-draft",
                    max_iterations=3,
                    auto_review_threshold=50,
                )
            ]

        handoff_event = next(event for event in events if event.type == StreamEventType.HANDOFF)
        assert "[待审查内容]" not in handoff_event.data.get("context", "")

        review_user_message = captured_review_task.get("user_message", "")
        assert "[待审查内容]" in review_user_message
        assert "a" * 50 in review_user_message
        assert any(event.type == StreamEventType.WORKFLOW_COMPLETE for event in events)

    @pytest.mark.asyncio
    async def test_task_complete_update_project_failure_does_not_block_workflow(self):
        """Auto finalize failures should not block WORKFLOW_COMPLETE."""
        from agent.graph.writing_graph import run_writing_workflow_streaming

        async def fake_run_streaming_agent(*_args, **_kwargs):
            yield StreamEvent(
                type=StreamEventType.TEXT,
                data={"text": "任务完成 [TASK_COMPLETE]"},
            )

        mock_update_project = AsyncMock(side_effect=RuntimeError("update_project failed"))
        state = {
            "user_message": "写一段内容",
            "messages": [],
            "system_prompt": "",
        }

        ToolContext.set_context(
            session=None,
            user_id="user-1",
            project_id="project-1",
            session_id="session-4",
        )
        try:
            with (
                patch("agent.graph.writing_graph.router_node", AsyncMock(return_value={})),
                patch("agent.graph.writing_graph.get_next_node", return_value="writer"),
                patch("agent.graph.writing_graph.run_streaming_agent", new=fake_run_streaming_agent),
                patch(
                    "services.infra.task_board_service.task_board_service.get_tasks",
                    return_value=[{"task": "step-2", "status": "in_progress"}],
                ),
                patch("agent.graph.writing_graph.update_project", mock_update_project),
            ):
                events = [
                    event async for event in run_writing_workflow_streaming(
                        state=state,
                        thread_id="thread-4",
                    )
                ]
        finally:
            ToolContext.clear_context()

        mock_update_project.assert_awaited_once()
        # failure path should not emit tool_result, but workflow must still complete
        assert not any(
            event.type == StreamEventType.TOOL_RESULT
            and event.data.get("name") == "update_project"
            for event in events
        )
        assert any(event.type == StreamEventType.WORKFLOW_COMPLETE for event in events)
