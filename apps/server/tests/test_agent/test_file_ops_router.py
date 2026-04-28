from __future__ import annotations

from sqlmodel import Session

from agent.tools.file_ops import router as router_module
from agent.tools.permissions import PermissionError
from models import File, Project, User
from services.core.auth_service import hash_password


def _create_user(db_session: Session, suffix: str) -> User:
    user = User(
        email=f"router-{suffix}@example.com",
        username=f"router-{suffix}",
        hashed_password=hash_password("password123"),
        email_verified=True,
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def _create_project(db_session: Session, owner_id: str, name: str) -> Project:
    project = Project(name=name, owner_id=owner_id)
    db_session.add(project)
    db_session.commit()
    db_session.refresh(project)
    return project


def _create_file(db_session: Session, project_id: str, title: str, *, file_type: str = "draft") -> File:
    file = File(project_id=project_id, title=title, file_type=file_type, content="")
    db_session.add(file)
    db_session.commit()
    db_session.refresh(file)
    return file


def test_resolve_file_id_in_project_handles_id_title_and_ambiguity(db_session: Session):
    user = _create_user(db_session, "resolve")
    project = _create_project(db_session, user.id, "Router Project")
    exact = _create_file(db_session, project.id, "Exact")
    title_match = _create_file(db_session, project.id, "By Title")
    _create_file(db_session, project.id, "Duplicate")
    _create_file(db_session, project.id, "Duplicate")

    by_id = router_module.resolve_file_id_in_project(db_session, project.id, exact.id)
    by_title = router_module.resolve_file_id_in_project(db_session, project.id, "By Title")
    ambiguous = router_module.resolve_file_id_in_project(db_session, project.id, "Duplicate")
    missing = router_module.resolve_file_id_in_project(db_session, project.id, "Missing")

    assert by_id == {"status": "ok", "file_id": exact.id, "resolved_by": "id"}
    assert by_title == {"status": "ok", "file_id": title_match.id, "resolved_by": "title"}
    assert ambiguous["status"] == "ambiguous"
    assert len(ambiguous["candidates"]) == 2
    assert missing == {"status": "not_found"}


def test_resolve_file_id_in_project_ignores_deleted_and_other_project_matches(db_session: Session):
    user = _create_user(db_session, "deleted")
    project = _create_project(db_session, user.id, "Deleted Project")
    other_project = _create_project(db_session, user.id, "Other Project")

    deleted = _create_file(db_session, project.id, "Gone")
    deleted.is_deleted = True
    db_session.add(deleted)
    db_session.commit()
    _create_file(db_session, other_project.id, "Gone")

    assert router_module.resolve_file_id_in_project(db_session, project.id, deleted.id) == {"status": "not_found"}
    assert router_module.resolve_file_id_in_project(db_session, project.id, "Gone") == {"status": "not_found"}


def test_execute_file_tool_call_resolves_title_fallback_for_edit(monkeypatch, db_session: Session):
    user = _create_user(db_session, "fallback")
    project = _create_project(db_session, user.id, "Fallback Project")
    file = _create_file(db_session, project.id, "Chapter 1")

    captured = {}

    class DummyCRUD:
        def __init__(self, session, user_id):
            pass

    class DummyEditor:
        def __init__(self, session, user_id):
            pass

        def edit_file(self, **kwargs):
            captured["kwargs"] = kwargs
            return {"ok": True}

    class DummyProjectOps:
        def __init__(self, session, user_id):
            pass

    monkeypatch.setattr(router_module, "FileCRUD", DummyCRUD)
    monkeypatch.setattr(router_module, "FileEditor", DummyEditor)
    monkeypatch.setattr(router_module, "ProjectOperations", DummyProjectOps)

    result = router_module.execute_file_tool_call(
        db_session,
        "edit_file",
        {"project_id": project.id, "id": "Chapter 1", "operations": []},
        user.id,
    )

    assert result == {"status": "success", "data": {"ok": True}}
    assert captured["kwargs"]["id"] == file.id


def test_execute_file_tool_call_returns_ambiguous_error_for_duplicate_titles(db_session: Session):
    user = _create_user(db_session, "ambiguous")
    project = _create_project(db_session, user.id, "Ambiguous Project")
    _create_file(db_session, project.id, "Same Title")
    _create_file(db_session, project.id, "Same Title")

    result = router_module.execute_file_tool_call(
        db_session,
        "edit_file",
        {"project_id": project.id, "id": "Same Title", "operations": []},
        user.id,
    )

    assert result["status"] == "error"
    assert "文件名不唯一" in result["error"]
    assert "Same Title" in result["error"]


def test_execute_file_tool_call_handles_unknown_permission_and_runtime_errors(monkeypatch, db_session: Session):
    class DummyCRUD:
        def __init__(self, session, user_id):
            pass

        def create_file(self, **kwargs):
            raise PermissionError("create_file", "project:123")

        def update_file(self, **kwargs):
            raise ValueError("bad input")

        def delete_file(self, **kwargs):
            raise RuntimeError("boom")

    class DummyEditor:
        def __init__(self, session, user_id):
            pass

    class DummyProjectOps:
        def __init__(self, session, user_id):
            pass

    monkeypatch.setattr(router_module, "FileCRUD", DummyCRUD)
    monkeypatch.setattr(router_module, "FileEditor", DummyEditor)
    monkeypatch.setattr(router_module, "ProjectOperations", DummyProjectOps)

    permission_result = router_module.execute_file_tool_call(db_session, "create_file", {}, "user-1")
    value_error_result = router_module.execute_file_tool_call(db_session, "update_file", {}, "user-1")
    runtime_result = router_module.execute_file_tool_call(db_session, "delete_file", {}, "user-1")
    unknown_result = router_module.execute_file_tool_call(db_session, "unknown_tool", {}, "user-1")

    assert permission_result["status"] == "error"
    assert "权限错误" in permission_result["error"]
    assert value_error_result == {"status": "error", "error": "bad input"}
    assert runtime_result == {"status": "error", "error": "执行失败: boom"}
    assert unknown_result == {"status": "error", "error": "Unknown tool: unknown_tool"}
