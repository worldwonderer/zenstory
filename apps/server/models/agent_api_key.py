"""
Agent API Key model for API authentication.

Defines SQLModel entity for:
- AgentApiKey: API keys for programmatic access to agent endpoints
"""

from datetime import datetime

from sqlalchemy import JSON, Column
from sqlmodel import Field, SQLModel

from .utils import generate_uuid

# Default scopes for new API keys
DEFAULT_SCOPES = ["read", "write", "chat"]


class AgentApiKey(SQLModel, table=True):
    """
    Agent API Key model.

    Supports:
    - Multiple API keys per user
    - Scoped permissions (read, write, chat)
    - Project-level access restrictions
    - Key expiration and usage tracking
    """

    __tablename__ = "agent_api_key"

    id: str = Field(default_factory=generate_uuid, primary_key=True)
    user_id: str = Field(foreign_key="user.id", index=True)
    key_prefix: str = Field(max_length=8)  # "eg_" for identification
    key_hash: str = Field(unique=True, index=True)  # SHA256 hash
    name: str = Field(max_length=100)
    description: str | None = Field(default=None, max_length=500)
    scopes: list = Field(default_factory=lambda: DEFAULT_SCOPES.copy(), sa_column=Column(JSON))
    project_ids: list | None = Field(default=None, sa_column=Column(JSON))  # None = all projects
    is_active: bool = True
    last_used_at: datetime | None = None
    expires_at: datetime | None = None
    request_count: int = 0
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
