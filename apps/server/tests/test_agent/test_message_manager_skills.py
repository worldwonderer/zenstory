"""Tests for skill-related system prompt sections."""

import pytest

from agent.core.message_manager import MessageManager
from models import Project, User


def _create_user(db_session, *, suffix: str) -> User:
    user = User(
        email=f"message-manager-skill-{suffix}@example.com",
        username=f"message_manager_skill_{suffix}",
        hashed_password="hashed_password",
        email_verified=True,
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.mark.unit
def test_build_system_prompt_includes_explicit_selected_skill_section(db_session):
    owner = _create_user(db_session, suffix="owner")
    project = Project(
        name="Skill Prompt Project",
        owner_id=owner.id,
        project_type="novel",
    )
    db_session.add(project)
    db_session.commit()
    db_session.refresh(project)

    manager = MessageManager(project_id=project.id, user_id=owner.id)

    prompt = manager.build_system_prompt(
        session=db_session,
        language="zh",
        selected_skill={
            "id": "skill-1",
            "name": "悬念大师",
            "instructions": "先强化钩子，再收紧悬念。",
            "source": "user",
            "matched_text": "悬念大师",
        },
    )

    assert "## 用户本条消息指定技能" in prompt
    assert "### 悬念大师" in prompt
    assert "先强化钩子，再收紧悬念。" in prompt
    assert "[使用技能: 悬念大师]" in prompt
    assert "匹配前缀：`悬念大师`" in prompt
