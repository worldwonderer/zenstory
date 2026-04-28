"""
User-defined skill database model.

Stores user-created skills that can be triggered by keywords
and inject instructions into the AI system prompt.
"""

from datetime import datetime

from sqlmodel import Column, Field, SQLModel, Text

from .utils import generate_uuid


class UserSkill(SQLModel, table=True):
    """
    User-defined skill model.

    Allows users to create custom skills with trigger keywords
    that inject instructions into the AI assistant's system prompt.
    """

    __tablename__ = "user_skill"

    id: str = Field(default_factory=generate_uuid, primary_key=True)
    user_id: str = Field(foreign_key="user.id", index=True)

    # Skill metadata
    name: str = Field(max_length=100, description="Display name of the skill")
    description: str | None = Field(
        default=None,
        max_length=500,
        description="Brief description of what the skill does"
    )

    # Trigger keywords (stored as JSON array string)
    triggers: str = Field(
        default="[]",
        sa_column=Column(Text),
        description="JSON array of trigger keywords"
    )

    # Instructions to inject into system prompt
    instructions: str = Field(
        sa_column=Column(Text),
        description="Instructions to inject into system prompt"
    )

    # Status
    is_active: bool = Field(default=True, description="Whether the skill is active")

    # Sharing status
    is_shared: bool = Field(
        default=False,
        description="Whether this skill has been shared to public library"
    )
    shared_skill_id: str | None = Field(
        default=None,
        foreign_key="public_skill.id",
        description="ID of the public skill if shared"
    )

    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
