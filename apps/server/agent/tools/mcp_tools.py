"""
Tool execution functions for zenstory Agent.

Defines tool functions that can be called by the Claude adapter.
"""

import asyncio
import contextlib
import contextvars
import json
import os
import re
from collections.abc import Callable
from typing import Any
from uuid import uuid4

from sqlalchemy import desc
from sqlmodel import Session, and_, select

from agent.tools.file_ops import FileToolExecutor
from utils.logger import get_logger, log_with_context
from utils.title_sequence import extract_chapter_like_sequence_number, parse_chinese_number

logger = get_logger(__name__)

DEFAULT_TOOL_RESULT_MAX_CHARS = 200_000
MIN_TOOL_RESULT_MAX_CHARS = 512
TOOL_RESULT_OVERFLOW_ACTION = "tool_result_overflow"
TOOL_RESULT_OVERFLOW_REF_PREFIX = "tool_result_overflow"
TOOL_RESULT_OVERFLOW_SCHEMA_VERSION = 1
TOOL_RESULT_OVERFLOW_PREVIEW_CHARS = 180
TOOL_RESULT_OVERFLOW_BACKFILL_LIMIT = 3
STANDARD_HANDOFF_ARTIFACT_ACTIONS = (
    "create_file",
    "edit_file",
    "delete_file",
    "update_project",
)

PROJECT_STATUS_FIELD_ALIASES: dict[str, str] = {
    "currentPhase": "current_phase",
    "writingStyle": "writing_style",
    "projectSummary": "summary",
}


def _should_offload_tool_execution() -> bool:
    """Only offload tool DB work when running against PostgreSQL production-style infra."""
    from database import is_postgres

    return is_postgres


def _is_hybrid_search_tool_enabled() -> bool:
    """Temporary kill switch for agent-side hybrid search calls."""
    raw = os.getenv("AGENT_TOOL_HYBRID_SEARCH_ENABLED")
    if raw is None:
        return True
    return raw.strip().lower() not in {"0", "false", "no", "off"}


def _run_sync_tool_with_owned_session_cleanup(
    sync_func: Callable[[dict[str, Any]], dict[str, Any]],
    args: dict[str, Any],
) -> dict[str, Any]:
    """
    Run a sync tool helper and deterministically close any ToolContext-owned session.

    When PostgreSQL-mode tool calls are offloaded with ``asyncio.to_thread()``,
    ``ToolContext.get_session()`` may lazily create a session inside the worker
    thread. That worker context is separate from the main request context, so the
    normal ``ToolContext.clear_context()`` in the caller does not guarantee the
    thread-owned session is closed immediately. Close it here to avoid relying on
    GC timing for connection release.
    """
    try:
        return sync_func(args)
    finally:
        ToolContext._cleanup_owned_session()


def _get_tool_result_max_chars() -> int:
    """Read tool-result max chars limit from env with safe fallback."""
    raw = os.getenv("AGENT_TOOL_RESULT_MAX_CHARS")
    if raw is None:
        return DEFAULT_TOOL_RESULT_MAX_CHARS
    try:
        value = int(raw)
    except ValueError:
        return DEFAULT_TOOL_RESULT_MAX_CHARS
    return value if value >= MIN_TOOL_RESULT_MAX_CHARS else DEFAULT_TOOL_RESULT_MAX_CHARS


TOOL_RESULT_MAX_CHARS = _get_tool_result_max_chars()
DEFAULT_ARTIFACT_REF_LOOKBACK = 20

# 请求级别的上下文变量
# Note: Using None as default to avoid mutable default argument (B039)
_tool_context_var: contextvars.ContextVar[dict[str, Any] | None] = contextvars.ContextVar(
    'tool_context', default=None
)
_owned_session_var: contextvars.ContextVar[Session | None] = contextvars.ContextVar(
    'owned_session', default=None
)
_pending_empty_file_var: contextvars.ContextVar[dict[str, str] | None] = contextvars.ContextVar(
    'pending_empty_file', default=None
)


