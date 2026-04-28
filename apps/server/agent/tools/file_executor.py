"""
File-based Function Calling tools.

This module provides backward-compatible imports for the modular file operations
system. All functionality has been extracted into the file_ops/ subpackage.

Simple, unified CRUD operations on File model:
- create_file: Create any type of file
- update_file: Update existing file
- delete_file: Delete a file
- query_files: Query and search files (unified)

For direct access to the modular components, import from file_ops:
    from agent.tools.file_ops import FileToolExecutor, execute_file_tool_call
    from agent.tools.file_ops import FileCRUD, FileEditor, ProjectOperations
    from agent.tools.file_ops import serialize_file
"""

# Re-export main entry points from the modular file_ops package
# Re-export operation classes for advanced usage
from agent.tools.file_ops import (
    FileCRUD,
    FileEditor,
    FileToolExecutor,
    ProjectOperations,
    execute_file_tool_call,
    resolve_file_id_in_project,
    serialize_file,
)

__all__ = [
    # Main entry points
    "FileToolExecutor",
    "execute_file_tool_call",
    "resolve_file_id_in_project",
    # Serialization
    "serialize_file",
    # Operation classes
    "FileCRUD",
    "FileEditor",
    "ProjectOperations",
]
