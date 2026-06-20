"""Convert ZenStory MCP-style tools into OpenAI Agents SDK FunctionTool objects."""

from __future__ import annotations

import inspect
import json
from typing import Any

from agent.core.metrics import (
    TOOL_CALLS_DURATION_MS,
    TOOL_CALLS_ERRORS,
    TOOL_CALLS_TOTAL,
    get_metrics_collector,
)
from agent.openai_agents.events import extract_tool_result_text, tool_error_text
from agent.tools.registry import TOOL_FUNCTIONS, get_agent_tools
from utils.logger import get_logger, log_with_context

logger = get_logger(__name__)


def _extract_params_schema(tool_schema: dict[str, Any]) -> dict[str, Any]:
    schema = tool_schema.get("input_schema")
    if isinstance(schema, dict):
        return schema
    return {"type": "object", "properties": {}, "additionalProperties": True}


def _normalize_tool_result_text(result: Any) -> str:
    """Return the text sent back to the model for a project tool result."""
    text = extract_tool_result_text(result)
    if text:
        return text

    if isinstance(result, dict):
        return json.dumps(result, ensure_ascii=False)
    return str(result)


def _parse_tool_arguments(raw_arguments: str, *, tool_name: str) -> tuple[dict[str, Any] | None, str | None]:
    from agent.openai_agents.events import parse_json_object

    parsed, parse_error, parse_metadata = parse_json_object(raw_arguments, tool_name=tool_name)
    if parse_error is None:
        if parse_metadata.get("strategy") == "json_repair":
            log_with_context(
                logger,
                20,  # INFO
                "OpenAI Agents tool input JSON repaired",
                tool_name=tool_name,
                repair_actions=parse_metadata.get("repair_actions"),
            )
        return parsed, None

    log_with_context(
        logger,
        30,  # WARNING
        "Invalid OpenAI Agents tool input JSON",
        tool_name=tool_name,
        error=parse_error,
        repair_strategy=parse_metadata.get("strategy"),
        repair_error=parse_metadata.get("repair_error"),
    )
    return None, tool_error_text(
        "Invalid tool input JSON",
        error_type="invalid_tool_input_json",
        tool_name=tool_name,
    )


async def invoke_project_tool(tool_name: str, raw_arguments: str) -> str:
    """Invoke a project tool from an SDK FunctionTool callback."""
    metrics = get_metrics_collector()
    metrics.increment_counter(TOOL_CALLS_TOTAL)

    with metrics.time_histogram(TOOL_CALLS_DURATION_MS):
        parsed_args, parse_error_text = _parse_tool_arguments(raw_arguments, tool_name=tool_name)
        if parse_error_text is not None:
            metrics.increment_counter(TOOL_CALLS_ERRORS)
            return parse_error_text

        tool_func = TOOL_FUNCTIONS.get(tool_name)
        if tool_func is None:
            metrics.increment_counter(TOOL_CALLS_ERRORS)
            return tool_error_text(f"Unknown tool: {tool_name}", tool_name=tool_name)

        try:
            result = tool_func(parsed_args or {})
            if inspect.isawaitable(result):
                result = await result
            return _normalize_tool_result_text(result)
        except Exception as exc:
            metrics.increment_counter(TOOL_CALLS_ERRORS)
            log_with_context(
                logger,
                40,  # ERROR
                "OpenAI Agents tool execution error",
                tool_name=tool_name,
                error=str(exc),
                error_type=type(exc).__name__,
            )
            return tool_error_text(str(exc), tool_name=tool_name)


def build_agent_function_tools(agent_type: str) -> list[Any]:
    """Build SDK FunctionTool instances for the given writing agent role."""
    from agents import FunctionTool

    function_tools: list[Any] = []
    for tool_schema in get_agent_tools(agent_type):
        name = str(tool_schema.get("name") or "").strip()
        if not name:
            continue

        async def _on_invoke_tool(_ctx: Any, raw_arguments: str, *, _tool_name: str = name) -> str:
            return await invoke_project_tool(_tool_name, raw_arguments)

        function_tools.append(
            FunctionTool(
                name=name,
                description=str(tool_schema.get("description") or ""),
                params_json_schema=_extract_params_schema(tool_schema),
                on_invoke_tool=_on_invoke_tool,
                strict_json_schema=False,
            )
        )

    return function_tools