class ToolContext:
    """
    Holds session and user_id for tool execution.

    Uses contextvars for request-level isolation in async environments.
    Each concurrent request gets its own isolated context.
    """

    @classmethod
    def set_context(
        cls,
        session: Session | None,
        user_id: str | None,
        project_id: str,
        session_id: str | None,
        create_session_func: Callable[[], Session] | None = None,
        current_agent: str | None = None,
    ) -> None:
        """Set the execution context for tools (request-scoped)."""
        cls._cleanup_owned_session()
        _tool_context_var.set({
            "session": session,
            "user_id": user_id,
            "project_id": project_id,
            "session_id": session_id,
            "create_session_func": create_session_func,
            "current_agent": current_agent,
        })
        _owned_session_var.set(None)
        _pending_empty_file_var.set(None)

    @classmethod
    def _get_context(cls) -> dict[str, Any]:
        """Get current request's context."""
        context = _tool_context_var.get()
        return context if context is not None else {}

    @classmethod
    def get_session(cls) -> Session:
        """Get session, creating one if needed."""
        context = cls._get_context()
        if context.get("session"):
            return context["session"]

        owned = _owned_session_var.get()
        if owned is not None:
            return owned

        create_func = context.get("create_session_func")
        if create_func:
            new_session = create_func()
            _owned_session_var.set(new_session)
            return new_session

        raise RuntimeError("No session available in ToolContext")

    @classmethod
    def get_session_id(cls) -> str | None:
        """Get current request session_id."""
        context = cls._get_context()
        session_id = context.get("session_id")
        return session_id if isinstance(session_id, str) and session_id else None

    @classmethod
    def get_user_id(cls) -> str | None:
        """Get current request user_id."""
        context = cls._get_context()
        user_id = context.get("user_id")
        return user_id if isinstance(user_id, str) and user_id else None

    @classmethod
    def get_project_id(cls) -> str | None:
        """Get current request project_id."""
        context = cls._get_context()
        project_id = context.get("project_id")
        return project_id if isinstance(project_id, str) and project_id else None

    @classmethod
    def get_current_agent(cls) -> str | None:
        """Get current agent type bound to tool execution context."""
        context = cls._get_context()
        current_agent = context.get("current_agent")
        return current_agent if isinstance(current_agent, str) and current_agent else None

    @classmethod
    def set_current_agent(cls, current_agent: str | None) -> None:
        """Update current agent in request-scoped context."""
        context = cls._get_context()
        if not context:
            return
        next_context = dict(context)
        if isinstance(current_agent, str) and current_agent:
            next_context["current_agent"] = current_agent
        else:
            next_context.pop("current_agent", None)
        _tool_context_var.set(next_context)

    @classmethod
    def _cleanup_owned_session(cls) -> None:
        """Clean up owned session if exists."""
        owned = _owned_session_var.get()
        if owned is not None:
            try:
                owned.close()
            except Exception as e:
                logger.debug(f"Error closing owned session: {e}")
            _owned_session_var.set(None)

    @classmethod
    def clear_context(cls) -> None:
        """Clear context and clean up owned session."""
        cls._cleanup_owned_session()
        _tool_context_var.set(None)
        _pending_empty_file_var.set(None)

    @classmethod
    def set_pending_empty_file(cls, file_id: str, title: str) -> None:
        """标记有一个空文件等待流式写入。"""
        _pending_empty_file_var.set({"file_id": file_id, "title": title})

    @classmethod
    def clear_pending_empty_file(cls) -> None:
        """清除待写入文件标记。"""
        _pending_empty_file_var.set(None)

    @classmethod
    def has_pending_empty_file(cls) -> bool:
        """检查是否有待写入的空文件。"""
        return _pending_empty_file_var.get() is not None

    @classmethod
    def get_pending_empty_file(cls) -> dict[str, str] | None:
        """获取待写入的空文件信息。"""
        return _pending_empty_file_var.get()

    @classmethod
    def get_executor(cls) -> FileToolExecutor:
        """Get a FileToolExecutor with current context."""
        session = cls.get_session()
        context = cls._get_context()
        user_id = context.get("user_id")
        return FileToolExecutor(session, user_id)

    @classmethod
    def refresh_file_inventory(cls) -> dict[str, list[dict[str, Any]]] | None:
        """刷新文件清单，用于 handoff 时获取最新文件列表。"""
        context = cls._get_context()
        project_id = context.get("project_id")
        if project_id is None:
            return None

        session = cls.get_session()

        from sqlmodel import select

        from models import File

        inventory: dict[str, list[dict[str, Any]]] = {
            "outline": [],
            "draft": [],
            "character": [],
            "lore": [],
            "snippet": [],
        }

        files = session.exec(
            select(File).where(
                File.project_id == project_id,
                File.file_type != "folder",
                File.is_deleted.is_(False),
            ).order_by(File.order.asc())
        ).all()

        for file in files:
            if file.file_type in inventory:
                word_count = (
                    len(file.content)
                    if file.file_type == "draft" and file.content
                    else None
                )
                inventory[file.file_type].append({
                    "id": file.id,
                    "title": file.title,
                    "word_count": word_count,
                })

        return inventory


def _make_result(data: Any, *, tool_name: str | None = None) -> dict[str, Any]:
    """Create a tool result in MCP format."""
    return _make_mcp_payload(data, tool_name=tool_name)


def _make_error(error: str, *, tool_name: str | None = None) -> dict[str, Any]:
    """Create an error result in MCP format."""
    return _make_mcp_payload({"status": "error", "error": error}, tool_name=tool_name)


def _make_mcp_payload(payload: Any, *, tool_name: str | None = None) -> dict[str, Any]:
    """Create MCP payload with unified size guardrail."""
    text = _serialize_tool_payload(payload, tool_name=tool_name)
    return {
        "content": [{
            "type": "text",
            "text": text,
        }]
    }


def _normalize_payload_status(payload: Any) -> str:
    """Infer normalized status from tool payload."""
    status = "success"
    if isinstance(payload, dict):
        raw_status = payload.get("status")
        if isinstance(raw_status, str) and raw_status:
            status = raw_status
        elif "error" in payload:
            status = "error"
    return status


def _normalize_tool_name(tool_name: str | None) -> str:
    """Normalize tool name for storage metadata."""
    normalized = str(tool_name or "").strip()
    return normalized or "unknown_tool"


def _persist_tool_result_overflow(
    *,
    tool_name: str | None,
    status: str,
    serialized_payload: str,
) -> str | None:
    """Persist oversized tool payload into artifact ledger and return overflow ref."""
    overflow_ref = f"{TOOL_RESULT_OVERFLOW_REF_PREFIX}:{uuid4().hex}"
    stored = _record_artifact_ledger(
        action=TOOL_RESULT_OVERFLOW_ACTION,
        tool_name=_normalize_tool_name(tool_name),
        artifact_refs=[overflow_ref],
        payload={
            "schema_version": TOOL_RESULT_OVERFLOW_SCHEMA_VERSION,
            "status": str(status),
            "tool_name": _normalize_tool_name(tool_name),
            "original_length": len(serialized_payload),
            "serialized_payload": serialized_payload,
        },
    )
    return overflow_ref if stored else None


