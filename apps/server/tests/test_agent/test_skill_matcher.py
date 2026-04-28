from __future__ import annotations

from unittest.mock import patch

import pytest

from agent.skills.matcher import _extract_words, _merge_skills, match_skills
from agent.skills.schemas import Skill, SkillSource


def _skill(skill_id: str, trigger: str, description: str = "desc") -> Skill:
    return Skill(
        id=skill_id,
        name=skill_id,
        description=description,
        triggers=[trigger],
        instructions=f"Use {skill_id}",
        source=SkillSource.BUILTIN,
    )


@pytest.mark.unit
def test_match_skills_prefers_user_skill_override_with_same_id():
    builtin_skill = _skill("outline-skill", "写大纲")
    user_skill = _skill("outline-skill", "写大纲", description="user override")
    user_skill.source = SkillSource.USER

    with patch("agent.skills.matcher.get_builtin_skills", return_value=[builtin_skill]):
        matches = match_skills("请帮我写大纲", user_skills=[user_skill])

    assert len(matches) == 1
    assert matches[0].skill.source == SkillSource.USER
    assert matches[0].skill.description == "user override"


@pytest.mark.unit
def test_match_skills_supports_synonym_matching():
    skill = _skill("outline-skill", "创建大纲")

    with patch("agent.skills.matcher.get_builtin_skills", return_value=[skill]):
        matches = match_skills("请帮我新建大纲", user_skills=None)

    assert len(matches) == 1
    assert matches[0].confidence == 0.9
    assert "via 新建" in matches[0].matched_trigger


@pytest.mark.unit
def test_match_skills_supports_fuzzy_action_and_noun_patterns():
    skill = _skill("world-skill", "世界观")

    with patch("agent.skills.matcher.get_builtin_skills", return_value=[skill]):
        matches = match_skills("帮我设计世界背景", user_skills=None)

    assert len(matches) == 1
    assert matches[0].confidence == 0.8
    assert "(fuzzy: 世界)" in matches[0].matched_trigger


@pytest.mark.unit
def test_match_skills_limits_results_by_confidence_order():
    skills = [
        _skill("outline-skill", "写大纲"),
        _skill("character-skill", "角色设定"),
        _skill("world-skill", "世界观"),
    ]

    with patch("agent.skills.matcher.get_builtin_skills", return_value=skills):
        matches = match_skills("请写大纲并做角色设定，还想看看世界观", max_skills=2)

    assert [match.skill.id for match in matches] == ["outline-skill", "character-skill"]


@pytest.mark.unit
def test_match_skills_respects_confidence_threshold():
    skill = _skill("world-skill", "世界观")

    with patch("agent.skills.matcher.get_builtin_skills", return_value=[skill]):
        matches = match_skills("帮我设计世界背景", confidence_threshold=0.85)

    assert matches == []


@pytest.mark.unit
def test_match_skills_exact_match_has_highest_confidence():
    skill = _skill("edit-skill", "润色文案")

    with patch("agent.skills.matcher.get_builtin_skills", return_value=[skill]):
        matches = match_skills("请直接润色文案")

    assert len(matches) == 1
    assert matches[0].matched_trigger == "润色文案"
    assert matches[0].confidence == 1.0


@pytest.mark.unit
def test_match_skills_does_not_trigger_fuzzy_match_without_action_word():
    skill = _skill("character-skill", "创建角色")

    with patch("agent.skills.matcher.get_builtin_skills", return_value=[skill]):
        matches = match_skills("档案资料汇总", user_skills=None)

    assert matches == []


@pytest.mark.unit
def test_extract_words_prefers_two_character_synonyms():
    assert _extract_words("创建大纲") == ["创建", "大纲"]


@pytest.mark.unit
def test_merge_skills_returns_builtin_when_no_user_skills():
    builtin_skill = _skill("builtin", "写大纲")

    with patch("agent.skills.matcher.get_builtin_skills", return_value=[builtin_skill]):
        merged = _merge_skills(None)

    assert merged == [builtin_skill]
