"""
Tests for agent/graph/nodes.py

Tests the graph-facing writing agent entrypoint and output evaluation helpers.
"""

from unittest.mock import patch

import pytest


@pytest.fixture(autouse=True)
def _reset_global_metrics():
    from agent.core.metrics import reset_metrics_collector

    reset_metrics_collector()
    yield
    reset_metrics_collector()


@pytest.mark.unit
class TestEvaluationSignals:
    """Tests for heuristic evaluator and marker fallback behavior."""

    def test_detect_task_complete_explicit_marker(self):
        """[TASK_COMPLETE] at end of content → is_complete True, reason explicit_complete_marker."""
        from agent.graph.nodes import detect_task_complete

        result = detect_task_complete("这是最终输出内容。[TASK_COMPLETE]")
        assert result.is_complete is True
        assert result.confidence == 1.0
        assert result.reason == "explicit_complete_marker"

    def test_detect_task_complete_chinese_phrase_mid_text_no_longer_triggers(self):
        """'已完成' mid-text without the explicit marker must NOT flip should_complete (false positive fix)."""
        from agent.graph.nodes import detect_task_complete

        result = detect_task_complete(
            "任务已完成，最终结果如下：\n"
            "1. 已补齐章节结构与冲突线。\n"
            "2. 已修复角色名不一致问题并统一术语。\n"
            "3. 已完成文风润色、段落衔接和末尾悬念钩子优化。\n"
            "4. 关键改动与验证信息已整理完毕，准备交付。\n"
            "5. 附：涉及文件、测试结果、风险评估与后续建议均已在交付说明中完整列出。"
        )
        assert result.is_complete is False

    def test_detect_task_complete_empty_content_not_complete(self):
        """Empty / whitespace-only content → not complete."""
        from agent.graph.nodes import detect_task_complete

        assert detect_task_complete("").is_complete is False
        assert detect_task_complete("   ").is_complete is False

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


@pytest.mark.unit
class TestRunStreamingAgent:
    """Tests for the graph-facing streaming agent wrapper."""

    @pytest.mark.asyncio
    async def test_run_streaming_agent_persists_end_turn_assistant_text_for_downstream(self):
        """Assistant text from end_turn must be persisted into state.messages."""
        from agent.core.workflow_events import StreamEvent, StreamEventType
        from agent.graph.nodes import run_streaming_agent

        async def fake_openai_runner(state, agent_type, system_prompt, get_steering_messages=None):
            assert agent_type == "planner"
            assert "base prompt" in system_prompt
            assert get_steering_messages is None
            state["messages"] = [
                {"role": "user", "content": state["user_message"]},
                {"role": "assistant", "content": [{"type": "text", "text": "这是规划内容"}]},
            ]
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

        with patch("agent.graph.nodes.run_openai_agents_streaming_agent", new=fake_openai_runner):
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
