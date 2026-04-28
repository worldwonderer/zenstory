"""
Agent API endpoints.

Provides FastAPI router for agent endpoints:
- POST /api/v1/agent/stream - Stream AI response with Function Calling
- GET /api/v1/agent/health - Health check
- POST /api/v1/agent/suggest - Generate intelligent next-step suggestions
"""

import asyncio
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Depends, Header
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from services.auth import get_current_active_user
from sqlmodel import Session

from agent.service import get_agent_service
from core.error_codes import ErrorCode
from core.error_handler import APIException
from database import create_session, get_session
from models import User
from services.quota_service import quota_service
from utils.logger import get_logger, log_with_context
from utils.permission import verify_project_access
from utils.request_context import bind_request_context, reset_request_context

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1/agent", tags=["Agent"])


def _should_offload_session_work(session: Session) -> bool:
    """Only offload when running against PostgreSQL production-style sessions."""
    bind = session.get_bind() if hasattr(session, "get_bind") else None
    dialect_name = getattr(getattr(bind, "dialect", None), "name", "")
    return dialect_name == "postgresql"


def _check_ai_conversation_quota_sync(user_id: str) -> tuple[bool, int, int]:
    """Check quota using a fresh sync DB session."""
    with create_session() as quota_session:
        return quota_service.check_ai_conversation_quota(quota_session, user_id)


def _consume_ai_conversation_sync(user_id: str) -> bool:
    """Consume quota using a fresh sync DB session."""
    with create_session() as quota_session:
        return quota_service.consume_ai_conversation(quota_session, user_id)


def _release_ai_conversation_sync(user_id: str) -> bool:
    """Release quota using a fresh sync DB session."""
    with create_session() as quota_session:
        return quota_service.release_ai_conversation(quota_session, user_id)


# ==================== Request Models ====================


class AgentRequest(BaseModel):
    """Request body for agent processing."""

    project_id: str = Field(..., description="Project ID (UUID)")
    message: str = Field(..., description="User message")
    session_id: str | None = Field(
        default=None,
        description="Optional session ID for steering continuity",
    )
    selected_text: str | None = Field(default=None, description="Selected text")
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Additional metadata"
    )


class SuggestRequest(BaseModel):
    """Request body for suggestion generation."""

    project_id: str = Field(..., description="Project ID (UUID)")
    recent_messages: list | None = Field(
        default=None, description="Recent conversation messages"
    )
    count: int = Field(
        default=3, ge=1, le=5, description="Number of suggestions to generate"
    )


class SuggestResponse(BaseModel):
    """Response body for suggestion generation."""

    suggestions: list[str] = Field(..., description="Generated suggestion texts")


class SteeringRequest(BaseModel):
    """Request body for steering message."""

    session_id: str = Field(..., description="Active session ID")
    message: str = Field(..., description="Steering message content")


class SteeringResponse(BaseModel):
    """Response for steering message."""

    message_id: str
    queued: bool


# ==================== Endpoints ====================


