"""
Tests for agent/graph/nodes.py

Tests the agent nodes for LangGraph writing workflow.
"""

import json
from unittest.mock import AsyncMock, patch

import pytest


@pytest.fixture(autouse=True)
def _reset_global_metrics():
    from agent.core.metrics import reset_metrics_collector

    reset_metrics_collector()
    yield
    reset_metrics_collector()


@pytest.mark.unit
class TestToolFunctions:
    """Tests for TOOL_FUNCTIONS mapping."""

    def test_all_tools_mapped(self):
        """Test that all tools are mapped in TOOL_FUNCTIONS."""
        from agent.graph.nodes import TOOL_FUNCTIONS

        expected_tools = [
            "create_file",
            "edit_file",
            "delete_file",
            "query_files",
            "hybrid_search",
            "update_project",
            "handoff_to_agent",
            "request_clarification",
            "parallel_execute",
        ]

        for tool_name in expected_tools:
            assert tool_name in TOOL_FUNCTIONS, f"Tool {tool_name} not found"

    def test_tool_functions_are_callable(self):
        """Test that all mapped functions are callable."""
        from agent.graph.nodes import TOOL_FUNCTIONS

        for name, func in TOOL_FUNCTIONS.items():
            assert callable(func), f"Tool {name} is not callable"

    def test_tool_iteration_limit_uses_runtime_config(self):
        """Tool loop iteration limit should come from centralized runtime config."""
        from agent.graph.nodes import MAX_TOOL_ITERATIONS
        from config.agent_runtime import AGENT_TOOL_CALL_MAX_ITERATIONS

        assert MAX_TOOL_ITERATIONS == AGENT_TOOL_CALL_MAX_ITERATIONS


@pytest.mark.integration
class TestExecuteTool:
    """Tests for execute_tool function."""

    @pytest.mark.asyncio
    async def test_execute_unknown_tool(self):
        """Test executing unknown tool returns error."""
        from agent.core.metrics import (
            TOOL_CALLS_DURATION_MS,
            TOOL_CALLS_ERRORS,
            TOOL_CALLS_TOTAL,
            get_metrics_collector,
        )
        from agent.graph.nodes import execute_tool

        result = await execute_tool("unknown_tool", {})

        assert "content" in result
        content = result["content"]
        assert len(content) > 0
        assert "error" in content[0].get("text", "")

        metrics = get_metrics_collector().get_all_metrics()
        assert metrics["counters"][TOOL_CALLS_TOTAL]["value"] == 1
        assert metrics["counters"][TOOL_CALLS_ERRORS]["value"] == 1
        assert metrics["histograms"][TOOL_CALLS_DURATION_MS]["summary"]["count"] == 1

    @pytest.mark.asyncio
    async def test_execute_tool_with_exception(self):
        """Test execute_tool handles exceptions."""
        from agent.core.metrics import (
            TOOL_CALLS_DURATION_MS,
            TOOL_CALLS_ERRORS,
            TOOL_CALLS_TOTAL,
            get_metrics_collector,
        )
        from agent.graph.nodes import execute_tool

        with patch("agent.graph.nodes.TOOL_FUNCTIONS", {"test_tool": AsyncMock(side_effect=Exception("Test error"))}):
            result = await execute_tool("test_tool", {})

            assert "content" in result
            content = result["content"]
            assert "error" in content[0].get("text", "")

        metrics = get_metrics_collector().get_all_metrics()
        assert metrics["counters"][TOOL_CALLS_TOTAL]["value"] == 1
        assert metrics["counters"][TOOL_CALLS_ERRORS]["value"] == 1
        assert metrics["histograms"][TOOL_CALLS_DURATION_MS]["summary"]["count"] == 1

    @pytest.mark.asyncio
    async def test_execute_parallel_tool_uses_tasks_array_contract(self):
        """Test parallel_execute receives args['tasks'] list, not the whole args object."""
        from agent.core.metrics import (
            TOOL_CALLS_DURATION_MS,
            TOOL_CALLS_ERRORS,
            TOOL_CALLS_TOTAL,
            get_metrics_collector,
        )
        from agent.graph.nodes import execute_tool

        tasks = [{"type": "query_files", "description": "Q1", "params": {}}]
        expected_result = {"content": [{"type": "text", "text": '{"status":"success"}'}]}

        with patch("agent.tools.registry.execute_parallel", new=AsyncMock(return_value=expected_result)) as mock_exec:
            result = await execute_tool("parallel_execute", {"tasks": tasks})

        mock_exec.assert_awaited_once_with(tasks)
        assert result == expected_result

        metrics = get_metrics_collector().get_all_metrics()
        assert metrics["counters"][TOOL_CALLS_TOTAL]["value"] == 1
        assert TOOL_CALLS_ERRORS not in metrics["counters"]
        assert metrics["histograms"][TOOL_CALLS_DURATION_MS]["summary"]["count"] == 1

    @pytest.mark.asyncio
    async def test_execute_parallel_tool_rejects_non_array_tasks(self):
        """Test parallel_execute returns MCP error when tasks is not an array."""
        from agent.graph.nodes import execute_tool

        result = await execute_tool("parallel_execute", {"tasks": "not-an-array"})
        payload = json.loads(result["content"][0]["text"])

        assert payload["status"] == "error"
        assert "tasks" in payload["error"]

    @pytest.mark.asyncio
    async def test_execute_handoff_tool_keeps_structured_packet_fields(self):
        """handoff_to_agent should preserve structured packet fields."""
        from agent.graph.nodes import execute_tool

        result = await execute_tool(
            "handoff_to_agent",
            {
                "target_agent": "quality_reviewer",
                "reason": "请审查",
                "context": "已完成首稿",
                "completed": ["完成章节草稿"],
                "todo": ["进行质量审查"],
                "evidence": ["draft/ch1.md 已更新"],
            },
        )
        payload = json.loads(result["content"][0]["text"])

        assert payload["status"] == "handoff"
        assert payload["target_agent"] == "quality_reviewer"
        assert payload["completed"] == ["完成章节草稿"]
        assert payload["todo"] == ["进行质量审查"]
        assert payload["evidence"] == ["draft/ch1.md 已更新"]


