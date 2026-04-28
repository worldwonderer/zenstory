"""Tests for screenplay episode create_file normalization and idempotency safeguards."""

import pytest
from sqlmodel import Session, select

from agent.tools.file_ops.crud import FileCRUD
from models import File, Project, User


@pytest.fixture
def test_user(db_session: Session) -> User:
    user = User(
        email="screenplay_idempotency@example.com",
        username="screenplay_idempotency",
        hashed_password="hashed_password",
        email_verified=True,
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def screenplay_project(db_session: Session, test_user: User) -> Project:
    project = Project(
        name="Test Screenplay",
        owner_id=test_user.id,
        project_type="screenplay",
    )
    db_session.add(project)
    db_session.commit()
    db_session.refresh(project)

    # Create the screenplay root script folder.
    script_folder = File(
        id=f"{project.id}-script-folder",
        project_id=project.id,
        title="剧本",
        file_type="folder",
        order=0,
        parent_id=None,
    )
    db_session.add(script_folder)
    db_session.commit()
    return project


@pytest.mark.unit
def test_create_file_normalizes_episode_draft_to_script(db_session: Session, test_user: User, screenplay_project: Project):
    crud = FileCRUD(db_session, user_id=test_user.id)

    result = crud.create_file(
        project_id=screenplay_project.id,
        title="第1集：测试",
        file_type="draft",  # legacy default when LLM omits file_type
        parent_id=f"{screenplay_project.id}-script-folder",
    )

    assert result["file_type"] == "script"
    stored = db_session.get(File, result["id"])
    assert stored is not None
    assert stored.file_type == "script"


@pytest.mark.unit
def test_create_file_reuses_existing_episode_when_streaming(db_session: Session, test_user: User, screenplay_project: Project):
    crud = FileCRUD(db_session, user_id=test_user.id)

    first = crud.create_file(
        project_id=screenplay_project.id,
        title="第2集：测试",
        file_type="draft",
        parent_id=f"{screenplay_project.id}-script-folder",
    )

    # Simulate that the file already has content (previous episode write).
    crud.update_file(id=first["id"], content="OLD CONTENT")

    second = crud.create_file(
        project_id=screenplay_project.id,
        title="第2集：测试",
        file_type="draft",
        parent_id=f"{screenplay_project.id}-script-folder",
        content="",  # streaming mode
    )

    assert second["id"] == first["id"]
    # Streaming pipeline requires empty content in tool response to activate <file> capture mode.
    assert second["content"] == ""

    rows = db_session.exec(
        select(File).where(
            File.project_id == screenplay_project.id,
            File.parent_id == f"{screenplay_project.id}-script-folder",
            File.title == "第2集：测试",
            File.is_deleted.is_(False),
        )
    ).all()
    assert len(rows) == 1


@pytest.mark.unit
def test_create_file_promotes_legacy_episode_draft_in_script_folder(db_session: Session, test_user: User, screenplay_project: Project):
    legacy = File(
        project_id=screenplay_project.id,
        title="第3集：测试",
        file_type="draft",
        parent_id=f"{screenplay_project.id}-script-folder",
        order=0,
        content="LEGACY",
    )
    db_session.add(legacy)
    db_session.commit()
    db_session.refresh(legacy)

    crud = FileCRUD(db_session, user_id=test_user.id)
    result = crud.create_file(
        project_id=screenplay_project.id,
        title="第3集：测试",
        file_type="draft",
        parent_id=f"{screenplay_project.id}-script-folder",
        content="",  # streaming mode
    )

    assert result["id"] == legacy.id
    assert result["file_type"] == "script"
    assert result["content"] == ""

    db_session.refresh(legacy)
    assert legacy.file_type == "script"