@router.post("/stream")
async def stream_request(
    body: AgentRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_active_user),
    accept_language: str | None = Header(None, alias="Accept-Language"),
):
    """
    Process request with streaming SSE output.

    Returns Server-Sent Events:
    - thinking: Status updates
    - tool_call: AI is calling a tool
    - tool_result: Tool execution result
    - content: Generated content chunks
    - done: Processing complete
    - error: Error occurred
    """
    service = get_agent_service()
    user_id = current_user.id
    message_preview = body.message[:100] + "..." if len(body.message) > 100 else body.message

    # Verify project access first to avoid charging quota for unauthorized/invalid projects
    await verify_project_access(body.project_id, session, current_user)

    # If a runtime session_id is provided, ensure it is either:
    # - an existing queue owned by current user, or
    # - a brand-new queue id (KeyError -> allowed and created later).
    if body.session_id:
        from agent.core.steering import get_steering_queue_for_user_async

        try:
            await get_steering_queue_for_user_async(body.session_id, current_user.id)
        except KeyError:
            # New runtime session id - allow creation in service layer.
            pass
        except PermissionError as exc:
            raise APIException(
                error_code=ErrorCode.NOT_AUTHORIZED,
                status_code=403,
                detail="Not authorized to reuse this runtime session",
            ) from exc

    # Check AI conversation quota (pre-flight check for better UX).
    if _should_offload_session_work(session):
        allowed, used, limit = await asyncio.to_thread(
            _check_ai_conversation_quota_sync,
            current_user.id,
        )
    else:
        allowed, used, limit = quota_service.check_ai_conversation_quota(session, current_user.id)
    if not allowed:
        raise APIException(
            error_code=ErrorCode.QUOTA_AI_CONVERSATIONS_EXCEEDED,
            status_code=402,
            detail=f"AI conversation quota exceeded ({used}/{limit}). Please upgrade your plan.",
        )

    agent_run_id = uuid4().hex

    log_with_context(
        logger,
        20,  # INFO
        "stream_request received",
        agent_run_id=agent_run_id,
        project_id=body.project_id,
        user_id=user_id,
        message_length=len(body.message),
        message_preview=message_preview,
        has_selected_text=body.selected_text is not None,
        language=accept_language,
    )

    lang = (accept_language or "").split(",")[0].split("-")[0].strip().lower() or "zh"

    try:
        # Reserve one quota unit before streaming to avoid concurrent overrun.
        # We may compensate (refund) in finally when the stream fails internally.
        if _should_offload_session_work(session):
            consumed = await asyncio.to_thread(
                _consume_ai_conversation_sync,
                current_user.id,
            )
        else:
            consumed = quota_service.consume_ai_conversation(session, current_user.id)
        if not consumed:
            raise APIException(
                error_code=ErrorCode.QUOTA_AI_CONVERSATIONS_EXCEEDED,
                status_code=402,
                detail=f"AI conversation quota exceeded ({used}/{limit}). Please upgrade your plan.",
            )

        async def event_generator():
            agent_ctx_tokens = bind_request_context(agent_run_id=agent_run_id)
            saw_any_event = False
            saw_terminal_event = False
            saw_internal_error_event = False
            user_cancelled = False
            unexpected_exception = False
            billing_reason = "completed"

            def _extract_sse_event_type(sse_payload: str) -> str:
                for line in sse_payload.splitlines():
                    if line.startswith("event:"):
                        return line.split(":", 1)[1].strip()
                return ""

            try:
                async for event in service.process_stream(
                    project_id=body.project_id,
                    user_id=user_id,
                    message=body.message,
                    session_id=body.session_id,
                    session=session,
                    selected_text=body.selected_text,
                    metadata=body.metadata,
                    language=lang,
                ):
                    saw_any_event = True
                    if isinstance(event, str):
                        event_type = _extract_sse_event_type(event)
                        if event_type in {"done", "workflow_complete", "workflow_stopped"}:
                            saw_terminal_event = True
                        elif event_type == "error":
                            saw_internal_error_event = True
                            saw_terminal_event = True
                    yield event
            except asyncio.CancelledError:
                user_cancelled = True
                billing_reason = "user_cancelled"
                raise
            except Exception:
                unexpected_exception = True
                billing_reason = "internal_exception"
                raise
            finally:
                should_refund = False
                if user_cancelled:
                    billing_reason = "user_cancelled"
                elif saw_terminal_event and not saw_internal_error_event and not unexpected_exception:
                    billing_reason = "completed"
                else:
                    billing_reason = "internal_error"
                    if saw_any_event and not saw_terminal_event and not unexpected_exception:
                        billing_reason = "internal_error_no_terminal"
                    should_refund = True

                refund_applied = False
                if should_refund:
                    try:
                        if _should_offload_session_work(session):
                            refund_applied = await asyncio.to_thread(
                                _release_ai_conversation_sync,
                                current_user.id,
                            )
                        else:
                            refund_applied = quota_service.release_ai_conversation(session, current_user.id)
                    except Exception as refund_error:
                        log_with_context(
                            logger,
                            30,  # WARNING
                            "Failed to refund AI conversation quota after stream error",
                            user_id=user_id,
                            project_id=body.project_id,
                            agent_run_id=agent_run_id,
                            error=str(refund_error),
                            error_type=type(refund_error).__name__,
                            billing_reason=billing_reason,
                        )

                log_with_context(
                    logger,
                    20,
                    "Agent stream billing evaluated",
                    user_id=user_id,
                    project_id=body.project_id,
                    agent_run_id=agent_run_id,
                    charged=not should_refund,
                    refunded=refund_applied,
                    billing_reason=billing_reason,
                    saw_any_event=saw_any_event,
                    saw_terminal_event=saw_terminal_event,
                    saw_internal_error_event=saw_internal_error_event,
                    user_cancelled=user_cancelled,
                    unexpected_exception=unexpected_exception,
                )
                reset_request_context(agent_ctx_tokens)

        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
                "X-Agent-Run-ID": agent_run_id,
            },
        )
    except Exception:
        raise