def _serialize_tool_payload(payload: Any, *, tool_name: str | None = None) -> str:
    """Serialize tool payload and truncate oversized results safely."""
    serialized = json.dumps(payload, ensure_ascii=False)
    if len(serialized) <= TOOL_RESULT_MAX_CHARS:
        return serialized

    original_length = len(serialized)
    status = _normalize_payload_status(payload)
    overflow_ref = _persist_tool_result_overflow(
        tool_name=tool_name,
        status=status,
        serialized_payload=serialized,
    )

    truncated_payload: dict[str, Any] = {
        "status": status,
        "truncated": True,
        "max_chars": TOOL_RESULT_MAX_CHARS,
        "original_length": original_length,
    }
    if overflow_ref:
        truncated_payload["overflow_ref"] = overflow_ref

    if status == "error":
        error_message = ""
        if isinstance(payload, dict):
            raw_error = payload.get("error")
            if raw_error is not None:
                error_message = str(raw_error)
        truncated_payload["error"] = error_message or "Tool result exceeded max size and was truncated"
    else:
        truncated_payload["data"] = {
            "truncated": True,
            "max_chars": TOOL_RESULT_MAX_CHARS,
            "original_length": original_length,
        }

    encoded_truncated = json.dumps(truncated_payload, ensure_ascii=False)
    if len(encoded_truncated) <= TOOL_RESULT_MAX_CHARS:
        return encoded_truncated

    if status == "error" and "error" in truncated_payload:
        compact_payload = dict(truncated_payload)
        compact_payload["error"] = str(compact_payload["error"])
        encoded_truncated = json.dumps(compact_payload, ensure_ascii=False)
        while len(encoded_truncated) > TOOL_RESULT_MAX_CHARS and compact_payload["error"]:
            overflow = len(encoded_truncated) - TOOL_RESULT_MAX_CHARS
            trim_count = max(1, overflow)
            compact_payload["error"] = compact_payload["error"][:-trim_count]
            encoded_truncated = json.dumps(compact_payload, ensure_ascii=False)
        if len(encoded_truncated) <= TOOL_RESULT_MAX_CHARS:
            return encoded_truncated

    # Final safety fallback: always return a small valid payload.
    minimal_payload = {
        "status": status,
        "truncated": True,
        "max_chars": TOOL_RESULT_MAX_CHARS,
        "original_length": original_length,
    }
    if overflow_ref:
        minimal_payload["overflow_ref"] = overflow_ref
    if status != "error":
        minimal_payload["data"] = {"truncated": True}
    else:
        minimal_payload["error"] = "Tool result truncated"
    return json.dumps(minimal_payload, ensure_ascii=False)


def _merge_unique_refs(*groups: list[str]) -> list[str]:
    """Merge artifact refs while preserving order and removing duplicates."""
    merged: list[str] = []
    seen: set[str] = set()
    for group in groups:
        for ref in group:
            normalized = str(ref).strip()
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            merged.append(normalized)
    return merged


def _get_ledger_session() -> tuple[Session, bool]:
    """
    Get session for artifact-ledger operations.

    Returns:
        (session, owns_session)
    """
    context = ToolContext._get_context()
    create_func = context.get("create_session_func")
    if callable(create_func):
        return create_func(), True
    return ToolContext.get_session(), False


def _extract_tool_artifact_refs(tool_name: str, args: dict[str, Any], result: Any) -> list[str]:
    """Extract artifact refs from successful tool outputs."""
    refs: list[str] = []

    if tool_name == "create_file" and isinstance(result, dict) or tool_name == "edit_file" and isinstance(result, dict):
        file_id = result.get("id")
        if isinstance(file_id, str):
            refs.append(file_id)
    elif tool_name == "delete_file":
        file_id = args.get("id")
        if isinstance(file_id, str):
            refs.append(file_id)
    elif tool_name == "update_project":
        context = ToolContext._get_context()
        project_id = context.get("project_id")
        if isinstance(project_id, str):
            refs.append(f"project:{project_id}")
        session_id = context.get("session_id")
        if "tasks" in args and isinstance(session_id, str) and session_id.strip():
            refs.append(f"task_board:{session_id.strip()}")

    return _merge_unique_refs(refs)


def _record_artifact_ledger(
    *,
    action: str,
    tool_name: str,
    artifact_refs: list[str],
    payload: Any | None = None,
) -> bool:
    """
    Persist artifact refs for later handoff/compaction recovery.

    Best effort: failures should never break tool success path.
    """
    refs = _merge_unique_refs(artifact_refs)
    if not refs:
        return False

    context = ToolContext._get_context()
    project_id = context.get("project_id")
    if not isinstance(project_id, str) or not project_id.strip():
        return False

    try:
        from models import AgentArtifactLedger
    except Exception:
        return False

    try:
        session, owns_session = _get_ledger_session()
    except Exception:
        return False

    session_id = context.get("session_id") if isinstance(context.get("session_id"), str) else None
    user_id = context.get("user_id") if isinstance(context.get("user_id"), str) else None
    payload_json: str | None = None
    if payload is not None:
        try:
            payload_json = json.dumps(payload, ensure_ascii=False)
        except (TypeError, ValueError):
            payload_json = json.dumps({"raw": str(payload)}, ensure_ascii=False)

    try:
        for artifact_ref in refs:
            session.add(
                AgentArtifactLedger(
                    project_id=project_id,
                    session_id=session_id,
                    user_id=user_id,
                    action=action,
                    tool_name=tool_name,
                    artifact_ref=artifact_ref,
                    payload=payload_json,
                )
            )
        session.commit()
        return True
    except Exception as e:
        with contextlib.suppress(Exception):
            session.rollback()
        logger.warning(
            "Failed to persist agent artifact ledger entry",
            extra={
                "project_id": project_id,
                "tool_name": tool_name,
                "action": action,
                "error": str(e),
            },
        )
        return False
    finally:
        if owns_session:
            with contextlib.suppress(Exception):
                session.close()


