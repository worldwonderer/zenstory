"""
Session loader for the agent module.

Encapsulates context assembly and chat session loading logic,
reducing complexity in the main service module.
"""

import asyncio
import json
import logging
import os
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from sqlalchemy import desc, or_
from sqlmodel import Session, and_, select

from agent.utils.token_utils import estimate_message_tokens
from config.agent_runtime import (
    AGENT_CHAT_HISTORY_TOKEN_BUDGET,
    AGENT_COMPACTION_CHECKPOINT_RETENTION,
)
from database import create_session
from utils.logger import get_logger, log_with_context

if TYPE_CHECKING:
    from agent.context.compaction import CompactionResult

logger = get_logger(__name__)

COMPACTION_SUMMARY_ACTION = "compaction_summary"
COMPACTION_SUMMARY_TOOL_NAME = "context_compaction"
COMPACTION_CHECKPOINT_SCHEMA_VERSION = 1


@dataclass
class SessionData:
    """Data loaded for a chat session."""

    chat_session: Any | None = None
    session_id: str | None = None
    history_messages: list[dict[str, Any]] = field(default_factory=list)
    context_data: Any | None = None
    compaction_result: Any | None = None  # CompactionResult if compaction occurred


class SessionLoader:
    """
    Loader for chat session and context data.

    Handles:
    - Context assembly using ContextAssembler
    - Chat session loading from database
    - Message history retrieval
    """

    def __init__(
        self,
        project_id: str,
        user_id: str | None,
    ):
        """
        Initialize session loader.

        Args:
            project_id: Current project ID
            user_id: Current user ID
        """
        self.project_id = project_id
        self.user_id = user_id

    def assemble_context(
        self,
        session: Session,
        context_assembler,
        query: str,
        focus_file_id: str | None = None,
        attached_file_ids: list[str] | None = None,
        attached_library_materials: list[dict[str, int]] | None = None,
        text_quotes: list[dict[str, str]] | None = None,
        max_tokens: int = 6000,
    ):
        """
        Assemble context using the context assembler.

        Args:
            session: Database session
            context_assembler: ContextAssembler instance
            query: User query for context retrieval
            focus_file_id: Currently focused file ID
            attached_file_ids: List of attached file IDs
            attached_library_materials: List of library material references
            text_quotes: List of user-selected text quotes
            max_tokens: Maximum tokens for context

        Returns:
            Assembled context data
        """
        started = time.perf_counter()
        threshold_raw = (os.getenv("AGENT_CONTEXT_ASSEMBLY_LOG_THRESHOLD_MS") or "").strip()
        try:
            threshold_ms = int(threshold_raw) if threshold_raw else 200
        except ValueError:
            threshold_ms = 200

        force_log = (os.getenv("AGENT_CONTEXT_ASSEMBLY_LOG_ALWAYS") or "").strip().lower() in {
            "1",
            "true",
            "yes",
            "y",
            "on",
        }

        log_with_context(
            logger,
            logging.INFO if force_log else logging.DEBUG,
            "Starting context assembly",
            project_id=self.project_id,
            user_id=self.user_id,
            focus_file_id=focus_file_id,
            attached_file_count=len(attached_file_ids) if attached_file_ids else 0,
            attached_library_count=len(attached_library_materials) if attached_library_materials else 0,
        )

        context_data = context_assembler.assemble(
            session=session,
            project_id=self.project_id,
            user_id=self.user_id,
            query=query,
            focus_file_id=focus_file_id,
            attached_file_ids=attached_file_ids,
            attached_library_materials=attached_library_materials,
            text_quotes=text_quotes,
            max_tokens=max_tokens,
            include_characters=True,
            include_lores=True,
        )

        duration_ms = round((time.perf_counter() - started) * 1000, 2)
        log_level = (
            logging.INFO
            if force_log or duration_ms >= threshold_ms
            else logging.DEBUG
        )
        log_with_context(
            logger,
            log_level,
            "Context assembly completed",
            project_id=self.project_id,
            user_id=self.user_id,
            item_count=len(context_data.items),
            token_estimate=context_data.token_estimate,
            duration_ms=duration_ms,
            threshold_ms=threshold_ms,
            forced=force_log,
        )

        return context_data

    def load_chat_session(self, session: Session) -> SessionData:
        """
        Load chat session and message history.

        Args:
            session: Database session

        Returns:
            SessionData with chat session and history
        """
        from models import ChatSession, Project, User

        result = SessionData()

        if not self.user_id:
            return result

        # Check if project exists and is not deleted
        project = session.get(Project, self.project_id)
        if not project or project.is_deleted:
            return result

        # Defense in depth: verify user owns the project (superuser can access all projects)
        user = session.get(User, self.user_id)
        if not user:
            log_with_context(
                logger,
                30,  # WARNING level
                "Session load blocked: user not found",
                project_id=self.project_id,
                user_id=self.user_id,
            )
            return result

        if not user.is_superuser and project.owner_id != self.user_id:
            log_with_context(
                logger,
                30,  # WARNING level
                "Session load blocked: user does not own project",
                project_id=self.project_id,
                user_id=self.user_id,
                owner_id=project.owner_id,
            )
            return result
        if user.is_superuser and project.owner_id != self.user_id:
            log_with_context(
                logger,
                20,  # INFO
                "Session load allowed for superuser across project ownership boundary",
                project_id=self.project_id,
                user_id=self.user_id,
                owner_id=project.owner_id,
            )

        # Load active chat session deterministically (newest first)
        stmt = (
            select(ChatSession)
            .where(
                and_(
                    ChatSession.project_id == self.project_id,
                    ChatSession.user_id == self.user_id,
                    ChatSession.is_active,
                )
            )
            .order_by(
                desc(ChatSession.updated_at),
                desc(ChatSession.created_at),
                desc(ChatSession.id),
            )
        )
        active_sessions = session.exec(stmt).all()
        chat_session = active_sessions[0] if active_sessions else None

        # Repair stale multi-active states defensively.
        if len(active_sessions) > 1 and chat_session is not None:
            stale_count = 0
            for stale in active_sessions[1:]:
                if stale.is_active:
                    stale.is_active = False
                    session.add(stale)
                    stale_count += 1
            if stale_count > 0:
                session.commit()
                session.refresh(chat_session)
                log_with_context(
                    logger,
                    30,  # WARNING
                    "Session loader detected multiple active chat sessions; stale sessions deactivated",
                    project_id=self.project_id,
                    user_id=self.user_id,
                    kept_session_id=chat_session.id,
                    stale_count=stale_count,
                )

        if not chat_session:
            return result

        result.chat_session = chat_session
        result.session_id = chat_session.id

        # Load recent user/assistant messages under token budget.
        #
        # IMPORTANT: Long sessions may contain thousands of chat_message rows.
        # Loading them all on every request can be slow and can cause the writing
        # assistant to "hang" on the frontend while context is assembled.
        #
        # We therefore paginate from newest -> oldest and stop as soon as the
        # token budget window is filled, then reverse to preserve chronology.
        result.history_messages = self._load_history_window_under_token_budget(
            session=session,
            chat_session_id=chat_session.id,
            token_budget=AGENT_CHAT_HISTORY_TOKEN_BUDGET,
        )

        log_with_context(
            logger,
            20,
            "Chat history loaded",
            project_id=self.project_id,
            user_id=self.user_id,
            session_id=chat_session.id,
            total_history_message_count=getattr(chat_session, "message_count", None),
            history_message_count=len(result.history_messages),
            history_token_budget=AGENT_CHAT_HISTORY_TOKEN_BUDGET,
        )

        return result

    def _load_session_and_context_sync(
        self,
        context_assembler,
        query: str,
        focus_file_id: str | None = None,
        attached_file_ids: list[str] | None = None,
        attached_library_materials: list[dict[str, int]] | None = None,
        text_quotes: list[dict[str, str]] | None = None,
        max_tokens: int = 6000,
    ) -> SessionData:
        """
        Load session and context using a fresh sync DB session.

        This method is intended to run in a worker thread so read-heavy sync ORM
        work does not block the async request event loop.
        """
        with create_session() as read_session:
            result = self.load_chat_session(read_session)
            result.context_data = self.assemble_context(
                read_session,
                context_assembler,
                query,
                focus_file_id,
                attached_file_ids,
                attached_library_materials,
                text_quotes,
                max_tokens,
            )
            return result

    def _should_offload_session_work(self, session: Session) -> bool:
        """Only offload when running against PostgreSQL production-style sessions."""
        bind = session.get_bind() if hasattr(session, "get_bind") else None
        dialect_name = getattr(getattr(bind, "dialect", None), "name", "")
        return dialect_name == "postgresql"

    def _load_history_window_under_token_budget(
        self,
        *,
        session: Session,
        chat_session_id: str,
        token_budget: int,
        page_size: int = 200,
    ) -> list[dict[str, Any]]:
        """
        Load a newest-first sliding window under token budget without reading all rows.

        This avoids O(total_messages) memory/time behavior for long chat sessions.
        """
        from models import ChatMessage

        # Keep the newest single message even if budget is non-positive.
        if token_budget <= 0:
            msg_stmt = (
                select(ChatMessage)
                .where(
                    and_(
                        ChatMessage.session_id == chat_session_id,
                        ChatMessage.role.in_(("user", "assistant")),
                    )
                )
                .order_by(desc(ChatMessage.created_at), desc(ChatMessage.id))
                .limit(1)
            )
            msg = session.exec(msg_stmt).first()
            if not msg:
                return []
            return [self._format_chat_message_for_history(msg)]

        selected_reversed: list[dict[str, Any]] = []
        used_tokens = 0
        cursor_created_at = None
        cursor_id = None

        while True:
            msg_stmt = select(ChatMessage).where(
                and_(
                    ChatMessage.session_id == chat_session_id,
                    ChatMessage.role.in_(("user", "assistant")),
                )
            )

            if cursor_created_at is not None and cursor_id is not None:
                msg_stmt = msg_stmt.where(
                    or_(
                        ChatMessage.created_at < cursor_created_at,
                        and_(
                            ChatMessage.created_at == cursor_created_at,
                            ChatMessage.id < cursor_id,
                        ),
                    )
                )

            msg_stmt = msg_stmt.order_by(desc(ChatMessage.created_at), desc(ChatMessage.id)).limit(
                max(1, int(page_size or 200))
            )
            page = session.exec(msg_stmt).all()
            if not page:
                break

            stop = False
            for msg in page:
                msg_data = self._format_chat_message_for_history(msg)
                msg_tokens = max(1, estimate_message_tokens(msg_data))

                if selected_reversed and used_tokens + msg_tokens > token_budget:
                    stop = True
                    break

                selected_reversed.append(msg_data)
                used_tokens += msg_tokens

                if used_tokens >= token_budget:
                    stop = True
                    break

            if stop:
                break

            last = page[-1]
            cursor_created_at = last.created_at
            cursor_id = last.id

            # Safety: stop if we somehow keep fetching but never make progress.
            if len(page) == 0:
                break

        return list(reversed(selected_reversed))

    def _format_chat_message_for_history(self, msg: Any) -> dict[str, Any]:
        """Convert ChatMessage ORM row to dict for agent history + compaction token math."""
        msg_data: dict[str, Any] = {
            "id": msg.id,
            "role": msg.role,
            "content": msg.content,
        }

        # Include reasoning_content for assistant messages
        # Anthropic protocol expects thinking inside content array, not top-level
        if msg.role == "assistant" and getattr(msg, "reasoning_content", None):
            reasoning = msg.reasoning_content
            # Reconstruct content as array with thinking block first
            if isinstance(msg_data.get("content"), str):
                parts: list[dict[str, Any]] = [
                    {"type": "thinking", "thinking": reasoning},
                ]
                if msg_data["content"]:
                    parts.append({"type": "text", "text": msg_data["content"]})
                msg_data["content"] = parts

        # Include persisted assistant metadata for compaction token estimation
        if msg.role == "assistant" and getattr(msg, "message_metadata", None):
            try:
                metadata = json.loads(msg.message_metadata)
            except (TypeError, json.JSONDecodeError):
                metadata = {}

            if isinstance(metadata, dict):
                stop_reason = metadata.get("stop_reason")
                usage = metadata.get("usage")
                status_cards = metadata.get("status_cards")
                if isinstance(stop_reason, str) and stop_reason:
                    msg_data["stop_reason"] = stop_reason
                if isinstance(usage, dict):
                    msg_data["usage"] = usage
                if isinstance(status_cards, list):
                    synthesized_content = self._build_status_cards_history_content(status_cards)
                    if synthesized_content and not str(msg_data.get("content") or "").strip():
                        msg_data["content"] = synthesized_content

        return msg_data

    def _build_status_cards_history_content(
        self,
        status_cards: list[Any],
    ) -> str:
        """Build a lightweight text summary so status-only turns remain visible to the model."""
        summaries: list[str] = []

        for card in status_cards:
            if not isinstance(card, dict):
                continue

            card_type = str(card.get("type") or "").strip()
            if card_type == "workflow_stopped":
                parts = ["[workflow_stopped]"]
                reason = str(card.get("reason") or "").strip()
                question = str(card.get("question") or card.get("message") or "").strip()
                context = str(card.get("context") or "").strip()
                details = card.get("details")

                if reason:
                    parts.append(f"reason: {reason}")
                if question:
                    parts.append(f"question: {question}")
                if context:
                    parts.append(f"context: {context}")
                if isinstance(details, list):
                    normalized_details = [
                        str(detail).strip()
                        for detail in details
                        if detail is not None and str(detail).strip()
                    ]
                    if normalized_details:
                        parts.append("details: " + "; ".join(normalized_details))

                summaries.append("\n".join(parts))
                continue

            if card_type == "iteration_exhausted":
                parts = ["[iteration_exhausted]"]
                layer = str(card.get("layer") or "").strip()
                iterations_used = card.get("iterationsUsed")
                max_iterations = card.get("maxIterations")
                reason = str(card.get("reason") or "").strip()
                last_agent = str(card.get("lastAgent") or "").strip()

                if layer:
                    parts.append(f"layer: {layer}")
                if iterations_used is not None or max_iterations is not None:
                    parts.append(
                        "iterations: "
                        f"{iterations_used if iterations_used is not None else '?'}"
                        "/"
                        f"{max_iterations if max_iterations is not None else '?'}"
                    )
                if reason:
                    parts.append(f"reason: {reason}")
                if last_agent:
                    parts.append(f"last_agent: {last_agent}")

                summaries.append("\n".join(parts))

        return "\n\n".join(summary for summary in summaries if summary)

    def _trim_history_to_token_budget(
        self,
        messages: list[dict[str, Any]],
        token_budget: int,
    ) -> list[dict[str, Any]]:
        """
        Keep the newest messages within a token budget while preserving chronology.

        The window slides from newest -> oldest and stops when adding an older
        message would exceed the budget. At least one newest message is retained
        when history exists.
        """
        if not messages:
            return []

        if token_budget <= 0:
            return [messages[-1]]

        selected_reversed: list[dict[str, Any]] = []
        used_tokens = 0

        for message in reversed(messages):
            message_tokens = max(1, estimate_message_tokens(message))
            if selected_reversed and used_tokens + message_tokens > token_budget:
                break

            selected_reversed.append(message)
            used_tokens += message_tokens

            if used_tokens >= token_budget:
                break

        return list(reversed(selected_reversed))

    async def load_session_with_compaction(
        self,
        session: Session,
        context_assembler,
        query: str,
        focus_file_id: str | None = None,
        attached_file_ids: list[str] | None = None,
        attached_library_materials: list[dict[str, int]] | None = None,
        text_quotes: list[dict[str, str]] | None = None,
        max_tokens: int = 6000,
        enable_compaction: bool = True,
    ) -> "SessionData":
        """
        Load session with optional async compaction.

        This is the primary method for new code. It combines:
        1. Chat session loading
        2. Context assembly
        3. Async compaction when needed

        Args:
            session: Database session
            context_assembler: ContextAssembler instance
            query: User query for context retrieval
            focus_file_id: Currently focused file ID
            attached_file_ids: List of attached file IDs
            attached_library_materials: List of library material references
            text_quotes: List of user-selected text quotes
            max_tokens: Maximum tokens for context
            enable_compaction: Whether to enable compaction

        Returns:
            SessionData with chat session, context, and optional compaction result
        """
        from agent.context.compaction import (
            CONTEXT_WINDOW,
            CompactionSettings,
            compact_context,
            estimate_context_tokens,
            should_compact,
        )

        if self._should_offload_session_work(session):
            # 1 & 2. Load chat session + assemble context in a worker thread with a
            # fresh sync DB session so async request handling stays responsive.
            result = await asyncio.to_thread(
                self._load_session_and_context_sync,
                context_assembler,
                query,
                focus_file_id,
                attached_file_ids,
                attached_library_materials,
                text_quotes,
                max_tokens,
            )
        else:
            # Keep sqlite/test execution on the caller session so existing test
            # fixtures and in-memory DB behavior remain deterministic.
            result = self.load_chat_session(session)
            result.context_data = self.assemble_context(
                session,
                context_assembler,
                query,
                focus_file_id,
                attached_file_ids,
                attached_library_materials,
                text_quotes,
                max_tokens,
            )

        # 3. Check and perform compaction (async)
        if enable_compaction and result.history_messages:
            settings = CompactionSettings()
            estimate = estimate_context_tokens(result.history_messages)

            log_with_context(
                logger,
                20,
                "Checking compaction need",
                total_tokens=estimate.total_tokens,
                context_window=CONTEXT_WINDOW,
                reserve_tokens=settings.reserve_tokens,
            )

            if should_compact(estimate.total_tokens, CONTEXT_WINDOW, settings):
                previous_summary = self._load_previous_compaction_summary(
                    session=session,
                    session_id=result.session_id,
                )
                log_with_context(
                    logger,
                    20,
                    "Starting async compaction",
                    total_tokens=estimate.total_tokens,
                    has_previous_summary=previous_summary is not None,
                )

                compaction_result = await compact_context(
                    result.history_messages,
                    settings,
                    previous_summary=previous_summary,
                )

                if compaction_result:
                    result.history_messages = self._apply_compaction(
                        result.history_messages,
                        compaction_result,
                    )
                    result.compaction_result = compaction_result
                    self._persist_compaction_summary_checkpoint(
                        session=session,
                        session_id=result.session_id,
                        summary=compaction_result.summary,
                        tokens_before=compaction_result.tokens_before,
                        tokens_after=compaction_result.tokens_after,
                        messages_removed=compaction_result.messages_removed,
                    )

                    log_with_context(
                        logger,
                        20,
                        "Compaction applied to session",
                        tokens_before=compaction_result.tokens_before,
                        tokens_after=compaction_result.tokens_after,
                        messages_removed=compaction_result.messages_removed,
                    )

        return result

    def _load_previous_compaction_summary(
        self,
        session: Session,
        session_id: str | None,
    ) -> str | None:
        """Load the latest persisted compaction summary checkpoint if available."""
        if not session_id:
            return None

        try:
            from models import AgentArtifactLedger
        except Exception:
            return None

        try:
            rows = session.exec(
                select(AgentArtifactLedger.payload)
                .where(
                    and_(
                        AgentArtifactLedger.project_id == self.project_id,
                        AgentArtifactLedger.session_id == session_id,
                        AgentArtifactLedger.action == COMPACTION_SUMMARY_ACTION,
                    )
                )
                .order_by(
                    desc(AgentArtifactLedger.created_at),
                    desc(AgentArtifactLedger.id),
                )
                .limit(5)
            ).all()
        except Exception as e:
            log_with_context(
                logger,
                30,  # WARNING
                "Failed to load previous compaction summary checkpoint",
                project_id=self.project_id,
                session_id=session_id,
                error=str(e),
                error_type=type(e).__name__,
            )
            return None

        for row in rows:
            if not isinstance(row, str) or not row.strip():
                continue

            payload_text = row.strip()
            try:
                payload = json.loads(payload_text)
            except (TypeError, json.JSONDecodeError):
                if payload_text:
                    return payload_text
                continue

            if isinstance(payload, dict):
                schema_version = payload.get("schema_version")
                if schema_version not in (None, COMPACTION_CHECKPOINT_SCHEMA_VERSION):
                    continue

                summary = payload.get("summary")
                if isinstance(summary, str) and summary.strip():
                    return summary.strip()

                nested_data = payload.get("data")
                if isinstance(nested_data, dict):
                    nested_summary = nested_data.get("summary")
                    if isinstance(nested_summary, str) and nested_summary.strip():
                        return nested_summary.strip()

        return None

    def _persist_compaction_summary_checkpoint(
        self,
        session: Session,
        session_id: str | None,
        summary: str,
        tokens_before: int,
        tokens_after: int,
        messages_removed: int,
    ) -> None:
        """
        Persist compaction summary checkpoint for incremental compaction.

        Note:
            This method only stages the ledger row in the current DB session.
            Commit is handled by the caller/request lifecycle.
        """
        if not session_id or not summary.strip():
            return

        try:
            from models import AgentArtifactLedger
        except Exception:
            return

        payload = json.dumps(
            {
                "schema_version": COMPACTION_CHECKPOINT_SCHEMA_VERSION,
                "summary": summary,
                "tokens_before": int(tokens_before),
                "tokens_after": int(tokens_after),
                "messages_removed": int(messages_removed),
            },
            ensure_ascii=False,
        )

        try:
            session.add(
                AgentArtifactLedger(
                    project_id=self.project_id,
                    session_id=session_id,
                    user_id=self.user_id,
                    action=COMPACTION_SUMMARY_ACTION,
                    tool_name=COMPACTION_SUMMARY_TOOL_NAME,
                    artifact_ref=f"compaction:{session_id}",
                    payload=payload,
                )
            )
        except Exception as e:
            log_with_context(
                logger,
                30,  # WARNING
                "Failed to persist compaction summary checkpoint",
                project_id=self.project_id,
                session_id=session_id,
                error=str(e),
                error_type=type(e).__name__,
            )

        self._prune_compaction_summary_checkpoints(
            session=session,
            session_id=session_id,
            keep_latest=AGENT_COMPACTION_CHECKPOINT_RETENTION,
        )

    def _prune_compaction_summary_checkpoints(
        self,
        session: Session,
        session_id: str,
        keep_latest: int,
    ) -> None:
        """Best-effort pruning to cap persisted checkpoints per session."""
        if keep_latest <= 0:
            return

        try:
            from models import AgentArtifactLedger
        except Exception:
            return

        try:
            session.flush()
            stale_rows = session.exec(
                select(AgentArtifactLedger)
                .where(
                    and_(
                        AgentArtifactLedger.project_id == self.project_id,
                        AgentArtifactLedger.session_id == session_id,
                        AgentArtifactLedger.action == COMPACTION_SUMMARY_ACTION,
                    )
                )
                .order_by(
                    desc(AgentArtifactLedger.created_at),
                    desc(AgentArtifactLedger.id),
                )
                .offset(keep_latest)
            ).all()

            for row in stale_rows:
                session.delete(row)

            if stale_rows:
                log_with_context(
                    logger,
                    20,
                    "Pruned stale compaction summary checkpoints",
                    project_id=self.project_id,
                    session_id=session_id,
                    pruned_count=len(stale_rows),
                    keep_latest=keep_latest,
                )
        except Exception as e:
            log_with_context(
                logger,
                30,  # WARNING
                "Failed to prune compaction summary checkpoints",
                project_id=self.project_id,
                session_id=session_id,
                keep_latest=keep_latest,
                error=str(e),
                error_type=type(e).__name__,
            )

    def _apply_compaction(
        self,
        messages: list[dict[str, Any]],
        result: "CompactionResult",
    ) -> list[dict[str, Any]]:
        """
        Apply compaction result to message list.

        Args:
            messages: Original message list
            result: Compaction result with summary and cut point

        Returns:
            New message list with summary at cut point
        """
        from agent.context.compaction import create_compaction_summary_message

        # Create summary message
        summary_msg = create_compaction_summary_message(
            result.summary,
            result.tokens_before,
        )

        # Use messages_removed as a stable fallback when message IDs are unavailable.
        cut_index = min(max(result.messages_removed, 0), len(messages))
        matched_by_id = False
        if result.first_kept_message_id:
            for i, msg in enumerate(messages):
                if msg.get("id") == result.first_kept_message_id:
                    cut_index = i
                    matched_by_id = True
                    break

        # Return new message list with summary at cut point
        new_messages = [summary_msg] + messages[cut_index:]

        log_with_context(
            logger,
            20,
            "Applied compaction to message history",
            original_count=len(messages),
            new_count=len(new_messages),
            messages_removed=len(messages) - len(new_messages),
            cut_index=cut_index,
            matched_by_id=matched_by_id,
        )

        return new_messages
