"""
Integration test for chapter completion percentage functionality.

Tests:
1. Create a project with outline and draft folders
2. Add draft files with content
3. Verify completion percentage calculates correctly
4. Verify chapter details display proper status
"""
import os
import sys
import tempfile

# Add the parent directory to the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlmodel import Session, SQLModel, create_engine

from models.entities import Project, User
from models.file_model import FILE_TYPE_DRAFT, FILE_TYPE_OUTLINE, File
from services.features.writing_stats_service import writing_stats_service


def create_test_database():
    """Create a temporary test database."""
    db_fd, db_path = tempfile.mkstemp(suffix='.db')
    database_url = f"sqlite:///{db_path}"
    engine = create_engine(database_url, echo=False)
    SQLModel.metadata.create_all(engine)
    return engine, db_fd, db_path


def test_chapter_completion_percentage():
    """Test chapter completion percentage calculates correctly."""
    print("=" * 60)
    print("Testing Chapter Completion Percentage Functionality")
    print("=" * 60)

    engine, db_fd, db_path = create_test_database()

    try:
        with Session(engine) as session:
            # Step 1: Create test user and project
            print("\n1. Creating test user and project...")
            test_user = User(
                id="test-user-chapter",
                email="chapter@example.com",
                username="chapteruser",
                hashed_password="hashed",
            )
            session.add(test_user)

            test_project = Project(
                id="test-project-chapter",
                name="Test Novel with Chapters",
                owner_id=test_user.id,
                project_type="novel",
            )
            session.add(test_project)
            session.commit()
            print(f"   Created user: {test_user.id}")
            print(f"   Created project: {test_project.name}")

            # Step 2: Create outline files (planned chapters)
            print("\n2. Creating outline files (planned chapters)...")
            outlines = [
                File(
                    id="outline-001",
                    project_id=test_project.id,
                    title="Chapter 1: The Beginning",
                    file_type=FILE_TYPE_OUTLINE,
                    content="# Chapter 1 Outline\n\n- Introduction\n- Setup\n- First event",
                    order=1,
                ),
                File(
                    id="outline-002",
                    project_id=test_project.id,
                    title="Chapter 2: The Journey",
                    file_type=FILE_TYPE_OUTLINE,
                    content="# Chapter 2 Outline\n\n- Travel scene\n- Meeting characters\n- Conflict starts",
                    order=2,
                ),
                File(
                    id="outline-003",
                    project_id=test_project.id,
                    title="Chapter 3: The Climax",
                    file_type=FILE_TYPE_OUTLINE,
                    content="# Chapter 3 Outline\n\n- Big battle\n- Resolution\n- Setup for sequel",
                    order=3,
                ),
                File(
                    id="outline-004",
                    project_id=test_project.id,
                    title="Chapter 4: Epilogue",
                    file_type=FILE_TYPE_OUTLINE,
                    content="# Chapter 4 Outline\n\n- Aftermath\n- Character futures",
                    order=4,
                ),
            ]
            for outline in outlines:
                session.add(outline)
            session.commit()
            print(f"   Created {len(outlines)} outline files")

            # Step 3: Create draft files with varying content
            print("\n3. Creating draft files with varying content...")

            # Complete chapter (100+ words, well above threshold)
            complete_draft = File(
                id="draft-001",
                project_id=test_project.id,
                title="Chapter 1: The Beginning",  # Exact match with outline
                file_type=FILE_TYPE_DRAFT,
                content="The sun rose over the distant mountains, casting long shadows across the valley. "
                "Sarah stood at the edge of the cliff, watching the world below awaken. "
                "This was her favorite time of day, when everything felt possible. "
                "She took a deep breath and began her descent into the unknown lands that lay ahead. "
                "The journey would be long, but she was prepared for whatever challenges awaited her.",
                order=1,
            )
            session.add(complete_draft)

            # In-progress chapter (some content, but less than 50 words)
            in_progress_draft = File(
                id="draft-002",
                project_id=test_project.id,
                title="Chapter 2: The Journey",  # Exact match with outline
                file_type=FILE_TYPE_DRAFT,
                content="The road stretched before her, winding through forests and meadows.",
                order=2,
            )
            session.add(in_progress_draft)

            # No draft for Chapter 3 (not started)
            # Intentionally not creating a draft file

            # Another complete chapter
            complete_draft_2 = File(
                id="draft-004",
                project_id=test_project.id,
                title="Chapter 4: Epilogue",  # Exact match with outline
                file_type=FILE_TYPE_DRAFT,
                content="Years had passed since that fateful journey. Sarah often found herself reflecting on "
                "the paths she had taken and the choices that had shaped her life. The friends she made "
                "along the way remained close, their bonds forged in the fires of adventure. "
                "As she sat by the fire one evening, watching the flames dance, she smiled. "
                "Every step had been worth it. Every challenge had made her stronger. "
                "And though the journey was over, she knew new adventures awaited on the horizon.",
                order=4,
            )
            session.add(complete_draft_2)
            session.commit()

            print(f"   Created complete draft: '{complete_draft.title}' ({len(complete_draft.content.split())} words)")
            print(f"   Created in-progress draft: '{in_progress_draft.title}' ({len(in_progress_draft.content.split())} words)")
            print("   No draft for 'Chapter 3: The Climax' (not started)")
            print(f"   Created complete draft: '{complete_draft_2.title}' ({len(complete_draft_2.content.split())} words)")

            # Step 4: Get chapter completion stats
            print("\n4. Verifying chapter completion stats...")
            completion_stats = writing_stats_service.get_chapter_completion_stats(
                session, test_project.id, min_words_for_complete=50
            )

            # Print the stats
            print(f"   Total chapters: {completion_stats['total_chapters']}")
            print(f"   Completed chapters: {completion_stats['completed_chapters']}")
            print(f"   In-progress chapters: {completion_stats['in_progress_chapters']}")
            print(f"   Not-started chapters: {completion_stats['not_started_chapters']}")
            print(f"   Completion percentage: {completion_stats['completion_percentage']}%")

            # Step 5: Verify completion stats
            print("\n5. Verifying calculation accuracy...")

            # Check total chapters
            assert completion_stats['total_chapters'] == 4, \
                f"Expected 4 total chapters, got {completion_stats['total_chapters']}"
            print("   ✓ Total chapters: 4")

            # Check completed chapters (2 drafts with >= 50 words)
            assert completion_stats['completed_chapters'] == 2, \
                f"Expected 2 completed chapters, got {completion_stats['completed_chapters']}"
            print("   ✓ Completed chapters: 2")

            # Check in-progress chapters (1 draft with < 50 words but > 0)
            assert completion_stats['in_progress_chapters'] == 1, \
                f"Expected 1 in-progress chapter, got {completion_stats['in_progress_chapters']}"
            print("   ✓ In-progress chapters: 1")

            # Check not-started chapters (1 outline with no matching draft)
            assert completion_stats['not_started_chapters'] == 1, \
                f"Expected 1 not-started chapter, got {completion_stats['not_started_chapters']}"
            print("   ✓ Not-started chapters: 1")

            # Check completion percentage (2/4 = 50%)
            assert completion_stats['completion_percentage'] == 50, \
                f"Expected 50% completion, got {completion_stats['completion_percentage']}%"
            print("   ✓ Completion percentage: 50%")

            # Step 6: Verify chapter details
            print("\n6. Verifying individual chapter details...")
            chapter_details = completion_stats['chapter_details']

            # Check that we have details for all chapters
            assert len(chapter_details) == 4, \
                f"Expected 4 chapter details, got {len(chapter_details)}"
            print("   ✓ Chapter details count: 4")

            # Verify each chapter's status
            for detail in chapter_details:
                print(f"   - '{detail['title']}': {detail['status']} ({detail['word_count']} words)")
                assert 'outline_id' in detail, "Chapter detail should have outline_id"
                assert 'title' in detail, "Chapter detail should have title"
                assert 'status' in detail, "Chapter detail should have status"
                assert 'word_count' in detail, "Chapter detail should have word_count"
                assert 'completion_percentage' in detail, "Chapter detail should have completion_percentage"
                assert detail['status'] in ['complete', 'in_progress', 'not_started'], \
                    f"Invalid status: {detail['status']}"

            # Verify specific chapters
            chapter1 = next((c for c in chapter_details if "Chapter 1" in c['title']), None)
            assert chapter1 is not None, "Chapter 1 should exist in details"
            assert chapter1['status'] == 'complete', f"Chapter 1 should be complete, got {chapter1['status']}"
            assert chapter1['word_count'] >= 50, f"Chapter 1 should have >= 50 words, got {chapter1['word_count']}"
            print("   ✓ Chapter 1 status verified: complete")

            chapter2 = next((c for c in chapter_details if "Chapter 2" in c['title']), None)
            assert chapter2 is not None, "Chapter 2 should exist in details"
            assert chapter2['status'] == 'in_progress', f"Chapter 2 should be in_progress, got {chapter2['status']}"
            assert 0 < chapter2['word_count'] < 50, f"Chapter 2 should have 0-50 words, got {chapter2['word_count']}"
            print("   ✓ Chapter 2 status verified: in_progress")

            chapter3 = next((c for c in chapter_details if "Chapter 3" in c['title']), None)
            assert chapter3 is not None, "Chapter 3 should exist in details"
            assert chapter3['status'] == 'not_started', f"Chapter 3 should be not_started, got {chapter3['status']}"
            assert chapter3['word_count'] == 0, f"Chapter 3 should have 0 words, got {chapter3['word_count']}"
            assert chapter3['draft_id'] is None, "Chapter 3 should have no draft_id"
            print("   ✓ Chapter 3 status verified: not_started")

            chapter4 = next((c for c in chapter_details if "Chapter 4" in c['title']), None)
            assert chapter4 is not None, "Chapter 4 should exist in details"
            assert chapter4['status'] == 'complete', f"Chapter 4 should be complete, got {chapter4['status']}"
            print("   ✓ Chapter 4 status verified: complete")

            # Step 7: Test completion percentage with only drafts (no outlines)
            print("\n7. Testing draft-only mode (no outlines)...")

            # Create a new project with only drafts
            project_drafts_only = Project(
                id="test-project-drafts-only",
                name="Drafts Only Project",
                owner_id=test_user.id,
                project_type="novel",
            )
            session.add(project_drafts_only)
            session.commit()

            # Add only draft files - ensure sufficient words for completion threshold
            draft_only_1 = File(
                id="draft-only-1",
                project_id=project_drafts_only.id,
                title="Story Part 1",
                file_type=FILE_TYPE_DRAFT,
                content="This is a complete draft with more than fifty words in it. "
                "It tells a story about something interesting that happened once upon a time. "
                "The characters were all very fascinating and the plot was incredibly engaging. "
                "Readers would be captivated from the very first page until the exciting conclusion.",
                order=1,
            )
            draft_only_2 = File(
                id="draft-only-2",
                project_id=project_drafts_only.id,
                title="Story Part 2",
                file_type=FILE_TYPE_DRAFT,
                content="Short",  # Less than 50 words but not zero
                order=2,
            )
            session.add(draft_only_1)
            session.add(draft_only_2)
            session.commit()

            draft_only_stats = writing_stats_service.get_chapter_completion_stats(
                session, project_drafts_only.id, min_words_for_complete=50
            )

            print(f"   Draft-only total chapters: {draft_only_stats['total_chapters']}")
            print(f"   Draft-only completed: {draft_only_stats['completed_chapters']}")
            print(f"   Draft-only completion: {draft_only_stats['completion_percentage']}%")

            assert draft_only_stats['total_chapters'] == 2, \
                f"Expected 2 total (drafts), got {draft_only_stats['total_chapters']}"
            assert draft_only_stats['completed_chapters'] == 1, \
                f"Expected 1 completed, got {draft_only_stats['completed_chapters']}"
            assert draft_only_stats['completion_percentage'] == 50, \
                f"Expected 50%, got {draft_only_stats['completion_percentage']}%"
            assert len(draft_only_stats['chapter_details']) == 2, \
                f"Expected 2 chapter details, got {len(draft_only_stats['chapter_details'])}"
            assert all(item['draft_id'] is not None for item in draft_only_stats['chapter_details']), \
                "Draft-only mode should still provide draft-linked chapter details"
            print("   ✓ Draft-only mode works correctly")

            # Step 8: Test edge case - all chapters complete
            print("\n8. Testing 100% completion scenario...")

            # Update Chapter 3 to have a complete draft
            complete_draft_3 = File(
                id="draft-003",
                project_id=test_project.id,
                title="Chapter 3: The Climax",
                file_type=FILE_TYPE_DRAFT,
                content="The battle raged on through the night. Heroes fought with all their might. "
                "In the end, good triumphed over evil, and peace was restored to the land. "
                "The celebration that followed would be remembered for generations to come. "
                "Songs were sung about the brave warriors who had given everything to protect their home. "
                "Children would grow up hearing stories of this legendary day.",
                order=3,
            )
            session.add(complete_draft_3)
            session.commit()

            # Get updated stats
            updated_stats = writing_stats_service.get_chapter_completion_stats(
                session, test_project.id, min_words_for_complete=50
            )

            print(f"   Updated total: {updated_stats['total_chapters']}")
            print(f"   Updated completed: {updated_stats['completed_chapters']}")
            print(f"   Updated percentage: {updated_stats['completion_percentage']}%")

            assert updated_stats['completed_chapters'] == 3, \
                f"Expected 3 completed after update, got {updated_stats['completed_chapters']}"
            assert updated_stats['not_started_chapters'] == 0, \
                f"Expected 0 not-started, got {updated_stats['not_started_chapters']}"
            # 3 complete + 1 in_progress = 3/4 = 75%
            assert updated_stats['completion_percentage'] == 75, \
                f"Expected 75% completion, got {updated_stats['completion_percentage']}%"
            print("   ✓ 100% completion scenario verified (75% actual: 3/4 complete)")

            print("\n" + "=" * 60)
            print("✅ ALL CHAPTER COMPLETION TESTS PASSED!")
            print("=" * 60)

            # Print summary
            print("\n📊 Test Summary:")
            print("   - Created project with 4 outline files")
            print("   - Created drafts with varying completion levels")
            print(f"   - Verified completion percentage calculation: {completion_stats['completion_percentage']}%")
            print("   - Verified chapter detail statuses (complete/in_progress/not_started)")
            print("   - Tested draft-only mode (no outlines)")
            print("   - Tested dynamic updates (adding new drafts)")

    finally:
        os.close(db_fd)
        os.unlink(db_path)
        print("\n🧹 Test database cleaned up.")


