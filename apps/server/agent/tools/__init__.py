"""
Agent Tools module for File-based Function Calling.

Provides a unified abstraction for database CRUD operations on the File model,
allowing AI to dynamically create, read, update, and delete files.

Key features:
- Generic CRUD operations on unified File model
- Query and search capabilities
- Permission checking
- MCP tool definitions for Claude SDK

Usage:
    from agent.tools import FileToolExecutor, execute_file_tool_call

    # Execute tool call
    result = execute_file_tool_call(
        session=session,
        tool_name="create_file",
        tool_args={"project_id": 1, "title": "Chapter 1", "file_type": "outline"},
        user_id=123
    )
"""

from .file_executor import (
    FileToolExecutor,
    execute_file_tool_call,
)
from .permissions import (
    ForbiddenError,
    NotFoundError,
    PermissionContext,
    PermissionError,
    UnauthorizedError,
    check_file_ownership,
    check_project_ownership,
    format_permission_error,
)

__all__ = [
    # File Executor
    "FileToolExecutor",
    "execute_file_tool_call",
    # Permissions
    "PermissionError",
    "UnauthorizedError",
    "ForbiddenError",
    "NotFoundError",
    "check_project_ownership",
    "check_file_ownership",
    "PermissionContext",
    "format_permission_error",
]