@pytest.mark.unit
class TestEvaluationSignals:
    """Tests for heuristic evaluator and marker fallback behavior."""

    def test_detect_task_complete_by_heuristic_phrase(self):
        """Should allow completion without marker when clear completion language exists."""
        from agent.graph.nodes import detect_task_complete

        result = detect_task_complete(
            "任务已完成，最终结果如下：\n"
            "1. 已补齐章节结构与冲突线。\n"
            "2. 已修复角色名不一致问题并统一术语。\n"
            "3. 已完成文风润色、段落衔接和末尾悬念钩子优化。\n"
            "4. 关键改动与验证信息已整理完毕，准备交付。\n"
            "5. 附：涉及文件、测试结果、风险评估与后续建议均已在交付说明中完整列出。"
        )
        assert result.is_complete is True
        assert result.confidence >= 0.75

    def test_detect_clarification_phrase_only_does_not_trigger(self):
        """Clarification detection should ignore phrase-only text."""
        from agent.graph.nodes import detect_clarification_needed

        result = detect_clarification_needed("信息不够明确，请提供角色姓名和时间线？")
        assert result.needs_clarification is False
        assert result.reason == "structured_tool_required"

    def test_detect_clarification_marker_only_does_not_trigger(self):
        """Clarification detection should ignore legacy marker fallback."""
        from agent.graph.nodes import detect_clarification_needed

        result = detect_clarification_needed("请补充信息\n[NEEDS_CLARIFICATION]")
        assert result.needs_clarification is False
        assert result.reason == "structured_tool_required"

    def test_quality_reviewer_exempt_from_clarification(self):
        """quality_reviewer output should not trigger clarification stop."""
        from agent.graph.nodes import detect_clarification_needed

        result = detect_clarification_needed(
            "请确认是否继续修改这段表达？",
            agent_type="quality_reviewer",
        )
        assert result.needs_clarification is False
        assert result.reason == "quality_reviewer_exempt"