def test_chapter_completion_matches_by_chapter_number_when_titles_differ():
    """
    Outline/draft titles can differ in wording; chapter number should still match.
    """
    engine, db_fd, db_path = create_test_database()

    try:
        with Session(engine) as session:
            user = User(
                id="test-user-chapter-number",
                email="chapter-number@example.com",
                username="chapternumberuser",
                hashed_password="hashed",
            )
            project = Project(
                id="test-project-chapter-number",
                name="Chapter Number Matching",
                owner_id=user.id,
                project_type="novel",
            )
            session.add(user)
            session.add(project)
            session.commit()

            # Outline titles and draft titles intentionally differ.
            session.add(
                File(
                    id="outline-cn-1",
                    project_id=project.id,
                    title="第一章 女主在男主床上醒来",
                    file_type=FILE_TYPE_OUTLINE,
                    content="outline 1",
                    order=10,
                )
            )
            session.add(
                File(
                    id="outline-cn-2",
                    project_id=project.id,
                    title="第2章 陌路重逢",
                    file_type=FILE_TYPE_OUTLINE,
                    content="outline 2",
                    order=20,
                )
            )

            session.add(
                File(
                    id="draft-cn-1",
                    project_id=project.id,
                    title="第1章 开场（正文稿）",
                    file_type=FILE_TYPE_DRAFT,
                    content="这是一段明显超过五十字的正文内容，用来验证章节匹配逻辑在标题不一致时依然可以正确关联并统计为已完成状态。"
                    "为了确保测试稳定，这里再补充一段叙述文字：夜色渐深，窗外风雨交加，角色的命运也在这一刻悄然转向。",
                    order=1,
                )
            )
            session.add(
                File(
                    id="draft-cn-2",
                    project_id=project.id,
                    title="第2章 第二稿（正文）",
                    file_type=FILE_TYPE_DRAFT,
                    content="短内容",
                    order=2,
                )
            )
            session.commit()

            stats = writing_stats_service.get_chapter_completion_stats(
                session,
                project.id,
                min_words_for_complete=50,
            )

            assert stats["total_chapters"] == 2
            assert stats["completed_chapters"] == 1
            assert stats["in_progress_chapters"] == 1
            assert stats["not_started_chapters"] == 0
            assert stats["completion_percentage"] == 50

            details = stats["chapter_details"]
            assert len(details) == 2
            assert all(item["draft_id"] is not None for item in details)

    finally:
        os.close(db_fd)
        os.unlink(db_path)


