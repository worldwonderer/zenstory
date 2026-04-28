"""
Admin Audit Log API endpoints.

This module contains audit log endpoints for admin operations.
"""
import logging

from fastapi import APIRouter, Depends, Query
from sqlmodel import Session

from database import get_session
from models import User
from services.admin_audit_service import admin_audit_service
from services.core.auth_service import get_current_superuser
from utils.logger import get_logger, log_with_context

from .schemas import AuditLogListResponse

logger = get_logger(__name__)

router = APIRouter(tags=["admin-audit"])


# ==================== Audit Logs ====================


@router.get("/audit-logs", response_model=AuditLogListResponse)
def list_audit_logs(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=200, description="Items per page"),
    resource_type: str | None = Query(None, description="Filter by resource type"),
    action: str | None = Query(None, description="Filter by action"),
    current_user: User = Depends(get_current_superuser),
    session: Session = Depends(get_session),
):
    """
    List audit logs with filters.

    Requires superuser privileges.
    """
    logs = admin_audit_service.get_audit_logs(
        session,
        resource_type=resource_type,
        action=action,
        limit=page_size,
        offset=(page - 1) * page_size
    )

    log_with_context(
        logger,
        logging.INFO,
        "Retrieved audit logs",
        user_id=current_user.id,
        count=len(logs),
        resource_type=resource_type,
        action=action,
    )

    return AuditLogListResponse(
        items=[log.model_dump() for log in logs],
        page=page,
        page_size=page_size
    )
