"""
Integration test for word count trends functionality.

Tests:
1. Create a project with draft files
2. Record word count stats
3. Verify word count chart shows data
4. Change time range (daily/weekly/monthly)
5. Verify stats update correctly
"""
import os
import sys
import tempfile
from datetime import date, datetime, timedelta

# Add the parent directory to the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlmodel import Session, SQLModel, create_engine, select
from models.writing_stats import WritingStats, WritingStreak
from models.file_model import File
from models.entities import Project, User
from services.features.writing_stats_service import writing_stats_service


def create_test_database():
    """Create a temporary test database."""
    # Create a temporary file for the test database
    db_fd, db_path = tempfile.mkstemp(suffix='.db')
    database_url = f"sqlite:///{db_path}"
    engine = create_engine(database_url, echo=False)
    SQLModel.metadata.create_all(engine)
    return engine, db_fd, db_path


def test_word_count_trends():
    """Test word count trends display correctly with real data."""
    print("=" * 60)
    print("Testing Word Count Trends Functionality")
    print("=" * 60)

    # Create test database
    engine, db_fd, db_path = create_test_database()

    try:
        with Session(engine) as session:
            # Step 1: Create test user and project
            print("\n1. Creating test user and project...")
            test_user = User(
                id="test-user-001",
                email="test@example.com",
                username="testuser",
                hashed_password="hashed",
            )
            session.add(test_user)

            test_project = Project(
                id="test-project-001",
                name="Test Novel",
                owner_id=test_user.id,
                project_type="novel",
            )
            session.add(test_project)
            session.commit()
            print(f"   Created user: {test_user.id}")
            print(f"   Created project: {test_project.name}")

            # Step 2: Create draft files with content
            print("\n2. Creating draft files with content...")
            draft1 = File(
                id="draft-001",
                project_id=test_project.id,
                title="Chapter 1",
                file_type="draft",
                content="This is the content of chapter one. It contains several words for testing purposes. " * 20,
                order=1,
            )
            draft2 = File(
                id="draft-002",
                project_id=test_project.id,
                title="Chapter 2",
                file_type="draft",
                content="This is the content of chapter two. More content to test word counting functionality. " * 30,
                order=2,
            )
            session.add(draft1)
            session.add(draft2)
            session.commit()
            print(f"   Created draft files: {draft1.title}, {draft2.title}")

            # Step 3: Record word count stats for different dates
            print("\n3. Recording word count stats for different dates...")
            # Use UTC date for consistency with the service
            today = datetime.utcnow().date()

            # Calculate week_start early to ensure all stats are within the current week
            # This prevents test failures when running on Monday where yesterday/2-days-ago
            # would fall in the previous week
            week_start = today - timedelta(days=today.weekday())

            # Record stats for today (always within current week)
            stats_today = writing_stats_service.record_word_count(
                session=session,
                user_id=test_user.id,
                project_id=test_project.id,
                word_count=500,
                words_added=500,
                words_deleted=0,
                edit_time_seconds=3600,
                stats_date=today,
            )
            print(f"   Recorded today: {stats_today.word_count} words")

            # Record stats for a day earlier in this week (use week_start + 1 to stay in week)
            # If today is Monday (week_start == today), use week_start for other entries
            if today == week_start:
                # Monday: record additional stats for same day to total 1000 words
                stats_day2 = writing_stats_service.record_word_count(
                    session=session,
                    user_id=test_user.id,
                    project_id=test_project.id,
                    word_count=300,
                    words_added=300,
                    words_deleted=0,
                    edit_time_seconds=2400,
                    stats_date=today,  # Same day on Monday
                )
                stats_day3 = writing_stats_service.record_word_count(
                    session=session,
                    user_id=test_user.id,
                    project_id=test_project.id,
                    word_count=200,
                    words_added=200,
                    words_deleted=0,
                    edit_time_seconds=1800,
                    stats_date=today,  # Same day on Monday
                )
            else:
                # Not Monday: we need to record stats on days BEFORE today
                # to avoid affecting the "words today" count
                days_since_monday = (today - week_start).days
                # Use days that are definitely before today (yesterday and 2 days ago)
                # But ensure they're still within the current week
                if days_since_monday >= 2:
                    day2 = week_start + timedelta(days=days_since_monday - 1)  # yesterday
                    day3 = week_start + timedelta(days=days_since_monday - 2)  # 2 days ago
                elif days_since_monday == 1:
                    # Tuesday: can only use Monday (week_start) for other stats
                    day2 = week_start
                    day3 = week_start
                stats_day2 = writing_stats_service.record_word_count(
                    session=session,
                    user_id=test_user.id,
                    project_id=test_project.id,
                    word_count=300,
                    words_added=300,
                    words_deleted=0,
                    edit_time_seconds=2400,
                    stats_date=day2,
                )
                stats_day3 = writing_stats_service.record_word_count(
                    session=session,
                    user_id=test_user.id,
                    project_id=test_project.id,
                    word_count=200,
                    words_added=200,
                    words_deleted=0,
                    edit_time_seconds=1800,
                    stats_date=day3,
                )
            print(f"   Recorded day 2: {stats_day2.word_count} words")
            print(f"   Recorded day 3: {stats_day3.word_count} words")

            # Step 4: Verify word count chart shows data
            print("\n4. Verifying word count data retrieval...")

            # Get total word count
            total_word_count = writing_stats_service.get_total_word_count(
                session, test_user.id, test_project.id
            )
            print(f"   Total word count from draft files: {total_word_count}")
            assert total_word_count > 0, "Total word count should be greater than 0"

            # Get words written today
            words_today = writing_stats_service.get_words_written_in_period(
                session, test_user.id, test_project.id, today, today
            )
            print(f"   Words today: {words_today['net_words']}")
            # On Monday, all 3 records are on the same day, so words_added accumulates to 1000
            # On other days, only the first 500-word record is on today
            if today == week_start:
                # Monday: all stats are on today
                assert words_today["net_words"] == 1000, f"Expected 1000 for Monday, got {words_today['net_words']}"
            else:
                # Other days: only today's record
                assert words_today["net_words"] == 500, f"Expected 500, got {words_today['net_words']}"

            # Get words written this week (week_start already calculated earlier)
            words_this_week = writing_stats_service.get_words_written_in_period(
                session, test_user.id, test_project.id, week_start, today
            )
            print(f"   Words this week: {words_this_week['net_words']}")
            assert words_this_week["net_words"] == 1000, f"Expected 1000, got {words_this_week['net_words']}"

            # Step 5: Test time range changes (daily/weekly/monthly)
            print("\n5. Testing time range changes...")

            # Daily trend - only returns days with recorded stats, not empty days
            daily_trend = writing_stats_service.get_word_count_trend(
                session, test_user.id, test_project.id, period="daily", days=7
            )
            print(f"   Daily trend data points: {len(daily_trend)}")
            # Expect at least 1 day of stats (on Monday all 3 records are same day, so 1 unique date)
            # On other days, expect 2-3 unique dates depending on how the dates fall within the week
            assert len(daily_trend) >= 1, f"Expected at least 1 day of data, got {len(daily_trend)}"
            print(f"   Daily trend sample: {daily_trend[0]}")

            # Verify daily trend data structure
            for item in daily_trend:
                assert "date" in item, "Daily item should have date"
                assert "word_count" in item, "Daily item should have word_count"
                assert "net_words" in item, "Daily item should have net_words"

            # Weekly trend
            weekly_trend = writing_stats_service.get_word_count_trend(
                session, test_user.id, test_project.id, period="weekly", days=30
            )
            print(f"   Weekly trend data points: {len(weekly_trend)}")
            assert len(weekly_trend) >= 1, "Should have at least 1 week of data"
            print(f"   Weekly trend sample: {weekly_trend[0]}")

            # Verify weekly trend data structure
            for item in weekly_trend:
                assert "date" in item, "Weekly item should have date"
                assert "period_label" in item, "Weekly item should have period_label"
                assert "word_count" in item, "Weekly item should have word_count"
                assert "days_with_activity" in item, "Weekly item should have days_with_activity"

            # Monthly trend
            monthly_trend = writing_stats_service.get_word_count_trend(
                session, test_user.id, test_project.id, period="monthly", days=90
            )
            print(f"   Monthly trend data points: {len(monthly_trend)}")
            assert len(monthly_trend) >= 1, "Should have at least 1 month of data"
            print(f"   Monthly trend sample: {monthly_trend[0]}")

            # Verify monthly trend data structure
            for item in monthly_trend:
                assert "date" in item, "Monthly item should have date"
                assert "period_label" in item, "Monthly item should have period_label"
                assert "word_count" in item, "Monthly item should have word_count"

            # Step 6: Verify chart updates correctly
            print("\n6. Verifying chart updates with new data...")

            # Add more stats to verify updates - use a date guaranteed to be in current week
            # Use week_start if today is early in the week, otherwise use an earlier day in the week
            day4 = week_start + timedelta(days=min(3, (today - week_start).days))
            stats_day4 = writing_stats_service.record_word_count(
                session=session,
                user_id=test_user.id,
                project_id=test_project.id,
                word_count=150,
                words_added=150,
                words_deleted=0,
                edit_time_seconds=1200,
                stats_date=day4,
            )

            # Get updated daily trend
            updated_daily = writing_stats_service.get_word_count_trend(
                session, test_user.id, test_project.id, period="daily", days=7
            )
            print(f"   Updated daily trend data points: {len(updated_daily)}")
            # Expect at least as many data points as before (could be same if all on same day)
            assert len(updated_daily) >= len(daily_trend), f"Expected at least {len(daily_trend)} days of data after update, got {len(updated_daily)}"

            # Verify total words changed - should now include the additional 150 words
            updated_weekly = writing_stats_service.get_words_written_in_period(
                session, test_user.id, test_project.id, week_start, today
            )
            print(f"   Updated words this week: {updated_weekly['net_words']}")
            # Total should be at least 1000 (original) + potentially 150 more if day4 is a new unique date
            # If day4 == one of the existing days, the words_added accumulates on that date
            assert updated_weekly["net_words"] >= 1150, f"Expected at least 1150, got {updated_weekly['net_words']}"

            print("\n" + "=" * 60)
            print("✅ ALL WORD COUNT TREND TESTS PASSED!")
            print("=" * 60)

            # Print summary
            print("\n📊 Test Summary:")
            print(f"   - Created project: {test_project.name}")
            print(f"   - Created 2 draft files")
            print(f"   - Recorded 4 stat entries")
            print(f"   - Total word count: {total_word_count}")
            print(f"   - Words today: {words_today['net_words']}")
            print(f"   - Words this week: {updated_weekly['net_words']}")
            print(f"   - Daily trend points: {len(updated_daily)}")
            print(f"   - Weekly trend points: {len(weekly_trend)}")
            print(f"   - Monthly trend points: {len(monthly_trend)}")

    finally:
        # Cleanup
        os.close(db_fd)
        os.unlink(db_path)
        print("\n🧹 Test database cleaned up.")