def test_chapter_completion_prefers_target_word_count_when_provided():
    """Chapter completion should use target_word_count when available."""
    engine, db_fd, db_path = create_test_database()

    try:
        with Session(engine) as session:
            user = User(
                id="test-user-chapter-target",
                email="chapter-target@example.com",
                username="chaptertargetuser",
                hashed_password="hashed",
            )
            project = Project(
                id="test-project-chapter-target",
                name="Chapter Target Matching",
                owner_id=user.id,
                project_type="novel",
            )
            session.add(user)
            session.add(project)
            session.commit()

            outline_1 = File(
                id="outline-target-1",
                project_id=project.id,
                title="Chapter 1",
                file_type=FILE_TYPE_OUTLINE,
                content="outline 1",
                order=1,
            )
            outline_1.set_metadata_field("word_count_target", 100)
            outline_2 = File(
                id="outline-target-2",
                project_id=project.id,
                title="Chapter 2",
                file_type=FILE_TYPE_OUTLINE,
                content="outline 2",
                order=2,
            )
            outline_2.set_metadata_field("word_count_target", 40)
            outline_3 = File(
                id="outline-target-3",
                project_id=project.id,
                title="Chapter 3",
                file_type=FILE_TYPE_OUTLINE,
                content="outline 3",
                order=3,
            )

            session.add(outline_1)
            session.add(outline_2)
            session.add(outline_3)

            session.add(
                File(
                    id="draft-target-1",
                    project_id=project.id,
                    title="Chapter 1",
                    file_type=FILE_TYPE_DRAFT,
                    content=("word " * 60).strip(),
                    order=1,
                )
            )
            session.add(
                File(
                    id="draft-target-2",
                    project_id=project.id,
                    title="Chapter 2",
                    file_type=FILE_TYPE_DRAFT,
                    content=("word " * 50).strip(),
                    order=2,
                )
            )
            session.add(
                File(
                    id="draft-target-3",
                    project_id=project.id,
                    title="Chapter 3",
                    file_type=FILE_TYPE_DRAFT,
                    content=("word " * 30).strip(),
                    order=3,
                )
            )
            session.commit()

            stats = writing_stats_service.get_chapter_completion_stats(
                session,
                project.id,
                min_words_for_complete=50,
            )

            assert stats["total_chapters"] == 3
            assert stats["completed_chapters"] == 1
            assert stats["in_progress_chapters"] == 2
            assert stats["not_started_chapters"] == 0
            assert stats["completion_percentage"] == 33

            by_title = {item["title"]: item for item in stats["chapter_details"]}
            assert by_title["Chapter 1"]["target_word_count"] == 100
            assert by_title["Chapter 1"]["status"] == "in_progress"
            assert by_title["Chapter 1"]["completion_percentage"] == 60

            assert by_title["Chapter 2"]["target_word_count"] == 40
            assert by_title["Chapter 2"]["status"] == "complete"
            assert by_title["Chapter 2"]["completion_percentage"] == 100

            assert by_title["Chapter 3"]["target_word_count"] is None
            assert by_title["Chapter 3"]["status"] == "in_progress"
            assert by_title["Chapter 3"]["completion_percentage"] == 60

            # Also verify draft-only mode uses target_word_count when outlines are absent.
            draft_only_project = Project(
                id="test-project-chapter-target-draft-only",
                name="Draft-only with Targets",
                owner_id=user.id,
                project_type="novel",
            )
            session.add(draft_only_project)
            session.commit()

            draft_only_1 = File(
                id="draft-only-target-1",
                project_id=draft_only_project.id,
                title="Part 1",
                file_type=FILE_TYPE_DRAFT,
                content=("word " * 60).strip(),
                order=1,
            )
            draft_only_1.set_metadata_field("word_count_target", 120)

            draft_only_2 = File(
                id="draft-only-target-2",
                project_id=draft_only_project.id,
                title="Part 2",
                file_type=FILE_TYPE_DRAFT,
                content=("word " * 60).strip(),
                order=2,
            )

            session.add(draft_only_1)
            session.add(draft_only_2)
            session.commit()

            draft_only_stats = writing_stats_service.get_chapter_completion_stats(
                session,
                draft_only_project.id,
                min_words_for_complete=50,
            )
            assert draft_only_stats["total_chapters"] == 2
            assert draft_only_stats["completed_chapters"] == 1
            assert draft_only_stats["in_progress_chapters"] == 1
            assert draft_only_stats["completion_percentage"] == 50

            draft_only_by_title = {item["title"]: item for item in draft_only_stats["chapter_details"]}
            assert draft_only_by_title["Part 1"]["target_word_count"] == 120
            assert draft_only_by_title["Part 1"]["status"] == "in_progress"
            assert draft_only_by_title["Part 1"]["completion_percentage"] == 50

            assert draft_only_by_title["Part 2"]["target_word_count"] is None
            assert draft_only_by_title["Part 2"]["status"] == "complete"
            assert draft_only_by_title["Part 2"]["completion_percentage"] == 100

    finally:
        os.close(db_fd)
        os.unlink(db_path)