def _load_recent_artifact_refs_for_handoff(
    *,
    project_id: str | None,
    session_id: str | None,
    limit: int = DEFAULT_ARTIFACT_REF_LOOKBACK,
) -> list[str]:
    """Load recent artifact refs from ledger for handoff payload enrichment."""
    if not isinstance(project_id, str) or not project_id.strip():
        return []

    try:
        from models import AgentArtifactLedger
    except Exception:
        return []

    try:
        session, owns_session = _get_ledger_session()
    except Exception:
        return []

    resolved_limit = max(1, int(limit or DEFAULT_ARTIFACT_REF_LOOKBACK))
    refs: list[str] = []
    overflow_refs: list[str] = []

    try:
        if isinstance(session_id, str) and session_id.strip():
            scoped_rows = session.exec(
                select(AgentArtifactLedger.artifact_ref)
                .where(
                    and_(
                        AgentArtifactLedger.project_id == project_id,
                        AgentArtifactLedger.session_id == session_id.strip(),
                        AgentArtifactLedger.action.in_(STANDARD_HANDOFF_ARTIFACT_ACTIONS),
                    )
                )
                .order_by(desc(AgentArtifactLedger.created_at))
                .limit(resolved_limit)
            ).all()
            refs = [str(row).strip() for row in scoped_rows if str(row).strip()]

        if not refs:
            fallback_rows = session.exec(
                select(AgentArtifactLedger.artifact_ref)
                .where(
                    and_(
                        AgentArtifactLedger.project_id == project_id,
                        AgentArtifactLedger.action.in_(STANDARD_HANDOFF_ARTIFACT_ACTIONS),
                    )
                )
                .order_by(desc(AgentArtifactLedger.created_at))
                .limit(resolved_limit)
            ).all()
            refs = [str(row).strip() for row in fallback_rows if str(row).strip()]

        overflow_limit = max(1, min(resolved_limit, TOOL_RESULT_OVERFLOW_BACKFILL_LIMIT))
        if isinstance(session_id, str) and session_id.strip():
            overflow_scoped_rows = session.exec(
                select(AgentArtifactLedger.artifact_ref)
                .where(
                    and_(
                        AgentArtifactLedger.project_id == project_id,
                        AgentArtifactLedger.session_id == session_id.strip(),
                        AgentArtifactLedger.action == TOOL_RESULT_OVERFLOW_ACTION,
                    )
                )
                .order_by(desc(AgentArtifactLedger.created_at))
                .limit(overflow_limit)
            ).all()
            overflow_refs = [str(row).strip() for row in overflow_scoped_rows if str(row).strip()]

        if not overflow_refs:
            overflow_fallback_rows = session.exec(
                select(AgentArtifactLedger.artifact_ref)
                .where(
                    and_(
                        AgentArtifactLedger.project_id == project_id,
                        AgentArtifactLedger.action == TOOL_RESULT_OVERFLOW_ACTION,
                    )
                )
                .order_by(desc(AgentArtifactLedger.created_at))
                .limit(overflow_limit)
            ).all()
            overflow_refs = [str(row).strip() for row in overflow_fallback_rows if str(row).strip()]
    except Exception as e:
        with contextlib.suppress(Exception):
            session.rollback()
        logger.warning(
            "Failed to load artifact refs from ledger",
            extra={"project_id": project_id, "session_id": session_id, "error": str(e)},
        )
        return []
    finally:
        if owns_session:
            with contextlib.suppress(Exception):
                session.close()

    return _merge_unique_refs(refs, overflow_refs)


def _load_tool_result_overflow_entry(overflow_ref: str) -> dict[str, Any] | None:
    """Load persisted tool-result overflow payload by ref."""
    normalized_ref = str(overflow_ref).strip()
    if not normalized_ref.startswith(f"{TOOL_RESULT_OVERFLOW_REF_PREFIX}:"):
        return None

    context = ToolContext._get_context()
    project_id = context.get("project_id")
    if not isinstance(project_id, str) or not project_id.strip():
        return None
    project_id = project_id.strip()
    session_id = context.get("session_id") if isinstance(context.get("session_id"), str) else None

    try:
        from models import AgentArtifactLedger
    except Exception:
        return None

    try:
        session, owns_session = _get_ledger_session()
    except Exception:
        return None

    payload_row: str | None = None
    try:
        stmt = (
            select(AgentArtifactLedger.payload)
            .where(
                and_(
                    AgentArtifactLedger.project_id == project_id,
                    AgentArtifactLedger.action == TOOL_RESULT_OVERFLOW_ACTION,
                    AgentArtifactLedger.artifact_ref == normalized_ref,
                )
            )
            .order_by(
                desc(AgentArtifactLedger.created_at),
                desc(AgentArtifactLedger.id),
            )
            .limit(1)
        )
        if isinstance(session_id, str) and session_id.strip():
            stmt = stmt.where(AgentArtifactLedger.session_id == session_id.strip())

        payload_row = session.exec(stmt).first()
    except Exception as e:
        with contextlib.suppress(Exception):
            session.rollback()
        logger.warning(
            "Failed to load tool result overflow entry",
            extra={
                "project_id": project_id,
                "session_id": session_id,
                "overflow_ref": normalized_ref,
                "error": str(e),
            },
        )
        return None
    finally:
        if owns_session:
            with contextlib.suppress(Exception):
                session.close()

    if not isinstance(payload_row, str) or not payload_row.strip():
        return None

    try:
        payload = json.loads(payload_row)
    except (TypeError, json.JSONDecodeError):
        return None

    if not isinstance(payload, dict):
        return None

    schema_version = payload.get("schema_version")
    if schema_version not in (None, TOOL_RESULT_OVERFLOW_SCHEMA_VERSION):
        return None

    serialized_payload = payload.get("serialized_payload")
    if not isinstance(serialized_payload, str):
        return None

    raw_original_length = payload.get("original_length")
    try:
        original_length = int(raw_original_length)
    except (TypeError, ValueError):
        original_length = len(serialized_payload)

    return {
        "overflow_ref": normalized_ref,
        "tool_name": _normalize_tool_name(payload.get("tool_name")),
        "status": str(payload.get("status") or "success"),
        "original_length": original_length,
        "serialized_payload": serialized_payload,
    }


