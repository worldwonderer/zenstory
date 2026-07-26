"""
Tool router for file operations.

This module provides the main entry point for executing file tool calls,
routing requests to the appropriate operation handlers.

Extracted from the monolithic file_executor.py for better maintainability.
"""

from typing import Any

from sqlmodel import Session, col, select

from agent.constants import coerce_bool
from agent.tools.permissions import (
    PermissionError,
    format_permission_error,
)
from models import File

from .crud import FileCRUD
from .edit import FileEditor
from .project import ProjectOperations

# 各工具里语义为布尔的参数。工具参数由 LLM 生成且走 strict_json_schema=False，
# schema 声明的 "type": "boolean" 运行时没有约束力，模型可能发来 "false"/"0"/""
# 这类字符串；朴素真值判断会把它们判真，把「删一个文件」变成「递归删整棵子树」。
# 因此在路由入口统一用 coerce_bool 强转一遍（各执行器内部还有第二道防线）。
BOOL_TOOL_ARGS: dict[str, tuple[str, ...]] = {
    "delete_file": ("recursive",),
    "edit_file": ("continue_on_error",),
}


def resolve_file_id_in_project(
    session: Session,
    project_id: str,
    id_or_title: str,
) -> dict[str, Any]:
    """
    Resolve a file id within a project.

    This is a safety fallback for common LLM mistakes where a title is passed
    into an `id` field.

    Args:
        session: Database session
        project_id: Project ID to search within
        id_or_title: Either a file ID or a file title

    Returns:
        - {"status": "ok", "file_id": "...", "resolved_by": "id"|"title"} on success
        - {"status": "ambiguous", "candidates": [...]} if multiple matches
        - {"status": "not_found"} if no match
    """
    # 1) Treat as ID first
    file = session.get(File, id_or_title)
    if file and not file.is_deleted and file.project_id == project_id:
        return {"status": "ok", "file_id": file.id, "resolved_by": "id"}

    # 2) Fallback: exact title match within project
    rows = list(
        session.exec(
            select(File)
            .where(
                File.project_id == project_id,
                col(File.title) == id_or_title,
                File.is_deleted.is_(False)
            )
            .limit(6)
        ).all()
    )
    if not rows:
        return {"status": "not_found"}
    if len(rows) == 1:
        return {"status": "ok", "file_id": rows[0].id, "resolved_by": "title"}

    return {
        "status": "ambiguous",
        "candidates": [
            {"title": r.title, "file_type": r.file_type} for r in rows
        ],
    }


def execute_file_tool_call(
    session: Session,
    tool_name: str,
    tool_args: dict[str, Any],
    user_id: str | None = None,
) -> dict[str, Any]:
    """
    Execute a file tool call with error handling.

    This is the main entry point for executing file operations. It routes
    tool calls to the appropriate operation handlers and provides consistent
    error handling.

    Args:
        session: Database session
        tool_name: Name of tool to execute
        tool_args: Arguments for tool
        user_id: Current user ID

    Returns:
        Tool execution result with status and data:
        - {"status": "success", "data": ...} on success
        - {"status": "error", "error": "..."} on failure
    """
    # Create operation handlers
    crud = FileCRUD(session, user_id)
    editor = FileEditor(session, user_id)
    project_ops = ProjectOperations(session, user_id)

    try:
        # 布尔参数强制归一（见 BOOL_TOOL_ARGS 的说明）
        for bool_arg in BOOL_TOOL_ARGS.get(tool_name, ()):
            if bool_arg in tool_args:
                tool_args[bool_arg] = coerce_bool(tool_args[bool_arg])

        # Some tools may receive an injected project_id from the agent layer.
        # Only keep it for tools that accept it.
        injected_project_id: str | None = None
        if tool_name in ("edit_file", "update_file", "delete_file"):
            injected_project_id = tool_args.pop("project_id", None)

            # Fallback: resolve common LLM mistake where title is passed into `id`.
            id_value = tool_args.get("id")
            if injected_project_id and isinstance(id_value, str) and id_value.strip():
                resolved = resolve_file_id_in_project(
                    session,
                    injected_project_id,
                    id_value.strip(),
                )
                if resolved.get("status") == "ok":
                    tool_args["id"] = resolved["file_id"]
                elif resolved.get("status") == "ambiguous":
                    candidates = resolved.get("candidates") or []
                    cand_text = ", ".join(
                        [
                            f"{c.get('title')}[{c.get('file_type')}]"
                            for c in candidates[:5]
                        ]
                    )
                    return {
                        "status": "error",
                        "error": (
                            "文件名不唯一，无法确定要操作的文件。"
                            "请提供更具体的文件名/类型，或先 query_files 再使用返回的 id。"
                            f" 候选: {cand_text}"
                        ),
                    }

        # Route to appropriate executor method
        data: Any  # Different tools return different types (dict, bool, list)
        if tool_name == "create_file":
            data = crud.create_file(**tool_args)
        elif tool_name == "update_file":
            data = crud.update_file(**tool_args)
        elif tool_name == "delete_file":
            data = crud.delete_file(**tool_args)
        elif tool_name == "query_files":
            data = crud.query_files(**tool_args)
        elif tool_name == "hybrid_search":
            data = crud.hybrid_search(**tool_args)
        elif tool_name == "edit_file":
            data = editor.edit_file(**tool_args)
        elif tool_name == "update_project_status":
            data = project_ops.update_project_status(**tool_args)
        elif tool_name == "update_plan":
            data = project_ops.execute_update_plan(**tool_args)
        else:
            return {
                "status": "error",
                "error": f"Unknown tool: {tool_name}",
            }

        return {
            "status": "success",
            "data": data,
        }

    except PermissionError as e:
        return {
            "status": "error",
            "error": format_permission_error(e),
        }
    except ValueError as e:
        return {
            "status": "error",
            "error": str(e),
        }
    except Exception as e:
        return {
            "status": "error",
            "error": f"执行失败: {str(e)}",
        }


__all__ = [
    "BOOL_TOOL_ARGS",
    "execute_file_tool_call",
    "resolve_file_id_in_project",
]
