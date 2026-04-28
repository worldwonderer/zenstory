"""
Tests for SkillUsageService.

Unit tests for the skill usage tracking service, covering:
- Recording skill usage events
- Retrieving skill usage statistics
- Getting popular skills
- Daily usage tracking
- Project ownership validation
"""

import pytest
from datetime import datetime, timedelta
from sqlmodel import Session

from models import SkillUsage, Project, User
from services.skill_usage_service import (
    record_skill_usage,
    get_skill_usage_stats,
    _get_daily_usage,
    SkillUsageStats,
)


@pytest.fixture
def test_user(db_session: Session):
    """Create a test user."""
    user = User(
        email="test@example.com",
        username="testuser",
        hashed_password="hashed_password",
        name="Test User",
        email_verified=True,
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def test_project(db_session: Session, test_user: User):
    """Create a test project."""
    project = Project(
        name="Test Project",
        description="A test project for skill usage",
        owner_id=test_user.id,
    )
    db_session.add(project)
    db_session.commit()
    db_session.refresh(project)
    return project


@pytest.fixture
def another_user(db_session: Session):
    """Create another test user for ownership tests."""
    user = User(
        email="another@example.com",
        username="anotheruser",
        hashed_password="hashed_password",
        name="Another User",
        email_verified=True,
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.mark.unit
class TestRecordSkillUsage:
    """Tests for record_skill_usage function."""

    def test_record_usage_builtin_skill(self, db_session: Session, test_project: Project, test_user: User):
        """Test recording usage for a builtin skill."""
        usage = record_skill_usage(
            session=db_session,
            project_id=test_project.id,
            skill_id="skill-001",
            skill_name="Auto Pilot",
            skill_source="builtin",
            matched_trigger="autopilot",
            confidence=0.95,
            user_id=test_user.id,
            user_message="Please autopilot this task",
        )

        assert usage.id is not None
        assert usage.project_id == test_project.id
        assert usage.user_id == test_user.id
        assert usage.skill_id == "skill-001"
        assert usage.skill_name == "Auto Pilot"
        assert usage.skill_source == "builtin"
        assert usage.matched_trigger == "autopilot"
        assert usage.confidence == 0.95
        assert usage.user_message == "Please autopilot this task"
        assert usage.created_at is not None

    def test_record_usage_user_skill(self, db_session: Session, test_project: Project, test_user: User):
        """Test recording usage for a user-defined skill."""
        usage = record_skill_usage(
            session=db_session,
            project_id=test_project.id,
            skill_id="user-skill-001",
            skill_name="My Custom Skill",
            skill_source="user",
            matched_trigger="custom trigger",
            confidence=1.0,
            user_id=test_user.id,
        )

        assert usage.skill_source == "user"
        assert usage.skill_name == "My Custom Skill"
        assert usage.confidence == 1.0

    def test_record_usage_without_user_id(self, db_session: Session, test_project: Project):
        """Test recording usage without user_id (anonymous/optional)."""
        usage = record_skill_usage(
            session=db_session,
            project_id=test_project.id,
            skill_id="skill-002",
            skill_name="Anonymous Skill",
            skill_source="builtin",
            matched_trigger="anon",
            confidence=0.8,
        )

        assert usage.id is not None
        assert usage.user_id is None
        assert usage.project_id == test_project.id

    def test_record_usage_truncates_long_message(self, db_session: Session, test_project: Project, test_user: User):
        """Test that long user messages are truncated to 500 characters."""
        long_message = "x" * 600
        usage = record_skill_usage(
            session=db_session,
            project_id=test_project.id,
            skill_id="skill-003",
            skill_name="Test Skill",
            skill_source="builtin",
            matched_trigger="test",
            user_id=test_user.id,
            user_message=long_message,
        )

        assert len(usage.user_message) == 500
        assert usage.user_message == "x" * 500

    def test_record_usage_exact_500_char_message(self, db_session: Session, test_project: Project, test_user: User):
        """Test that 500-character messages are not truncated."""
        exact_message = "x" * 500
        usage = record_skill_usage(
            session=db_session,
            project_id=test_project.id,
            skill_id="skill-004",
            skill_name="Test Skill",
            skill_source="builtin",
            matched_trigger="test",
            user_id=test_user.id,
            user_message=exact_message,
        )

        assert len(usage.user_message) == 500
        assert usage.user_message == exact_message

    def test_record_usage_unauthorized_user(self, db_session: Session, test_project: Project, another_user: User):
        """Test that recording usage with wrong user_id raises ValueError."""
        with pytest.raises(ValueError, match="does not own project"):
            record_skill_usage(
                session=db_session,
                project_id=test_project.id,
                skill_id="skill-005",
                skill_name="Test Skill",
                skill_source="builtin",
                matched_trigger="test",
                user_id=another_user.id,  # Different user
            )

    def test_record_usage_nonexistent_project(self, db_session: Session, test_user: User):
        """Test recording usage for non-existent project."""
        # When user_id is provided and project doesn't exist, it should raise ValueError
        with pytest.raises(ValueError, match="does not own project"):
            record_skill_usage(
                session=db_session,
                project_id="nonexistent-project-id",
                skill_id="skill-006",
                skill_name="Test Skill",
                skill_source="builtin",
                matched_trigger="test",
                user_id=test_user.id,
            )

    def test_record_usage_low_confidence(self, db_session: Session, test_project: Project, test_user: User):
        """Test recording usage with low confidence score."""
        usage = record_skill_usage(
            session=db_session,
            project_id=test_project.id,
            skill_id="skill-007",
            skill_name="Fuzzy Match",
            skill_source="builtin",
            matched_trigger="fuzzy",
            confidence=0.3,
            user_id=test_user.id,
        )

        assert usage.confidence == 0.3

    def test_record_usage_multiple_times(self, db_session: Session, test_project: Project, test_user: User):
        """Test recording the same skill multiple times creates separate records."""
        # Record same skill twice
        usage1 = record_skill_usage(
            session=db_session,
            project_id=test_project.id,
            skill_id="skill-008",
            skill_name="Repeated Skill",
            skill_source="builtin",
            matched_trigger="repeat",
            user_id=test_user.id,
        )

        usage2 = record_skill_usage(
            session=db_session,
            project_id=test_project.id,
            skill_id="skill-008",
            skill_name="Repeated Skill",
            skill_source="builtin",
            matched_trigger="repeat",
            user_id=test_user.id,
        )

        assert usage1.id != usage2.id
        assert usage1.skill_id == usage2.skill_id


@pytest.mark.unit
class TestGetSkillUsageStats:
    """Tests for get_skill_usage_stats function."""

    def test_get_stats_empty_project(self, db_session: Session, test_project: Project):
        """Test getting stats for a project with no usage."""
        stats = get_skill_usage_stats(
            session=db_session,
            project_id=test_project.id,
        )

        assert stats["total_triggers"] == 0
        assert stats["builtin_count"] == 0
        assert stats["user_count"] == 0
        assert stats["avg_confidence"] == 0.0
        assert stats["top_skills"] == []
        assert len(stats["daily_usage"]) == 30  # Default 30 days

    def test_get_stats_with_usage(self, db_session: Session, test_project: Project, test_user: User):
        """Test getting stats for a project with usage."""
        # Create some usage records
        for i in range(5):
            record_skill_usage(
                session=db_session,
                project_id=test_project.id,
                skill_id=f"skill-{i}",
                skill_name=f"Skill {i}",
                skill_source="builtin" if i % 2 == 0 else "user",
                matched_trigger=f"trigger{i}",
                confidence=0.8 + (i * 0.04),
                user_id=test_user.id,
            )

        stats = get_skill_usage_stats(
            session=db_session,
            project_id=test_project.id,
        )

        assert stats["total_triggers"] == 5
        assert stats["builtin_count"] == 3  # i=0, 2, 4
        assert stats["user_count"] == 2  # i=1, 3
        assert stats["avg_confidence"] > 0.8
        assert len(stats["top_skills"]) <= 10

    def test_get_stats_counts_added_source_as_user(self, db_session: Session, test_project: Project, test_user: User):
        """Test added-source usage is included in user_count metrics."""
        record_skill_usage(
            session=db_session,
            project_id=test_project.id,
            skill_id="builtin-1",
            skill_name="Builtin Skill",
            skill_source="builtin",
            matched_trigger="builtin",
            user_id=test_user.id,
        )
        record_skill_usage(
            session=db_session,
            project_id=test_project.id,
            skill_id="added-1",
            skill_name="Added Skill",
            skill_source="added",
            matched_trigger="added",
            user_id=test_user.id,
        )

        stats = get_skill_usage_stats(
            session=db_session,
            project_id=test_project.id,
        )

        assert stats["total_triggers"] == 2
        assert stats["builtin_count"] == 1
        assert stats["user_count"] == 1

    def test_get_stats_top_skills_sorted_by_count(self, db_session: Session, test_project: Project, test_user: User):
        """Test that top skills are sorted by usage count (descending)."""
        # Create skills with different usage counts
        # Skill A: 3 times
        for _ in range(3):
            record_skill_usage(
                session=db_session,
                project_id=test_project.id,
                skill_id="skill-a",
                skill_name="Skill A",
                skill_source="builtin",
                matched_trigger="a",
                user_id=test_user.id,
            )

        # Skill B: 5 times
        for _ in range(5):
            record_skill_usage(
                session=db_session,
                project_id=test_project.id,
                skill_id="skill-b",
                skill_name="Skill B",
                skill_source="builtin",
                matched_trigger="b",
                user_id=test_user.id,
            )

        # Skill C: 1 time
        record_skill_usage(
            session=db_session,
            project_id=test_project.id,
            skill_id="skill-c",
            skill_name="Skill C",
            skill_source="builtin",
            matched_trigger="c",
            user_id=test_user.id,
        )

        stats = get_skill_usage_stats(
            session=db_session,
            project_id=test_project.id,
        )

        top_skills = stats["top_skills"]
        assert len(top_skills) == 3
        # Most used skill should be first
        assert top_skills[0]["skill_id"] == "skill-b"
        assert top_skills[0]["count"] == 5
        assert top_skills[1]["skill_id"] == "skill-a"
        assert top_skills[1]["count"] == 3
        assert top_skills[2]["skill_id"] == "skill-c"
        assert top_skills[2]["count"] == 1

    def test_get_stats_merges_same_skill_id_with_different_names(
        self,
        db_session: Session,
        test_project: Project,
        test_user: User,
    ):
        """Test top skills aggregates by skill_id/source even when skill names differ."""
        record_skill_usage(
            session=db_session,
            project_id=test_project.id,
            skill_id="renamed-skill",
            skill_name="Original Name",
            skill_source="user",
            matched_trigger="rename-1",
            user_id=test_user.id,
        )
        record_skill_usage(
            session=db_session,
            project_id=test_project.id,
            skill_id="renamed-skill",
            skill_name="Updated Name",
            skill_source="user",
            matched_trigger="rename-2",
            user_id=test_user.id,
        )

        stats = get_skill_usage_stats(
            session=db_session,
            project_id=test_project.id,
        )

        renamed_entries = [s for s in stats["top_skills"] if s["skill_id"] == "renamed-skill"]
        assert len(renamed_entries) == 1
        assert renamed_entries[0]["count"] == 2

    def test_get_stats_custom_days_range(self, db_session: Session, test_project: Project, test_user: User):
        """Test getting stats for a custom date range."""
        # Create recent usage
        record_skill_usage(
            session=db_session,
            project_id=test_project.id,
            skill_id="recent-skill",
            skill_name="Recent Skill",
            skill_source="builtin",
            matched_trigger="recent",
            user_id=test_user.id,
        )

        stats = get_skill_usage_stats(
            session=db_session,
            project_id=test_project.id,
            days=7,  # Last 7 days
        )

        assert stats["total_triggers"] == 1
        assert len(stats["daily_usage"]) == 7

    def test_get_stats_total_matches_daily_usage_sum(
        self,
        db_session: Session,
        test_project: Project,
        test_user: User,
    ):
        """Test aggregate total matches summed daily buckets."""
        for i in range(4):
            record_skill_usage(
                session=db_session,
                project_id=test_project.id,
                skill_id=f"sum-skill-{i}",
                skill_name=f"Sum Skill {i}",
                skill_source="builtin",
                matched_trigger=f"sum-{i}",
                user_id=test_user.id,
            )

        stats = get_skill_usage_stats(
            session=db_session,
            project_id=test_project.id,
            days=7,
        )

        assert stats["total_triggers"] == sum(day["count"] for day in stats["daily_usage"])

    def test_get_stats_excludes_old_data(self, db_session: Session, test_project: Project, test_user: User):
        """Test that stats only include data within the date range."""
        # Create recent usage
        record_skill_usage(
            session=db_session,
            project_id=test_project.id,
            skill_id="recent-skill",
            skill_name="Recent Skill",
            skill_source="builtin",
            matched_trigger="recent",
            user_id=test_user.id,
        )

        # Create old usage (manually insert with old timestamp)
        old_usage = SkillUsage(
            project_id=test_project.id,
            user_id=test_user.id,
            skill_id="old-skill",
            skill_name="Old Skill",
            skill_source="builtin",
            matched_trigger="old",
            confidence=1.0,
            created_at=datetime.utcnow() - timedelta(days=60),  # 60 days ago
        )
        db_session.add(old_usage)
        db_session.commit()

        # Get stats for last 30 days
        stats = get_skill_usage_stats(
            session=db_session,
            project_id=test_project.id,
            days=30,
        )

        # Should only count recent usage
        assert stats["total_triggers"] == 1
        assert len([s for s in stats["top_skills"] if s["skill_id"] == "old-skill"]) == 0

    def test_get_stats_average_confidence(self, db_session: Session, test_project: Project, test_user: User):
        """Test average confidence calculation."""
        # Create skills with specific confidence scores
        confidences = [0.5, 0.75, 1.0]
        for conf in confidences:
            record_skill_usage(
                session=db_session,
                project_id=test_project.id,
                skill_id=f"skill-conf-{conf}",
                skill_name=f"Skill {conf}",
                skill_source="builtin",
                matched_trigger="test",
                confidence=conf,
                user_id=test_user.id,
            )

        stats = get_skill_usage_stats(
            session=db_session,
            project_id=test_project.id,
        )

        expected_avg = sum(confidences) / len(confidences)
        assert abs(stats["avg_confidence"] - round(expected_avg, 2)) < 0.01

    def test_get_stats_isolated_per_project(self, db_session: Session, test_user: User):
        """Test that stats are isolated per project."""
        # Create two projects
        project1 = Project(name="Project 1", owner_id=test_user.id)
        project2 = Project(name="Project 2", owner_id=test_user.id)
        db_session.add_all([project1, project2])
        db_session.commit()
        db_session.refresh(project1)
        db_session.refresh(project2)

        # Add usage to project1
        record_skill_usage(
            session=db_session,
            project_id=project1.id,
            skill_id="skill-p1",
            skill_name="Project 1 Skill",
            skill_source="builtin",
            matched_trigger="p1",
            user_id=test_user.id,
        )

        # Add usage to project2
        record_skill_usage(
            session=db_session,
            project_id=project2.id,
            skill_id="skill-p2",
            skill_name="Project 2 Skill",
            skill_source="builtin",
            matched_trigger="p2",
            user_id=test_user.id,
        )

        stats1 = get_skill_usage_stats(session=db_session, project_id=project1.id)
        stats2 = get_skill_usage_stats(session=db_session, project_id=project2.id)

        assert stats1["total_triggers"] == 1
        assert stats1["top_skills"][0]["skill_id"] == "skill-p1"

        assert stats2["total_triggers"] == 1
        assert stats2["top_skills"][0]["skill_id"] == "skill-p2"

    def test_get_stats_top_skills_limited_to_10(self, db_session: Session, test_project: Project, test_user: User):
        """Test that top skills are limited to 10 results."""
        # Create 15 different skills
        for i in range(15):
            record_skill_usage(
                session=db_session,
                project_id=test_project.id,
                skill_id=f"skill-{i}",
                skill_name=f"Skill {i}",
                skill_source="builtin",
                matched_trigger=f"trigger{i}",
                user_id=test_user.id,
            )

        stats = get_skill_usage_stats(
            session=db_session,
            project_id=test_project.id,
        )

        assert len(stats["top_skills"]) == 10


@pytest.mark.unit
class TestGetDailyUsage:
    """Tests for _get_daily_usage helper function."""

    def test_get_daily_usage_returns_correct_days(self, db_session: Session, test_project: Project):
        """Test that daily usage returns the correct number of days."""
        daily = _get_daily_usage(
            session=db_session,
            project_id=test_project.id,
            days=7,
        )

        assert len(daily) == 7
        # Each entry should have date and count
        for entry in daily:
            assert "date" in entry
            assert "count" in entry
            assert entry["count"] == 0  # No usage

    def test_get_daily_usage_counts_correctly(self, db_session: Session, test_project: Project, test_user: User):
        """Test that daily usage counts are correct."""
        # Create usage today
        for _ in range(3):
            record_skill_usage(
                session=db_session,
                project_id=test_project.id,
                skill_id="daily-skill",
                skill_name="Daily Skill",
                skill_source="builtin",
                matched_trigger="daily",
                user_id=test_user.id,
            )

        daily = _get_daily_usage(
            session=db_session,
            project_id=test_project.id,
            days=7,
        )

        # Last entry should be today with 3 counts
        assert daily[-1]["count"] == 3
        # Previous days should have 0
        for entry in daily[:-1]:
            assert entry["count"] == 0

    def test_get_daily_usage_date_format(self, db_session: Session, test_project: Project):
        """Test that dates are formatted as YYYY-MM-DD."""
        daily = _get_daily_usage(
            session=db_session,
            project_id=test_project.id,
            days=1,
        )

        import re
        date_pattern = r"^\d{4}-\d{2}-\d{2}$"
        assert re.match(date_pattern, daily[0]["date"])

    def test_get_daily_usage_chronological_order(self, db_session: Session, test_project: Project):
        """Test that daily usage is returned in chronological order (oldest first)."""
        daily = _get_daily_usage(
            session=db_session,
            project_id=test_project.id,
            days=5,
        )

        dates = [entry["date"] for entry in daily]
        assert dates == sorted(dates)

    def test_get_daily_usage_30_days(self, db_session: Session, test_project: Project):
        """Test getting daily usage for 30 days."""
        daily = _get_daily_usage(
            session=db_session,
            project_id=test_project.id,
            days=30,
        )

        assert len(daily) == 30


@pytest.mark.unit
class TestSkillUsageStatsTypedDict:
    """Tests for SkillUsageStats TypedDict structure."""

    def test_stats_returns_correct_structure(self, db_session: Session, test_project: Project, test_user: User):
        """Test that stats dict has all required keys."""
        record_skill_usage(
            session=db_session,
            project_id=test_project.id,
            skill_id="test-skill",
            skill_name="Test Skill",
            skill_source="builtin",
            matched_trigger="test",
            user_id=test_user.id,
        )

        stats = get_skill_usage_stats(
            session=db_session,
            project_id=test_project.id,
        )

        # Check all required keys exist
        assert "total_triggers" in stats
        assert "builtin_count" in stats
        assert "user_count" in stats
        assert "avg_confidence" in stats
        assert "top_skills" in stats
        assert "daily_usage" in stats

        # Check types
        assert isinstance(stats["total_triggers"], int)
        assert isinstance(stats["builtin_count"], int)
        assert isinstance(stats["user_count"], int)
        assert isinstance(stats["avg_confidence"], (int, float))
        assert isinstance(stats["top_skills"], list)
        assert isinstance(stats["daily_usage"], list)

    def test_top_skills_structure(self, db_session: Session, test_project: Project, test_user: User):
        """Test that top_skills entries have correct structure."""
        record_skill_usage(
            session=db_session,
            project_id=test_project.id,
            skill_id="struct-skill",
            skill_name="Struct Skill",
            skill_source="builtin",
            matched_trigger="struct",
            user_id=test_user.id,
        )

        stats = get_skill_usage_stats(
            session=db_session,
            project_id=test_project.id,
        )

        top_skill = stats["top_skills"][0]
        assert "skill_id" in top_skill
        assert "skill_name" in top_skill
        assert "skill_source" in top_skill
        assert "count" in top_skill

    def test_daily_usage_structure(self, db_session: Session, test_project: Project):
        """Test that daily_usage entries have correct structure."""
        stats = get_skill_usage_stats(
            session=db_session,
            project_id=test_project.id,
            days=5,
        )

        daily_entry = stats["daily_usage"][0]
        assert "date" in daily_entry
        assert "count" in daily_entry


@pytest.mark.unit
class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_zero_confidence(self, db_session: Session, test_project: Project, test_user: User):
        """Test recording usage with zero confidence."""
        usage = record_skill_usage(
            session=db_session,
            project_id=test_project.id,
            skill_id="zero-conf",
            skill_name="Zero Confidence",
            skill_source="builtin",
            matched_trigger="zero",
            confidence=0.0,
            user_id=test_user.id,
        )

        assert usage.confidence == 0.0

    def test_empty_skill_name(self, db_session: Session, test_project: Project, test_user: User):
        """Test recording usage with empty skill name (should work at DB level)."""
        usage = record_skill_usage(
            session=db_session,
            project_id=test_project.id,
            skill_id="empty-name",
            skill_name="",
            skill_source="builtin",
            matched_trigger="empty",
            user_id=test_user.id,
        )

        assert usage.skill_name == ""

    def test_long_trigger_name(self, db_session: Session, test_project: Project, test_user: User):
        """Test recording usage with maximum length trigger."""
        long_trigger = "x" * 200
        usage = record_skill_usage(
            session=db_session,
            project_id=test_project.id,
            skill_id="long-trigger",
            skill_name="Long Trigger",
            skill_source="builtin",
            matched_trigger=long_trigger,
            user_id=test_user.id,
        )

        assert usage.matched_trigger == long_trigger

    def test_stats_with_only_user_skills(self, db_session: Session, test_project: Project, test_user: User):
        """Test stats when only user-defined skills are used."""
        for i in range(3):
            record_skill_usage(
                session=db_session,
                project_id=test_project.id,
                skill_id=f"user-skill-{i}",
                skill_name=f"User Skill {i}",
                skill_source="user",
                matched_trigger=f"user{i}",
                user_id=test_user.id,
            )

        stats = get_skill_usage_stats(
            session=db_session,
            project_id=test_project.id,
        )

        assert stats["builtin_count"] == 0
        assert stats["user_count"] == 3

    def test_stats_with_only_builtin_skills(self, db_session: Session, test_project: Project, test_user: User):
        """Test stats when only builtin skills are used."""
        for i in range(3):
            record_skill_usage(
                session=db_session,
                project_id=test_project.id,
                skill_id=f"builtin-skill-{i}",
                skill_name=f"Builtin Skill {i}",
                skill_source="builtin",
                matched_trigger=f"builtin{i}",
                user_id=test_user.id,
            )

        stats = get_skill_usage_stats(
            session=db_session,
            project_id=test_project.id,
        )

        assert stats["builtin_count"] == 3
        assert stats["user_count"] == 0