def _build_tool_result_overflow_backfill_entries(
    artifact_refs: list[str],
    *,
    limit: int = TOOL_RESULT_OVERFLOW_BACKFILL_LIMIT,
) -> list[dict[str, Any]]:
    """Resolve overflow refs into lightweight backfill entries."""
    backfills: list[dict[str, Any]] = []
    if not artifact_refs:
        return backfills

    for ref in artifact_refs:
        if len(backfills) >= max(0, int(limit)):
            break
        entry = _load_tool_result_overflow_entry(str(ref))
        if not entry:
            continue
        serialized_payload = entry.get("serialized_payload", "")
        preview = serialized_payload[:TOOL_RESULT_OVERFLOW_PREVIEW_CHARS]
        if len(serialized_payload) > TOOL_RESULT_OVERFLOW_PREVIEW_CHARS:
            preview = f"{preview}..."
        backfills.append({
            "overflow_ref": entry["overflow_ref"],
            "tool_name": entry["tool_name"],
            "status": entry["status"],
            "original_length": entry["original_length"],
            "preview": preview,
        })

    return backfills


def _format_tool_result_overflow_backfill_context(backfills: list[dict[str, Any]]) -> str:
    """Format overflow backfill entries into compact handoff context text."""
    if not backfills:
        return ""

    lines = ["[工具外溢引用回填]"]
    for item in backfills:
        preview = str(item.get("preview", "")).replace("\n", "\\n")
        lines.append(
            "- "
            f"{item.get('overflow_ref', '')} "
            f"(tool={item.get('tool_name', '')}, status={item.get('status', '')}, "
            f"len={item.get('original_length', 0)}): {preview}"
        )
    return "\n".join(lines)


async def create_file(args: dict[str, Any]) -> dict[str, Any]:
    """创建新文件。"""
    if _should_offload_tool_execution():
        return await asyncio.to_thread(_run_sync_tool_with_owned_session_cleanup, _create_file_sync, args)
    return _create_file_sync(args)


def _create_file_sync(args: dict[str, Any]) -> dict[str, Any]:
    """Synchronous create_file implementation."""
    tool_name = "create_file"
    executor = ToolContext.get_executor()
    project_id = ToolContext._get_context().get("project_id")

    if project_id is None:
        return _make_error("project_id not set", tool_name=tool_name)

    content = args.get("content", "")
    title = args.get("title", "")

    # 检查是否已有待写入的空文件（防止连续创建空文件导致内容丢失）
    if not content and ToolContext.has_pending_empty_file():
        pending = ToolContext.get_pending_empty_file()
        pending_title = pending.get("title", "未知") if pending else "未知"
        return _make_error(
            f"请先完成上一个文件「{pending_title}」的内容写入（使用 <file>内容</file> 标记），"
            f"然后再创建新文件「{title}」。一次只能流式写入一个文件。",
            tool_name=tool_name,
        )

    try:
        order_value = args.get("order") if "order" in args else None
        if order_value is not None:
            try:
                order_value = int(order_value)
            except (TypeError, ValueError):
                order_value = None

        result = executor.create_file(
            project_id=project_id,
            title=title,
            file_type=args.get("file_type", "draft"),
            content=content,
            parent_id=args.get("parent_id"),
            order=order_value,
            metadata=args.get("metadata"),
        )

        # 如果创建的是空文件，标记为待写入
        if not content:
            file_id = result.get("id", "")
            if file_id:
                ToolContext.set_pending_empty_file(file_id, title)

        _record_artifact_ledger(
            action=tool_name,
            tool_name=tool_name,
            artifact_refs=_extract_tool_artifact_refs(tool_name, args, result),
            payload={"title": result.get("title"), "file_type": result.get("file_type")},
        )

        return _make_result({"status": "success", "data": result}, tool_name=tool_name)
    except Exception as e:
        return _make_error(str(e), tool_name=tool_name)


async def edit_file(args: dict[str, Any]) -> dict[str, Any]:
    """精确编辑文件内容。"""
    if _should_offload_tool_execution():
        return await asyncio.to_thread(_run_sync_tool_with_owned_session_cleanup, _edit_file_sync, args)
    return _edit_file_sync(args)


