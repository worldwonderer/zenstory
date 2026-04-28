"""
Tool registry: central source for tool schema/handler wiring.

This module provides one place to assemble:
- Anthropic tool schema lists
- MCP handler dispatch map
- Agent-type -> toolset mapping
"""

import json
from typing import Any

from agent.tools.anthropic_tools import ANTHROPIC_TOOL_SCHEMAS
from agent.tools.mcp_tools import MCP_TOOL_HANDLERS
from agent.tools.parallel_executor import execute_parallel

DEFAULT_TOOL_NAMES: list[str] = [
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

QUALITY_REVIEWER_TOOL_NAMES: list[str] = [
    "query_files",
    "hybrid_search",
    "update_project",
    "handoff_to_agent",
    "request_clarification",
]

AGENT_TOOL_NAME_MAP: dict[str, list[str]] = {
    "planner": DEFAULT_TOOL_NAMES,
    "hook_designer": DEFAULT_TOOL_NAMES,
    "writer": DEFAULT_TOOL_NAMES,
    "quality_reviewer": QUALITY_REVIEWER_TOOL_NAMES,
}


async def _execute_parallel_tool(args: dict[str, Any]) -> dict[str, Any]:
    """Adapter for parallel_execute tool input contract."""
    tasks = args.get("tasks", [])
    if not isinstance(tasks, list):
        return {
            "content": [{
                "type": "text",
                "text": json.dumps({
                    "status": "error",
                    "error": "Invalid input for parallel_execute: 'tasks' must be an array.",
                }),
            }]
        }
    return await execute_parallel(tasks)

# Name -> MCP handler
TOOL_FUNCTIONS: dict[str, Any] = {
    **dict(MCP_TOOL_HANDLERS),
    "parallel_execute": _execute_parallel_tool,
}


def _build_tool_schemas(tool_names: list[str]) -> list[dict[str, Any]]:
    """Resolve Anthropic tool schema list from registry names."""
    return [ANTHROPIC_TOOL_SCHEMAS[name] for name in tool_names if name in ANTHROPIC_TOOL_SCHEMAS]


AGENT_TOOLS_MAP: dict[str, list[dict[str, Any]]] = {
    agent: _build_tool_schemas(tool_names)
    for agent, tool_names in AGENT_TOOL_NAME_MAP.items()
}


def get_agent_tools(agent_type: str) -> list[dict[str, Any]]:
    """Get Anthropic tool schema list by agent type."""
    return AGENT_TOOLS_MAP.get(agent_type, AGENT_TOOLS_MAP["writer"])


def validate_registry_alignment() -> dict[str, list[str]]:
    """
    Return alignment diagnostics between schema registry and handler registry.

    This is a lightweight helper for tests/diagnostics.
    """
    missing_schemas = [name for name in DEFAULT_TOOL_NAMES if name not in ANTHROPIC_TOOL_SCHEMAS]
    missing_handlers = [name for name in DEFAULT_TOOL_NAMES if name not in TOOL_FUNCTIONS]
    quality_reviewer_missing = [
        name for name in QUALITY_REVIEWER_TOOL_NAMES if name not in DEFAULT_TOOL_NAMES
    ]
    return {
        "missing_schemas": missing_schemas,
        "missing_handlers": missing_handlers,
        "invalid_quality_reviewer_tools": quality_reviewer_missing,
    }
