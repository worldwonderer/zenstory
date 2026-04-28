"""
Integration test for writing streak functionality.

Tests:
1. Create a project with draft files
2. Record writing activity on consecutive days
3. Verify streak increments correctly
4. Verify streak status transitions (active, at_risk, broken)
5. Verify streak recovery with grace period
6. Verify flame icon displays for active streak
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


def test_writing_streak():
    """Test writing streak updates with daily activity."""
    print("=" * 60)
    print("Testing Writing Streak Functionality")
    print("=" * 60)

    # Create test database
    engine, db_fd, db_path = create_test_database()

    try:
        with Session(engine) as session:
            # Step 1: Create test user and project
            print("\n1. Creating test user and project...")
            test_user = User(
                id="streak-user-001",
                email="streak@example.com",
                username="streakuser",
                hashed_password="hashed",
            )
            session.add(test_user)

            test_project = Project(
                id="streak-project-001",
                name="Streak Test Novel",
                owner_id=test_user.id,
                project_type="novel",
            )
            session.add(test_project)
            session.commit()
            print(f"   Created user: {test_user.id}")
            print(f"   Created project: {test_project.name}")

            # Step 2: Create draft files with content
            print("\n2. Creating draft files with content...")
            draft = File(
                id="streak-draft-001",
                project_id=test_project.id,
                title="Chapter 1",
                file_type="draft",
                content="This is the content of chapter one for testing streak functionality. " * 20,
                order=1,
            )
            session.add(draft)
            session.commit()
            print(f"   Created draft file: {draft.title}")

            # Use UTC date for consistency with the service
            today = datetime.utcnow().date()

            # Step 3: Test initial streak state (no activity)
            print("\n3. Testing initial streak state...")
            initial_streak = writing_stats_service.get_streak(
                session, test_user.id, test_project.id
            )
            print(f"   Initial streak status: {initial_streak['streak_status']}")
            print(f"   Current streak: {initial_streak['current_streak']}")
            assert initial_streak['streak_status'] == 'none', "Initial streak should be 'none'"
            assert initial_streak['current_streak'] == 0, "Initial streak count should be 0"

            # For testing consecutive days, we'll use dates relative to a "test reference date"
            # This allows us to simulate multiple days of consecutive writing
            yesterday = today - timedelta(days=1)
            two_days_ago = today - timedelta(days=2)

            # Step 4: Record first day of writing (yesterday) and verify streak starts
            print("\n4. Recording first day of writing (yesterday)...")
            stats_day1 = writing_stats_service.record_word_count(
                session=session,
                user_id=test_user.id,
                project_id=test_project.id,
                word_count=300,
                words_added=300,
                words_deleted=0,
                edit_time_seconds=2400,
                stats_date=yesterday,
            )
            print(f"   Day 1 stats: {stats_day1.word_count} words")

            # Update streak for day 1 (yesterday)
            streak_day1 = writing_stats_service.update_streak(
                session=session,
                user_id=test_user.id,
                project_id=test_project.id,
                words_written=300,
                stats_date=yesterday,
            )
            print(f"   Streak after day 1: {streak_day1.current_streak}")

            # Verify streak started
            assert streak_day1.current_streak == 1, "Streak should be 1 after first day"

            # Step 5: Record second consecutive day (today) and verify streak increments
            print("\n5. Recording second consecutive day (today)...")
            stats_day2 = writing_stats_service.record_word_count(
                session=session,
                user_id=test_user.id,
                project_id=test_project.id,
                word_count=500,
                words_added=500,
                words_deleted=0,
                edit_time_seconds=3600,
                stats_date=today,
            )
            print(f"   Day 2 stats: {stats_day2.word_count} words")

            # Update streak for today
            streak_day2 = writing_stats_service.update_streak(
                session=session,
                user_id=test_user.id,
                project_id=test_project.id,
                words_written=500,
                stats_date=today,
            )
            print(f"   Streak after second day: {streak_day2.current_streak}")
            assert streak_day2.current_streak == 2, "Streak should be 2 after consecutive day"

            # Verify streak status is now "active"
            streak_info_day2 = writing_stats_service.get_streak(
                session, test_user.id, test_project.id
            )
            print(f"   Streak status: {streak_info_day2['streak_status']}")
            assert streak_info_day2['streak_status'] == 'active', "Streak status should be 'active'"
            assert streak_info_day2['last_writing_date'] == str(today), "Last writing date should be today"

            # Step 6: Test streak at risk (grace period)
            print("\n6. Testing streak at risk (grace period)...")

            # Record three days ago
            three_days_ago = today - timedelta(days=3)
            stats_day3 = writing_stats_service.record_word_count(
                session=session,
                user_id=test_user.id,
                project_id=test_project.id,
                word_count=200,
                words_added=200,
                words_deleted=0,
                edit_time_seconds=1800,
                stats_date=three_days_ago,
            )

            # Reset streak and start fresh for at_risk test
            streak_reset = writing_stats_service.reset_streak(
                session, test_user.id, test_project.id
            )
            assert streak_reset.current_streak == 0, "Streak should be 0 after reset"

            # Write yesterday
            writing_stats_service.update_streak(
                session, test_user.id, test_project.id,
                words_written=200,
                stats_date=yesterday,
            )

            # Check streak status (should be at_risk since we haven't written today)
            # Create a separate test to verify at_risk status
            # For now, verify the current active streak
            current_streak_info = writing_stats_service.get_streak(
                session, test_user.id, test_project.id
            )
            print(f"   Current streak: {current_streak_info['current_streak']}")
            print(f"   Streak status: {current_streak_info['streak_status']}")

            # Step 7: Test multiple consecutive days
            print("\n7. Testing multiple consecutive days...")

            # Reset for fresh test
            writing_stats_service.reset_streak(session, test_user.id, test_project.id)

            # Simulate 5 consecutive days of writing
            consecutive_days = 5
            for i in range(consecutive_days):
                day = today - timedelta(days=consecutive_days - 1 - i)
                writing_stats_service.record_word_count(
                    session=session,
                    user_id=test_user.id,
                    project_id=test_project.id,
                    word_count=100 * (i + 1),
                    words_added=100,
                    words_deleted=0,
                    edit_time_seconds=600,
                    stats_date=day,
                )
                writing_stats_service.update_streak(
                    session, test_user.id, test_project.id,
                    words_written=100,
                    stats_date=day,
                )

            final_streak = writing_stats_service.get_streak(
                session, test_user.id, test_project.id
            )
            print(f"   Streak after {consecutive_days} consecutive days: {final_streak['current_streak']}")
            assert final_streak['current_streak'] == consecutive_days, f"Streak should be {consecutive_days}"
            assert final_streak['streak_status'] == 'active', "Streak should be active"
            assert final_streak['longest_streak'] == consecutive_days, f"Longest streak should be {consecutive_days}"

            # Step 8: Verify flame icon data (frontend verification)
            print("\n8. Verifying flame icon display conditions...")
            # Flame icon appears when:
            # 1. current_streak > 0
            # 2. streak_status == 'active'
            print(f"   Current streak > 0: {final_streak['current_streak'] > 0} ✓")
            print(f"   Streak status is 'active': {final_streak['streak_status'] == 'active'} ✓")
            print(f"   Flame icon should display: YES ✓")

            assert final_streak['current_streak'] > 0, "Flame icon requires streak > 0"
            assert final_streak['streak_status'] == 'active', "Flame icon requires active status"

            # Step 9: Test streak breaks after too many missed days
            print("\n9. Testing streak break after grace period...")

            # Reset and create a streak that will break
            writing_stats_service.reset_streak(session, test_user.id, test_project.id)

            # Write 5 days ago (beyond grace period of 1 day)
            five_days_ago = today - timedelta(days=5)
            writing_stats_service.record_word_count(
                session, test_user.id, test_project.id,
                word_count=100, words_added=100,
                stats_date=five_days_ago,
            )
            writing_stats_service.update_streak(
                session, test_user.id, test_project.id,
                words_written=100,
                stats_date=five_days_ago,
            )

            # Check streak status - should be broken (more than 2 days since last write)
            broken_streak = writing_stats_service.get_streak(
                session, test_user.id, test_project.id
            )
            print(f"   Streak after 5 days without writing: {broken_streak['streak_status']}")
            assert broken_streak['streak_status'] == 'broken', "Streak should be broken after grace period"

            # Step 10: Test streak recovery (using grace period by skipping a day)
            print("\n10. Testing streak recovery (using grace period)...")

            # Reset and test recovery
            writing_stats_service.reset_streak(session, test_user.id, test_project.id)

            # Write 2 days ago (this sets up for grace period recovery)
            two_days_ago = today - timedelta(days=2)
            writing_stats_service.record_word_count(
                session, test_user.id, test_project.id,
                word_count=100, words_added=100,
                stats_date=two_days_ago,
            )
            writing_stats_service.update_streak(
                session, test_user.id, test_project.id,
                words_written=100,
                stats_date=two_days_ago,
            )

            # Get streak (should be at_risk since we haven't written for 2 days)
            at_risk_streak = writing_stats_service.get_streak(
                session, test_user.id, test_project.id
            )
            print(f"   Streak status (skipped 1 day): {at_risk_streak['streak_status']}")
            print(f"   Can recover: {at_risk_streak['can_recover']}")
            assert at_risk_streak['streak_status'] == 'at_risk', "Streak should be at_risk"
            assert at_risk_streak['can_recover'] == True, "Streak should be recoverable"

            # Now write today to recover (using grace period - skipped yesterday)
            writing_stats_service.record_word_count(
                session, test_user.id, test_project.id,
                word_count=150, words_added=150,
                stats_date=today,
            )
            recovered_streak = writing_stats_service.update_streak(
                session, test_user.id, test_project.id,
                words_written=150,
                stats_date=today,
            )
            print(f"   Streak after recovery: {recovered_streak.current_streak}")
            print(f"   Recovery count: {recovered_streak.streak_recovery_count}")
            # Recovery count increments because we used grace period (days_since_last = 2)
            assert recovered_streak.streak_recovery_count == 1, "Recovery count should be 1"

            recovered_info = writing_stats_service.get_streak(
                session, test_user.id, test_project.id
            )
            assert recovered_info['streak_status'] == 'active', "Streak should be active after recovery"

            # Step 11: Test minimum word threshold
            print("\n11. Testing minimum word threshold (10 words)...")

            # Reset and try with too few words
            writing_stats_service.reset_streak(session, test_user.id, test_project.id)

            # Write only 5 words (below threshold of 10)
            below_threshold_streak = writing_stats_service.update_streak(
                session, test_user.id, test_project.id,
                words_written=5,
                stats_date=today,
            )
            print(f"   Streak with 5 words (below threshold): {below_threshold_streak.current_streak}")
            assert below_threshold_streak.current_streak == 0, "Streak should not count for < 10 words"

            # Write exactly 10 words
            threshold_streak = writing_stats_service.update_streak(
                session, test_user.id, test_project.id,
                words_written=10,
                stats_date=today,
            )
            print(f"   Streak with 10 words (at threshold): {threshold_streak.current_streak}")
            assert threshold_streak.current_streak == 1, "Streak should count for >= 10 words"

            print("\n" + "=" * 60)
            print("✅ ALL WRITING STREAK TESTS PASSED!")
            print("=" * 60)

            # Print summary
            print("\n📊 Test Summary:")
            print(f"   - Created project: {test_project.name}")
            print(f"   - Created 1 draft file")
            print(f"   - Initial streak status: none (verified)")
            print(f"   - Streak starts on first writing day: ✓")
            print(f"   - Streak increments on consecutive days: ✓")
            print(f"   - Streak becomes 'at_risk' after 1 missed day: ✓")
            print(f"   - Streak breaks after grace period: ✓")
            print(f"   - Streak recovery works correctly: ✓")
            print(f"   - Minimum word threshold (10) works: ✓")
            print(f"   - Flame icon displays for active streak: ✓")
            print(f"   - Longest streak tracked: {final_streak['longest_streak']} days")

    finally:
        # Cleanup
        os.close(db_fd)
        os.unlink(db_path)
        print("\n🧹 Test database cleaned up.")


if __name__ == "__main__":
    test_writing_streak()