def _edit_file_sync(args: dict[str, Any]) -> dict[str, Any]:
    """Synchronous edit_file implementation."""
    tool_name = "edit_file"
    executor = ToolContext.get_executor()

    try:
        file_id_raw = args.get("id") or args.get("file_id") or args.get("fileId")
        if isinstance(file_id_raw, str):
            file_id = file_id_raw.strip()
        elif file_id_raw is None:
            file_id = ""
        else:
            # Do not silently accept non-string IDs; keep tool inputs strict to
            # avoid noisy "file not found" logs when the caller passes wrong types.
            return _make_error(
                "edit_file: invalid param 'id' (must be a string).",
                tool_name=tool_name,
            )
        if not file_id:
            return _make_error(
                "edit_file: missing required param 'id' (alias: file_id). "
                "Please query_files to get the correct id, or use the provided 当前文件 ID.",
                tool_name=tool_name,
            )

        edits = args.get("edits")
        if edits is None:
            edits = args.get("operations", [])
        if not isinstance(edits, list):
            return _make_error(
                "edit_file: invalid param 'edits' (must be an array).",
                tool_name=tool_name,
            )

        result = executor.edit_file(
            id=file_id,
            edits=edits,
            continue_on_error=bool(args.get("continue_on_error", False)),
        )
        _record_artifact_ledger(
            action=tool_name,
            tool_name=tool_name,
            artifact_refs=_extract_tool_artifact_refs(tool_name, args, result),
            payload={"edits_applied": result.get("edits_applied")},
        )
        return _make_result({"status": "success", "data": result}, tool_name=tool_name)
    except Exception as e:
        return _make_error(str(e), tool_name=tool_name)


async def delete_file(args: dict[str, Any]) -> dict[str, Any]:
    """删除文件。"""
    if _should_offload_tool_execution():
        return await asyncio.to_thread(_run_sync_tool_with_owned_session_cleanup, _delete_file_sync, args)
    return _delete_file_sync(args)


def _delete_file_sync(args: dict[str, Any]) -> dict[str, Any]:
    """Synchronous delete_file implementation."""
    tool_name = "delete_file"
    executor = ToolContext.get_executor()

    try:
        result = executor.delete_file(
            id=args.get("id", ""),
            recursive=args.get("recursive", False),
        )
        _record_artifact_ledger(
            action=tool_name,
            tool_name=tool_name,
            artifact_refs=_extract_tool_artifact_refs(tool_name, args, result),
            payload={"recursive": bool(args.get("recursive", False))},
        )
        return _make_result({"status": "success", "data": result}, tool_name=tool_name)
    except Exception as e:
        return _make_error(str(e), tool_name=tool_name)


async def query_files(args: dict[str, Any]) -> dict[str, Any]:
    """查询和搜索项目中的文件。"""
    if _should_offload_tool_execution():
        return await asyncio.to_thread(_run_sync_tool_with_owned_session_cleanup, _query_files_sync, args)
    return _query_files_sync(args)


def _query_files_sync(args: dict[str, Any]) -> dict[str, Any]:
    """Synchronous query_files implementation."""
    tool_name = "query_files"
    executor = ToolContext.get_executor()
    project_id = ToolContext._get_context().get("project_id")

    if project_id is None:
        return _make_error("project_id not set", tool_name=tool_name)

    try:
        query_kwargs: dict[str, Any] = {
            "project_id": project_id,
            "query": args.get("query"),
            "file_type": args.get("file_type"),
            "file_types": args.get("file_types"),
            "parent_id": args.get("parent_id"),
            "metadata_filter": args.get("metadata_filter"),
            "limit": args.get("limit", 50),
            "offset": args.get("offset", 0),
        }

        optional_keys = ("id", "response_mode", "content_preview_chars", "include_content")
        for key in optional_keys:
            if key in args:
                query_kwargs[key] = args.get(key)

        try:
            result = executor.query_files(**query_kwargs)
        except TypeError as exc:
            # Backward compatibility for older executors that don't support new args yet.
            if not _is_query_files_param_mismatch(exc):
                raise
            for key in optional_keys:
                query_kwargs.pop(key, None)
            result = executor.query_files(**query_kwargs)

        return _make_result({"status": "success", "data": result}, tool_name=tool_name)
    except Exception as e:
        return _make_error(str(e), tool_name=tool_name)


def _is_query_files_param_mismatch(exc: TypeError) -> bool:
    """Check if TypeError is due to unsupported query_files kwargs."""
    message = str(exc)
    if "unexpected keyword argument" not in message:
        return False
    return any(param in message for param in ("id", "response_mode", "content_preview_chars", "include_content"))


async def hybrid_search(args: dict[str, Any]) -> dict[str, Any]:
    """混合检索（向量 + 关键词融合）。"""
    if _should_offload_tool_execution():
        return await asyncio.to_thread(_run_sync_tool_with_owned_session_cleanup, _hybrid_search_sync, args)
    return _hybrid_search_sync(args)


def _hybrid_search_sync(args: dict[str, Any]) -> dict[str, Any]:
    """Synchronous hybrid_search implementation."""
    tool_name = "hybrid_search"
    project_id = ToolContext._get_context().get("project_id")

    if project_id is None:
        return _make_error("project_id not set", tool_name=tool_name)

    query = args.get("query", "")
    top_k = args.get("top_k", 10)
    entity_types = args.get("entity_types")
    min_score = args.get("min_score", 0.0)

    if not _is_hybrid_search_tool_enabled():
        log_with_context(
            logger,
            30,  # WARNING
            "Agent hybrid_search tool disabled by env",
            project_id=project_id,
            top_k=top_k,
        )
        return _make_result(
            {
                "status": "success",
                "data": {
                    "query": query,
                    "top_k": top_k,
                    "min_score": float(min_score or 0.0),
                    "search_mode": "disabled",
                    "results": [],
                    "result_count": 0,
                    "disabled_reason": "hybrid_search_disabled_by_env",
                    "entity_types": entity_types,
                },
            },
            tool_name=tool_name,
        )

    executor = ToolContext.get_executor()

    try:
        result = executor.hybrid_search(
            project_id=project_id,
            query=query,
            top_k=top_k,
            entity_types=entity_types,
            min_score=min_score,
        )
        return _make_result({"status": "success", "data": result}, tool_name=tool_name)
    except Exception as e:
        log_with_context(
            logger,
            30,  # WARNING
            "Agent hybrid_search failed",
            project_id=project_id,
            error=str(e),
            error_type=type(e).__name__,
        )
        return _make_error(str(e), tool_name=tool_name)


