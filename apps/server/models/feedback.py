"""
User feedback model.

Stores in-app issue feedback submitted from dashboard/editor headers.
"""

from datetime import datetime

from sqlmodel import Field, SQLModel

from .utils import generate_uuid


class UserFeedback(SQLModel, table=True):
    """User feedback with optional screenshot attachment."""

    __tablename__ = "user_feedback"

    id: str = Field(default_factory=generate_uuid, primary_key=True)
    user_id: str = Field(foreign_key="user.id", index=True)
    source_page: str = Field(index=True, max_length=32, description="dashboard/editor")
    source_route: str | None = Field(default=None, max_length=255, description="Current route path")
    issue_text: str = Field(description="Feedback text content")
    # Debug correlation fields (optional).
    trace_id: str | None = Field(default=None, index=True, max_length=64, description="Client trace ID")
    request_id: str | None = Field(default=None, index=True, max_length=64, description="Server request ID")
    agent_run_id: str | None = Field(default=None, index=True, max_length=64, description="Agent run ID")
    project_id: str | None = Field(default=None, index=True, max_length=64, description="Related project id")
    agent_session_id: str | None = Field(default=None, max_length=128, description="Agent runtime session id")
    screenshot_path: str | None = Field(default=None, max_length=512, description="Saved screenshot absolute path")
    screenshot_original_name: str | None = Field(default=None, max_length=255)
    screenshot_content_type: str | None = Field(default=None, max_length=100)
    screenshot_size_bytes: int | None = Field(default=None)
    status: str = Field(default="open", index=True, max_length=32, description="open/processing/resolved")
    created_at: datetime = Field(default_factory=datetime.utcnow, index=True)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
