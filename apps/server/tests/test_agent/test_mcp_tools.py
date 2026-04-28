"""Tests for MCP tool wrappers."""

import json
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from agent.tools.mcp_tools import (
    create_file,
    delete_file,
    edit_file,
    handoff_to_agent,
    hybrid_search,
    query_files,
    request_clarification,
    update_project,
)


def _parse_payload(result: dict) -> dict:
    text = result["content"][0]["text"]
    return json.loads(text)


@pytest.mark.asyncio
@pytest.mark.unit
async def test_update_project_supports_empty_string_and_returns_compat_fields():
    mock_executor = MagicMock()
    mock_executor.update_project_status.return_value = {
        "project_id": "proj-1",
        "updated_fields": ["summary"],
        "current_status": {"summary": ""},
    }

    with patch("agent.tools.mcp_tools.ToolContext.get_executor", return_value=mock_executor), patch(
        "agent.tools.mcp_tools.ToolContext._get_context",
        return_value={"project_id": "proj-1", "session_id": "sess-1"},
    ):
        result = await update_project({"summary": ""})

    payload = _parse_payload(result)
    assert payload["status"] == "success"
    assert payload["data"]["project_status"]["updated_fields"] == ["summary"]
    assert payload["data"]["updated_fields"] == ["summary"]
    assert payload["data"]["project_id"] == "proj-1"
    assert payload["data"]["current_status"]["summary"] == ""

    mock_executor.update_project_status.assert_called_once_with(
        project_id="proj-1",
        summary="",
        current_phase=None,
        writing_style=None,
        notes=None,
    )


@pytest.mark.asyncio
@pytest.mark.unit
async def test_update_project_accepts_current_phase_camel_case_alias():
    mock_executor = MagicMock()
    mock_executor.update_project_status.return_value = {
        "project_id": "proj-1",
        "updated_fields": ["current_phase"],
        "current_status": {"current_phase": "已写至第5章"},
    }

    with patch("agent.tools.mcp_tools.ToolContext.get_executor", return_value=mock_executor), patch(
        "agent.tools.mcp_tools.ToolContext._get_context",
        return_value={"project_id": "proj-1", "session_id": "sess-1"},
    ):
        result = await update_project({"currentPhase": "已写至第5章"})

    payload = _parse_payload(result)
    assert payload["status"] == "success"
    assert payload["data"]["updated_fields"] == ["current_phase"]
    assert payload["data"]["current_status"]["current_phase"] == "已写至第5章"

    mock_executor.update_project_status.assert_called_once_with(
        project_id="proj-1",
        summary=None,
        current_phase="已写至第5章",
        writing_style=None,
        notes=None,
    )


@pytest.mark.asyncio
@pytest.mark.unit
async def test_update_project_passes_empty_tasks_array_when_present():
    mock_executor = MagicMock()
    mock_executor.execute_update_plan.return_value = {
        "tasks": [],
    }

    with patch("agent.tools.mcp_tools.ToolContext.get_executor", return_value=mock_executor), patch(
        "agent.tools.mcp_tools.ToolContext._get_context",
        return_value={"project_id": "proj-1", "session_id": "sess-1"},
    ):
        result = await update_project({"tasks": []})

    payload = _parse_payload(result)
    assert payload["status"] == "success"
    assert payload["data"]["plan"] == {"tasks": []}

    mock_executor.execute_update_plan.assert_called_once_with(
        session_id="sess-1",
        tasks=[],
        user_id=None,
        project_id="proj-1",
    )


@pytest.mark.asyncio
@pytest.mark.unit
async def test_update_project_tasks_only_can_auto_sync_current_phase():
    mock_executor = MagicMock()
    mock_executor.execute_update_plan.return_value = {
        "tasks": [{"task": "写第5章", "status": "done"}],
    }
    mock_executor.update_project_status.return_value = {
        "project_id": "proj-1",
        "updated_fields": ["current_phase"],
        "current_status": {"current_phase": "已写至第5章"},
    }

    with patch("agent.tools.mcp_tools.ToolContext.get_executor", return_value=mock_executor), patch(
        "agent.tools.mcp_tools.ToolContext._get_context",
        return_value={"project_id": "proj-1", "session_id": "sess-1"},
    ), patch(
        "agent.tools.mcp_tools._suggest_auto_current_phase_from_drafts",
        return_value="已写至第5章",
    ):
        result = await update_project({"tasks": [{"task": "写第5章", "status": "done"}]})

    payload = _parse_payload(result)
    assert payload["status"] == "success"
    assert payload["data"]["plan"]["tasks"] == [{"task": "写第5章", "status": "done"}]
    assert payload["data"]["updated_fields"] == ["current_phase"]
    assert payload["data"]["current_status"]["current_phase"] == "已写至第5章"

    mock_executor.execute_update_plan.assert_called_once_with(
        session_id="sess-1",
        tasks=[{"task": "写第5章", "status": "done"}],
        user_id=None,
        project_id="proj-1",
    )
    mock_executor.update_project_status.assert_called_once_with(
        project_id="proj-1",
        summary=None,
        current_phase="已写至第5章",
        writing_style=None,
        notes=None,
    )