_PHASE_CN_CHAPTER_PATTERN = re.compile(r"第\s*([零一二三四五六七八九十百千\d]+)\s*章")
_PHASE_EN_CHAPTER_PATTERN = re.compile(r"\bchapter\s+(\d+)\b", re.IGNORECASE)


def _normalize_update_project_args(args: dict[str, Any]) -> dict[str, Any]:
    """Normalize update_project args with backward-compatible alias mapping."""
    normalized = dict(args)
    for alias, canonical in PROJECT_STATUS_FIELD_ALIASES.items():
        if canonical in normalized or alias not in normalized:
            continue
        normalized[canonical] = normalized[alias]
    return normalized


def _extract_phase_chapter_number(phase_text: str | None) -> int | None:
    """Extract chapter number from phase text using chapter-only patterns."""
    text = (phase_text or "").strip()
    if not text:
        return None

    cn_match = _PHASE_CN_CHAPTER_PATTERN.search(text)
    if cn_match:
        token = cn_match.group(1).strip()
        if token.isdigit():
            parsed = int(token)
            return parsed if parsed > 0 else None
        parsed = parse_chinese_number(token)
        return parsed if parsed and parsed > 0 else None

    en_match = _PHASE_EN_CHAPTER_PATTERN.search(text)
    if en_match:
        try:
            parsed = int(en_match.group(1))
        except ValueError:
            parsed = 0
        return parsed if parsed > 0 else None

    return None


def _suggest_auto_current_phase_from_drafts(project_id: str) -> str | None:
    """
    Suggest monotonic chapter phase text from draft files.

    Rules:
    - Only infer from draft titles with explicit sequence numbers.
    - If existing current_phase has chapter number >= inferred, keep unchanged.
    - If existing current_phase is non-empty but not chapter-like, do not override.
    """
    if not project_id:
        return None

    session = ToolContext.get_session()
    from models import File, Project

    project = session.get(Project, project_id)
    if not project:
        return None

    draft_titles = session.exec(
        select(File.title).where(
            and_(
                File.project_id == project_id,
                File.file_type == "draft",
                File.is_deleted.is_(False),
            )
        )
    ).all()
    if not draft_titles:
        return None

    inferred_latest = max(
        (
            seq
            for title in draft_titles
            if (seq := extract_chapter_like_sequence_number(title)) is not None
        ),
        default=None,
    )
    if inferred_latest is None or inferred_latest <= 0:
        return None

    current_phase = (project.current_phase or "").strip()
    current_phase_chapter = _extract_phase_chapter_number(current_phase)
    if current_phase_chapter is not None and current_phase_chapter >= inferred_latest:
        return None
    if current_phase and current_phase_chapter is None:
        return None

    return f"已写至第{inferred_latest}章"


async def update_project(args: dict[str, Any]) -> dict[str, Any]:
    """更新项目信息和任务计划。"""
    if _should_offload_tool_execution():
        return await asyncio.to_thread(_run_sync_tool_with_owned_session_cleanup, _update_project_sync, args)
    return _update_project_sync(args)


def _update_project_sync(args: dict[str, Any]) -> dict[str, Any]:
    """Synchronous update_project implementation."""
    tool_name = "update_project"
    executor = ToolContext.get_executor()
    project_id = ToolContext.get_project_id()
    session_id = ToolContext.get_session_id()
    user_id = ToolContext.get_user_id()

    if project_id is None:
        return _make_error("project_id not set", tool_name=tool_name)

    try:
        normalized_args = _normalize_update_project_args(args)
        result = {}

        # 更新项目状态（支持空字符串清空字段）
        status_keys = ["summary", "current_phase", "writing_style", "notes"]
        has_status_update_args = any(k in normalized_args for k in status_keys)
        if has_status_update_args:
            status_result = executor.update_project_status(
                project_id=project_id,
                summary=normalized_args.get("summary"),
                current_phase=normalized_args.get("current_phase"),
                writing_style=normalized_args.get("writing_style"),
                notes=normalized_args.get("notes"),
            )
            result["project_status"] = status_result
            # Backward compatibility: keep common fields at top level for older clients.
            result["project_id"] = status_result.get("project_id")
            result["updated_fields"] = status_result.get("updated_fields", [])
            result["current_status"] = status_result.get("current_status", {})

        # 更新任务计划（允许传空数组以清空任务板）
        if "tasks" in normalized_args and session_id:
            plan_result = executor.execute_update_plan(
                session_id=session_id,
                tasks=normalized_args.get("tasks", []),
                user_id=user_id,
                project_id=project_id,
            )
            result["plan"] = plan_result

        # 任务板-only 更新是正常路径（prompt 和 workflow completion hook 都会这样调用）。
        # 这里仅做信息性记录，并尝试自动前推 current_phase（单调不回退）。
        if "tasks" in normalized_args and not has_status_update_args:
            tasks_arg = normalized_args.get("tasks", [])
            task_count = len(tasks_arg) if isinstance(tasks_arg, list) else None
            log_with_context(
                logger,
                20,  # INFO
                "update_project received task-board-only payload",
                project_id=project_id,
                session_id=session_id,
                task_count=task_count,
                arg_keys=sorted(normalized_args.keys()),
            )

            try:
                suggested_phase = _suggest_auto_current_phase_from_drafts(project_id)
                if suggested_phase:
                    status_result = executor.update_project_status(
                        project_id=project_id,
                        summary=None,
                        current_phase=suggested_phase,
                        writing_style=None,
                        notes=None,
                    )
                    result["project_status"] = status_result
                    result["project_id"] = status_result.get("project_id")
                    result["updated_fields"] = status_result.get("updated_fields", [])
                    result["current_status"] = status_result.get("current_status", {})
                    log_with_context(
                        logger,
                        20,  # INFO
                        "Auto-synced project current_phase from draft progress",
                        project_id=project_id,
                        current_phase=suggested_phase,
                    )
            except Exception as exc:
                log_with_context(
                    logger,
                    40,  # ERROR
                    "Failed to auto-sync current_phase from drafts",
                    project_id=project_id,
                    session_id=session_id,
                    error=str(exc),
                )

        _record_artifact_ledger(
            action=tool_name,
            tool_name=tool_name,
            artifact_refs=_extract_tool_artifact_refs(tool_name, normalized_args, result),
            payload={
                "updated_fields": result.get("updated_fields", []),
                "has_plan": "plan" in result,
            },
        )

        return _make_result({"status": "success", "data": result}, tool_name=tool_name)
    except Exception as e:
        return _make_error(str(e), tool_name=tool_name)


