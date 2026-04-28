"""Tests for streak status when client provides local reference date."""

import os
import sys
import tempfile
from datetime import date

from sqlmodel import SQLModel, Session, create_engine

# Add the parent directory to the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models.entities import Project, User
from services.features.writing_stats_service import writing_stats_service


def create_test_database():
    """Create a temporary test database."""
    db_fd, db_path = tempfile.mkstemp(suffix=".db")
    database_url = f"sqlite:///{db_path}"
    engine = create_engine(database_url, echo=False)
    SQLModel.metadata.create_all(engine)
    return engine, db_fd, db_path


def test_get_streak_uses_reference_date_when_provided():
    """Streak status should be evaluated against the provided reference date."""
    engine, db_fd, db_path = create_test_database()

    try:
        with Session(engine) as session:
            user = User(
                id="test-user-streak-reference-date",
                email="streak-reference-date@example.com",
                username="streakreferencedate",
                hashed_password="hashed",
            )
            project = Project(
                id="test-project-streak-reference-date",
                name="Streak Reference Date Project",
                owner_id=user.id,
                project_type="novel",
            )
            session.add(user)
            session.add(project)
            session.commit()

            writing_day = date(2026, 1, 2)
            writing_stats_service.update_streak(
                session=session,
                user_id=user.id,
                project_id=project.id,
                words_written=100,
                stats_date=writing_day,
            )

            same_day = writing_stats_service.get_streak(
                session=session,
                user_id=user.id,
                project_id=project.id,
                reference_date=writing_day,
            )
            assert same_day["streak_status"] == "active"

            next_day = writing_stats_service.get_streak(
                session=session,
                user_id=user.id,
                project_id=project.id,
                reference_date=date(2026, 1, 3),
            )
            assert next_day["streak_status"] == "at_risk"
            assert next_day["days_until_break"] >= 0

    finally:
        os.close(db_fd)
        os.unlink(db_path)