@pytest.mark.integration
class TestHandoffEventStructure:
    """Tests for structured handoff packet in streamed HANDOFF events."""

    @pytest.mark.asyncio
    async def test_run_agent_loop_emits_handoff_packet(self):
        """run_agent_loop_streaming should emit HANDOFF with handoff_packet payload."""
        from agent.graph.nodes import run_agent_loop_streaming
        from agent.llm.anthropic_client import StreamEvent, StreamEventType

        class DummyClient:
            async def stream_message(self, **_kwargs):
                yield StreamEvent(
                    type=StreamEventType.TOOL_USE,
                    data={"status": "start", "id": "tool-1", "name": "handoff_to_agent"},
                )
                yield StreamEvent(
                    type=StreamEventType.TOOL_USE,
                    data={
                        "status": "delta",
                        "partial_json": json.dumps({
                            "target_agent": "quality_reviewer",
                            "reason": "请做质量审查",
                            "context": "已完成初稿",
                            "completed": ["章节初稿完成"],
                            "todo": ["检查逻辑和文风"],
                            "evidence": ["draft/ch1.md updated"],
                        }),
                    },
                )
                yield StreamEvent(
                    type=StreamEventType.TOOL_USE,
                    data={"status": "stop", "id": "tool-1", "name": "handoff_to_agent"},
                )

        events = []
        async for event in run_agent_loop_streaming(
            client=DummyClient(),
            messages=[{"role": "user", "content": "test"}],
            system_prompt="test",
            tools=[],
            agent_type="writer",
        ):
            events.append(event)

        handoff_events = [e for e in events if e.type == StreamEventType.HANDOFF]
        tool_result_events = [e for e in events if e.type == StreamEventType.TOOL_RESULT]
        assert len(handoff_events) == 1
        assert len(tool_result_events) == 1
        assert tool_result_events[0].data["name"] == "handoff_to_agent"
        assert events.index(tool_result_events[0]) < events.index(handoff_events[0])
        packet = handoff_events[0].data["handoff_packet"]
        assert packet["target_agent"] == "quality_reviewer"
        assert packet["completed"] == ["章节初稿完成"]
        assert packet["todo"] == ["检查逻辑和文风"]
        assert packet["artifact_refs"] == []

    @pytest.mark.asyncio
    async def test_run_agent_loop_emits_workflow_stopped_for_request_clarification(self):
        """request_clarification should emit canonical WORKFLOW_STOPPED event."""
        from agent.core.metrics import AGENT_CLARIFICATION_TOTAL, get_metrics_collector
        from agent.graph.nodes import run_agent_loop_streaming
        from agent.llm.anthropic_client import StreamEvent, StreamEventType

        class DummyClient:
            async def stream_message(self, **_kwargs):
                yield StreamEvent(
                    type=StreamEventType.TOOL_USE,
                    data={"status": "start", "id": "tool-1", "name": "request_clarification"},
                )
                yield StreamEvent(
                    type=StreamEventType.TOOL_USE,
                    data={
                        "status": "delta",
                        "partial_json": json.dumps({
                            "question": "请确认主角姓名",
                            "context": "大纲已完成",
                            "details": ["主角姓名", "时代背景"],
                        }),
                    },
                )
                yield StreamEvent(
                    type=StreamEventType.TOOL_USE,
                    data={"status": "stop", "id": "tool-1", "name": "request_clarification"},
                )

        events = []
        async for event in run_agent_loop_streaming(
            client=DummyClient(),
            messages=[{"role": "user", "content": "test"}],
            system_prompt="test",
            tools=[],
            agent_type="writer",
        ):
            events.append(event)

        stopped_events = [e for e in events if e.type == StreamEventType.WORKFLOW_STOPPED]
        tool_result_events = [e for e in events if e.type == StreamEventType.TOOL_RESULT]
        assert len(stopped_events) == 1
        assert len(tool_result_events) == 1
        assert tool_result_events[0].data["name"] == "request_clarification"
        assert events.index(tool_result_events[0]) < events.index(stopped_events[0])
        data = stopped_events[0].data
        assert data["reason"] == "clarification_needed"
        assert data["question"] == "请确认主角姓名"
        assert data["details"] == ["主角姓名", "时代背景"]

        metrics = get_metrics_collector().get_all_metrics()
        assert metrics["counters"][AGENT_CLARIFICATION_TOTAL]["value"] == 1

    @pytest.mark.asyncio
    async def test_handoff_packet_includes_accumulated_artifact_refs(self):
        """handoff packet should include refs produced by earlier successful tools."""
        from agent.graph.nodes import run_agent_loop_streaming
        from agent.llm.anthropic_client import StreamEvent, StreamEventType

        class DummyClient:
            async def stream_message(self, **_kwargs):
                yield StreamEvent(
                    type=StreamEventType.TOOL_USE,
                    data={"status": "start", "id": "tool-1", "name": "create_file"},
                )
                yield StreamEvent(
                    type=StreamEventType.TOOL_USE,
                    data={
                        "status": "delta",
                        "partial_json": json.dumps({"title": "ch1", "file_type": "draft"}),
                    },
                )
                yield StreamEvent(
                    type=StreamEventType.TOOL_USE,
                    data={"status": "stop", "id": "tool-1", "name": "create_file"},
                )
                yield StreamEvent(
                    type=StreamEventType.TOOL_USE,
                    data={"status": "start", "id": "tool-2", "name": "handoff_to_agent"},
                )
                yield StreamEvent(
                    type=StreamEventType.TOOL_USE,
                    data={
                        "status": "delta",
                        "partial_json": json.dumps({
                            "target_agent": "quality_reviewer",
                            "reason": "请审查",
                        }),
                    },
                )
                yield StreamEvent(
                    type=StreamEventType.TOOL_USE,
                    data={"status": "stop", "id": "tool-2", "name": "handoff_to_agent"},
                )

        async def _mock_execute_tool(name: str, _args: dict):
            if name == "create_file":
                return {
                    "content": [{
                        "type": "text",
                        "text": json.dumps(
                            {"status": "success", "data": {"id": "file-123"}},
                            ensure_ascii=False,
                        ),
                    }]
                }
            if name == "handoff_to_agent":
                return {
                    "content": [{
                        "type": "text",
                        "text": json.dumps(
                            {
                                "status": "handoff",
                                "target_agent": "quality_reviewer",
                                "reason": "请审查",
                            },
                            ensure_ascii=False,
                        ),
                    }]
                }
            return {"content": [{"type": "text", "text": json.dumps({"status": "success"})}]}

        events = []
        with patch("agent.graph.nodes.execute_tool", new=AsyncMock(side_effect=_mock_execute_tool)):
            async for event in run_agent_loop_streaming(
                client=DummyClient(),
                messages=[{"role": "user", "content": "test"}],
                system_prompt="test",
                tools=[],
                agent_type="writer",
            ):
                events.append(event)

        handoff_events = [e for e in events if e.type == StreamEventType.HANDOFF]
        assert len(handoff_events) == 1
        packet = handoff_events[0].data["handoff_packet"]
        assert packet["artifact_refs"] == ["file-123"]

    @pytest.mark.asyncio
    async def test_clarification_wins_over_handoff_when_both_tools_appear(self):
        """request_clarification should block handoff when both tools appear in same turn."""
        from agent.graph.nodes import run_agent_loop_streaming
        from agent.llm.anthropic_client import StreamEvent, StreamEventType

        class DummyClient:
            async def stream_message(self, **_kwargs):
                yield StreamEvent(
                    type=StreamEventType.TOOL_USE,
                    data={"status": "start", "id": "tool-1", "name": "request_clarification"},
                )
                yield StreamEvent(
                    type=StreamEventType.TOOL_USE,
                    data={
                        "status": "delta",
                        "partial_json": json.dumps({"question": "请补充设定"}),
                    },
                )
                yield StreamEvent(
                    type=StreamEventType.TOOL_USE,
                    data={"status": "stop", "id": "tool-1", "name": "request_clarification"},
                )
                yield StreamEvent(
                    type=StreamEventType.TOOL_USE,
                    data={"status": "start", "id": "tool-2", "name": "handoff_to_agent"},
                )
                yield StreamEvent(
                    type=StreamEventType.TOOL_USE,
                    data={
                        "status": "delta",
                        "partial_json": json.dumps({
                            "target_agent": "quality_reviewer",
                            "reason": "先做审查",
                            "context": "已完成初稿",
                        }),
                    },
                )
                yield StreamEvent(
                    type=StreamEventType.TOOL_USE,
                    data={"status": "stop", "id": "tool-2", "name": "handoff_to_agent"},
                )

        events = []
        async for event in run_agent_loop_streaming(
            client=DummyClient(),
            messages=[{"role": "user", "content": "test"}],
            system_prompt="test",
            tools=[],
            agent_type="writer",
        ):
            events.append(event)

        stopped_events = [event for event in events if event.type == StreamEventType.WORKFLOW_STOPPED]
        assert len(stopped_events) == 1
        assert stopped_events[0].data.get("reason") == "clarification_needed"
        assert not any(event.type == StreamEventType.HANDOFF for event in events)

    @pytest.mark.asyncio
    async def test_clarification_wins_over_handoff_when_handoff_appears_first(self):
        """request_clarification should still win when handoff appears first."""
        from agent.graph.nodes import run_agent_loop_streaming
        from agent.llm.anthropic_client import StreamEvent, StreamEventType

        class DummyClient:
            async def stream_message(self, **_kwargs):
                yield StreamEvent(
                    type=StreamEventType.TOOL_USE,
                    data={"status": "start", "id": "tool-1", "name": "handoff_to_agent"},
                )
                yield StreamEvent(
                    type=StreamEventType.TOOL_USE,
                    data={
                        "status": "delta",
                        "partial_json": json.dumps({
                            "target_agent": "quality_reviewer",
                            "reason": "先做审查",
                            "context": "已完成初稿",
                        }),
                    },
                )
                yield StreamEvent(
                    type=StreamEventType.TOOL_USE,
                    data={"status": "stop", "id": "tool-1", "name": "handoff_to_agent"},
                )
                yield StreamEvent(
                    type=StreamEventType.TOOL_USE,
                    data={"status": "start", "id": "tool-2", "name": "request_clarification"},
                )
                yield StreamEvent(
                    type=StreamEventType.TOOL_USE,
                    data={
                        "status": "delta",
                        "partial_json": json.dumps({"question": "请补充设定"}),
                    },
                )
                yield StreamEvent(
                    type=StreamEventType.TOOL_USE,
                    data={"status": "stop", "id": "tool-2", "name": "request_clarification"},
                )

        events = []
        async for event in run_agent_loop_streaming(
            client=DummyClient(),
            messages=[{"role": "user", "content": "test"}],
            system_prompt="test",
            tools=[],
            agent_type="writer",
        ):
            events.append(event)

        stopped_events = [event for event in events if event.type == StreamEventType.WORKFLOW_STOPPED]
        assert len(stopped_events) == 1
        assert stopped_events[0].data.get("reason") == "clarification_needed"
        assert not any(event.type == StreamEventType.HANDOFF for event in events)

    @pytest.mark.asyncio
    async def test_tool_input_json_repair_executes_tool_when_repairable(self):
        """Malformed-but-repairable tool input JSON should be repaired and executed."""
        from agent.graph.nodes import run_agent_loop_streaming
        from agent.llm.anthropic_client import StreamEvent, StreamEventType

        class DummyClient:
            async def stream_message(self, **_kwargs):
                yield StreamEvent(
                    type=StreamEventType.TOOL_USE,
                    data={"status": "start", "id": "tool-1", "name": "query_files"},
                )
                yield StreamEvent(
                    type=StreamEventType.TOOL_USE,
                    data={"status": "delta", "partial_json": '{"query":"abc"'},  # missing right brace
                )
                yield StreamEvent(
                    type=StreamEventType.TOOL_USE,
                    data={"status": "stop", "id": "tool-1", "name": "query_files"},
                )

        mock_result = {
            "content": [{
                "type": "text",
                "text": json.dumps({"status": "success"}, ensure_ascii=False),
            }]
        }

        with patch("agent.graph.nodes.execute_tool", new=AsyncMock(return_value=mock_result)) as mock_execute_tool:
            events = []
            async for event in run_agent_loop_streaming(
                client=DummyClient(),
                messages=[{"role": "user", "content": "test"}],
                system_prompt="test",
                tools=[],
                agent_type="writer",
            ):
                events.append(event)

        mock_execute_tool.assert_awaited_once()
        called_pos_args, _called_kwargs = mock_execute_tool.call_args
        assert called_pos_args[0] == "query_files"
        assert called_pos_args[1]["query"] == "abc"

        complete_events = [
            event for event in events
            if event.type == StreamEventType.TOOL_USE and event.data.get("status") == "complete"
        ]
        assert len(complete_events) == 1
        assert complete_events[0].data["input"]["query"] == "abc"

        tool_result_events = [event for event in events if event.type == StreamEventType.TOOL_RESULT]
        assert len(tool_result_events) == 1
        assert tool_result_events[0].data["name"] == "query_files"

    @pytest.mark.asyncio
    async def test_tool_input_json_repair_handles_unescaped_quotes_for_edit_file(self):
        """json_repair should salvage common quote-escaping mistakes in edit_file inputs."""
        from agent.graph.nodes import run_agent_loop_streaming
        from agent.llm.anthropic_client import StreamEvent, StreamEventType

        # This JSON is invalid because the old string contains an unescaped quote.
        broken = (
            '{'
            '"id":"file-1",'
            '"edits":[{"op":"replace","old":"hello "world","new":"x"}]'
            '}'
        )

        class DummyClient:
            async def stream_message(self, **_kwargs):
                yield StreamEvent(
                    type=StreamEventType.TOOL_USE,
                    data={"status": "start", "id": "tool-1", "name": "edit_file"},
                )
                yield StreamEvent(
                    type=StreamEventType.TOOL_USE,
                    data={"status": "delta", "partial_json": broken},
                )
                yield StreamEvent(
                    type=StreamEventType.TOOL_USE,
                    data={"status": "stop", "id": "tool-1", "name": "edit_file"},
                )

        mock_result = {"content": [{"type": "text", "text": json.dumps({"status": "success"})}]}

        with patch("agent.graph.nodes.execute_tool", new=AsyncMock(return_value=mock_result)) as mock_execute_tool:
            events = [
                event async for event in run_agent_loop_streaming(
                    client=DummyClient(),
                    messages=[{"role": "user", "content": "test"}],
                    system_prompt="test",
                    tools=[],
                    agent_type="writer",
                )
            ]

        mock_execute_tool.assert_awaited_once()
        called_pos_args, _called_kwargs = mock_execute_tool.call_args
        assert called_pos_args[0] == "edit_file"
        assert called_pos_args[1]["id"] == "file-1"
        assert called_pos_args[1]["edits"][0]["op"] == "replace"
        assert called_pos_args[1]["edits"][0]["old"] == 'hello "world'

        complete_events = [
            event for event in events
            if event.type == StreamEventType.TOOL_USE and event.data.get("status") == "complete"
        ]
        assert len(complete_events) == 1
        assert complete_events[0].data["name"] == "edit_file"

    @pytest.mark.asyncio
    async def test_invalid_tool_input_json_emits_structured_error_without_execution(self):
        """Unrepairable tool input should produce structured TOOL_RESULT error and skip execution."""
        from agent.graph.nodes import run_agent_loop_streaming
        from agent.llm.anthropic_client import StreamEvent, StreamEventType

        class DummyClient:
            async def stream_message(self, **_kwargs):
                yield StreamEvent(
                    type=StreamEventType.TOOL_USE,
                    data={"status": "start", "id": "tool-1", "name": "query_files"},
                )
                yield StreamEvent(
                    type=StreamEventType.TOOL_USE,
                    data={"status": "delta", "partial_json": "not json at all"},  # non-JSON garbage
                )
                yield StreamEvent(
                    type=StreamEventType.TOOL_USE,
                    data={"status": "stop", "id": "tool-1", "name": "query_files"},
                )

        with patch("agent.graph.nodes.execute_tool", new=AsyncMock()) as mock_execute_tool:
            events = []
            async for event in run_agent_loop_streaming(
                client=DummyClient(),
                messages=[{"role": "user", "content": "test"}],
                system_prompt="test",
                tools=[],
                agent_type="writer",
            ):
                events.append(event)

        mock_execute_tool.assert_not_awaited()
        tool_result_events = [event for event in events if event.type == StreamEventType.TOOL_RESULT]
        assert len(tool_result_events) == 1
        payload_text = tool_result_events[0].data["result"]["content"][0]["text"]
        payload = json.loads(payload_text)
        assert payload["status"] == "error"
        assert payload["error_type"] == "invalid_tool_input_json"
        assert payload["tool_name"] == "query_files"

    @pytest.mark.asyncio
    async def test_run_agent_loop_emits_tool_use_complete_with_input(self):
        """Tool completion event should include parsed input for persistence pipeline."""
        from agent.graph.nodes import run_agent_loop_streaming
        from agent.llm.anthropic_client import StreamEvent, StreamEventType

        class DummyClient:
            async def stream_message(self, **_kwargs):
                yield StreamEvent(
                    type=StreamEventType.TOOL_USE,
                    data={"status": "start", "id": "tool-1", "name": "create_file"},
                )
                yield StreamEvent(
                    type=StreamEventType.TOOL_USE,
                    data={
                        "status": "delta",
                        "partial_json": json.dumps({"title": "章节1", "file_type": "draft"}),
                    },
                )
                yield StreamEvent(
                    type=StreamEventType.TOOL_USE,
                    data={"status": "stop", "id": "tool-1", "name": "create_file"},
                )
                yield StreamEvent(
                    type=StreamEventType.MESSAGE_END,
                    data={"stop_reason": "end_turn"},
                )

        mock_result = {"content": [{"type": "text", "text": '{"status":"success"}'}]}

        with patch("agent.graph.nodes.execute_tool", new=AsyncMock(return_value=mock_result)):
            events = []
            async for event in run_agent_loop_streaming(
                client=DummyClient(),
                messages=[{"role": "user", "content": "test"}],
                system_prompt="test",
                tools=[],
                agent_type="writer",
            ):
                events.append(event)

        complete_events = [
            event for event in events
            if event.type == StreamEventType.TOOL_USE and event.data.get("status") == "complete"
        ]
        assert len(complete_events) == 1
        assert complete_events[0].data["name"] == "create_file"
        assert complete_events[0].data["input"]["title"] == "章节1"
        assert any(event.type == StreamEventType.TOOL_RESULT for event in events)

    @pytest.mark.asyncio
    async def test_run_streaming_agent_persists_end_turn_assistant_text_for_downstream(self):
        """Assistant text from end_turn must be persisted into state.messages."""
        from agent.graph.nodes import run_streaming_agent
        from agent.llm.anthropic_client import StreamEvent, StreamEventType

        class DummyClient:
            async def stream_message(self, **_kwargs):
                yield StreamEvent(
                    type=StreamEventType.TEXT,
                    data={"text": "这是规划内容"},
                )
                yield StreamEvent(
                    type=StreamEventType.MESSAGE_END,
                    data={"stop_reason": "end_turn"},
                )

        state = {
            "user_message": "请先给我计划",
            "messages": [],
            "system_prompt": "base prompt",
        }

        with (
            patch("agent.graph.nodes.get_anthropic_client", return_value=DummyClient()),
            patch("agent.graph.nodes.get_agent_tools", return_value=[]),
        ):
            events = [
                event async for event in run_streaming_agent(state=state, agent_type="planner")
            ]

        assert any(event.type == StreamEventType.TEXT for event in events)
        assert len(state["messages"]) == 2
        assert state["messages"][0]["role"] == "user"
        assert state["messages"][1]["role"] == "assistant"
        assistant_content = state["messages"][1]["content"]
        assert isinstance(assistant_content, list)
        assert assistant_content[0]["type"] == "text"
        assert assistant_content[0]["text"] == "这是规划内容"


@pytest.mark.integration
class TestAgentToolsMap:
    """Tests for AGENT_TOOLS_MAP configuration."""

    def test_agent_tools_map_exists(self):
        """Test that AGENT_TOOLS_MAP is properly configured."""
        from agent.tools.registry import AGENT_TOOLS_MAP

        expected_agents = [
            "planner",
            "hook_designer",
            "writer",
            "quality_reviewer",
        ]

        for agent in expected_agents:
            assert agent in AGENT_TOOLS_MAP, f"Agent {agent} not in AGENT_TOOLS_MAP"

    def test_quality_reviewer_has_restricted_tools(self):
        """Test that quality_reviewer uses restricted tool set."""
        from agent.tools.registry import AGENT_TOOLS_MAP, get_agent_tools

        reviewer_tools = get_agent_tools("quality_reviewer")
        assert AGENT_TOOLS_MAP["quality_reviewer"] == reviewer_tools
