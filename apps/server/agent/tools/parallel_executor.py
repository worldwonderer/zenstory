"""
Parallel execution tool for dispatching concurrent subagent tasks.

Allows the main agent to execute multiple independent tasks in parallel,
then aggregate results.
"""

import asyncio
import json
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from utils.logger import get_logger

logger = get_logger(__name__)

MAX_PARALLEL_TASKS = 5
MAX_CONCURRENCY = 2
PARALLEL_TASK_TYPES = (
    "write_chapter",
    "edit_file",
    "delete_file",
    "query_files",
    "hybrid_search",
)


@dataclass
class SubagentTask:
    """A task to be executed by a subagent."""
    id: str
    task_type: str  # One of PARALLEL_TASK_TYPES
    description: str
    parameters: dict[str, Any]
    status: str = "pending"  # pending, running, completed, failed
    result: Any = None
    error: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None


@dataclass
class ParallelExecutionResult:
    """Result of a parallel execution."""
    execution_id: str
    tasks: list[SubagentTask]
    all_completed: bool
    any_failed: bool
    total_duration_ms: int


# Tool definition
PARALLEL_EXECUTE_TOOL: dict[str, Any] = {
    "name": "parallel_execute",
    "description": """Execute multiple independent tasks in parallel using subagents.

Use this when you need to perform multiple independent operations simultaneously,
such as:
- Writing multiple chapters at once
- Editing multiple files concurrently
- Running multiple queries in parallel

All tasks must be independent (not depend on each other's results).
Maximum 5 parallel tasks per call.

Task param conventions:
- edit_file (recommended): params = {"id": "<file_id>", "edits": [...], "continue_on_error": false}
  - Legacy aliases: {"file_id": "..."} for id, {"operations": [...]} for edits
- delete_file: params = {"id": "<file_id>", "recursive": false}
""",
    "input_schema": {
        "type": "object",
        "properties": {
            "tasks": {
                "type": "array",
                "maxItems": 5,
                "items": {
                    "type": "object",
                    "properties": {
                        "type": {
                            "type": "string",
                            "description": "Task type: write_chapter, edit_file, delete_file, query_files, hybrid_search",
                            "enum": list(PARALLEL_TASK_TYPES),
                        },
                        "description": {
                            "type": "string",
                            "description": "Human-readable task description",
                        },
                        "params": {
                            "type": "object",
                            "description": "Task-specific parameters",
                        },
                    },
                    "required": ["type", "description", "params"],
                },
            },
        },
        "required": ["tasks"],
    },
}


def _make_result(data: Any) -> dict[str, Any]:
    """Create a tool result in MCP format."""
    return {
        "content": [{
            "type": "text",
            "text": json.dumps(data, ensure_ascii=False)
        }]
    }


def _make_error(error: str) -> dict[str, Any]:
    """Create an error result in MCP format."""
    return {
        "content": [{
            "type": "text",
            "text": json.dumps({"status": "error", "error": error}, ensure_ascii=False)
        }]
    }


async def handle_write_chapter(params: dict[str, Any]) -> dict[str, Any]:
    """Handle write_chapter task type - creates a draft file."""
    from agent.tools.mcp_tools import ToolContext, create_file

    project_id = ToolContext._get_context().get("project_id")
    if project_id is None:
        return _make_error("project_id not set")

    # 检查是否有待写入的空文件
    if ToolContext.has_pending_empty_file():
        pending = ToolContext.get_pending_empty_file()
        pending_title = pending.get("title", "unknown") if pending else "unknown"
        return _make_error(
            f"Please complete writing the previous file '{pending_title}' first."
        )

    try:
        result = await create_file({
            "title": params.get("title", "Untitled Chapter"),
            "file_type": "draft",
            "content": params.get("content", ""),
            "parent_id": params.get("parent_id"),
        })
        return result
    except RuntimeError as err:
        if str(err) == "No session available in ToolContext":
            return _make_error("project_id not set")
        raise


