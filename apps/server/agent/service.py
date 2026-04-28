"""
Agent service - AI writing assistant with multi-agent workflow.

Features:
- Open-ended conversation (no fixed intents)
- File operations via Function Calling (create, update, delete, query)
- Chat history with memory
- Streaming SSE output
- Intelligent context assembly with priority-based selection
- Multi-agent routing (planner/writer/quality_reviewer)
- Context compaction for long sessions
- Steering message support

Powered by custom workflow orchestration + Anthropic SDK.
"""

import asyncio
import uuid
from collections.abc import AsyncGenerator
from typing import Any

from sqlalchemy import desc
from sqlmodel import Session, and_, select

from config.agent_runtime import (
    AGENT_AUTO_REVIEW_THRESHOLD_CHARS,
    AGENT_COLLABORATION_MAX_ITERATIONS,
)
from config.agent_runtime import (
    AGENT_MAX_ITERATIONS as AGENT_REQUEST_MAX_ITERATIONS,
)
from config.datetime_utils import utcnow
from database import create_session
from utils.logger import get_logger, log_with_context

from .context import ContextAssembler, get_context_assembler
from .core.events import (
    compaction_done_event,
    compaction_start_event,
    context_event,
    done_event,
    error_event,
    session_started_event,
    thinking_event,
)
from .core.message_manager import MessageManager
from .core.metrics import (
    AGENT_REQUESTS_DURATION_MS,
    AGENT_REQUESTS_ERRORS,
    AGENT_REQUESTS_TOTAL,
    CONTEXT_COMPACTION_TOKENS_SAVED,
    CONTEXT_COMPACTION_TOTAL,
    CONTEXT_ITEMS_COUNT,
    CONTEXT_TOKENS_TOTAL,
    get_metrics_collector,
)
from .core.session_loader import SessionLoader
from .core.steering import cleanup_steering_queue_async, create_steering_queue_async
from .graph.state import WritingState
from .graph.writing_graph import run_writing_workflow_streaming
from .skills import get_skill_context_injector
from .skills.explicit_resolver import resolve_explicit_skill_selection
from .stream_adapter import create_stream_adapter
from .tools.mcp_tools import ToolContext

logger = get_logger(__name__)

# Backward-compatible export used by existing tests/callers.
AGENT_MAX_ITERATIONS = AGENT_REQUEST_MAX_ITERATIONS


