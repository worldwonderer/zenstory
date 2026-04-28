"""
File Operations module for agent tools.

This module provides modular file operation handlers extracted from the
monolithic file_executor.py. Each operation type is implemented in its own
module for better maintainability and testing.

Key features:
- Generic CRUD operations on unified File model
- Precise file content editing with fuzzy text matching
- Query and search capabilities (keyword, hybrid)
- Project status and task board management
- Permission checking integrated throughout

Structure:
- serialization.py: File serialization utilities
- text_matching.py: Fuzzy and approximate text matching utilities
- crud.py: File CRUD operations (create, update, delete, query, hybrid_search)
- edit.py: Precise file content editing operations
- project.py: Project status and task board operations
- executor.py: Composite FileToolExecutor class (main entry point)
- router.py: Tool routing and execution entry point

Usage:
    from agent.tools.file_ops import FileToolExecutor, execute_file_tool_call

    # Execute tool call (recommended entry point)
    result = execute_file_tool_call(
        session=session,
        tool_name="create_file",
        tool_args={"project_id": "uuid", "title": "Chapter 1", "file_type": "outline"},
        user_id="user-uuid"
    )

    # Or use the executor class directly
    executor = FileToolExecutor(session, user_id="user-uuid")
    file = executor.create_file(
        project_id="uuid",
        title="Chapter 1",
        file_type="outline"
    )
"""

# Serialization utilities
# Operation classes (for direct use if needed)
from .crud import FileCRUD
from .edit import FileEditor

# Composite executor (main entry point for file operations)
from .executor import FileToolExecutor
from .project import ProjectOperations

# Router (main entry point for tool calls)
from .router import execute_file_tool_call, resolve_file_id_in_project
from .serialization import serialize_file
from .text_matching import (
    build_span_previews as _build_span_previews,
)
from .text_matching import (
    find_approximate_match as _find_approximate_match,
)
from .text_matching import (
    find_fuzzy_spans as _find_fuzzy_spans,
)
from .text_matching import (
    find_unique_line_span as _find_unique_line_span,
)

# Text matching utilities (internal helpers with underscore prefix)
from .text_matching import (
    normalize_for_fuzzy_match as _normalize_for_fuzzy_match,
)
from .text_matching import (
    suggest_similar_lines as _suggest_similar_lines,
)

__all__ = [
    # Main entry points
    "FileToolExecutor",
    "execute_file_tool_call",
    "resolve_file_id_in_project",
    # Serialization
    "serialize_file",
    # Operation classes (for direct use if needed)
    "FileCRUD",
    "FileEditor",
    "ProjectOperations",
    # Text matching utilities (internal, underscore-prefixed)
    "_normalize_for_fuzzy_match",
    "_find_fuzzy_spans",
    "_find_approximate_match",
    "_build_span_previews",
    "_suggest_similar_lines",
    "_find_unique_line_span",
]