async def handle_edit_file(params: dict[str, Any]) -> dict[str, Any]:
    """Handle edit_file task type."""
    from agent.tools.mcp_tools import edit_file

    # Keep backward compatibility with the original parallel_execute contract
    # (file_id/operations) while aligning with the canonical edit_file tool
    # contract (id/edits) used everywhere else.
    file_id_raw = params.get("id") if params.get("id") is not None else params.get("file_id")
    if isinstance(file_id_raw, str):
        file_id = file_id_raw.strip()
    elif file_id_raw is None:
        file_id = ""
    else:
        return _make_error("Invalid edit_file task params: 'id' must be a string.")

    edits = params.get("edits")
    if edits is None:
        edits = params.get("operations", [])

    if not file_id:
        return _make_error(
            "Invalid edit_file task params: missing 'id'. "
            "Provide params.id (recommended) or params.file_id (legacy)."
        )
    if not isinstance(edits, list):
        return _make_error("Invalid edit_file task params: 'edits' must be an array.")

    result = await edit_file({
        "id": file_id,
        "edits": edits,
        "continue_on_error": bool(params.get("continue_on_error", False)),
    })
    return result


async def handle_delete_file(params: dict[str, Any]) -> dict[str, Any]:
    """Handle delete_file task type."""
    from agent.tools.mcp_tools import delete_file

    file_id_raw = params.get("id") if params.get("id") is not None else params.get("file_id")
    if isinstance(file_id_raw, str):
        file_id = file_id_raw.strip()
    elif file_id_raw is None:
        file_id = ""
    else:
        return _make_error("Invalid delete_file task params: 'id' must be a string.")

    if not file_id:
        return _make_error(
            "Invalid delete_file task params: missing 'id'. "
            "Provide params.id (recommended) or params.file_id (legacy)."
        )

    return await delete_file({
        "id": file_id,
        "recursive": bool(params.get("recursive", False)),
    })


async def handle_query_files(params: dict[str, Any]) -> dict[str, Any]:
    """Handle query_files task type."""
    from agent.tools.mcp_tools import ToolContext, query_files

    project_id = ToolContext._get_context().get("project_id")
    if project_id is None:
        return _make_error("project_id not set")

    try:
        result = await query_files({
            "project_id": project_id,
            "id": params.get("id"),
            "query": params.get("query"),
            "file_type": params.get("file_type"),
            "file_types": params.get("file_types"),
            "parent_id": params.get("parent_id"),
            "limit": params.get("limit", 50),
            "offset": params.get("offset", 0),
        })
        return result
    except RuntimeError as err:
        if str(err) == "No session available in ToolContext":
            return _make_error("project_id not set")
        raise


async def handle_hybrid_search(params: dict[str, Any]) -> dict[str, Any]:
    """Handle hybrid_search task type."""
    from agent.tools.mcp_tools import ToolContext, hybrid_search

    project_id = ToolContext._get_context().get("project_id")
    if project_id is None:
        return _make_error("project_id not set")

    try:
        result = await hybrid_search({
            "query": params.get("query", ""),
            "top_k": params.get("top_k", 10),
            "entity_types": params.get("entity_types"),
            "min_score": params.get("min_score", 0.0),
        })
        return result
    except RuntimeError as err:
        if str(err) == "No session available in ToolContext":
            return _make_error("project_id not set")
        raise


