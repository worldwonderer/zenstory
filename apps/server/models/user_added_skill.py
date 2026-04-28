"""
User added skill database model.

Junction table linking users to public skills they have added.
"""

from datetime import datetime

from sqlalchemy import UniqueConstraint
from sqlmodel import Field, SQLModel

from .utils import generate_uuid


class UserAddedSkill(SQLModel, table=True):
    """
    User added skill model - links users to public skills.

    Tracks which public skills a user has added to their collection.
    """

    __tablename__ = "user_added_skill"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "public_skill_id",
            name="uq_user_added_skill_user_public",
        ),
    )

    id: str = Field(default_factory=generate_uuid, primary_key=True)

    # Foreign keys
    user_id: str = Field(foreign_key="user.id", index=True)
    public_skill_id: str = Field(foreign_key="public_skill.id", index=True)

    # Customization
    custom_name: str | None = Field(
        default=None,
        max_length=100,
        description="User's custom name for this skill (optional)"
    )

    # Status
    is_active: bool = Field(
        default=True,
        description="Whether the skill is active for this user"
    )

    # Timestamps
    added_at: datetime = Field(default_factory=datetime.utcnow)
