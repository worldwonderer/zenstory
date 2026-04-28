"""
Admin Check-in Management API endpoints.

This module contains check-in statistics endpoints for admin operations.
"""
import logging
from datetime import timedelta

from fastapi import APIRouter, Depends, Query
from sqlmodel import Session, func, select

from config.datetime_utils import utcnow
from database import get_session
from models import User
from models.points import CheckInRecord
from services.core.auth_service import get_current_superuser
from utils.logger import get_logger, log_with_context

from .schemas import (
    CheckInRecordListResponse,
    CheckInRecordResponse,
    CheckInStatsResponse,
)

logger = get_logger(__name__)

router = APIRouter(tags=["admin-checkin"])


# ==================== Check-in Stats ====================


@router.get("/check-in/stats", response_model=CheckInStatsResponse)
def get_check_in_stats(
    current_user: User = Depends(get_current_superuser),
    session: Session = Depends(get_session),
):
    """
    Get check-in statistics.

    Requires superuser privileges.
    """
    today = utcnow().date()
    yesterday = today - timedelta(days=1)
    week_ago = today - timedelta(days=7)

    # Today's check-ins
    today_count = session.exec(
        select(func.count()).select_from(CheckInRecord).where(CheckInRecord.check_in_date == today)
    ).one()

    # Yesterday's check-ins
    yesterday_count = session.exec(
        select(func.count()).select_from(CheckInRecord).where(CheckInRecord.check_in_date == yesterday)
    ).one()

    # Week total
    week_total = session.exec(
        select(func.count()).select_from(CheckInRecord).where(CheckInRecord.check_in_date >= week_ago)
    ).one()

    # Streak distribution (7, 14, 30 days)
    streak_distribution = {}
    for threshold in [7, 14, 30]:
        count = session.exec(
            select(func.count()).select_from(CheckInRecord)
            .where(CheckInRecord.check_in_date == today)
            .where(CheckInRecord.streak_days >= threshold)
        ).one()
        if count > 0:
            streak_distribution[str(threshold)] = count

    log_with_context(
        logger,
        logging.INFO,
        "Retrieved check-in stats",
        user_id=current_user.id,
        today_count=today_count,
        week_total=week_total,
    )

    return CheckInStatsResponse(
        today_count=today_count,
        yesterday_count=yesterday_count,
        week_total=week_total,
        streak_distribution=streak_distribution,
    )


@router.get("/check-in/records", response_model=CheckInRecordListResponse)
def get_check_in_records(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    user_id_filter: str | None = Query(None, alias="user_id", description="Filter by user ID"),
    current_user: User = Depends(get_current_superuser),
    session: Session = Depends(get_session),
):
    """
    Get check-in records with pagination.

    Requires superuser privileges.
    """
    base_query = select(CheckInRecord)

    if user_id_filter:
        base_query = base_query.where(CheckInRecord.user_id == user_id_filter)

    # Get total count
    count_query = select(func.count()).select_from(base_query.subquery())
    total = session.exec(count_query).one()

    # Apply pagination
    query = (
        select(CheckInRecord, User.username)
        .select_from(CheckInRecord)
        .join(User, User.id == CheckInRecord.user_id, isouter=True)
    )
    if user_id_filter:
        query = query.where(CheckInRecord.user_id == user_id_filter)
    query = query.order_by(CheckInRecord.check_in_date.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)

    records = session.exec(query).all()

    items = []
    for record, username in records:
        items.append(CheckInRecordResponse(
            id=record.id,
            user_id=record.user_id,
            username=username or "Unknown",
            check_in_date=record.check_in_date,
            streak_days=record.streak_days,
            points_earned=record.points_earned,
            created_at=record.created_at,
        ))

    log_with_context(
        logger,
        logging.INFO,
        "Retrieved check-in records",
        user_id=current_user.id,
        count=len(items),
        user_id_filter=user_id_filter,
    )

    return CheckInRecordListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
    )
