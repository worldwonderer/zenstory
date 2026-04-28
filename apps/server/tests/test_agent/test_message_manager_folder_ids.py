"""Tests for legacy root folder id resolution in MessageManager.

These tests ensure that MessageManager builds prompt folder placeholders
using the *actual* root folders stored in the database for legacy projects,
instead of always assuming deterministic IDs like "{project_id}-draft-folder".
"""

from agent.core.message_manager import MessageManager
from models import File, Project, User


def _create_user(db_session):
    user = User(
        email="folder_ids_test@example.com",
        username="folder_ids_test",
        hashed_password="hashed_password",
        email_verified=True,
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def test_folder_ids_prefers_legacy_root_folder_with_children(db_session):
    """When both legacy+deterministic roots exist, prefer the one actively used."""
    user = _create_user(db_session)
    project = Project(
        name="Legacy Root Folder Project",
        owner_id=user.id,
        project_type="screenplay",
    )
    db_session.add(project)
    db_session.commit()
    db_session.refresh(project)

    deterministic_character_id = f"{project.id}-character-folder"
    legacy_character_id = "legacy-character-root"

    # Deterministic root exists but has no children (e.g. created by a bug).
    db_session.add(
        File(
            id=deterministic_character_id,
            project_id=project.id,
            title="角色",
            file_type="folder",
            parent_id=None,
            order=0,
        )
    )

    # Legacy root folder (UUID) has children -> should be selected.
    db_session.add(
        File(
            id=legacy_character_id,
            project_id=project.id,
            title="角色",
            file_type="folder",
            parent_id=None,
            order=0,
        )
    )
    db_session.commit()

    # Add a child file under the legacy root to mark it as "active".
    db_session.add(
        File(
            id="child-1",
            project_id=project.id,
            title="李妍",
            file_type="character",
            parent_id=legacy_character_id,
            order=1,
            content="测试角色",
        )
    )
    db_session.commit()

    manager = MessageManager(project_id=project.id, user_id=user.id)
    folder_ids = manager._get_folder_ids(  # noqa: SLF001 - intentional private-method unit test
        session=db_session,
        project_type="screenplay",
    )

    assert folder_ids["character"] == legacy_character_id


def test_folder_ids_maps_screenplay_scene_folder_to_lore(db_session):
    """Legacy screenplay projects may use a root folder titled '场景' as settings."""
    user = _create_user(db_session)
    project = Project(
        name="Legacy Scene Folder Project",
        owner_id=user.id,
        project_type="screenplay",
    )
    db_session.add(project)
    db_session.commit()
    db_session.refresh(project)

    legacy_scene_id = "legacy-scene-root"
    db_session.add(
        File(
            id=legacy_scene_id,
            project_id=project.id,
            title="场景",
            file_type="folder",
            parent_id=None,
            order=1,
        )
    )
    db_session.commit()

    manager = MessageManager(project_id=project.id, user_id=user.id)
    folder_ids = manager._get_folder_ids(  # noqa: SLF001
        session=db_session,
        project_type="screenplay",
    )

    assert folder_ids["lore"] == legacy_scene_id
