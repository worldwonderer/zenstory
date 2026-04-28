"""
Tests for skill loader module.

Tests SKILL.md parsing for OpenViking and zenstory formats.
"""

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
import tempfile
import os

from agent.skills.loader import (
    parse_skill_md,
    parse_openviking_format,
    parse_zenstory_format,
    load_skills_from_dir,
    load_builtin_skills,
    load_project_skills,
    load_user_skills,
    get_all_skills,
    get_builtin_skills,
    reload_builtin_skills,
    to_skill_md,
    FRONTMATTER_PATTERN,
)
from agent.skills.schemas import Skill, SkillSource


@pytest.mark.unit
class TestFrontmatterPattern:
    """Test YAML frontmatter regex pattern."""

    def test_matches_basic_frontmatter(self):
        """Test matching basic frontmatter."""
        content = """---
name: Test Skill
description: A test skill
---
# Instructions
Do something."""
        match = FRONTMATTER_PATTERN.match(content)
        assert match is not None
        frontmatter, body = match.groups()
        assert "name: Test Skill" in frontmatter
        assert "# Instructions" in body

    def test_no_match_without_delimiters(self):
        """Test no match without proper delimiters."""
        content = "# Test Skill\n\nNo frontmatter here."
        match = FRONTMATTER_PATTERN.match(content)
        assert match is None

    def test_matches_multiline_frontmatter(self):
        """Test matching multiline frontmatter."""
        content = """---
name: Test
description: |
  Multi-line
  description
tags:
  - tag1
  - tag2
---
Body content."""
        match = FRONTMATTER_PATTERN.match(content)
        assert match is not None


@pytest.mark.unit
class TestParseOpenVikingFormat:
    """Test OpenViking format parsing."""

    def test_parse_basic(self):
        """Test parsing basic OpenViking format."""
        content = """---
name: Chapter Writer
description: Writes chapters
---
# Instructions
Write chapters following the outline."""
        skill = parse_openviking_format(content, "chapter-writer.md")

        assert skill is not None
        assert skill.name == "Chapter Writer"
        assert skill.description == "Writes chapters"
        assert "Write chapters" in skill.instructions

    def test_parse_with_triggers(self):
        """Test parsing with triggers."""
        content = """---
name: Test
description: Test skill
triggers:
  - write
  - chapter
---
Instructions here."""
        skill = parse_openviking_format(content, "test.md")

        assert skill is not None
        assert "write" in skill.triggers
        assert "chapter" in skill.triggers

    def test_parse_with_allowed_tools(self):
        """Test parsing with allowed-tools."""
        content = """---
name: Test
description: Test
allowed-tools:
  - create_file
  - edit_file
---
Instructions."""
        skill = parse_openviking_format(content, "test.md")

        assert skill is not None
        assert skill.allowed_tools is not None
        assert "create_file" in skill.allowed_tools
        assert "edit_file" in skill.allowed_tools

    def test_parse_with_tags(self):
        """Test parsing with tags."""
        content = """---
name: Test
description: Test
tags:
  - writing
  - creative
---
Instructions."""
        skill = parse_openviking_format(content, "test.md")

        assert skill is not None
        assert "writing" in skill.tags
        assert "creative" in skill.tags

    def test_parse_missing_name(self):
        """Test parsing with missing name returns None."""
        content = """---
description: No name here
---
Instructions."""
        skill = parse_openviking_format(content, "test.md")
        assert skill is None

    def test_parse_missing_description(self):
        """Test parsing with missing description returns None."""
        content = """---
name: Test Name
---
Instructions."""
        skill = parse_openviking_format(content, "test.md")
        assert skill is None

    def test_parse_invalid_yaml(self):
        """Test parsing invalid YAML returns None."""
        content = """---
name: [invalid yaml
description: Test
---
Instructions."""
        skill = parse_openviking_format(content, "test.md")
        assert skill is None

    def test_skill_id_from_filename(self):
        """Test skill ID is derived from filename."""
        content = """---
name: Test Skill
description: Test
---
Instructions."""
        skill = parse_openviking_format(content, "My Test Skill.md")
        assert skill.id == "my-test-skill"


