"""
Tests for agent/graph/router.py

Tests the router node for LangGraph writing workflow.
"""

from unittest.mock import AsyncMock, patch

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

        route_response = {
            "content": [
                {
                    "type": "text",
                    "text": (
                        '{"agent_type":"planner","workflow_type":"standard",'
                        '"reason":"需要先规划","confidence":0.95}'
                    ),
                }
            ]
        }
        with patch("agent.graph.router._route_with_deepseek_chat", AsyncMock(return_value=route_response)):
            state = {"user_message": "Plan a story outline"}
            result = await router_node(state)

            assert result["current_agent"] == "planner"
            assert result["workflow_plan"] == "standard"
            assert result["routing_metadata"]["reason"] == "需要先规划"

    async def test_router_node_error_defaults_to_writer(self):
        """Test router defaults to writer on error."""
        from agent.graph.router import router_node

        with patch("agent.graph.router._route_with_deepseek_chat", AsyncMock(side_effect=ValueError("API Error"))):
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


@pytest.mark.unit
class TestExtractRouterPayloadUnifiedJsonRepair:
    """5.2: verify unified JSON-repair path handles malformed/markdown-wrapped outputs."""

    def test_markdown_fenced_json_is_extracted(self):
        """JSON inside a markdown code fence should be parsed correctly."""
        from agent.graph.router import _extract_router_payload

        text = '```json\n{"agent_type":"writer","workflow_type":"quick","reason":"simple","confidence":0.8}\n```'
        payload = _extract_router_payload(text)

        assert payload.get("agent_type") == "writer"
        assert payload.get("workflow_type") == "quick"

    def test_multi_object_text_prefers_routing_keyed_object(self):
        """When text contains multiple JSON objects, prefer the one with routing keys."""
        from agent.graph.router import _extract_router_payload

        text = (
            'note {"foo":"bar"}\n'
            '{"agent_type":"planner","workflow_type":"standard","reason":"需要规划","confidence":0.9}'
        )
        payload = _extract_router_payload(text)

        assert payload.get("agent_type") == "planner"
        assert payload.get("workflow_type") == "standard"

    def test_unrelated_json_returns_fallback_object(self):
        """A JSON object without routing keys is still returned as best-effort fallback."""
        from agent.graph.router import _extract_router_payload

        payload = _extract_router_payload('{"foo":"bar"}')

        # Must return the dict (not empty), normalization handles defaults.
        assert isinstance(payload, dict)

    def test_legacy_two_line_still_works(self):
        """Non-JSON text with agent/workflow on separate lines still parses."""
        from agent.graph.router import _extract_router_payload

        payload = _extract_router_payload("writer\nquick")

        assert payload.get("agent_type") == "writer"
        assert payload.get("workflow_type") == "quick"


@pytest.mark.integration
class TestRouterNodeSdkOutputTypeFlag:
    """5.1: flag-guarded SDK output_type path in router_node."""

    async def test_flag_off_uses_chat_completions_path(self):
        """When AGENT_ROUTER_USE_OUTPUT_TYPE is False, _route_with_deepseek_chat is called."""
        from agent.graph.router import router_node

        route_response = {
            "content": [{"type": "text", "text": '{"agent_type":"writer","workflow_type":"quick"}'}]
        }
        with (
            patch("agent.graph.router.AGENT_ROUTER_USE_OUTPUT_TYPE", False),
            patch("agent.graph.router._route_with_deepseek_chat", AsyncMock(return_value=route_response)) as mock_chat,
            patch("agent.graph.router._route_with_sdk_output_type", AsyncMock()) as mock_sdk,
        ):
            result = await router_node({"user_message": "write something"})

        mock_chat.assert_called_once()
        mock_sdk.assert_not_called()
        assert result["current_agent"] == "writer"

    async def test_flag_on_well_formed_sdk_result_returns_decision(self):
        """When flag ON and SDK returns a valid RouterDecision, it is used directly."""
        from agent.graph.router import RouterDecision, router_node

        sdk_decision = RouterDecision(
            agent_type="planner",
            workflow_type="standard",
            reason="sdk path",
            confidence=0.9,
        )
        with (
            patch("agent.graph.router.AGENT_ROUTER_USE_OUTPUT_TYPE", True),
            patch("agent.graph.router._route_with_sdk_output_type", AsyncMock(return_value=sdk_decision)),
            patch("agent.graph.router._route_with_deepseek_chat", AsyncMock()) as mock_chat,
        ):
            result = await router_node({"user_message": "plan a story"})

        mock_chat.assert_not_called()
        assert result["current_agent"] == "planner"
        assert result["workflow_plan"] == "standard"
        assert result["routing_metadata"]["reason"] == "sdk path"

    async def test_flag_on_sdk_failure_falls_back_to_tolerant_parser(self):
        """When flag ON but SDK path returns None, tolerant parser is used as fallback."""
        from agent.graph.router import router_node

        route_response = {
            "content": [{"type": "text", "text": '{"agent_type":"writer","workflow_type":"quick"}'}]
        }
        with (
            patch("agent.graph.router.AGENT_ROUTER_USE_OUTPUT_TYPE", True),
            # SDK path returns None (simulates any failure inside _route_with_sdk_output_type)
            patch("agent.graph.router._route_with_sdk_output_type", AsyncMock(return_value=None)),
            patch("agent.graph.router._route_with_deepseek_chat", AsyncMock(return_value=route_response)) as mock_chat,
        ):
            result = await router_node({"user_message": "write something"})

        mock_chat.assert_called_once()
        assert result["current_agent"] == "writer"
        assert result["workflow_plan"] == "quick"


@pytest.mark.unit
class TestRouteWithSdkOutputTypeInternalFallback:
    """5.1: _route_with_sdk_output_type returns None on exceptions/bad output."""

    async def test_returns_none_on_exception(self):
        """Any exception inside the SDK call makes _route_with_sdk_output_type return None."""
        from agent.graph.router import _route_with_sdk_output_type

        with patch("agent.graph.router.get_deepseek_chat_model", side_effect=RuntimeError("no sdk")):
            result = await _route_with_sdk_output_type("hello")

        assert result is None

    async def test_returns_none_when_final_output_is_wrong_type(self):
        """If Runner.run returns a non-RouterDecision final_output, return None."""
        from unittest.mock import MagicMock

        from agent.graph.router import _route_with_sdk_output_type

        mock_result = MagicMock()
        mock_result.final_output = {"not": "a RouterDecision"}

        with (
            patch("agent.graph.router.get_deepseek_chat_model", return_value=MagicMock()),
            patch("agents.Agent", MagicMock()),
            patch("agents.Runner") as mock_runner_cls,
        ):
            mock_runner_cls.run = AsyncMock(return_value=mock_result)
            result = await _route_with_sdk_output_type("hello")

        assert result is None
