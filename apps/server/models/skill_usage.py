"""
Skill usage tracking model.

Records each skill match event for analytics and optimization.
"""

from datetime import datetime

from sqlmodel import Field, SQLModel

from .utils import generate_uuid


class SkillUsage(SQLModel, table=True):
    """
    Skill usage tracking model.

    Records each time a skill is matched and activated,
    enabling usage analytics and optimization insights.
    """

    __tablename__ = "skill_usage"

    id: str = Field(default_factory=generate_uuid, primary_key=True)
    user_id: str | None = Field(default=None, foreign_key="user.id", index=True)
    project_id: str = Field(foreign_key="project.id", index=True)

    # Skill information
    skill_id: str = Field(index=True, description="ID of the matched skill")
    skill_name: str = Field(max_length=100, description="Name of the skill")
    skill_source: str = Field(
        max_length=20,
        description="Source: 'builtin', 'user', or 'added'"
    )

    # Match details
    matched_trigger: str = Field(
        max_length=200,
        description="The trigger that matched"
    )
    confidence: float = Field(
        default=1.0,
        description="Match confidence score (0.0-1.0)"
    )
    user_message: str | None = Field(
        default=None,
        max_length=500,
        description="Truncated user message that triggered the skill"
    )

    # Timestamp
    created_at: datetime = Field(default_factory=datetime.utcnow, index=True)