@pytest.mark.unit
class TestParseZenstoryFormat:
    """Test zenstory native format parsing."""

    def test_parse_basic(self):
        """Test parsing basic zenstory format."""
        content = """# Chapter Writer

This skill helps write chapters.

## Triggers
- write chapter
- new chapter

## Instructions
Follow these steps to write a chapter."""
        skill = parse_zenstory_format(content, "chapter-writer.md")

        assert skill is not None
        assert skill.name == "Chapter Writer"
        assert "helps write chapters" in skill.description
        assert "write chapter" in skill.triggers
        assert "Follow these steps" in skill.instructions

    def test_parse_no_triggers(self):
        """Test parsing without triggers section."""
        content = """# Simple Skill

Basic description.

## Instructions
Just do it."""
        skill = parse_zenstory_format(content, "simple.md")

        assert skill is not None
        assert skill.name == "Simple Skill"
        assert skill.triggers == []

    def test_parse_no_instructions(self):
        """Test parsing without instructions section."""
        content = """# No Instructions

Just a description."""
        skill = parse_zenstory_format(content, "no-instr.md")

        assert skill is not None
        assert skill.name == "No Instructions"
        assert skill.instructions == ""

    def test_parse_no_name(self):
        """Test parsing without name returns None."""
        content = """No heading here

## Instructions
Some instructions."""
        skill = parse_zenstory_format(content, "test.md")
        assert skill is None

    def test_parse_multiline_instructions(self):
        """Test parsing multiline instructions."""
        content = """# Test

## Instructions
Line 1
Line 2
Line 3"""
        skill = parse_zenstory_format(content, "test.md")

        assert skill is not None
        assert "Line 1" in skill.instructions
        assert "Line 2" in skill.instructions
        assert "Line 3" in skill.instructions

    def test_parse_chinese_content(self):
        """Test parsing Chinese content."""
        content = """# 章节写作助手

帮助写作章节。

## Triggers
- 写章节
- 新章节

## Instructions
按照以下步骤写作章节。"""
        skill = parse_zenstory_format(content, "chinese.md")

        assert skill is not None
        assert skill.name == "章节写作助手"
        assert "写章节" in skill.triggers


@pytest.mark.unit
class TestParseSkillMd:
    """Test parse_skill_md function that auto-detects format."""

    def test_detects_openviking(self):
        """Test detecting OpenViking format."""
        content = """---
name: Test
description: Test
---
Instructions."""
        skill = parse_skill_md(content, "test.md")
        assert skill is not None
        assert skill.name == "Test"

    def test_detects_zenstory(self):
        """Test detecting zenstory format."""
        content = """# Test Skill

Description here.

## Instructions
Do something."""
        skill = parse_skill_md(content, "test.md")
        assert skill is not None
        assert skill.name == "Test Skill"

    def test_returns_none_for_invalid(self):
        """Test returns None for invalid content."""
        content = "Just some random text\nwithout proper format"
        skill = parse_skill_md(content, "test.md")
        assert skill is None


@pytest.mark.unit
class TestLoadSkillsFromDir:
    """Test loading skills from directory."""

    def test_load_from_empty_dir(self):
        """Test loading from non-existent directory."""
        skills = load_skills_from_dir("/nonexistent/path", SkillSource.BUILTIN)
        assert skills == []

    def test_load_from_dir_with_skills(self):
        """Test loading from directory with skill files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create skill file
            skill_content = """---
name: Test Skill
description: A test
---
Instructions here."""
            skill_file = Path(tmpdir) / "test-skill.md"
            skill_file.write_text(skill_content)

            skills = load_skills_from_dir(tmpdir, SkillSource.PROJECT)

            assert len(skills) == 1
            assert skills[0].name == "Test Skill"
            assert skills[0].source == SkillSource.PROJECT

    def test_load_ignores_non_md_files(self):
        """Test that non-.md files are ignored."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create skill file
            (Path(tmpdir) / "skill.md").write_text("""---
name: Test
description: Test
---
Instructions.""")
            # Create non-skill file
            (Path(tmpdir) / "notes.txt").write_text("Some notes")

            skills = load_skills_from_dir(tmpdir, SkillSource.BUILTIN)

            assert len(skills) == 1

    def test_load_handles_invalid_files(self):
        """Test that invalid files are skipped."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Valid skill
            (Path(tmpdir) / "valid.md").write_text("""---
name: Valid
description: Valid
---
Instructions.""")
            # Invalid skill (missing required fields in YAML)
            (Path(tmpdir) / "invalid.md").write_text("---\nfoo: bar\n---\nNo name or description")

            skills = load_skills_from_dir(tmpdir, SkillSource.BUILTIN)

            # Should only load the valid one
            assert len(skills) == 1
            assert skills[0].name == "Valid"


@pytest.mark.unit
class TestGetAllSkills:
    """Test get_all_skills with priority override."""

    def test_priority_user_over_project(self):
        """Test user skills override project skills."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create project skill
            project_dir = Path(tmpdir) / "project"
            project_dir.mkdir()
            (project_dir / ".zenstory" / "skills").mkdir(parents=True)
            (project_dir / ".zenstory" / "skills" / "test.md").write_text("""---
name: Test Skill
description: Project version
---
Project instructions.""")

            # Create user skill with same ID
            with patch("agent.skills.loader.USER_SKILLS_DIR", project_dir / ".zenstory" / "skills"):
                with patch("agent.skills.loader.load_user_skills") as mock_user:
                    with patch("agent.skills.loader.load_project_skills") as mock_project:
                        with patch("agent.skills.loader.get_builtin_skills") as mock_builtin:
                            mock_builtin.return_value = []
                            mock_project.return_value = [
                                Skill(
                                    id="test",
                                    name="Test Skill",
                                    description="Project version",
                                    instructions="Project instructions",
                                    source=SkillSource.PROJECT,
                                )
                            ]
                            mock_user.return_value = [
                                Skill(
                                    id="test",
                                    name="Test Skill",
                                    description="User version",
                                    instructions="User instructions",
                                    source=SkillSource.USER,
                                )
                            ]

                            skills = get_all_skills(str(project_dir))

                            # Should have only one skill (user version)
                            assert len(skills) == 1
                            assert skills[0].description == "User version"

    def test_priority_order(self):
        """Test priority order: user > project > builtin."""
        with patch("agent.skills.loader.get_builtin_skills") as mock_builtin:
            with patch("agent.skills.loader.load_project_skills") as mock_project:
                with patch("agent.skills.loader.load_user_skills") as mock_user:
                    mock_builtin.return_value = [
                        Skill(id="s1", name="S1", description="Builtin", instructions="", source=SkillSource.BUILTIN),
                    ]
                    mock_project.return_value = [
                        Skill(id="s2", name="S2", description="Project", instructions="", source=SkillSource.PROJECT),
                        Skill(id="s1", name="S1", description="Project Override", instructions="", source=SkillSource.PROJECT),
                    ]
                    mock_user.return_value = [
                        Skill(id="s1", name="S1", description="User Override", instructions="", source=SkillSource.USER),
                    ]

                    skills = get_all_skills("/project")

                    # s1 should be user version, s2 should be project version
                    assert len(skills) == 2
                    s1 = next(s for s in skills if s.id == "s1")
                    s2 = next(s for s in skills if s.id == "s2")
                    assert s1.description == "User Override"
                    assert s2.description == "Project"


