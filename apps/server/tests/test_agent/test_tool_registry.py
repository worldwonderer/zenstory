"""Tests for centralized tool registry wiring."""

import pytest


@pytest.mark.unit
def test_registry_alignment_has_no_missing_handlers():
    from agent.tools.registry import validate_registry_alignment

    diagnostics = validate_registry_alignment()
    assert diagnostics["missing_schemas"] == []
    assert diagnostics["missing_handlers"] == []
    assert diagnostics["invalid_quality_reviewer_tools"] == []


@pytest.mark.unit
def test_registry_contains_hybrid_search_handler():
    from agent.tools.registry import TOOL_FUNCTIONS

    assert "hybrid_search" in TOOL_FUNCTIONS
    assert callable(TOOL_FUNCTIONS["hybrid_search"])


@pytest.mark.unit
def test_registry_contains_parallel_execute_handler():
    from agent.tools.registry import TOOL_FUNCTIONS

    assert "parallel_execute" in TOOL_FUNCTIONS
    assert callable(TOOL_FUNCTIONS["parallel_execute"])


@pytest.mark.unit
def test_writer_toolset_exposes_hybrid_search_only():
    from agent.tools.registry import get_agent_tools

    tool_names = [tool["name"] for tool in get_agent_tools("writer")]
    assert "hybrid_search" in tool_names
    assert "semantic_search" not in tool_names


@pytest.mark.unit
def test_quality_reviewer_toolset_exposes_hybrid_search_only():
    from agent.tools.registry import get_agent_tools

    tool_names = [tool["name"] for tool in get_agent_tools("quality_reviewer")]
    assert "hybrid_search" in tool_names
    assert "semantic_search" not in tool_names
