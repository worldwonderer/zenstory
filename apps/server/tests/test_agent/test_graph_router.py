"""
Tests for agent/graph/router.py

Tests the router node for LangGraph writing workflow.
"""

from unittest.mock import MagicMock, patch

import pytest


@pytest.mark.unit
class TestGetNextNode:
    """Tests for get_next_node function."""

    def test_get_next_node_planner(self):
        """Test routing to planner."""
        from agent.graph.router import get_next_node

        state = {"current_agent": "planner"}
        result = get_next_node(state)

        assert result == "planner"

    def test_get_next_node_writer(self):
        """Test routing to writer."""
        from agent.graph.router import get_next_node

        state = {"current_agent": "writer"}
        result = get_next_node(state)

        assert result == "writer"

    def test_get_next_node_legacy_reviewer_defaults_to_writer(self):
        """Legacy reviewer alias should no longer be accepted."""
        from agent.graph.router import get_next_node

        state = {"current_agent": "reviewer"}
        result = get_next_node(state)

        assert result == "writer"

    def test_get_next_node_default(self):
        """Test default to writer for unknown agent."""
        from agent.graph.router import get_next_node

        state = {"current_agent": "unknown"}
        result = get_next_node(state)

        assert result == "writer"

    def test_get_next_node_missing_key(self):
        """Test default to writer when key is missing."""
        from agent.graph.router import get_next_node

        state = {}
        result = get_next_node(state)

        assert result == "writer"


@pytest.mark.integration
class TestRouterNode:
    """Tests for router_node async function."""

    async def test_router_node_empty_message(self):
        """Test router defaults to writer for empty message."""
        from agent.graph.router import router_node

        state = {"user_message": ""}
        result = await router_node(state)

        assert result["current_agent"] == "writer"

    async def test_router_node_with_message(self):
        """Test router with valid message."""
        from agent.graph.router import router_node
        from agent.llm.anthropic_client import StreamEvent, StreamEventType

        with patch("agent.graph.router.get_router_client") as mock_get_client:
            async def mock_stream_message(**_kwargs):
                yield StreamEvent(
                    type=StreamEventType.TEXT,
                    data={
                        "text": (
                            '{"agent_type":"planner","workflow_type":"standard",'
                            '"reason":"需要先规划","confidence":0.95}'
                        ),
                    },
                )

            mock_client = MagicMock()
            mock_client.stream_message = mock_stream_message
            mock_get_client.return_value = mock_client

            state = {"user_message": "Plan a story outline"}
            result = await router_node(state)

            assert result["current_agent"] == "planner"
            assert result["workflow_plan"] == "standard"
            assert result["routing_metadata"]["reason"] == "需要先规划"

    async def test_router_node_error_defaults_to_writer(self):
        """Test router defaults to writer on error."""
        from agent.graph.router import router_node
        from agent.llm.anthropic_client import StreamEvent, StreamEventType

        with patch("agent.graph.router.get_router_client") as mock_get_client:
            async def mock_stream_message(**_kwargs):
                yield StreamEvent(
                    type=StreamEventType.ERROR,
                    data={"error": "API Error", "error_type": "Exception"},
                )

            mock_client = MagicMock()
            mock_client.stream_message = mock_stream_message
            mock_get_client.return_value = mock_client

            state = {"user_message": "Some message"}
            result = await router_node(state)

            assert result["current_agent"] == "writer"
            assert result["workflow_plan"] == "quick"


@pytest.mark.unit
class TestParseRouterResponse:
    """Tests for structured router response parsing."""

    def test_parse_router_response_supports_legacy_two_line_output(self):
        """Legacy line-based output should still parse for backward compatibility."""
        from agent.graph.router import _parse_router_response

        response = {"content": [{"type": "text", "text": "planner\nstandard"}]}
        decision = _parse_router_response(response)

        assert decision.agent_type == "planner"
        assert decision.workflow_type == "standard"

    def test_parse_router_response_legacy_reviewer_defaults_to_writer(self):
        """Legacy reviewer alias should no longer map to quality_reviewer."""
        from agent.graph.router import _parse_router_response

        response = {"content": [{"type": "text", "text": '{"agent":"reviewer","workflow":"review_only"}'}]}
        decision = _parse_router_response(response)

        assert decision.agent_type == "writer"
        assert decision.workflow_type == "review_only"

    def test_parse_router_response_extracts_relevant_json_when_multiple_objects_present(self):
        """Should prefer JSON object containing routing keys over unrelated objects."""
        from agent.graph.router import _parse_router_response

        response = {
            "content": [{
                "type": "text",
                "text": (
                    'note {"foo":"bar"}\n'
                    '{"agent_type":"planner","workflow_type":"standard","reason":"需要规划","confidence":0.9}'
                ),
            }],
        }

        decision = _parse_router_response(response)
        assert decision.agent_type == "planner"
        assert decision.workflow_type == "standard"
        assert decision.reason == "需要规划"

    def test_parse_router_response_defaults_when_only_unrelated_json_is_present(self):
        """A JSON object without routing keys should fall back to writer/quick."""
        from agent.graph.router import _parse_router_response

        response = {
            "content": [{"type": "text", "text": '{"foo":"bar","confidence":"oops"}'}],
        }

        decision = _parse_router_response(response)
        assert decision.agent_type == "writer"
        assert decision.workflow_type == "quick"
        assert decision.confidence == 0.0


@pytest.mark.unit
class TestNormalizeRouterPayload:
    def test_normalize_router_payload_maps_aliases_and_clamps_confidence(self):
        from agent.graph.router import _normalize_router_payload

        normalized = _normalize_router_payload(
            {
                "target_agent": "quality_reviewer",
                "workflow_plan": "review_only",
                "reason": "needs review",
                "confidence": 4,
            }
        )

        assert normalized["agent_type"] == "quality_reviewer"
        assert normalized["workflow_type"] == "review_only"
        assert normalized["reason"] == "needs review"
        assert normalized["confidence"] == 1.0

    def test_normalize_router_payload_infers_hook_focus_for_hook_designer(self):
        from agent.graph.router import _normalize_router_payload

        normalized = _normalize_router_payload({"agent": "hook_designer"})

        assert normalized["agent_type"] == "hook_designer"
        assert normalized["workflow_type"] == "hook_focus"

    def test_normalize_router_payload_unknown_workflow_falls_back_to_quick(self):
        from agent.graph.router import _normalize_router_payload

        normalized = _normalize_router_payload(
            {"agent_type": "planner", "workflow_type": "mystery", "confidence": "nope"}
        )

        assert normalized["agent_type"] == "planner"
        assert normalized["workflow_type"] == "quick"
        assert normalized["confidence"] == 0.0