@pytest.mark.unit
class TestToSkillMd:
    """Test converting Skill to SKILL.md format."""

    def test_basic_conversion(self):
        """Test basic skill conversion."""
        skill = Skill(
            id="test",
            name="Test Skill",
            description="A test skill",
            instructions="Do something.",
        )
        md = to_skill_md(skill)

        assert "---" in md
        assert "name: Test Skill" in md
        assert "description: A test skill" in md
        assert "Do something." in md

    def test_with_triggers(self):
        """Test conversion with triggers."""
        skill = Skill(
            id="test",
            name="Test",
            description="Test",
            instructions="Instructions",
            triggers=["write", "create"],
        )
        md = to_skill_md(skill)

        assert "triggers:" in md
        assert "- write" in md
        assert "- create" in md

    def test_with_allowed_tools(self):
        """Test conversion with allowed tools."""
        skill = Skill(
            id="test",
            name="Test",
            description="Test",
            instructions="Instructions",
            allowed_tools=["create_file", "edit_file"],
        )
        md = to_skill_md(skill)

        assert "allowed-tools:" in md
        assert "- create_file" in md

    def test_with_tags(self):
        """Test conversion with tags."""
        skill = Skill(
            id="test",
            name="Test",
            description="Test",
            instructions="Instructions",
            tags=["writing", "creative"],
        )
        md = to_skill_md(skill)

        assert "tags:" in md
        assert "- writing" in md


@pytest.mark.unit
class TestBuiltinSkillsCache:
    """Test builtin skills caching."""

    def test_get_builtin_skills_caches(self):
        """Test that get_builtin_skills caches results."""
        with patch("agent.skills.loader.load_builtin_skills") as mock_load:
            mock_load.return_value = [
                Skill(id="s1", name="S1", description="D1", instructions="", source=SkillSource.BUILTIN),
            ]

            # Clear cache first
            import agent.skills.loader as loader
            loader._builtin_skills_cache = None

            # First call
            skills1 = get_builtin_skills()
            # Second call
            skills2 = get_builtin_skills()

            # Should only load once
            assert mock_load.call_count == 1
            assert skills1 is skills2

    def test_reload_clears_cache(self):
        """Test that reload_builtin_skills clears cache."""
        with patch("agent.skills.loader.load_builtin_skills") as mock_load:
            mock_load.return_value = [
                Skill(id="s1", name="S1", description="D1", instructions="", source=SkillSource.BUILTIN),
            ]

            import agent.skills.loader as loader
            loader._builtin_skills_cache = None

            # First load
            get_builtin_skills()
            # Clear and reload
            reload_builtin_skills()

            # Should have loaded twice
            assert mock_load.call_count == 2


@pytest.mark.integration
class TestSkillLoaderIntegration:
    """Integration tests for skill loader."""

    def test_full_workflow(self):
        """Test complete skill loading workflow."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create skill file
            skill_content = """---
name: Integration Test Skill
description: A skill for integration testing
triggers:
  - test trigger
allowed-tools:
  - create_file
tags:
  - testing
---
# Instructions

This is a test skill with **markdown** content.

1. Step one
2. Step two
3. Step three
"""
            skill_file = Path(tmpdir) / "test-skill.md"
            skill_file.write_text(skill_content)

            # Load skills
            skills = load_skills_from_dir(tmpdir, SkillSource.PROJECT)

            assert len(skills) == 1
            skill = skills[0]

            # Verify all fields
            assert skill.name == "Integration Test Skill"
            assert skill.description == "A skill for integration testing"
            assert "test trigger" in skill.triggers
            assert "create_file" in (skill.allowed_tools or [])
            assert "testing" in skill.tags
            assert "Step one" in skill.instructions

            # Convert back to markdown
            md = to_skill_md(skill)
            assert "Integration Test Skill" in md
            assert "A skill for integration testing" in md