async def execute_parallel(
    tasks: list[dict[str, Any]],
) -> dict[str, Any]:
    """
    Execute multiple tasks in parallel with limited concurrency.

    Args:
        tasks: List of task specifications with type, description, and params

    Returns:
        ParallelExecutionResult as MCP-formatted dict
    """
    from agent.tools.mcp_tools import ToolContext

    # Check if there's a pending empty file - parallel execution not allowed
    if ToolContext.has_pending_empty_file():
        pending = ToolContext.get_pending_empty_file()
        pending_title = pending.get("title", "unknown") if pending else "unknown"
        return _make_error(
            f"Cannot execute parallel tasks while file '{pending_title}' is pending. "
            "Please complete the file write first."
        )

    execution_id = f"par-{datetime.now().timestamp()}"
    start_time = datetime.now()

    # Limit tasks to MAX_PARALLEL_TASKS
    limited_tasks = tasks[:MAX_PARALLEL_TASKS]
    if len(tasks) > MAX_PARALLEL_TASKS:
        logger.warning(
            f"parallel_execute: Truncated {len(tasks)} tasks to {MAX_PARALLEL_TASKS}"
        )

    # Create SubagentTask objects
    # Use .get() defensively — LLM may omit optional-ish fields despite
    # the schema marking them required.
    subagent_tasks = [
        SubagentTask(
            id=f"{execution_id}-{i}",
            task_type=t.get("type", "unknown"),
            description=t.get("description", ""),
            parameters=t.get("params", {}),
        )
        for i, t in enumerate(limited_tasks)
    ]

    # Map task types to handlers
    task_handlers: dict[str, Callable] = {
        "write_chapter": handle_write_chapter,
        "edit_file": handle_edit_file,
        "delete_file": handle_delete_file,
        "query_files": handle_query_files,
        "hybrid_search": handle_hybrid_search,
    }

    semaphore = asyncio.Semaphore(MAX_CONCURRENCY)

    async def execute_task(task: SubagentTask) -> SubagentTask:
        async with semaphore:
            task.status = "running"
            task.started_at = datetime.now()

            try:
                handler = task_handlers.get(task.task_type)
                if not handler:
                    raise ValueError(f"Unknown task type: {task.task_type}")

                # Give each task its own context so get_session() creates a
                # fresh session instead of sharing the parent ToolContext's
                # session across concurrent threads (SQLAlchemy sessions are
                # not thread-safe).
                from agent.tools.mcp_tools import (
                    ToolContext,
                    _tool_context_var,
                )

                original_ctx = _tool_context_var.get()
                task_ctx = dict(original_ctx) if isinstance(original_ctx, dict) else {}
                task_ctx["session"] = None  # force get_session() to create a new one
                token = _tool_context_var.set(task_ctx)
                try:
                    result = await handler(task.parameters)
                finally:
                    _tool_context_var.reset(token)
                    ToolContext._cleanup_owned_session()

                # Extract result text from MCP format
                content_list = result.get("content", [])
                if content_list and content_list[0].get("type") == "text":
                    result_text = content_list[0].get("text", "")
                    try:
                        task.result = json.loads(result_text)
                    except json.JSONDecodeError:
                        task.result = {"raw": result_text}
                else:
                    task.result = result

                if isinstance(task.result, dict) and task.result.get("status") == "error":
                    task.status = "failed"
                    task.error = str(
                        task.result.get("error")
                        or task.result.get("message")
                        or "Task reported error status"
                    )
                else:
                    task.status = "completed"
            except Exception as e:
                task.error = str(e)
                task.status = "failed"
                logger.error(f"parallel_execute task failed: {e}", exc_info=True)
            finally:
                task.completed_at = datetime.now()

            return task

    # Execute all tasks concurrently with semaphore limiting
    completed_tasks = await asyncio.gather(*[execute_task(t) for t in subagent_tasks])

    end_time = datetime.now()
    duration_ms = int((end_time - start_time).total_seconds() * 1000)

    # Build result summary
    result_data = {
        "execution_id": execution_id,
        "total_tasks": len(completed_tasks),
        "completed": sum(1 for t in completed_tasks if t.status == "completed"),
        "failed": sum(1 for t in completed_tasks if t.status == "failed"),
        "all_completed": all(t.status == "completed" for t in completed_tasks),
        "any_failed": any(t.status == "failed" for t in completed_tasks),
        "total_duration_ms": duration_ms,
        "tasks": [
            {
                "id": t.id,
                "type": t.task_type,
                "description": t.description,
                "status": t.status,
                "result": t.result,
                "error": t.error,
            }
            for t in completed_tasks
        ],
    }

    logger.info(
        f"parallel_execute completed: {result_data['completed']}/{result_data['total_tasks']} "
        f"tasks in {duration_ms}ms"
    )

    return _make_result({"status": "success", "data": result_data})
