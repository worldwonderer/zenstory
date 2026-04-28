"""Tests for MessageManager permission checks."""

import pytest

from agent.core.message_manager import MessageManager
from models import Project, User


def _create_user(db_session, *, suffix: str, is_superuser: bool = False) -> User:
    user = User(
        email=f"message_manager_perm_{suffix}@example.com",
        username=f"message_manager_perm_{suffix}",
        hashed_password="hashed_password",
        email_verified=True,
        is_active=True,
        is_superuser=is_superuser,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def test_build_system_prompt_denies_cross_project_access(db_session):
    owner = _create_user(db_session, suffix="owner")
    attacker = _create_user(db_session, suffix="attacker")

    project = Project(
        name="Permission Test Project",
        owner_id=owner.id,
        project_type="novel",
    )
    db_session.add(project)
    db_session.commit()
    db_session.refresh(project)

    manager = MessageManager(project_id=project.id, user_id=attacker.id)

    with pytest.raises(ValueError):
        manager.build_system_prompt(session=db_session, language="zh")


def test_build_system_prompt_allows_superuser_access(db_session):
    owner = _create_user(db_session, suffix="owner2")
    superuser = _create_user(db_session, suffix="superuser", is_superuser=True)

    project = Project(
        name="Superuser Access Project",
        owner_id=owner.id,
        project_type="novel",
    )
    db_session.add(project)
    db_session.commit()
    db_session.refresh(project)

    manager = MessageManager(project_id=project.id, user_id=superuser.id)

    prompt = manager.build_system_prompt(session=db_session, language="zh")
    assert isinstance(prompt, str)
    assert prompt

