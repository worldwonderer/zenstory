from __future__ import annotations

from pathlib import Path

from agent.skills.loader import load_skills_from_dir
from agent.skills.schemas import SkillSource


def test_load_skills_from_dir_returns_empty_for_missing_directory(tmp_path: Path):
    missing_dir = tmp_path / "missing"

    assert load_skills_from_dir(missing_dir, SkillSource.PROJECT) == []


def test_load_skills_from_dir_sets_source_and_file_path(tmp_path: Path):
    skill_file = tmp_path / "story.md"
    skill_file.write_text(
        "# Story Skill\n"
        "A small description.\n\n"
        "## Triggers\n"
        "- story\n\n"
        "## Instructions\n"
        "Do story work.\n",
        encoding="utf-8",
    )

    skills = load_skills_from_dir(tmp_path, SkillSource.PROJECT)

    assert len(skills) == 1
    assert skills[0].source == SkillSource.PROJECT
    assert skills[0].file_path == str(skill_file)
