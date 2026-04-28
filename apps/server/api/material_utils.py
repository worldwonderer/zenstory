"""Shared utilities for formatting material entities to markdown."""

import json
from typing import Any

from sqlmodel import Session, select

from models.material_models import (
    Character,
    CharacterRelationship,
    GoldenFinger,
    Story,
    StoryLine,
    WorldView,
)


def _safe_json_parse(json_str: str | None) -> list[Any]:
    """Safely parse JSON string, returning empty list on failure."""
    if not json_str:
        return []
    try:
        parsed = json.loads(json_str)
        return parsed if isinstance(parsed, list) else []
    except json.JSONDecodeError:
        return []


def format_character_to_markdown(character: Character, novel_title: str) -> tuple[str, str]:
    """
    Format character to markdown.

    Returns:
        tuple of (title, markdown)
    """
    # Parse aliases
    aliases = _safe_json_parse(character.aliases)

    title = character.name
    markdown = f"# {character.name}\n\n"
    markdown += f"**类型**: {character.archetype or '未知'}\n"
    if aliases:
        markdown += f"**别名**: {'、'.join(aliases)}\n"
    markdown += f"\n## 描述\n{character.description or '无'}\n\n"
    markdown += f"---\n> 参考来源: 《{novel_title}》\n"

    return title, markdown


def format_worldview_to_markdown(world_view: WorldView, novel_title: str) -> tuple[str, str]:
    """
    Format worldview to markdown.

    Returns:
        tuple of (title, markdown)
    """
    # Parse factions
    factions = _safe_json_parse(world_view.key_factions)
    factions_text = ""
    for faction in factions:
        if isinstance(faction, dict):
            factions_text += f"- {faction.get('name', '未知')}\n"
        else:
            factions_text += f"- {faction}\n"

    title = "世界观设定"
    markdown = "# 世界观设定\n\n"
    markdown += f"## 力量体系\n{world_view.power_system or '无'}\n\n"
    markdown += f"## 世界结构\n{world_view.world_structure or '无'}\n\n"
    if factions_text:
        markdown += f"## 主要势力\n{factions_text}\n"
    markdown += f"## 特殊规则\n{world_view.special_rules or '无'}\n\n"
    markdown += f"---\n> 参考来源: 《{novel_title}》\n"

    return title, markdown


def format_goldenfinger_to_markdown(golden_finger: GoldenFinger, novel_title: str) -> tuple[str, str]:
    """
    Format golden finger to markdown.

    Returns:
        tuple of (title, markdown)
    """
    # Parse evolution history
    evolution_stages = _safe_json_parse(golden_finger.evolution_history)
    evolution_text = ""
    for i, stage in enumerate(evolution_stages, 1):
        if isinstance(stage, dict):
            evolution_text += f"{i}. {stage.get('description', '未知')}\n"
        else:
            evolution_text += f"{i}. {stage}\n"

    title = golden_finger.name
    markdown = f"# {golden_finger.name}\n\n"
    markdown += f"**类型**: {golden_finger.type or '未知'}\n\n"
    markdown += f"## 描述\n{golden_finger.description or '无'}\n\n"
    if evolution_text:
        markdown += f"## 进化历程\n{evolution_text}\n"
    markdown += f"---\n> 参考来源: 《{novel_title}》\n"

    return title, markdown


def format_storyline_to_markdown(storyline: StoryLine, session: Session, novel_title: str) -> tuple[str, str]:
    """
    Format storyline to markdown.

    Returns:
        tuple of (title, markdown)
    """
    from models.material_models import Story

    # Parse main_characters and themes
    main_chars = _safe_json_parse(storyline.main_characters)
    main_chars_text = "、".join(main_chars) if main_chars else ""

    themes = _safe_json_parse(storyline.themes)
    themes_text = "、".join(themes) if themes else ""

    # Get stories under this storyline
    stories = session.exec(
        select(Story).where(Story.story_line_id == storyline.id)
    ).all()
    stories_text = ""
    for story in stories:
        stories_text += f"- {story.title}\n"

    title = storyline.title
    markdown = f"# {storyline.title}\n\n"
    markdown += f"{storyline.description or '无'}\n\n"
    if main_chars_text:
        markdown += f"## 主要角色\n{main_chars_text}\n\n"
    if themes_text:
        markdown += f"## 主题\n{themes_text}\n\n"
    if stories_text:
        markdown += f"## 包含剧情\n{stories_text}\n"
    markdown += f"---\n> 参考来源: 《{novel_title}》\n"

    return title, markdown


def format_story_to_markdown(story: Story, novel_title: str) -> tuple[str, str]:
    """
    Format story to markdown.

    Returns:
        tuple of (title, markdown)
    """
    themes = _safe_json_parse(story.themes)
    themes_text = "、".join(themes) if themes else (story.themes or "")

    title = story.title
    markdown = f"# {story.title}\n\n"
    markdown += f"## 剧情概述\n{story.synopsis or '无'}\n\n"
    markdown += f"## 核心目标\n{story.core_objective or '无'}\n\n"
    markdown += f"## 核心冲突\n{story.core_conflict or '无'}\n\n"
    markdown += f"## 剧情类型\n{story.story_type or '未知'}\n\n"
    markdown += f"## 章节范围\n{story.chapter_range or '未知'}\n\n"
    if themes_text:
        markdown += f"## 主题\n{themes_text}\n\n"
    markdown += f"---\n> 参考来源: 《{novel_title}》\n"

    return title, markdown


def format_relationship_to_markdown(
    novel_id: int,
    session: Session,
    novel_title: str,
    relationship_id: int | None = None,
) -> tuple[str, str]:
    """
    Format all relationships for a novel to markdown.

    Returns:
        tuple of (title, markdown)
    """
    from sqlalchemy.orm import aliased

    CharacterA = aliased(Character, name="character_a")
    CharacterB = aliased(Character, name="character_b")

    stmt = (
        select(
            CharacterRelationship,
            CharacterA.name.label("character_a_name"),
            CharacterB.name.label("character_b_name")
        )
        .join(CharacterA, CharacterRelationship.character_a_id == CharacterA.id)
        .join(CharacterB, CharacterRelationship.character_b_id == CharacterB.id)
        .where(CharacterRelationship.novel_id == novel_id)
    )
    if relationship_id is not None:
        stmt = stmt.where(CharacterRelationship.id == relationship_id)

    results = session.exec(stmt).all()

    if relationship_id is not None and len(results) == 1:
        _, char_a_name, char_b_name = results[0]
        title = f"{char_a_name} ↔ {char_b_name}"
    else:
        title = "角色关系"
    markdown = "# 角色关系\n\n"
    for rel, char_a_name, char_b_name in results:
        markdown += f"## {char_a_name} ↔ {char_b_name}\n"
        markdown += f"- **关系**: {rel.relationship_type}\n"
        if rel.sentiment:
            markdown += f"- **态度**: {rel.sentiment}\n"
        if rel.description:
            markdown += f"- {rel.description}\n"
        markdown += "\n"
    markdown += f"---\n> 参考来源: 《{novel_title}》\n"

    return title, markdown