async def handoff_to_agent(args: dict[str, Any]) -> dict[str, Any]:
    """将任务交接给另一个Agent。这是一个特殊工具，返回值会被图处理。"""
    tool_name = "handoff_to_agent"
    target_agent = str(args.get("target_agent", "")).strip().lower()
    reason = str(args.get("reason", "")).strip()
    context = args.get("context", "")
    completed = args.get("completed", [])
    todo = args.get("todo", [])
    evidence = args.get("evidence", [])
    artifact_refs = args.get("artifact_refs", [])
    tool_context = ToolContext._get_context()
    project_id = tool_context.get("project_id")
    session_id = tool_context.get("session_id")

    if target_agent not in ("planner", "hook_designer", "writer", "quality_reviewer"):
        return _make_error(f"Invalid target_agent: {target_agent}", tool_name=tool_name)

    current_agent = ToolContext.get_current_agent()
    if current_agent and target_agent == current_agent:
        return _make_error(
            f"Self handoff is not allowed: {current_agent} -> {target_agent}",
            tool_name=tool_name,
        )

    # Normalize optional structured handoff fields
    completed_list = completed if isinstance(completed, list) else []
    todo_list = todo if isinstance(todo, list) else []
    evidence_list = evidence if isinstance(evidence, list) else []
    artifact_ref_list = artifact_refs if isinstance(artifact_refs, list) else []
    recent_artifact_refs = _load_recent_artifact_refs_for_handoff(
        project_id=project_id if isinstance(project_id, str) else None,
        session_id=session_id if isinstance(session_id, str) else None,
    )
    merged_artifact_refs = _merge_unique_refs(artifact_ref_list, recent_artifact_refs)
    overflow_backfills = _build_tool_result_overflow_backfill_entries(merged_artifact_refs)
    backfill_context = _format_tool_result_overflow_backfill_context(overflow_backfills)
    context_str = str(context).strip()
    if not context_str:
        # Some models omit `context` even though downstream workflow relies on it.
        # Fallback to `reason` (and then a stable generic message) to avoid losing
        # the handoff signal (e.g. quality_reviewer should not receive the original
        # user writing request as its task).
        context_str = reason
    if not context_str:
        current_agent = ToolContext.get_current_agent() or "agent"
        context_str = f"Handoff requested: {current_agent} -> {target_agent}"
    if backfill_context:
        context_str = f"{context_str}\n\n{backfill_context}" if context_str else backfill_context

    # 返回交接信息，由图节点处理
    return _make_result({
        "status": "handoff",
        "target_agent": target_agent,
        "reason": reason,
        "context": context_str,
        "completed": [str(item) for item in completed_list if str(item).strip()],
        "todo": [str(item) for item in todo_list if str(item).strip()],
        "evidence": [str(item) for item in evidence_list if str(item).strip()],
        "artifact_refs": merged_artifact_refs,
        "overflow_backfill": overflow_backfills,
    }, tool_name=tool_name)


async def request_clarification(args: dict[str, Any]) -> dict[str, Any]:
    """请求用户澄清，触发工作流暂停并等待用户回复。"""
    tool_name = "request_clarification"
    question = str(args.get("question", "")).strip()
    context = str(args.get("context", "")).strip()
    details = args.get("details", [])

    if not question:
        return _make_error("question is required", tool_name=tool_name)

    details_list = details if isinstance(details, list) else []

    return _make_result({
        "status": "clarification_needed",
        "question": question,
        "context": context,
        "details": [str(item).strip() for item in details_list if str(item).strip()],
    }, tool_name=tool_name)


# Export all tools as a list for easy registration
MCP_TOOL_HANDLERS: dict[str, Callable[[dict[str, Any]], Any]] = {
    "create_file": create_file,
    "edit_file": edit_file,
    "delete_file": delete_file,
    "query_files": query_files,
    "hybrid_search": hybrid_search,
    "update_project": update_project,
    "handoff_to_agent": handoff_to_agent,
    "request_clarification": request_clarification,
}

ALL_MCP_TOOLS = list(MCP_TOOL_HANDLERS.values())
