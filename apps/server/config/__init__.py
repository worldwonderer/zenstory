"""
Configuration module for project templates and settings.
"""

from .datetime_utils import utcnow
from .project_templates import (
    PROJECT_TEMPLATES,
    get_file_type_mapping,
    get_folders_for_type,
    get_template_by_type,
)

__all__ = [
    "PROJECT_TEMPLATES",
    "get_template_by_type",
    "get_folders_for_type",
    "get_file_type_mapping",
    "utcnow",
]
