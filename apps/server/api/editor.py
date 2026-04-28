"""Editor utility endpoints."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Header
from pydantic import BaseModel, Field
from services.auth import get_current_active_user
from sqlmodel import Session

from core.error_codes import ErrorCode
from core.error_handler import APIException
from database import get_session
from models import User
from services.features.natural_polish_service import natural_polish_service
from services.quota_service import quota_service
from utils.permission import verify_project_access

router = APIRouter(prefix="/api/v1/editor", tags=["editor"])

MAX_SELECTED_TEXT_LENGTH = 6000


class NaturalPolishRequest(BaseModel):
    """Request payload for natural polish."""

    project_id: str = Field(..., description="Project ID")
    selected_text: str = Field(..., description="Selected text to rewrite")
    metadata: dict[str, Any] = Field(default_factory=dict)


class NaturalPolishResponse(BaseModel):
    """Response payload for natural polish."""

    text: str
    model: str | None = None


@router.post("/natural-polish", response_model=NaturalPolishResponse)
async def natural_polish(
    body: NaturalPolishRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_active_user),
    accept_language: str | None = Header(None, alias="Accept-Language"),
) -> NaturalPolishResponse:
    """Single-round natural polish (non-streaming)."""
    await verify_project_access(body.project_id, session, current_user)

    if not body.selected_text.strip():
        raise APIException(
            error_code=ErrorCode.VALIDATION_ERROR,
            status_code=422,
            detail="selected_text cannot be empty.",
        )

    if len(body.selected_text) > MAX_SELECTED_TEXT_LENGTH:
        raise APIException(
            error_code=ErrorCode.VALIDATION_ERROR,
            status_code=422,
            detail=f"selected_text must be <= {MAX_SELECTED_TEXT_LENGTH} characters.",
        )

    allowed, used, limit = quota_service.check_ai_conversation_quota(session, current_user.id)
    if not allowed:
        raise APIException(
            error_code=ErrorCode.QUOTA_AI_CONVERSATIONS_EXCEEDED,
            status_code=402,
            detail=f"AI conversation quota exceeded ({used}/{limit}). Please upgrade your plan.",
        )

    # Consume quota before generation (failure does not refund; aligns with stream endpoint).
    consumed = quota_service.consume_ai_conversation(session, current_user.id)
    if not consumed:
        raise APIException(
            error_code=ErrorCode.QUOTA_AI_CONVERSATIONS_EXCEEDED,
            status_code=402,
            detail="AI conversation quota exceeded. Please upgrade your plan.",
        )

    lang = (accept_language or "").split(",")[0].split("-")[0].strip().lower() or "zh"

    try:
        result = await natural_polish_service.natural_polish(
            selected_text=body.selected_text,
            language=lang,
        )
    except APIException:
        raise
    except Exception as exc:
        raise APIException(
            error_code=ErrorCode.INTERNAL_SERVER_ERROR,
            status_code=500,
            detail=f"Natural polish failed: {type(exc).__name__}",
        ) from exc

    return NaturalPolishResponse(
        text=result.polished_text,
        model=result.model,
    )
