"""User persona onboarding profile model."""

from datetime import datetime

from sqlmodel import Field, SQLModel

from .utils import generate_uuid


class UserPersonaProfile(SQLModel, table=True):
    """Persisted persona onboarding profile for recommendation personalization."""

    __tablename__ = "user_persona_profile"

    id: str = Field(default_factory=generate_uuid, primary_key=True)
    user_id: str = Field(foreign_key="user.id", index=True, unique=True)

    version: int = Field(default=1)
    selected_personas: str = Field(default="[]")
    selected_goals: str = Field(default="[]")
    experience_level: str = Field(default="beginner", max_length=32)
    skipped: bool = Field(default=False)
    completed_at: datetime = Field(default_factory=datetime.utcnow)

    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