def test_word_count_trend_respects_explicit_end_date():
    """Trend window should use caller-provided end_date when given."""
    engine, db_fd, db_path = create_test_database()

    try:
        with Session(engine) as session:
            user = User(
                id="test-user-trend-end-date",
                email="trend-end-date@example.com",
                username="trendenddateuser",
                hashed_password="hashed",
            )
            project = Project(
                id="test-project-trend-end-date",
                name="Trend End Date Project",
                owner_id=user.id,
                project_type="novel",
            )
            session.add(user)
            session.add(project)
            session.commit()

            stats_day = date(2026, 1, 2)
            writing_stats_service.record_word_count(
                session=session,
                user_id=user.id,
                project_id=project.id,
                word_count=200,
                words_added=200,
                words_deleted=0,
                edit_time_seconds=60,
                stats_date=stats_day,
            )

            missing_day = writing_stats_service.get_word_count_trend(
                session=session,
                user_id=user.id,
                project_id=project.id,
                period="daily",
                days=1,
                end_date=date(2026, 1, 1),
            )
            assert missing_day == []

            included_day = writing_stats_service.get_word_count_trend(
                session=session,
                user_id=user.id,
                project_id=project.id,
                period="daily",
                days=1,
                end_date=stats_day,
            )
            assert len(included_day) == 1
            assert included_day[0]["date"] == "2026-01-02"
            assert included_day[0]["words_added"] == 200

    finally:
        os.close(db_fd)
        os.unlink(db_path)


if __name__ == "__main__":
    test_word_count_trends()
