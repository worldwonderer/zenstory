"""
Activation event model.

Stores user lifecycle activation milestones for funnel analytics.
"""

from datetime import datetime

from sqlalchemy import JSON, Column, UniqueConstraint
from sqlmodel import Field, SQLModel

from config.datetime_utils import utcnow

from .utils import generate_uuid

ACTIVATION_EVENT_SIGNUP_SUCCESS = "signup_success"
ACTIVATION_EVENT_PROJECT_CREATED = "project_created"
ACTIVATION_EVENT_FIRST_FILE_SAVED = "first_file_saved"
ACTIVATION_EVENT_FIRST_AI_ACTION_ACCEPTED = "first_ai_action_accepted"

ACTIVATION_EVENT_NAMES = {
    ACTIVATION_EVENT_SIGNUP_SUCCESS,
    ACTIVATION_EVENT_PROJECT_CREATED,
    ACTIVATION_EVENT_FIRST_FILE_SAVED,
    ACTIVATION_EVENT_FIRST_AI_ACTION_ACCEPTED,
}


class ActivationEvent(SQLModel, table=True):
    """User activation milestone event."""

    __tablename__ = "activation_event"
    __table_args__ = (
        UniqueConstraint("user_id", "event_name", name="uq_activation_event_user_event"),
    )

    id: str = Field(default_factory=generate_uuid, primary_key=True)
    user_id: str = Field(foreign_key="user.id", index=True)
    project_id: str | None = Field(default=None, foreign_key="project.id", index=True)
    event_name: str = Field(max_length=64, index=True)
    event_metadata: dict = Field(default_factory=dict, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=utcnow, index=True)