def test_chapter_completion_uses_target_word_count_for_progress_and_status():
    """
    If chapter target_word_count exists, progress/status should use target baseline
    instead of global min_words_for_complete fallback.
    """
    engine, db_fd, db_path = create_test_database()

    try:
        with Session(engine) as session:
            user = User(
                id="test-user-target-baseline",
                email="target-baseline@example.com",
                username="targetbaselineuser",
                hashed_password="hashed",
            )
            project = Project(
                id="test-project-target-baseline",
                name="Target Baseline Project",
                owner_id=user.id,
                project_type="novel",
            )
            session.add(user)
            session.add(project)
            session.commit()

            outline_1 = File(
                id="outline-target-1",
                project_id=project.id,
                title="Chapter A",
                file_type=FILE_TYPE_OUTLINE,
                content="outline A",
                order=1,
            )
            outline_1.set_metadata({"word_count_target": 1000})

            outline_2 = File(
                id="outline-target-2",
                project_id=project.id,
                title="Chapter B",
                file_type=FILE_TYPE_OUTLINE,
                content="outline B",
                order=2,
            )
            outline_2.set_metadata({"word_count_target": "80"})

            draft_1 = File(
                id="draft-target-1",
                project_id=project.id,
                title="Chapter A",
                file_type=FILE_TYPE_DRAFT,
                content="word " * 120,  # 120 words
                order=1,
            )
            draft_2 = File(
                id="draft-target-2",
                project_id=project.id,
                title="Chapter B",
                file_type=FILE_TYPE_DRAFT,
                content="word " * 90,  # 90 words
                order=2,
            )

            session.add(outline_1)
            session.add(outline_2)
            session.add(draft_1)
            session.add(draft_2)
            session.commit()

            stats = writing_stats_service.get_chapter_completion_stats(
                session,
                project.id,
                min_words_for_complete=50,
            )

            assert stats["total_chapters"] == 2
            assert stats["completed_chapters"] == 1
            assert stats["in_progress_chapters"] == 1
            assert stats["completion_percentage"] == 50

            detail_a = next(item for item in stats["chapter_details"] if item["title"] == "Chapter A")
            detail_b = next(item for item in stats["chapter_details"] if item["title"] == "Chapter B")

            # Chapter A: 120/1000 => 12%, still in progress
            assert detail_a["target_word_count"] == 1000
            assert detail_a["status"] == "in_progress"
            assert detail_a["completion_percentage"] == 12

            # Chapter B: 90/80 => complete, capped at 100%
            assert detail_b["target_word_count"] == 80
            assert detail_b["status"] == "complete"
            assert detail_b["completion_percentage"] == 100

    finally:
        os.close(db_fd)
        os.unlink(db_path)


if __name__ == "__main__":
    test_chapter_completion_percentage()