@pytest.mark.asyncio
@pytest.mark.unit
async def test_update_project_tasks_only_logs_info_not_warning():
    mock_executor = MagicMock()
    mock_executor.execute_update_plan.return_value = {
        "tasks": [{"task": "写第5章", "status": "done"}],
    }

    with patch("agent.tools.mcp_tools.ToolContext.get_executor", return_value=mock_executor), patch(
        "agent.tools.mcp_tools.ToolContext._get_context",
        return_value={"project_id": "proj-1", "session_id": "sess-1"},
    ), patch(
        "agent.tools.mcp_tools._suggest_auto_current_phase_from_drafts",
        return_value=None,
    ), patch("agent.tools.mcp_tools.log_with_context") as mock_log:
        result = await update_project({"tasks": [{"task": "写第5章", "status": "done"}]})

    payload = _parse_payload(result)
    assert payload["status"] == "success"
    assert payload["data"]["plan"]["tasks"] == [{"task": "写第5章", "status": "done"}]
    mock_executor.update_project_status.assert_not_called()

    mock_log.assert_called_once()
    assert mock_log.call_args.args[1] == 20
    assert mock_log.call_args.args[2] == "update_project received task-board-only payload"


@pytest.mark.asyncio
@pytest.mark.unit
async def test_update_project_tasks_only_auto_sync_failure_is_non_blocking():
    mock_executor = MagicMock()
    mock_executor.execute_update_plan.return_value = {
        "tasks": [{"task": "写第5章", "status": "done"}],
    }

    with patch("agent.tools.mcp_tools.ToolContext.get_executor", return_value=mock_executor), patch(
        "agent.tools.mcp_tools.ToolContext._get_context",
        return_value={"project_id": "proj-1", "session_id": "sess-1"},
    ), patch(
        "agent.tools.mcp_tools._suggest_auto_current_phase_from_drafts",
        side_effect=RuntimeError("boom"),
    ), patch("agent.tools.mcp_tools.log_with_context") as mock_log:
        result = await update_project({"tasks": [{"task": "写第5章", "status": "done"}]})

    payload = _parse_payload(result)
    assert payload["status"] == "success"
    assert payload["data"]["plan"]["tasks"] == [{"task": "写第5章", "status": "done"}]
    assert "project_status" not in payload["data"]

    mock_executor.execute_update_plan.assert_called_once_with(
        session_id="sess-1",
        tasks=[{"task": "写第5章", "status": "done"}],
        user_id=None,
        project_id="proj-1",
    )
    mock_executor.update_project_status.assert_not_called()

    assert mock_log.call_count >= 2
    error_calls = [call for call in mock_log.call_args_list if call.args[1] == 40]
    assert error_calls


