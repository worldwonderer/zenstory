"""Tests for explicit skill resolution from message prefixes."""

import json

import pytest

from agent.skills.explicit_resolver import resolve_explicit_skill_selection
from models import PublicSkill, User, UserAddedSkill, UserSkill


def _create_user(db_session, *, suffix: str) -> User:
    user = User(
        email=f"explicit-skill-{suffix}@example.com",
        username=f"explicit_skill_{suffix}",
        hashed_password="hashed_password",
        email_verified=True,
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.mark.unit
def test_resolve_explicit_user_skill_prefix_and_strip_message(db_session):
    user = _create_user(db_session, suffix="user-prefix")
    skill = UserSkill(
        user_id=user.id,
        name="悬念大师",
        description="增强钩子和悬念",
        triggers=json.dumps(["悬念大师", "制造悬念"]),
        instructions="先强化钩子，再收紧悬念。",
        is_active=True,
    )
    db_session.add(skill)
    db_session.commit()

    selection = resolve_explicit_skill_selection(
        session=db_session,
        user_id=user.id,
        message="悬念大师 帮我把这一段开头写得更抓人",
    )

    assert selection is not None
    assert selection.skill_id == skill.id
    assert selection.name == "悬念大师"
    assert selection.source == "user"
    assert selection.matched_text == "悬念大师"
    assert selection.cleaned_message == "帮我把这一段开头写得更抓人"


@pytest.mark.unit
def test_resolve_added_skill_by_name_when_public_tags_empty(db_session):
    user = _create_user(db_session, suffix="added-name")
    public_skill = PublicSkill(
        name="氛围渲染器",
        description="强化氛围和情绪",
        instructions="优先写环境与感官细节。",
        tags="[]",
        status="approved",
    )
    db_session.add(public_skill)
    db_session.commit()
    db_session.refresh(public_skill)

    added_skill = UserAddedSkill(
        user_id=user.id,
        public_skill_id=public_skill.id,
        is_active=True,
    )
    db_session.add(added_skill)
    db_session.commit()

    selection = resolve_explicit_skill_selection(
        session=db_session,
        user_id=user.id,
        message="氛围渲染器：帮我把场景压迫感拉满",
    )

    assert selection is not None
    assert selection.skill_id == public_skill.id
    assert selection.name == "氛围渲染器"
    assert selection.source == "added"
    assert selection.cleaned_message == "帮我把场景压迫感拉满"


@pytest.mark.unit
def test_resolve_added_skill_by_custom_name(db_session):
    user = _create_user(db_session, suffix="added-custom-name")
    public_skill = PublicSkill(
        name="氛围渲染器",
        description="强化氛围和情绪",
        instructions="优先写环境与感官细节。",
        tags="[]",
        status="approved",
    )
    db_session.add(public_skill)
    db_session.commit()
    db_session.refresh(public_skill)

    added_skill = UserAddedSkill(
        user_id=user.id,
        public_skill_id=public_skill.id,
        custom_name="阴影编织者",
        is_active=True,
    )
    db_session.add(added_skill)
    db_session.commit()

    selection = resolve_explicit_skill_selection(
        session=db_session,
        user_id=user.id,
        message="阴影编织者 帮我把这场戏写得更阴冷",
    )

    assert selection is not None
    assert selection.skill_id == public_skill.id
    assert selection.name == "阴影编织者"
    assert selection.source == "added"
    assert selection.cleaned_message == "帮我把这场戏写得更阴冷"


@pytest.mark.unit
def test_does_not_match_when_skill_name_is_not_explicit_prefix(db_session):
    user = _create_user(db_session, suffix="no-boundary")
    skill = UserSkill(
        user_id=user.id,
        name="悬念大师",
        description="增强钩子和悬念",
        triggers=json.dumps(["悬念大师"]),
        instructions="先强化钩子，再收紧悬念。",
        is_active=True,
    )
    db_session.add(skill)
    db_session.commit()

    selection = resolve_explicit_skill_selection(
        session=db_session,
        user_id=user.id,
        message="悬念大师这个技能为什么有时候不生效？",
    )

    assert selection is None


@pytest.mark.unit
def test_strips_multiple_leading_skill_prefixes_but_keeps_first_selection(db_session):
    user = _create_user(db_session, suffix="multi-prefix")
    first_skill = UserSkill(
        user_id=user.id,
        name="悬念大师",
        description="增强钩子和悬念",
        triggers=json.dumps(["悬念大师"]),
        instructions="先强化钩子，再收紧悬念。",
        is_active=True,
    )
    second_skill = UserSkill(
        user_id=user.id,
        name="节奏大师",
        description="压缩拖沓段落",
        triggers=json.dumps(["节奏大师"]),
        instructions="优先压缩重复动作和解释。",
        is_active=True,
    )
    db_session.add(first_skill)
    db_session.add(second_skill)
    db_session.commit()

    selection = resolve_explicit_skill_selection(
        session=db_session,
        user_id=user.id,
        message="悬念大师 节奏大师 帮我重写这一段",
    )

    assert selection is not None
    assert selection.skill_id == first_skill.id
    assert selection.name == "悬念大师"
    assert selection.cleaned_message == "帮我重写这一段"


@pytest.mark.unit
def test_returns_none_when_prefix_is_ambiguous_across_multiple_skills(db_session):
    user = _create_user(db_session, suffix="ambiguous-prefix")
    first_skill = UserSkill(
        user_id=user.id,
        name="悬念大师",
        description="增强钩子和悬念",
        triggers=json.dumps(["通用触发词"]),
        instructions="先强化钩子，再收紧悬念。",
        is_active=True,
    )
    second_skill = UserSkill(
        user_id=user.id,
        name="节奏大师",
        description="压缩拖沓段落",
        triggers=json.dumps(["通用触发词"]),
        instructions="优先压缩重复动作和解释。",
        is_active=True,
    )
    db_session.add(first_skill)
    db_session.add(second_skill)
    db_session.commit()

    selection = resolve_explicit_skill_selection(
        session=db_session,
        user_id=user.id,
        message="通用触发词 帮我处理这一段",
    )

    assert selection is None
