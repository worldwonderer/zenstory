"""
Writing statistics models for tracking daily word counts and streaks.

Defines SQLModel entities for:
- WritingStats: Daily word count tracking per project
- WritingStreak: Project-specific writing streak with recovery tracking
"""

from datetime import date, datetime

from sqlmodel import Field, SQLModel

from .utils import generate_uuid


class WritingStats(SQLModel, table=True):
    """
    Writing statistics model for daily word count tracking.

    Tracks daily writing activity per project with:
    - Word count for each day
    - Project association for per-project statistics
    - Date-based tracking for trend analysis
    """

    __tablename__ = "writing_stats"

    id: str = Field(default_factory=generate_uuid, primary_key=True)
    user_id: str = Field(foreign_key="user.id", index=True)
    project_id: str = Field(foreign_key="project.id", index=True)

    # Daily statistics
    stats_date: date = Field(index=True)

    # Word count for the day
    word_count: int = Field(default=0)

    # Additional statistics
    words_added: int = Field(default=0, description="New words added today")
    words_deleted: int = Field(default=0, description="Words deleted today")

    # Edit session tracking
    edit_sessions: int = Field(default=0, description="Number of edit sessions")
    total_edit_time_seconds: int = Field(default=0, description="Total time spent editing")

    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class WritingStreak(SQLModel, table=True):
    """
    Writing streak model for project-specific streak tracking.

    Tracks writing streaks with:
    - Current and longest streak counts
    - Streak recovery tracking after breaks
    - Project association for per-project streaks
    """

    __tablename__ = "writing_streak"

    id: str = Field(default_factory=generate_uuid, primary_key=True)
    user_id: str = Field(foreign_key="user.id", index=True)
    project_id: str = Field(foreign_key="project.id", index=True)

    # Streak tracking
    current_streak: int = Field(default=0)
    longest_streak: int = Field(default=0)

    # Streak dates
    last_writing_date: date | None = Field(default=None, index=True)
    streak_start_date: date | None = Field(default=None)

    # Recovery tracking
    streak_recovery_count: int = Field(default=0, description="Times streak was recovered after break")

    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