@router.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "agent"}


@router.post("/suggest", response_model=SuggestResponse)
async def suggest_next_action(
    body: SuggestRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_active_user),
    accept_language: str | None = Header(None, alias="Accept-Language"),
):
    """
    Generate intelligent next-step suggestions.

    Returns multiple short suggestions (~15 characters each) based on:
    - Project context (outlines, characters, lores)
    - Recent conversation history
    """
    user_id = current_user.id
    from agent.suggest_service import get_suggest_service

    # Keep authorization behavior consistent with chat/stream endpoints
    await verify_project_access(body.project_id, session, current_user)

    log_with_context(
        logger,
        20,  # INFO
        "suggest_next_action called",
        project_id=body.project_id,
        user_id=user_id,
        count=body.count,
        has_recent_messages=body.recent_messages is not None,
        message_count=len(body.recent_messages) if body.recent_messages else 0,
    )

    service = get_suggest_service()
    lang = (accept_language or "").split(",")[0].split("-")[0].strip().lower() or "zh"

    suggestions = await service.generate_suggestions(
        session=session,
        project_id=body.project_id,
        user_id=user_id,
        recent_messages=body.recent_messages,
        count=body.count,
        language=lang,
    )

    log_with_context(
        logger,
        20,  # INFO
        "suggest_next_action completed",
        project_id=body.project_id,
        suggestion_count=len(suggestions),
    )

    return SuggestResponse(suggestions=suggestions)


@router.post("/steer", response_model=SteeringResponse)
async def inject_steering(
    body: SteeringRequest,
    current_user: User = Depends(get_current_active_user),
):
    """
    Inject a steering message into an active agent session.

    Steering messages allow users to provide mid-execution guidance
    to the running agent loop without interrupting the conversation.
    """
    from agent.core.steering import get_steering_queue_for_user_async

    log_with_context(
        logger,
        20,  # INFO
        "inject_steering called",
        session_id=body.session_id,
        user_id=current_user.id,
        message_length=len(body.message),
    )

    try:
        queue = await get_steering_queue_for_user_async(body.session_id, current_user.id)
    except KeyError as exc:
        raise APIException(
            error_code=ErrorCode.CHAT_SESSION_NOT_FOUND,
            status_code=404,
            detail="Agent session not found",
        ) from exc
    except PermissionError as exc:
        raise APIException(
            error_code=ErrorCode.NOT_AUTHORIZED,
            status_code=403,
            detail="Not authorized to steer this session",
        ) from exc

    try:
        msg = await queue.add(body.message)
    except ValueError as exc:
        raise APIException(
            error_code=ErrorCode.BAD_REQUEST,
            status_code=400,
            detail=str(exc),
        ) from exc

    log_with_context(
        logger,
        20,  # INFO
        "inject_steering completed",
        session_id=body.session_id,
        message_id=msg.id,
    )

    return SteeringResponse(message_id=msg.id, queued=True)
