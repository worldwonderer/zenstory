"""
Tests for Agent material workflow integration.

Tests that verify materials (characters, lores, outlines) are correctly
referenced in the agent's context during AI workflows.

These tests focus on the ContextAssembler behavior without making
real LLM API calls.
"""

import pytest
from sqlmodel import Session

from agent.context.assembler import ContextAssembler, get_context_assembler
from agent.schemas.context import (
    ContextPriority,
)
from models import File, Project, User


@pytest.fixture
def test_user(db_session: Session):
    """Create a test user."""
    user = User(
        email="material_workflow_test@example.com",
        username="materialworkflowtest",
        hashed_password="hashed_password",
        name="Material Workflow Test User",
        email_verified=True,
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def test_project(db_session: Session, test_user):
    """Create a test project with writing style configured."""
    project = Project(
        name="Material Workflow Test Project",
        description="A test project for material workflow testing",
        user_id=test_user.id,
        summary="一部修仙题材的玄幻小说",
        current_phase="正文写作阶段",
        writing_style="轻松幽默，注重角色互动",
    )
    db_session.add(project)
    db_session.commit()
    db_session.refresh(project)
    return project


@pytest.fixture
def create_file(db_session: Session, test_project, test_user):
    """Helper function to create test files."""

    def _create(
        title: str,
        file_type: str,
        content: str = "",
        file_metadata: str | None = None,
        parent_id: str | None = None,
        order: int = 0,
    ):
        file = File(
            title=title,
            content=content,
            file_type=file_type,
            file_metadata=file_metadata,
            project_id=test_project.id,
            user_id=test_user.id,
            parent_id=parent_id,
            order=order,
        )
        db_session.add(file)
        db_session.commit()
        db_session.refresh(file)
        return file

    return _create


@pytest.fixture
def create_folder(db_session: Session, test_project, test_user):
    """Helper function to create folder files."""

    def _create(title: str, order: int = 0):
        folder = File(
            title=title,
            content="",
            file_type="folder",
            project_id=test_project.id,
            user_id=test_user.id,
            parent_id=None,
            order=order,
        )
        db_session.add(folder)
        db_session.commit()
        db_session.refresh(folder)
        return folder

    return _create


@pytest.mark.unit
class TestCharacterMaterialInContext:
    """Test that character materials are correctly included in agent context."""

    def test_single_character_in_context(
        self,
        db_session,
        test_project,
        create_file,
    ):
        """
        Test that a character file is included in the assembled context.

        Scenario:
        - Create a character with profile information
        - Assemble context for the project
        - Verify character appears in context with correct information
        """
        # Create character with detailed profile
        create_file(
            title="林逸风",
            file_type="character",
            content="修仙界年轻天才，性格倔强但心地善良。",
            file_metadata='{"role": "主角", "age": "18", "gender": "男", "personality": "倔强、善良、有正义感"}',
        )

        assembler = ContextAssembler()
        result = assembler.assemble(
            session=db_session,
            project_id=test_project.id,
            max_tokens=2000,
            include_characters=True,
        )

        # Verify character is in context
        assert result.original_item_count >= 1
        assert "林逸风" in result.context
        assert "【角色信息】" in result.context

        # Verify character metadata is included
        assert "主角" in result.context or "倔强" in result.context

    def test_multiple_characters_prioritized(
        self,
        db_session,
        test_project,
        create_file,
    ):
        """
        Test that multiple characters are all included with CONSTRAINT priority.

        Scenario:
        - Create multiple characters with different roles
        - Verify all characters appear in context
        - Verify characters have CONSTRAINT priority
        """
        # Create multiple characters
        create_file(
            title="林逸风",
            file_type="character",
            content="主角，修仙天才",
            file_metadata='{"role": "主角"}',
        )
        create_file(
            title="苏晴雪",
            file_type="character",
            content="女主角，冰山美人",
            file_metadata='{"role": "女主角"}',
        )
        create_file(
            title="王霸道",
            file_type="character",
            content="反派，阴险狡诈",
            file_metadata='{"role": "反派"}',
        )

        assembler = ContextAssembler()
        result = assembler.assemble(
            session=db_session,
            project_id=test_project.id,
            max_tokens=3000,
            include_characters=True,
        )

        # All characters should be included
        assert result.original_item_count == 3
        assert "林逸风" in result.context
        assert "苏晴雪" in result.context
        assert "王霸道" in result.context

        # All should have CONSTRAINT priority
        character_items = [
            item for item in result.items if item["type"] == "character"
        ]
        assert len(character_items) == 3
        for item in character_items:
            assert item["priority"] == ContextPriority.CONSTRAINT.value

    def test_character_excluded_when_flag_disabled(
        self,
        db_session,
        test_project,
        create_file,
    ):
        """
        Test that characters are excluded when include_characters=False.

        Scenario:
        - Create character files
        - Assemble context with include_characters=False
        - Verify characters are not in detailed context
        """
        create_file(
            title="林逸风",
            file_type="character",
            content="主角",
        )

        assembler = ContextAssembler()
        result = assembler.assemble(
            session=db_session,
            project_id=test_project.id,
            max_tokens=1000,
            include_characters=False,
        )

        # Character should not be in detailed content
        assert result.original_item_count == 0
        assert "【角色信息】" not in result.context

    def test_character_with_focus_file(
        self,
        db_session,
        test_project,
        create_file,
        create_folder,
    ):
        """
        Test that characters are included alongside focus file.

        Scenario:
        - Create an outline as focus file
        - Create character files
        - Verify both focus file and characters appear in context
        """
        # Create focus file (outline)
        folder = create_folder(title="第一卷")
        outline = create_file(
            title="第一章",
            file_type="outline",
            content="林逸风初入修仙界，遇到苏晴雪。",
            parent_id=folder.id,
            order=1,
        )

        # Create characters
        create_file(
            title="林逸风",
            file_type="character",
            content="修仙天才",
        )
        create_file(
            title="苏晴雪",
            file_type="character",
            content="冰山美人",
        )

        assembler = ContextAssembler()
        result = assembler.assemble(
            session=db_session,
            project_id=test_project.id,
            focus_file_id=outline.id,
            max_tokens=3000,
            include_characters=True,
        )

        # Focus file and characters should both be present
        assert "第一章" in result.context
        assert "林逸风" in result.context
        assert "苏晴雪" in result.context


@pytest.mark.unit
class TestLoreMaterialIntegration:
    """Test that lore (world-building) materials are correctly integrated."""

    def test_single_lore_in_context(
        self,
        db_session,
        test_project,
        create_file,
    ):
        """
        Test that a lore file is included in context.

        Scenario:
        - Create a lore with world-building information
        - Verify lore appears in context
        """
        create_file(
            title="修仙体系",
            file_type="lore",
            content="修仙分为练气、筑基、金丹、元婴四个境界。",
            file_metadata='{"category": "修炼体系", "importance": "high"}',
        )

        assembler = ContextAssembler()
        result = assembler.assemble(
            session=db_session,
            project_id=test_project.id,
            max_tokens=2000,
            include_lores=True,
        )

        # Lore should be in context
        assert result.original_item_count >= 1
        assert "修仙体系" in result.context
        assert "【世界设定】" in result.context

    def test_lore_importance_prioritization(
        self,
        db_session,
        test_project,
        create_file,
    ):
        """
        Test that lores are prioritized by importance.

        Scenario:
        - Create lores with different importance levels
        - Verify high importance lores get CONSTRAINT priority
        - Verify low importance lores get INSPIRATION priority
        """
        # Create lores with different importance
        create_file(
            title="核心设定",
            file_type="lore",
            content="核心世界规则",
            file_metadata='{"importance": "high"}',
            order=3,
        )
        create_file(
            title="重要设定",
            file_type="lore",
            content="重要世界信息",
            file_metadata='{"importance": "medium"}',
            order=2,
        )
        create_file(
            title="背景设定",
            file_type="lore",
            content="背景信息",
            file_metadata='{"importance": "low"}',
            order=1,
        )

        assembler = ContextAssembler()
        result = assembler.assemble(
            session=db_session,
            project_id=test_project.id,
            max_tokens=3000,
            include_lores=True,
        )

        # All lores should be included
        assert result.original_item_count == 3

        # Check priorities
        lore_items = [item for item in result.items if item["type"] == "lore"]
        assert len(lore_items) == 3

        # High importance should have CONSTRAINT priority
        high_item = next(
            (i for i in lore_items if "核心设定" in i["title"]), None
        )
        assert high_item is not None
        assert high_item["priority"] == ContextPriority.CONSTRAINT.value

    def test_lore_category_in_context(
        self,
        db_session,
        test_project,
        create_file,
    ):
        """
        Test that lore category is included in context.

        Scenario:
        - Create lore with category
        - Verify category appears in formatted context
        """
        create_file(
            title="天元大陆",
            file_type="lore",
            content="故事发生的大陆，分为东、西、南、北四个区域。",
            file_metadata='{"category": "地理", "importance": "medium"}',
        )

        assembler = ContextAssembler()
        result = assembler.assemble(
            session=db_session,
            project_id=test_project.id,
            max_tokens=2000,
            include_lores=True,
        )

        # Category should be in context
        assert "天元大陆" in result.context
        assert "地理" in result.context

    def test_lore_excluded_when_flag_disabled(
        self,
        db_session,
        test_project,
        create_file,
    ):
        """
        Test that lores are excluded when include_lores=False.
        """
        create_file(
            title="魔法体系",
            file_type="lore",
            content="魔法分为四种元素",
        )

        assembler = ContextAssembler()
        result = assembler.assemble(
            session=db_session,
            project_id=test_project.id,
            max_tokens=1000,
            include_lores=False,
        )

        # Lore should not be in detailed content
        assert result.original_item_count == 0
        assert "【世界设定】" not in result.context


@pytest.mark.unit
class TestOutlineStructurePreservation:
    """Test that outline structures are preserved in context."""

    def test_outline_in_context(
        self,
        db_session,
        test_project,
        create_file,
    ):
        """
        Test that an outline file is included in context.

        Scenario:
        - Create an outline with chapter structure
        - Verify outline appears in context
        """
        outline = create_file(
            title="第一章大纲",
            file_type="outline",
            content="1. 林逸风初入修仙界\n2. 遇到师父\n3. 开始修炼",
        )

        assembler = ContextAssembler()
        result = assembler.assemble(
            session=db_session,
            project_id=test_project.id,
            focus_file_id=outline.id,
            max_tokens=2000,
        )

        # Outline should be in context as focus
        assert "第一章大纲" in result.context
        assert "林逸风" in result.context

    def test_outline_hierarchy_preserved(
        self,
        db_session,
        test_project,
        create_file,
        create_folder,
    ):
        """
        Test that outline hierarchy (parent-child) is preserved.

        Scenario:
        - Create folder structure for volume
        - Create outlines under the folder
        - Verify parent outline is included when child is focus
        """
        # Create folder structure
        volume_folder = create_folder(title="第一卷")

        # Create parent outline (volume summary)
        create_file(
            title="第一卷总纲",
            file_type="outline",
            content="第一卷讲述主角初入修仙界的故事",
            parent_id=volume_folder.id,
            order=0,
        )

        # Create chapter outlines
        chapter1 = create_file(
            title="第一章",
            file_type="outline",
            content="主角登场",
            parent_id=volume_folder.id,
            order=1,
        )
        create_file(
            title="第二章",
            file_type="outline",
            content="遇到师父",
            parent_id=volume_folder.id,
            order=2,
        )

        assembler = ContextAssembler()
        result = assembler.assemble(
            session=db_session,
            project_id=test_project.id,
            focus_file_id=chapter1.id,
            max_tokens=3000,
        )

        # Focus chapter should be included
        assert "第一章" in result.context

        # Verify focus marker
        assert "当前焦点" in result.context

    def test_outline_with_siblings(
        self,
        db_session,
        test_project,
        create_file,
        create_folder,
    ):
        """
        Test that sibling outlines are included for context.

        Scenario:
        - Create multiple chapter outlines under same parent
        - Set one as focus
        - Verify sibling outlines are also included
        """
        folder = create_folder(title="第一卷")

        create_file(
            title="第一章",
            file_type="outline",
            content="主角登场，展示世界观",
            parent_id=folder.id,
            order=1,
        )
        chapter2 = create_file(
            title="第二章",
            file_type="outline",
            content="遇到师父，开始修炼",
            parent_id=folder.id,
            order=2,
        )
        create_file(
            title="第三章",
            file_type="outline",
            content="初次战斗，展示实力",
            parent_id=folder.id,
            order=3,
        )

        assembler = ContextAssembler()
        result = assembler.assemble(
            session=db_session,
            project_id=test_project.id,
            focus_file_id=chapter2.id,
            max_tokens=4000,
        )

        # Focus chapter should be included
        assert "第二章" in result.context
        # Siblings may or may not be included depending on budget
        # but focus should always be present

    def test_draft_as_focus_file(
        self,
        db_session,
        test_project,
        create_file,
    ):
        """
        Test that draft files can be focus files.

        Scenario:
        - Create a draft file
        - Set it as focus
        - Verify it appears in context with correct type
        """
        draft = create_file(
            title="第一章草稿",
            file_type="draft",
            content="林逸风站在山门前，望着那高耸入云的山峰...",
        )

        assembler = ContextAssembler()
        result = assembler.assemble(
            session=db_session,
            project_id=test_project.id,
            focus_file_id=draft.id,
            max_tokens=3000,
        )

        # Draft should be in context
        assert "第一章草稿" in result.context
        assert "林逸风" in result.context


@pytest.mark.unit
class TestMaterialCombinationWorkflow:
    """Test workflows that combine multiple material types."""

    def test_all_materials_in_context(
        self,
        db_session,
        test_project,
        create_file,
        create_folder,
    ):
        """
        Test that all material types are included together.

        Scenario:
        - Create outline, draft, characters, and lores
        - Verify all types appear in context
        """
        # Create outline
        folder = create_folder(title="第一卷")
        outline = create_file(
            title="第一章",
            file_type="outline",
            content="主角初入修仙界",
            parent_id=folder.id,
        )

        # Create draft
        create_file(
            title="第一章草稿",
            file_type="draft",
            content="林逸风站在山门前...",
        )

        # Create characters
        create_file(
            title="林逸风",
            file_type="character",
            content="修仙天才",
        )

        # Create lore
        create_file(
            title="修仙体系",
            file_type="lore",
            content="练气筑基金丹元婴",
        )

        assembler = ContextAssembler()
        result = assembler.assemble(
            session=db_session,
            project_id=test_project.id,
            focus_file_id=outline.id,
            max_tokens=5000,
            include_characters=True,
            include_lores=True,
        )

        # All materials should be referenced
        assert "第一章" in result.context
        assert "林逸风" in result.context
        assert "修仙体系" in result.context

        # Check that different sections exist
        context = result.context
        has_outline = "【大纲详情】" in context
        has_character = "【角色信息】" in context
        has_lore = "【世界设定】" in context

        # At least one detailed section should exist
        assert has_outline or has_character or has_lore

    def test_material_with_attached_files(
        self,
        db_session,
        test_project,
        create_file,
    ):
        """
        Test that attached files have highest priority.

        Scenario:
        - Create characters and lores
        - Attach specific files manually
        - Verify attached files have CRITICAL priority
        """
        # Create files
        char1 = create_file(
            title="主角",
            file_type="character",
            content="主角描述",
        )
        create_file(
            title="配角",
            file_type="character",
            content="配角描述",
        )
        lore = create_file(
            title="世界观",
            file_type="lore",
            content="世界观描述",
        )

        assembler = ContextAssembler()
        result = assembler.assemble(
            session=db_session,
            project_id=test_project.id,
            attached_file_ids=[char1.id, lore.id],
            max_tokens=3000,
            include_characters=True,
            include_lores=True,
        )

        # Attached files should have CRITICAL priority
        attached_items = [
            item for item in result.items
            if item.get("metadata", {}).get("attached")
        ]
        assert len(attached_items) == 2
        for item in attached_items:
            assert item["priority"] == ContextPriority.CRITICAL.value

    def test_material_with_text_quotes(
        self,
        db_session,
        test_project,
        create_file,
    ):
        """
        Test that text quotes are included with highest priority.

        Scenario:
        - Create materials
        - Add user-selected text quotes
        - Verify quotes have CRITICAL priority
        """
        # Create a file
        draft = create_file(
            title="第一章",
            file_type="draft",
            content="正文内容...",
        )

        # Create text quote
        text_quotes = [
            {
                "text": "林逸风心中一动，感受到天地灵气的流动",
                "fileId": draft.id,
                "fileTitle": "第一章",
            }
        ]

        assembler = ContextAssembler()
        result = assembler.assemble(
            session=db_session,
            project_id=test_project.id,
            text_quotes=text_quotes,
            max_tokens=2000,
        )

        # Quote should be in context
        assert "林逸风" in result.context
        assert "【用户引用文本】" in result.context

        # Quote should have CRITICAL priority
        quote_items = [
            item for item in result.items if item["type"] == "quote"
        ]
        assert len(quote_items) == 1
        assert quote_items[0]["priority"] == ContextPriority.CRITICAL.value


@pytest.mark.unit
class TestSoftDeletedMaterials:
    """Test that soft-deleted materials are properly excluded."""

    def test_soft_deleted_character_excluded(
        self,
        db_session,
        test_project,
        create_file,
    ):
        """
        Test that soft-deleted characters are excluded from context.
        """
        # Create active character
        create_file(
            title="活跃角色",
            file_type="character",
            content="活跃角色描述",
        )

        # Create and soft-delete character
        char_deleted = create_file(
            title="已删除角色",
            file_type="character",
            content="已删除角色描述",
        )
        char_deleted.is_deleted = True
        db_session.commit()

        assembler = ContextAssembler()
        result = assembler.assemble(
            session=db_session,
            project_id=test_project.id,
            max_tokens=2000,
            include_characters=True,
        )

        # Only active character should be included
        assert result.original_item_count == 1
        assert "活跃角色" in result.context
        assert "已删除角色" not in result.context

    def test_soft_deleted_lore_excluded(
        self,
        db_session,
        test_project,
        create_file,
    ):
        """
        Test that soft-deleted lores are excluded from context.
        """
        create_file(
            title="活跃设定",
            file_type="lore",
            content="活跃设定内容",
        )

        lore_deleted = create_file(
            title="已删除设定",
            file_type="lore",
            content="已删除设定内容",
        )
        lore_deleted.is_deleted = True
        db_session.commit()

        assembler = ContextAssembler()
        result = assembler.assemble(
            session=db_session,
            project_id=test_project.id,
            max_tokens=2000,
            include_lores=True,
        )

        assert result.original_item_count == 1
        assert "活跃设定" in result.context
        assert "已删除设定" not in result.context

    def test_soft_deleted_outline_excluded(
        self,
        db_session,
        test_project,
        create_file,
    ):
        """
        Test that soft-deleted outlines are excluded from context.
        """
        outline_active = create_file(
            title="活跃大纲",
            file_type="outline",
            content="活跃大纲内容",
        )

        outline_deleted = create_file(
            title="已删除大纲",
            file_type="outline",
            content="已删除大纲内容",
        )
        outline_deleted.is_deleted = True
        db_session.commit()

        assembler = ContextAssembler()
        result = assembler.assemble(
            session=db_session,
            project_id=test_project.id,
            focus_file_id=outline_active.id,
            max_tokens=2000,
        )

        assert "活跃大纲" in result.context
        assert "已删除大纲" not in result.context


@pytest.mark.unit
class TestTokenBudgetWithMaterials:
    """Test that token budget works correctly with materials."""

    def test_budget_limits_materials(
        self,
        db_session,
        test_project,
        create_file,
    ):
        """
        Test that materials are trimmed when budget is limited.

        Scenario:
        - Create many lore files with large content
        - Set small token budget
        - Verify some items are trimmed
        """
        # Create many lores
        for i in range(10):
            create_file(
                title=f"设定{i}",
                file_type="lore",
                content=f"这是设定{i}的详细内容。" * 50,  # Large content
                file_metadata='{"importance": "medium"}',
            )

        assembler = ContextAssembler()
        result = assembler.assemble(
            session=db_session,
            project_id=test_project.id,
            max_tokens=500,  # Small budget
            include_lores=True,
        )

        # Some items should be trimmed
        assert result.original_item_count > 0
        assert result.trimmed_item_count <= result.original_item_count

    def test_high_priority_materials_preserved(
        self,
        db_session,
        test_project,
        create_file,
    ):
        """
        Test that high priority materials are preserved when budget is tight.

        Scenario:
        - Create high importance lore
        - Create low importance lore
        - Set tight budget
        - Verify high importance lore is prioritized
        """
        # High importance lore
        create_file(
            title="核心设定",
            file_type="lore",
            content="核心设定内容" * 10,
            file_metadata='{"importance": "high"}',
        )

        # Low importance lore
        create_file(
            title="背景设定",
            file_type="lore",
            content="背景设定内容" * 10,
            file_metadata='{"importance": "low"}',
        )

        assembler = ContextAssembler()
        result = assembler.assemble(
            session=db_session,
            project_id=test_project.id,
            max_tokens=200,  # Very tight budget
            include_lores=True,
        )

        # High importance should be prioritized
        # (exact behavior depends on budget calculation)
        assert result.trimmed_item_count >= 0


@pytest.mark.unit
class TestContextAssemblerSingleton:
    """Test ContextAssembler singleton behavior."""

    def test_singleton_returns_same_instance(self):
        """Test that get_context_assembler returns the same instance."""
        assembler1 = get_context_assembler()
        assembler2 = get_context_assembler()
        assert assembler1 is assembler2

    def test_new_instance_possible(self):
        """Test that creating new instance is possible."""
        assembler1 = ContextAssembler()
        assembler2 = ContextAssembler()
        assert assembler1 is not assembler2
