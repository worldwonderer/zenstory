"""
Shared utility functions for database models.
"""

from uuid import uuid4


def generate_uuid() -> str:
    """Generate a new UUID string."""
    return str(uuid4())
