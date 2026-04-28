"""
Integration test for streak updates when editing activity is deletion-heavy.
"""
import os
import sys
import tempfile
from datetime import datetime

# Add the parent directory to the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlmodel import Session, SQLModel, create_engine

from api.stats import RecordStatsRequest, record_project_stats
from models.entities import Project, User
from services.features.writing_stats_service import writing_stats_service


def create_test_database():
    """Create a temporary test database."""
    db_fd, db_path = tempfile.mkstemp(suffix=".db")
    database_url = f"sqlite:///{db_path}"
    engine = create_engine(database_url, echo=False)
    SQLModel.metadata.create_all(engine)
    return engine, db_fd, db_path


def test_record_stats_updates_streak_when_words_deleted():
    """
    Streak should update when there is meaningful editing activity
    even if net additions are zero.
    """
    engine, db_fd, db_path = create_test_database()

    try:
        with Session(engine) as session:
            user = User(
                id="test-user-streak-activity",
                email="streak-activity@example.com",
                username="streakactivity",
                hashed_password="hashed",
            )
            project = Project(
                id="test-project-streak-activity",
                name="Streak Activity Test",
                owner_id=user.id,
                project_type="novel",
            )
            session.add(user)
            session.add(project)
            session.commit()

            today = datetime.utcnow().date().isoformat()
            response = record_project_stats(
                project_id=project.id,
                request=RecordStatsRequest(
                    word_count=1200,
                    words_added=0,
                    words_deleted=15,
                    edit_time_seconds=300,
                    stats_date=today,
                ),
                current_user=user,
                session=session,
            )

            assert response.streak_updated is True
            assert response.new_streak == 1

            streak = writing_stats_service.get_streak(session, user.id, project.id)
            assert streak["current_streak"] == 1
            assert streak["last_writing_date"] == today
    finally:
        os.close(db_fd)
        os.unlink(db_path)