@pytest.mark.asyncio
@pytest.mark.unit
async def test_create_file_infers_order_from_episode_title_when_order_missing(db_session):
    """create_file tool should infer `order` from titles like 第8集 when caller omits order."""
    from agent.tools.mcp_tools import ToolContext
    from models import File, Project, User

    suffix = uuid4().hex[:8]
    user = User(
        email=f"mcp-tools-order-{suffix}@example.com",
        username=f"mcp_tools_order_{suffix}",
        hashed_password="hashed",
        email_verified=True,
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    project = Project(
        name=f"MCP Tools Order Project {suffix}",
        owner_id=user.id,
        project_type="novel",
    )
    db_session.add(project)
    db_session.commit()
    db_session.refresh(project)

    folder = File(
        project_id=project.id,
        title="分集大纲",
        file_type="folder",
        order=0,
    )
    db_session.add(folder)
    db_session.commit()
    db_session.refresh(folder)

    ToolContext.set_context(
        session=db_session,
        user_id=user.id,
        project_id=project.id,
        session_id="sess-1",
    )
    try:
        result = await create_file({
            "title": "第8集：测试",
            "file_type": "outline",
            "parent_id": folder.id,
            "content": "outline",
        })
    finally:
        ToolContext.clear_context()

    payload = _parse_payload(result)
    assert payload["status"] == "success"
    assert payload["data"]["title"] == "第8集：测试"
    assert payload["data"]["order"] == 8


@pytest.mark.asyncio
@pytest.mark.unit
async def test_create_file_normalizes_suspicious_explicit_order_from_title(db_session):
    """Explicit order like 580 for 第58章 should be normalized before persistence."""
    from agent.tools.mcp_tools import ToolContext
    from models import File, Project, User

    suffix = uuid4().hex[:8]
    user = User(
        email=f"mcp-tools-order-fix-{suffix}@example.com",
        username=f"mcp_tools_order_fix_{suffix}",
        hashed_password="hashed",
        email_verified=True,
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    project = Project(
        name=f"MCP Tools Order Fix Project {suffix}",
        owner_id=user.id,
        project_type="novel",
    )
    db_session.add(project)
    db_session.commit()
    db_session.refresh(project)

    folder = File(
        project_id=project.id,
        title="正文",
        file_type="folder",
        order=0,
    )
    db_session.add(folder)
    db_session.commit()
    db_session.refresh(folder)

    ToolContext.set_context(
        session=db_session,
        user_id=user.id,
        project_id=project.id,
        session_id="sess-order-fix",
    )
    try:
        result = await create_file({
            "title": "第58章 真相",
            "file_type": "draft",
            "parent_id": folder.id,
            "order": 580,
            "content": "content",
        })
    finally:
        ToolContext.clear_context()

    payload = _parse_payload(result)
    assert payload["status"] == "success"
    assert payload["data"]["title"] == "第58章 真相"
    assert payload["data"]["order"] == 58


@pytest.mark.asyncio
@pytest.mark.unit
async def test_create_file_prefers_title_sequence_over_explicit_order_for_chapter_files(db_session):
    """Chapter-like draft/outline/script files should ignore conflicting explicit order."""
    from agent.tools.mcp_tools import ToolContext
    from models import File, Project, User

    suffix = uuid4().hex[:8]
    user = User(
        email=f"mcp-tools-order-lock-{suffix}@example.com",
        username=f"mcp_tools_order_lock_{suffix}",
        hashed_password="hashed",
        email_verified=True,
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    project = Project(
        name=f"MCP Tools Order Lock Project {suffix}",
        owner_id=user.id,
        project_type="novel",
    )
    db_session.add(project)
    db_session.commit()
    db_session.refresh(project)

    folder = File(
        project_id=project.id,
        title="正文",
        file_type="folder",
        order=0,
    )
    db_session.add(folder)
    db_session.commit()
    db_session.refresh(folder)

    ToolContext.set_context(
        session=db_session,
        user_id=user.id,
        project_id=project.id,
        session_id="sess-order-lock",
    )
    try:
        result = await create_file({
            "title": "第58章 真相",
            "file_type": "draft",
            "parent_id": folder.id,
            "order": 1,
            "content": "content",
        })
    finally:
        ToolContext.clear_context()

    payload = _parse_payload(result)
    assert payload["status"] == "success"
    assert payload["data"]["title"] == "第58章 真相"
    assert payload["data"]["order"] == 58


@pytest.mark.asyncio
@pytest.mark.unit
async def test_handoff_to_agent_rejects_legacy_reviewer_alias():
    """Legacy reviewer alias should no longer be accepted."""
    result = await handoff_to_agent({
        "target_agent": "reviewer",
        "reason": "legacy alias",
    })

    payload = _parse_payload(result)
    assert payload["status"] == "error"
    assert "Invalid target_agent" in payload["error"]


@pytest.mark.asyncio
@pytest.mark.unit
async def test_handoff_to_agent_rejects_case_insensitive_reviewer_alias():
    """Reviewer alias should be rejected even with mixed case input."""
    result = await handoff_to_agent({
        "target_agent": "Reviewer",
        "reason": "legacy alias with mixed case",
    })

    payload = _parse_payload(result)
    assert payload["status"] == "error"
    assert "Invalid target_agent" in payload["error"]


@pytest.mark.asyncio
@pytest.mark.unit
async def test_handoff_to_agent_keeps_artifact_refs():
    result = await handoff_to_agent({
        "target_agent": "writer",
        "reason": "继续创作",
        "artifact_refs": ["file-1", "  ", "file-2"],
    })

    payload = _parse_payload(result)
    assert payload["status"] == "handoff"
    assert payload["artifact_refs"] == ["file-1", "file-2"]


@pytest.mark.asyncio
@pytest.mark.unit
async def test_handoff_to_agent_defaults_context_to_reason_when_missing():
    """Context is required downstream; tool should fall back to reason when omitted."""
    result = await handoff_to_agent({
        "target_agent": "quality_reviewer",
        "reason": "内容已完成，请进行质量检查",
        "context": "   ",
    })

    payload = _parse_payload(result)
    assert payload["status"] == "handoff"
    assert payload["context"] == "内容已完成，请进行质量检查"


@pytest.mark.asyncio
@pytest.mark.unit
async def test_handoff_to_agent_generates_context_when_both_reason_and_context_missing():
    """Even empty handoff packets should carry a stable handoff context string."""
    result = await handoff_to_agent({
        "target_agent": "quality_reviewer",
        "reason": " ",
        "context": "",
    })

    payload = _parse_payload(result)
    assert payload["status"] == "handoff"
    assert payload["context"]
    assert "quality_reviewer" in payload["context"]


@pytest.mark.asyncio
@pytest.mark.unit
async def test_handoff_to_agent_merges_recent_ledger_refs():
    with patch(
        "agent.tools.mcp_tools.ToolContext._get_context",
        return_value={"project_id": "proj-1", "session_id": "sess-1"},
    ), patch(
        "agent.tools.mcp_tools._load_recent_artifact_refs_for_handoff",
        return_value=["file-a", "file-b"],
    ):
        result = await handoff_to_agent({
            "target_agent": "writer",
            "reason": "继续",
            "artifact_refs": ["file-b", "file-c"],
        })

    payload = _parse_payload(result)
    assert payload["status"] == "handoff"
    assert payload["artifact_refs"] == ["file-b", "file-c", "file-a"]


@pytest.mark.asyncio
@pytest.mark.unit
async def test_handoff_to_agent_backfills_overflow_refs_into_context():
    overflow_ref = "tool_result_overflow:abc123"
    with patch(
        "agent.tools.mcp_tools.ToolContext._get_context",
        return_value={"project_id": "proj-1", "session_id": "sess-1"},
    ), patch(
        "agent.tools.mcp_tools._load_recent_artifact_refs_for_handoff",
        return_value=[overflow_ref],
    ), patch(
        "agent.tools.mcp_tools._load_tool_result_overflow_entry",
        return_value={
            "overflow_ref": overflow_ref,
            "tool_name": "query_files",
            "status": "success",
            "original_length": 4096,
            "serialized_payload": '{"status":"success","data":"..."}',
        },
    ):
        result = await handoff_to_agent({
            "target_agent": "writer",
            "reason": "继续",
            "context": "已完成检索",
        })

    payload = _parse_payload(result)
    assert payload["status"] == "handoff"
    assert payload["artifact_refs"] == [overflow_ref]
    assert "[工具外溢引用回填]" in payload["context"]
    assert overflow_ref in payload["context"]
    assert payload["overflow_backfill"][0]["overflow_ref"] == overflow_ref


@pytest.mark.unit
def test_load_recent_artifact_refs_for_handoff_filters_out_compaction_summary(db_session):
    from agent.tools import mcp_tools
    from models import AgentArtifactLedger, ChatSession, Project, User

    suffix = uuid4().hex[:8]
    user = User(
        email=f"mcp-tools-{suffix}@example.com",
        username=f"mcp_tools_{suffix}",
        hashed_password="hashed",
        name="MCP Tools Test User",
        email_verified=True,
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    project = Project(
        name=f"MCP Tools Project {suffix}",
        owner_id=user.id,
        project_type="novel",
    )
    db_session.add(project)
    db_session.commit()
    db_session.refresh(project)

    chat_session = ChatSession(
        user_id=user.id,
        project_id=project.id,
        title="MCP Tools Test Chat",
        is_active=True,
        message_count=0,
    )
    db_session.add(chat_session)
    db_session.commit()
    db_session.refresh(chat_session)

    base_time = datetime.utcnow()
    db_session.add(
        AgentArtifactLedger(
            project_id=project.id,
            session_id=chat_session.id,
            user_id=user.id,
            action="create_file",
            tool_name="create_file",
            artifact_ref="file-1",
            created_at=base_time - timedelta(seconds=2),
        )
    )
    db_session.add(
        AgentArtifactLedger(
            project_id=project.id,
            session_id=chat_session.id,
            user_id=user.id,
            action="compaction_summary",
            tool_name="context_compaction",
            artifact_ref=f"compaction:{chat_session.id}",
            payload=json.dumps({"summary": "checkpoint"}),
            created_at=base_time,
        )
    )
    db_session.add(
        AgentArtifactLedger(
            project_id=project.id,
            session_id=chat_session.id,
            user_id=user.id,
            action="edit_file",
            tool_name="edit_file",
            artifact_ref="file-2",
            created_at=base_time - timedelta(seconds=1),
        )
    )
    db_session.commit()

    with patch("agent.tools.mcp_tools._get_ledger_session", return_value=(db_session, False)):
        refs = mcp_tools._load_recent_artifact_refs_for_handoff(
            project_id=project.id,
            session_id=chat_session.id,
            limit=10,
        )

    assert refs == ["file-2", "file-1"]


@pytest.mark.unit
def test_load_tool_result_overflow_entry_returns_payload(db_session):
    from agent.tools import mcp_tools
    from models import AgentArtifactLedger, ChatSession, Project, User

    suffix = uuid4().hex[:8]
    user = User(
        email=f"overflow-ref-{suffix}@example.com",
        username=f"overflow_ref_{suffix}",
        hashed_password="hashed",
        name="Overflow Ref User",
        email_verified=True,
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    project = Project(
        name=f"Overflow Ref Project {suffix}",
        owner_id=user.id,
        project_type="novel",
    )
    db_session.add(project)
    db_session.commit()
    db_session.refresh(project)

    chat_session = ChatSession(
        user_id=user.id,
        project_id=project.id,
        title="Overflow Ref Chat",
        is_active=True,
        message_count=0,
    )
    db_session.add(chat_session)
    db_session.commit()
    db_session.refresh(chat_session)

    overflow_ref = "tool_result_overflow:test-ref"
    db_session.add(
        AgentArtifactLedger(
            project_id=project.id,
            session_id=chat_session.id,
            user_id=user.id,
            action="tool_result_overflow",
            tool_name="query_files",
            artifact_ref=overflow_ref,
            payload=json.dumps(
                {
                    "schema_version": 1,
                    "status": "success",
                    "tool_name": "query_files",
                    "original_length": 3210,
                    "serialized_payload": '{"status":"success","data":"large"}',
                },
                ensure_ascii=False,
            ),
        )
    )
    db_session.commit()

    with patch("agent.tools.mcp_tools._get_ledger_session", return_value=(db_session, False)), patch(
        "agent.tools.mcp_tools.ToolContext._get_context",
        return_value={"project_id": project.id, "session_id": chat_session.id},
    ):
        entry = mcp_tools._load_tool_result_overflow_entry(overflow_ref)

    assert entry is not None
    assert entry["overflow_ref"] == overflow_ref
    assert entry["tool_name"] == "query_files"
    assert entry["status"] == "success"
    assert entry["original_length"] == 3210
    assert entry["serialized_payload"] == '{"status":"success","data":"large"}'


@pytest.mark.asyncio
@pytest.mark.unit
async def test_handoff_to_agent_rejects_self_handoff():
    with patch(
        "agent.tools.mcp_tools.ToolContext._get_context",
        return_value={"current_agent": "writer"},
    ):
        result = await handoff_to_agent({
            "target_agent": "writer",
            "reason": "self",
        })

    payload = _parse_payload(result)
    assert payload["status"] == "error"
    assert "Self handoff is not allowed" in payload["error"]


@pytest.mark.asyncio
@pytest.mark.unit
async def test_edit_file_forwards_continue_on_error():
    mock_executor = MagicMock()
    mock_executor.edit_file.return_value = {"id": "f-1", "edits_applied": 1}

    with patch("agent.tools.mcp_tools.ToolContext.get_executor", return_value=mock_executor):
        result = await edit_file({
            "id": "f-1",
            "edits": [{"op": "append", "text": "x"}],
            "continue_on_error": True,
        })

    payload = _parse_payload(result)
    assert payload["status"] == "success"
    mock_executor.edit_file.assert_called_once_with(
        id="f-1",
        edits=[{"op": "append", "text": "x"}],
        continue_on_error=True,
    )


@pytest.mark.asyncio
@pytest.mark.unit
async def test_edit_file_accepts_file_id_alias():
    """Backward compatibility: accept file_id as an alias for id."""
    mock_executor = MagicMock()
    mock_executor.edit_file.return_value = {"id": "f-1", "edits_applied": 1}

    with patch("agent.tools.mcp_tools.ToolContext.get_executor", return_value=mock_executor):
        result = await edit_file({
            "file_id": "f-1",
            "edits": [{"op": "append", "text": "x"}],
        })

    payload = _parse_payload(result)
    assert payload["status"] == "success"
    mock_executor.edit_file.assert_called_once_with(
        id="f-1",
        edits=[{"op": "append", "text": "x"}],
        continue_on_error=False,
    )


@pytest.mark.asyncio
@pytest.mark.unit
async def test_create_file_records_artifact_ledger_on_success():
    mock_executor = MagicMock()
    mock_executor.create_file.return_value = {
        "id": "f-1",
        "title": "chapter1",
        "file_type": "draft",
    }

    with patch("agent.tools.mcp_tools.ToolContext.get_executor", return_value=mock_executor), patch(
        "agent.tools.mcp_tools.ToolContext._get_context",
        return_value={"project_id": "proj-1", "session_id": "sess-1"},
    ), patch("agent.tools.mcp_tools._record_artifact_ledger") as mock_record:
        result = await create_file({
            "title": "chapter1",
            "file_type": "draft",
            "content": "正文",
        })

    payload = _parse_payload(result)
    assert payload["status"] == "success"
    mock_record.assert_called_once()
    kwargs = mock_record.call_args.kwargs
    assert kwargs["action"] == "create_file"
    assert kwargs["tool_name"] == "create_file"
    assert kwargs["artifact_refs"] == ["f-1"]


@pytest.mark.asyncio
@pytest.mark.unit
async def test_tool_result_payload_is_truncated_when_exceeding_limit():
    mock_executor = MagicMock()
    mock_executor.edit_file.return_value = {
        "id": "f-1",
        "content": "x" * 2000,
    }

    with patch("agent.tools.mcp_tools.ToolContext.get_executor", return_value=mock_executor), patch(
        "agent.tools.mcp_tools.TOOL_RESULT_MAX_CHARS",
        180,
    ):
        result = await edit_file({
            "id": "f-1",
            "edits": [{"op": "append", "text": "x"}],
        })

    payload = _parse_payload(result)
    assert payload["status"] == "success"
    assert payload["truncated"] is True
    assert payload["max_chars"] == 180
    assert payload["original_length"] > 180
    assert payload["data"]["truncated"] is True


@pytest.mark.asyncio
@pytest.mark.unit
async def test_tool_result_payload_persists_overflow_ref_when_ledger_available():
    mock_executor = MagicMock()
    mock_executor.edit_file.return_value = {
        "id": "f-1",
        "content": "x" * 2000,
    }

    def _record_side_effect(**_kwargs):
        return True

    with patch("agent.tools.mcp_tools.ToolContext.get_executor", return_value=mock_executor), patch(
        "agent.tools.mcp_tools.ToolContext._get_context",
        return_value={"project_id": "proj-1", "session_id": "sess-1"},
    ), patch(
        "agent.tools.mcp_tools.TOOL_RESULT_MAX_CHARS",
        180,
    ), patch(
        "agent.tools.mcp_tools._record_artifact_ledger",
        side_effect=_record_side_effect,
    ) as mock_record:
        result = await edit_file({
            "id": "f-1",
            "edits": [{"op": "append", "text": "x"}],
        })

    payload = _parse_payload(result)
    assert payload["status"] == "success"
    assert payload["truncated"] is True
    assert payload["overflow_ref"].startswith("tool_result_overflow:")

    overflow_calls = [
        call.kwargs for call in mock_record.call_args_list if call.kwargs.get("action") == "tool_result_overflow"
    ]
    assert len(overflow_calls) == 1
    overflow_call = overflow_calls[0]
    assert overflow_call["tool_name"] == "edit_file"
    assert overflow_call["artifact_refs"] == [payload["overflow_ref"]]
    assert overflow_call["payload"]["schema_version"] == 1
    assert overflow_call["payload"]["original_length"] > 180


@pytest.mark.asyncio
@pytest.mark.unit
async def test_tool_result_payload_drops_overflow_ref_when_ledger_persist_fails():
    mock_executor = MagicMock()
    mock_executor.edit_file.return_value = {
        "id": "f-1",
        "content": "x" * 2000,
    }

    def _record_side_effect(**kwargs):
        if kwargs.get("action") == "tool_result_overflow":
            return False
        return True

    with patch("agent.tools.mcp_tools.ToolContext.get_executor", return_value=mock_executor), patch(
        "agent.tools.mcp_tools.ToolContext._get_context",
        return_value={"project_id": "proj-1", "session_id": "sess-1"},
    ), patch(
        "agent.tools.mcp_tools.TOOL_RESULT_MAX_CHARS",
        180,
    ), patch(
        "agent.tools.mcp_tools._record_artifact_ledger",
        side_effect=_record_side_effect,
    ):
        result = await edit_file({
            "id": "f-1",
            "edits": [{"op": "append", "text": "x"}],
        })

    payload = _parse_payload(result)
    assert payload["status"] == "success"
    assert payload["truncated"] is True
    assert "overflow_ref" not in payload


@pytest.mark.asyncio
@pytest.mark.unit
async def test_tool_error_payload_is_truncated_when_exceeding_limit():
    mock_executor = MagicMock()
    mock_executor.edit_file.side_effect = ValueError("boom-" + ("x" * 2000))

    with patch("agent.tools.mcp_tools.ToolContext.get_executor", return_value=mock_executor), patch(
        "agent.tools.mcp_tools.TOOL_RESULT_MAX_CHARS",
        180,
    ):
        result = await edit_file({
            "id": "f-1",
            "edits": [{"op": "append", "text": "x"}],
        })

    payload = _parse_payload(result)
    assert payload["status"] == "error"
    assert payload["truncated"] is True
    assert payload["max_chars"] == 180
    assert payload["original_length"] > 180


@pytest.mark.asyncio
@pytest.mark.unit
async def test_query_files_forwards_new_wrapper_params():
    mock_executor = MagicMock()
    mock_executor.query_files.return_value = [{"id": "f-1"}]

    with patch("agent.tools.mcp_tools.ToolContext.get_executor", return_value=mock_executor), patch(
        "agent.tools.mcp_tools.ToolContext._get_context",
        return_value={"project_id": "proj-1"},
    ):
        result = await query_files({
            "query": "chapter",
            "response_mode": "summary",
            "content_preview_chars": 120,
            "include_content": False,
        })

    payload = _parse_payload(result)
    assert payload["status"] == "success"
    mock_executor.query_files.assert_called_once_with(
        project_id="proj-1",
        query="chapter",
        file_type=None,
        file_types=None,
        parent_id=None,
        metadata_filter=None,
        limit=50,
        offset=0,
        response_mode="summary",
        content_preview_chars=120,
        include_content=False,
    )


@pytest.mark.asyncio
@pytest.mark.unit
async def test_query_files_falls_back_for_legacy_executor_signature():
    calls: list[dict] = []

    def _legacy_query_files(**kwargs):
        calls.append(dict(kwargs))
        if "response_mode" in kwargs:
            raise TypeError("query_files() got an unexpected keyword argument 'response_mode'")
        return [{"id": "f-legacy"}]

    mock_executor = MagicMock()
    mock_executor.query_files.side_effect = _legacy_query_files

    with patch("agent.tools.mcp_tools.ToolContext.get_executor", return_value=mock_executor), patch(
        "agent.tools.mcp_tools.ToolContext._get_context",
        return_value={"project_id": "proj-1"},
    ):
        result = await query_files({
            "query": "chapter",
            "response_mode": "full",
            "content_preview_chars": 500,
            "include_content": True,
        })

    payload = _parse_payload(result)
    assert payload["status"] == "success"
    assert len(calls) == 2
    assert "response_mode" in calls[0]
    assert "response_mode" not in calls[1]
    assert calls[1]["project_id"] == "proj-1"


@pytest.mark.asyncio
@pytest.mark.unit
async def test_hybrid_search_forwards_args_to_executor():
    mock_executor = MagicMock()
    mock_executor.hybrid_search.return_value = {
        "query": "hero",
        "result_count": 1,
        "results": [{"entity_id": "f-1", "fused_score": 0.88}],
    }

    with patch("agent.tools.mcp_tools.ToolContext.get_executor", return_value=mock_executor), patch(
        "agent.tools.mcp_tools.ToolContext._get_context",
        return_value={"project_id": "proj-1"},
    ):
        result = await hybrid_search({
            "query": "hero",
            "top_k": 5,
            "entity_types": ["draft"],
            "min_score": 0.2,
        })

    payload = _parse_payload(result)
    assert payload["status"] == "success"
    assert payload["data"]["result_count"] == 1
    mock_executor.hybrid_search.assert_called_once_with(
        project_id="proj-1",
        query="hero",
        top_k=5,
        entity_types=["draft"],
        min_score=0.2,
    )


@pytest.mark.asyncio
@pytest.mark.unit
async def test_hybrid_search_executor_failure_returns_error():
    """When executor.hybrid_search raises, tool returns error with structured log."""
    mock_executor = MagicMock()
    mock_executor.hybrid_search.side_effect = RuntimeError("vector infra down")

    with patch("agent.tools.mcp_tools.ToolContext.get_executor", return_value=mock_executor), patch(
        "agent.tools.mcp_tools.ToolContext._get_context",
        return_value={"project_id": "proj-1"},
    ), patch("agent.tools.mcp_tools.log_with_context") as mock_log:
        result = await hybrid_search({"query": "hero", "top_k": 5})

    payload = _parse_payload(result)
    assert payload["status"] == "error"
    mock_executor.hybrid_search.assert_called_once()
    mock_log.assert_called_once()
    assert mock_log.call_args.args[2] == "Agent hybrid_search failed"


@pytest.mark.asyncio
@pytest.mark.unit
@pytest.mark.parametrize(
    ("tool_func", "sync_helper", "args"),
    [
        (create_file, "_create_file_sync", {"title": "T", "file_type": "draft"}),
        (edit_file, "_edit_file_sync", {"id": "file-1", "edits": []}),
        (delete_file, "_delete_file_sync", {"id": "file-1"}),
        (query_files, "_query_files_sync", {"query": "hero"}),
        (hybrid_search, "_hybrid_search_sync", {"query": "hero"}),
        (update_project, "_update_project_sync", {"tasks": []}),
    ],
)
async def test_offloaded_wrappers_cleanup_owned_session(tool_func, sync_helper, args):
    """PostgreSQL offloaded wrappers should deterministically close ToolContext-owned sessions."""

    async def _run_inline(func, *call_args):
        return func(*call_args)

    with (
        patch("agent.tools.mcp_tools._should_offload_tool_execution", return_value=True),
        patch("agent.tools.mcp_tools.asyncio.to_thread", side_effect=_run_inline) as mock_to_thread,
        patch(
            f"agent.tools.mcp_tools.{sync_helper}",
            return_value={"content": [{"type": "text", "text": '{"status":"success"}'}]},
        ) as mock_sync,
        patch("agent.tools.mcp_tools.ToolContext._cleanup_owned_session") as mock_cleanup,
    ):
        result = await tool_func(args)

    assert _parse_payload(result)["status"] == "success"
    mock_to_thread.assert_called_once()
    mock_sync.assert_called_once_with(args)
    mock_cleanup.assert_called_once()


@pytest.mark.unit
def test_record_artifact_ledger_rolls_back_on_commit_error():
    from agent.tools import mcp_tools

    mock_session = MagicMock()
    mock_session.commit.side_effect = RuntimeError("db write failed")

    class DummyLedger:
        def __init__(self, **_kwargs):
            pass

    with patch("agent.tools.mcp_tools._get_ledger_session", return_value=(mock_session, False)), patch(
        "agent.tools.mcp_tools.ToolContext._get_context",
        return_value={"project_id": "proj-1", "session_id": "sess-1", "user_id": "user-1"},
    ), patch("models.AgentArtifactLedger", DummyLedger):
        mcp_tools._record_artifact_ledger(
            action="create_file",
            tool_name="create_file",
            artifact_refs=["file-1"],
            payload={"title": "chapter1"},
        )

    mock_session.rollback.assert_called_once()


@pytest.mark.asyncio
@pytest.mark.unit
async def test_request_clarification_returns_structured_payload():
    result = await request_clarification({
        "question": "请确认主角姓名",
        "context": "已完成大纲第一章",
        "details": ["主角姓名", "时代背景"],
    })

    payload = _parse_payload(result)
    assert payload["status"] == "clarification_needed"
    assert payload["question"] == "请确认主角姓名"
    assert payload["context"] == "已完成大纲第一章"
    assert payload["details"] == ["主角姓名", "时代背景"]


@pytest.mark.asyncio
@pytest.mark.unit
async def test_request_clarification_requires_question():
    result = await request_clarification({
        "question": "   ",
        "context": "任意上下文",
    })

    payload = _parse_payload(result)
    assert payload["status"] == "error"
    assert "question is required" in payload["error"]