class AgentService:
    """
    AI writing assistant service powered by workflow orchestration + Anthropic SDK.

    Features:
    - Multi-agent routing (planner/writer/quality_reviewer)
    - Open-ended conversation with Claude
    - File CRUD via tool calling
    - Chat history persistence
    - Streaming responses
    - Intelligent context assembly
    """

    def __init__(
        self,
        context_assembler: ContextAssembler | None = None,
    ):
        """Initialize agent service."""
        self.context_assembler = context_assembler or get_context_assembler()
        log_with_context(
            logger,
            20,  # INFO
            "AgentService initialized with workflow orchestration",
        )

    @staticmethod
    def _schedule_background_cleanup(coro: Any, *, description: str, session_id: str | None) -> None:
        """Run async cleanup out of band when generator cancellation makes awaiting risky."""
        task = asyncio.create_task(coro)

        def _log_task_result(done_task: asyncio.Task) -> None:
            try:
                done_task.result()
            except Exception as exc:  # pragma: no cover - depends on runtime cancellation timing
                log_with_context(
                    logger,
                    30,  # WARNING
                    "Background cleanup task failed",
                    description=description,
                    session_id=session_id,
                    error=str(exc),
                    error_type=type(exc).__name__,
                )

        task.add_done_callback(_log_task_result)

    @staticmethod
    def _should_offload_session_work(session: Session) -> bool:
        """Only offload when running against PostgreSQL production-style sessions."""
        bind = session.get_bind() if hasattr(session, "get_bind") else None
        dialect_name = getattr(getattr(bind, "dialect", None), "name", "")
        return dialect_name == "postgresql"

    def _resolve_or_create_chat_session_id(
        self,
        session: Session,
        *,
        project_id: str,
        user_id: str,
        requested_session_id: str | None,
    ) -> str:
        """
        Resolve the `session_id` used by:
        - SSE `session_started` event (frontend steering + continuity)
        - ToolContext (task board + artifact ledger)

        IMPORTANT: This value must exist in `chat_session.id` because
        `agent_artifact_ledger.session_id` has a FK to `chat_session.id`.
        """
        from models import ChatSession

        normalized_requested = (requested_session_id or "").strip()

        # 1) If caller provided a runtime session id, we REQUIRE it to exist in
        #    `chat_session.id` because agent_artifact_ledger has an FK to it.
        #    - If it exists and belongs to this user+project, reuse it.
        #    - If it doesn't exist, create it with that exact id (so we can echo
        #      it back in `session_started` for steering continuity).
        #    - If it exists but belongs to someone else, ignore it and fall back
        #      to the latest active session (defense-in-depth).
        if normalized_requested:
            candidate = session.get(ChatSession, normalized_requested)

            if candidate is not None:
                if candidate.user_id != user_id or candidate.project_id != project_id:
                    log_with_context(
                        logger,
                        30,  # WARNING
                        "Requested session_id does not belong to user/project; ignoring",
                        project_id=project_id,
                        user_id=user_id,
                        requested_session_id=normalized_requested,
                        candidate_user_id=candidate.user_id,
                        candidate_project_id=candidate.project_id,
                    )
                else:
                    other_actives = session.exec(
                        select(ChatSession)
                        .where(
                            and_(
                                ChatSession.project_id == project_id,
                                ChatSession.user_id == user_id,
                                ChatSession.is_active,
                                ChatSession.id != candidate.id,
                            )
                        )
                        .order_by(
                            desc(ChatSession.updated_at),
                            desc(ChatSession.created_at),
                            desc(ChatSession.id),
                        )
                    ).all()

                    changed = False
                    if not candidate.is_active:
                        candidate.is_active = True
                        changed = True

                    for stale in other_actives:
                        if stale.is_active:
                            stale.is_active = False
                            session.add(stale)
                            changed = True

                    candidate.updated_at = utcnow()
                    session.add(candidate)

                    if changed:
                        session.commit()
                        session.refresh(candidate)

                    return candidate.id

            else:
                # Compatibility note:
                # - Before artifact-ledger FK enforcement, the frontend/session layer
                #   used a runtime UUID that was NOT persisted to `chat_session.id`.
                #   Those legacy clients may still send such a session_id after a
                #   backend deploy while an active chat_session (with history) exists.
                #   In that case, we must NOT create a new chat_session (which would
                #   effectively "lose" the current active history in UI).
                existing_actives = session.exec(
                    select(ChatSession)
                    .where(
                        and_(
                            ChatSession.project_id == project_id,
                            ChatSession.user_id == user_id,
                            ChatSession.is_active,
                        )
                    )
                    .order_by(
                        desc(ChatSession.updated_at),
                        desc(ChatSession.created_at),
                        desc(ChatSession.id),
                    )
                ).all()

                if existing_actives:
                    log_with_context(
                        logger,
                        20,  # INFO
                        "Requested session_id not found; falling back to active chat session",
                        project_id=project_id,
                        user_id=user_id,
                        requested_session_id=normalized_requested,
                        resolved_session_id=existing_actives[0].id,
                    )

                    # Repair stale multi-active states defensively (newest wins).
                    if len(existing_actives) > 1:
                        for stale in existing_actives[1:]:
                            if stale.is_active:
                                stale.is_active = False
                                session.add(stale)
                        session.commit()
                        session.refresh(existing_actives[0])

                    return existing_actives[0].id

                chat_session = ChatSession(
                    id=normalized_requested,
                    user_id=user_id,
                    project_id=project_id,
                    title="AI 助手对话",
                    is_active=True,
                    message_count=0,
                )
                session.add(chat_session)
                session.commit()
                session.refresh(chat_session)
                return chat_session.id

        # 2) Otherwise, use the newest active session (if any).
        active_sessions = session.exec(
            select(ChatSession)
            .where(
                and_(
                    ChatSession.project_id == project_id,
                    ChatSession.user_id == user_id,
                    ChatSession.is_active,
                )
            )
            .order_by(
                desc(ChatSession.updated_at),
                desc(ChatSession.created_at),
                desc(ChatSession.id),
            )
        ).all()
        chat_session = active_sessions[0] if active_sessions else None

        # Repair stale multi-active states defensively (newest wins).
        if chat_session is not None and len(active_sessions) > 1:
            for stale in active_sessions[1:]:
                if stale.is_active:
                    stale.is_active = False
                    session.add(stale)
            session.commit()
            session.refresh(chat_session)

        if chat_session is not None:
            return chat_session.id

        # 3) If no active session exists yet, create one now so tools can safely
        #    write agent_artifact_ledger rows during streaming.
        chat_session = ChatSession(
            user_id=user_id,
            project_id=project_id,
            title="AI 助手对话",
            is_active=True,
            message_count=0,
        )
        session.add(chat_session)
        session.commit()
        session.refresh(chat_session)
        return chat_session.id

    def _resolve_or_create_chat_session_id_sync(
        self,
        *,
        project_id: str,
        user_id: str,
        requested_session_id: str | None,
    ) -> str:
        """Resolve/create chat session id using a fresh sync DB session."""
        with create_session() as sync_session:
            return self._resolve_or_create_chat_session_id(
                sync_session,
                project_id=project_id,
                user_id=user_id,
                requested_session_id=requested_session_id,
            )

    def _prepare_prompt_artifacts_sync(
        self,
        *,
        project_id: str,
        user_id: str | None,
        explicit_skill: Any,
        processed_message: str,
        session_id: str | None,
        metadata: dict[str, Any] | None,
        language: str,
        assembled_context: str | None,
        context_items: list[dict[str, Any]] | None,
    ) -> tuple[Any, str, str | None, str | None, str]:
        """
        Resolve skill references + system prompt in a fresh sync session.
        """
        with create_session() as sync_session:
            skill_injector = get_skill_context_injector()
            skill_catalog = skill_injector.build_skill_catalog(sync_session, user_id)
            skill_reference = skill_injector.build_skill_reference(sync_session, user_id)

            message_manager = MessageManager(
                project_id=project_id,
                user_id=user_id,
            )
            system_prompt = message_manager.build_system_prompt(
                session=sync_session,
                session_id=session_id,
                metadata=metadata,
                assembled_context=assembled_context,
                context_items=context_items,
                language=language,
                skill_catalog=skill_catalog,
                skill_reference=skill_reference,
                selected_skill=(
                    {
                        "id": explicit_skill.skill_id,
                        "name": explicit_skill.name,
                        "instructions": explicit_skill.instructions,
                        "source": explicit_skill.source,
                        "matched_text": explicit_skill.matched_text,
                    }
                    if explicit_skill
                    else None
                ),
            )

            return (
                explicit_skill,
                processed_message,
                skill_catalog,
                skill_reference,
                system_prompt,
            )

    def _resolve_explicit_skill_selection_sync(
        self,
        *,
        user_id: str | None,
        message: str,
    ) -> Any:
        """Resolve explicit skill selection using a fresh sync DB session."""
        with create_session() as sync_session:
            return resolve_explicit_skill_selection(
                session=sync_session,
                user_id=user_id,
                message=message,
            )

    async def process_stream(
        self,
        project_id: str,
        user_id: str | None,
        message: str,
        session: Session,
        session_id: str | None = None,
        selected_text: str | None = None,
        metadata: dict[str, Any] | None = None,
        language: str | None = None,
    ) -> AsyncGenerator[str, None]:
        """
        Process user message with streaming response.

        Args:
            project_id: Project ID (UUID)
            user_id: User ID (UUID, for chat history)
            message: User's message
            session: Database session
            selected_text: Optional selected text for context
            metadata: Optional metadata (current_file_id, etc.)
            language: Language preference (zh/en)

        Yields:
            SSE event strings
        """
        start_time = utcnow()
        metrics = get_metrics_collector()
        metrics.increment_counter(AGENT_REQUESTS_TOTAL)
        message_preview = message[:100] + "..." if len(message) > 100 else message

        log_with_context(
            logger,
            20,  # INFO
            "Agent process_stream started (workflow)",
            project_id=project_id,
            user_id=user_id,
            message_length=len(message),
            message_preview=message_preview,
            has_selected_text=selected_text is not None,
            language=language,
            current_file_id=metadata.get("current_file_id") if metadata else None,
        )

        # Resolve chat-session id for continuity + artifact-ledger FK safety.
        # (Historically this was a standalone runtime UUID; but artifact ledger
        # requires `session_id` to exist in `chat_session.id`.)
        requested_session_id = session_id
        if user_id:
            if self._should_offload_session_work(session):
                session_id = await asyncio.to_thread(
                    self._resolve_or_create_chat_session_id_sync,
                    project_id=project_id,
                    user_id=user_id,
                    requested_session_id=requested_session_id,
                )
            else:
                session_id = self._resolve_or_create_chat_session_id(
                    session,
                    project_id=project_id,
                    user_id=user_id,
                    requested_session_id=requested_session_id,
                )
        else:
            session_id = requested_session_id or str(uuid.uuid4())

        # Initialize steering queue for this session
        steering_queue = await create_steering_queue_async(session_id, user_id)

        # Initialize tracking variables before try block for exception safety
        all_tool_calls: list[dict[str, Any]] = []
        tool_call_index_by_id: dict[str, int] = {}
        assistant_response = ""
        reasoning_content = ""
        assistant_stop_reason: str | None = None
        assistant_usage: dict[str, Any] | None = None
        assistant_status_cards: list[dict[str, Any]] = []
        pending_done_payload: dict[str, Any] | None = None
        had_stream_error = False
        request_failed = False
        stream_cancelled = False

        try:
            lang = (language or "").strip().lower() or "zh"
            force_en = lang.startswith("en")

            # Emit session_started event FIRST
            yield session_started_event(session_id).to_sse()

            # Extract metadata
            focus_file_id = metadata.get("current_file_id") if metadata else None
            attached_file_ids = metadata.get("attached_file_ids") if metadata else None
            attached_library_materials = metadata.get("attached_library_materials") if metadata else None
            text_quotes = metadata.get("text_quotes") if metadata else None
            generation_mode_raw = metadata.get("generation_mode") if metadata else None
            generation_mode = (
                str(generation_mode_raw).strip().lower()
                if generation_mode_raw is not None
                else None
            )
            if generation_mode not in {"fast", "quality"}:
                generation_mode = None

            if self._should_offload_session_work(session):
                explicit_skill = await asyncio.to_thread(
                    self._resolve_explicit_skill_selection_sync,
                    user_id=user_id,
                    message=message,
                )
            else:
                explicit_skill = resolve_explicit_skill_selection(
                    session=session,
                    user_id=user_id,
                    message=message,
                )
            processed_message = (
                explicit_skill.cleaned_message
                if explicit_skill and explicit_skill.cleaned_message
                else message
            )

            # Assemble intelligent context with compaction
            yield thinking_event(
                "Assembling context..." if force_en else "正在组装上下文..."
            ).to_sse()

            session_loader = SessionLoader(project_id, user_id)
            session_data = await session_loader.load_session_with_compaction(
                session=session,
                context_assembler=self.context_assembler,
                query=processed_message,
                focus_file_id=focus_file_id,
                attached_file_ids=attached_file_ids,
                attached_library_materials=attached_library_materials,
                text_quotes=text_quotes,
            )

            context_data = session_data.context_data
            history_messages = session_data.history_messages
            token_count = max(0, int(getattr(context_data, "token_estimate", 0) or 0))
            item_count = len(getattr(context_data, "items", []) or [])
            metrics.increment_counter(CONTEXT_TOKENS_TOTAL, amount=token_count)
            metrics.increment_counter(CONTEXT_ITEMS_COUNT, amount=item_count)

            # Emit context event to frontend
            if context_data and context_data.items:
                yield context_event(
                    items=context_data.items,
                    token_count=context_data.token_estimate,
                ).to_sse()

            # Emit compaction event if occurred
            if session_data.compaction_result:
                compaction = session_data.compaction_result
                tokens_saved = max(0, int(compaction.tokens_before) - int(compaction.tokens_after))
                metrics.increment_counter(CONTEXT_COMPACTION_TOTAL)
                metrics.increment_counter(
                    CONTEXT_COMPACTION_TOKENS_SAVED,
                    amount=tokens_saved,
                )
                log_with_context(
                    logger,
                    20,
                    "Emitting compaction events",
                    tokens_before=compaction.tokens_before,
                    tokens_after=compaction.tokens_after,
                    messages_removed=compaction.messages_removed,
                )
                yield compaction_start_event(
                    compaction.tokens_before,
                    len(history_messages),
                ).to_sse()
                yield compaction_done_event(
                    compaction.tokens_after,
                    compaction.messages_removed,
                    compaction.summary[:100],
                ).to_sse()

            message_manager = MessageManager(
                project_id=project_id,
                user_id=user_id,
            )

            if self._should_offload_session_work(session):
                (
                    explicit_skill,
                    processed_message,
                    skill_catalog,
                    skill_reference,
                    system_prompt,
                ) = await asyncio.to_thread(
                    self._prepare_prompt_artifacts_sync,
                    project_id=project_id,
                    user_id=user_id,
                    explicit_skill=explicit_skill,
                    processed_message=processed_message,
                    session_id=session_id,
                    metadata=metadata,
                    language=lang,
                    assembled_context=context_data.context if context_data.context else None,
                    context_items=context_data.items if context_data.items else None,
                )
            else:
                # Build skill catalog for AI-driven selection
                skill_injector = get_skill_context_injector()
                skill_catalog = skill_injector.build_skill_catalog(session, user_id)
                skill_reference = skill_injector.build_skill_reference(session, user_id)

                # Build system prompt with assembled context
                system_prompt = message_manager.build_system_prompt(
                    session=session,
                    session_id=session_id,
                    metadata=metadata,
                    assembled_context=context_data.context if context_data.context else None,
                    context_items=context_data.items if context_data.items else None,
                    language=lang,
                    skill_catalog=skill_catalog,
                    skill_reference=skill_reference,
                    selected_skill=(
                        {
                            "id": explicit_skill.skill_id,
                            "name": explicit_skill.name,
                            "instructions": explicit_skill.instructions,
                            "source": explicit_skill.source,
                            "matched_text": explicit_skill.matched_text,
                        }
                        if explicit_skill
                        else None
                    ),
                )

            # Build current user message
            user_content = processed_message
            if selected_text:
                user_content += f"\n\n{'Selected text' if force_en else '选中的文本'}:\n{selected_text}"

            if metadata:
                context_parts = []
                if "current_file_id" in metadata:
                    context_parts.append(
                        f"{'Current file ID' if force_en else '当前文件 ID'}: {metadata['current_file_id']}"
                    )
                if "current_file_type" in metadata:
                    context_parts.append(
                        f"{'File type' if force_en else '文件类型'}: {metadata['current_file_type']}"
                    )
                if context_parts:
                    user_content += f"\n\n{'Context' if force_en else '上下文'}:\n" + "\n".join(context_parts)

            # Combine messages (without system message - it's passed separately to Claude)
            messages = history_messages + [{"role": "user", "content": user_content}]

            yield thinking_event(
                "Thinking..." if force_en else "正在思考..."
            ).to_sse()

            log_with_context(
                logger,
                20,  # INFO
                "Starting workflow streaming",
                project_id=project_id,
                user_id=user_id,
                total_messages=len(messages),
            )

            # Set tool context for tool execution
            ToolContext.set_context(
                session=None if self._should_offload_session_work(session) else session,
                user_id=user_id,
                project_id=project_id,
                session_id=session_id,
                create_session_func=create_session,
            )

            # Build WritingState for workflow execution
            writing_state: WritingState = {
                "user_message": user_content,
                # Router only needs the raw user message (exclude selected_text / metadata decorations)
                "router_message": processed_message,
                "project_id": project_id,
                "user_id": user_id or "",
                "session_id": session_id,
                "generation_mode": generation_mode,
                "system_prompt": system_prompt,
                "context_data": {
                    "context": context_data.context if context_data.context else "",
                    "items": context_data.items,
                },
                "messages": messages,
                "tool_calls": [],
            }

            # Create stream adapter for SSE conversion
            stream_adapter = create_stream_adapter(
                project_id=project_id,
                user_id=user_id,
                process_file_markers=True,
            )

            # Add steering callback to agent loop
            async def get_steering_messages():
                """Get pending steering messages for agent loop."""
                messages = await steering_queue.get_pending()
                return [{"id": m.id, "content": m.content} for m in messages]

            try:
                # Process through workflow stream
                # Use session_id as thread_id for trace correlation
                thread_id = f"{project_id}:{session_id}" if session_id else project_id
                async for event in stream_adapter.process_workflow_events(
                    run_writing_workflow_streaming(
                        writing_state,
                        thread_id=thread_id,
                        max_iterations=AGENT_COLLABORATION_MAX_ITERATIONS,
                        auto_review_threshold=AGENT_AUTO_REVIEW_THRESHOLD_CHARS,
                        get_steering_messages=get_steering_messages,
                    )
                ):
                    if event.type.value == "done":
                        pending_done_payload = event.data if isinstance(event.data, dict) else {}
                        continue

                    # Yield SSE event
                    yield event.to_sse()

                    # Track content for history
                    if event.type.value == "content":
                        assistant_response += event.data.get("text", "")
                    elif event.type.value == "thinking_content":
                        reasoning_content += event.data.get("content", "")
                    elif event.type.value == "tool_call":
                        tool_use_id = str(event.data.get("tool_use_id") or "").strip()
                        tool_call_record = {
                            "id": tool_use_id,
                            "name": event.data.get("tool_name", ""),
                            "arguments": event.data.get("arguments", {}),
                            "status": "pending",
                        }
                        if tool_use_id:
                            existing_index = tool_call_index_by_id.get(tool_use_id)
                            if existing_index is None:
                                tool_call_index_by_id[tool_use_id] = len(all_tool_calls)
                                all_tool_calls.append(tool_call_record)
                            else:
                                all_tool_calls[existing_index].update(tool_call_record)
                        else:
                            all_tool_calls.append(tool_call_record)
                    elif event.type.value == "tool_result":
                        tool_use_id = str(event.data.get("tool_use_id") or "").strip()
                        target_call: dict[str, Any] | None = None

                        if tool_use_id:
                            existing_index = tool_call_index_by_id.get(tool_use_id)
                            if existing_index is None:
                                target_call = {
                                    "id": tool_use_id,
                                    "name": event.data.get("tool_name", ""),
                                    "arguments": {},
                                    "status": "pending",
                                }
                                tool_call_index_by_id[tool_use_id] = len(all_tool_calls)
                                all_tool_calls.append(target_call)
                            else:
                                target_call = all_tool_calls[existing_index]
                        elif all_tool_calls:
                            target_call = all_tool_calls[-1]

                        if target_call is not None:
                            target_call["status"] = event.data.get("status", "success")
                            target_call["result"] = event.data.get("data")
                            target_call["error"] = event.data.get("error")
                    elif event.type.value == "workflow_stopped":
                        assistant_status_cards.append(
                            {
                                "type": "workflow_stopped",
                                "reason": event.data.get("reason"),
                                "agentType": event.data.get("agent_type"),
                                "message": event.data.get("message"),
                                "question": event.data.get("question"),
                                "context": event.data.get("context"),
                                "details": event.data.get("details"),
                                "confidence": event.data.get("confidence"),
                                "evaluation": event.data.get("evaluation"),
                            }
                        )
                    elif event.type.value == "iteration_exhausted":
                        assistant_status_cards.append(
                            {
                                "type": "iteration_exhausted",
                                "layer": event.data.get("layer"),
                                "iterationsUsed": event.data.get("iterations_used"),
                                "maxIterations": event.data.get("max_iterations"),
                                "reason": event.data.get("reason"),
                                "lastAgent": event.data.get("last_agent"),
                            }
                        )
                    elif event.type.value == "error":
                        had_stream_error = True

                model_metadata = stream_adapter.get_last_message_metadata()
                assistant_stop_reason = model_metadata.get("stop_reason")
                usage_candidate = model_metadata.get("usage")
                assistant_usage = usage_candidate if isinstance(usage_candidate, dict) else None
                if had_stream_error:
                    # Still persist partial history so the user and AI can
                    # recover context on the next turn instead of losing
                    # everything (user message + completed tool calls).
                    log_with_context(
                        logger,
                        30,  # WARNING
                        "Stream emitted an error event — saving partial history for recovery",
                        project_id=project_id,
                        user_id=user_id,
                        response_length=len(assistant_response),
                        tool_calls=len(all_tool_calls) if all_tool_calls else 0,
                    )

                # Save to history
                assistant_message_id = await message_manager.save_messages(
                    session,
                    session_id,
                    message,
                    assistant_response,
                    all_tool_calls if all_tool_calls else None,
                    reasoning_content if reasoning_content else None,
                    assistant_stop_reason=assistant_stop_reason,
                    assistant_usage=assistant_usage,
                    assistant_status_cards=assistant_status_cards or None,
                )
                if pending_done_payload is not None:
                    refs_candidate = pending_done_payload.get("refs")
                    refs = refs_candidate if isinstance(refs_candidate, list) else None
                    yield done_event(
                        apply_action=(
                            str(pending_done_payload.get("apply_action"))
                            if pending_done_payload.get("apply_action") is not None
                            else None
                        ),
                        refs=refs,
                        intent=(
                            str(pending_done_payload.get("intent"))
                            if pending_done_payload.get("intent") is not None
                            else None
                        ),
                        assistant_message_id=assistant_message_id,
                        session_id=session_id,
                    ).to_sse()
            finally:
                # Clean up tool context
                ToolContext.clear_context()

        except asyncio.CancelledError:
            stream_cancelled = True
            raise
        except Exception as e:
            request_failed = True
            metrics.increment_counter(AGENT_REQUESTS_ERRORS)
            log_with_context(
                logger,
                40,  # ERROR
                "Agent process_stream failed",
                project_id=project_id,
                user_id=user_id,
                error=str(e),
                error_type=type(e).__name__,
            )
            yield error_event(str(e)).to_sse()

        finally:
            # Cleanup steering queue
            if stream_cancelled:
                self._schedule_background_cleanup(
                    cleanup_steering_queue_async(session_id),
                    description="cleanup_steering_queue_async",
                    session_id=session_id,
                )
                log_with_context(
                    logger,
                    20,
                    "Scheduled steering queue cleanup in background after stream cancellation",
                    session_id=session_id,
                )
            else:
                await cleanup_steering_queue_async(session_id)

            total_duration = int((utcnow() - start_time).total_seconds() * 1000)
            metrics.observe_histogram(AGENT_REQUESTS_DURATION_MS, total_duration)
            completed_with_errors = request_failed or had_stream_error or stream_cancelled
            log_with_context(
                logger,
                30 if completed_with_errors else 20,
                (
                    "Agent process_stream completed with errors"
                    if completed_with_errors
                    else "Agent process_stream completed successfully (workflow)"
                ),
                project_id=project_id,
                user_id=user_id,
                tool_calls_count=len(all_tool_calls),
                response_length=len(assistant_response),
                duration_ms=total_duration,
                request_failed=request_failed,
                stream_error=had_stream_error,
                stream_cancelled=stream_cancelled,
            )

# Singleton
_service: AgentService | None = None


def get_agent_service() -> AgentService:
    """Get singleton agent service."""
    global _service
    if _service is None:
        _service = AgentService()
    return _service
