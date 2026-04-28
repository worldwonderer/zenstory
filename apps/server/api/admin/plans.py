"""
Admin Subscription Plan Management API endpoints.

This module contains all subscription plan management endpoints for admin operations.
"""
import logging

from fastapi import APIRouter, Depends, Request, status
from sqlmodel import Session, select

from config.datetime_utils import utcnow
from core.error_codes import ErrorCode
from core.error_handler import APIException
from database import get_session
from models import User
from models.subscription import SubscriptionPlan
from services.admin_audit_service import admin_audit_service
from services.core.auth_service import get_current_superuser
from utils.logger import get_logger, log_with_context

from .schemas import PlanUpdateRequest

logger = get_logger(__name__)

router = APIRouter(tags=["admin-plans"])


# ==================== Plan Management ====================


@router.get("/plans", response_model=list[SubscriptionPlan])
def list_plans(
    current_user: User = Depends(get_current_superuser),
    session: Session = Depends(get_session),
):
    """
    List all subscription plans.

    Requires superuser privileges.
    """
    plans = session.exec(select(SubscriptionPlan)).all()

    log_with_context(
        logger,
        logging.INFO,
        "Retrieved subscription plans list",
        user_id=current_user.id,
        count=len(plans),
    )

    return plans


@router.put("/plans/{plan_id}", response_model=SubscriptionPlan)
def update_plan(
    plan_id: str,
    request: PlanUpdateRequest,
    http_request: Request,
    current_user: User = Depends(get_current_superuser),
    session: Session = Depends(get_session),
):
    """
    Update a subscription plan.

    Requires superuser privileges.
    """
    plan = session.get(SubscriptionPlan, plan_id)
    if not plan:
        raise APIException(
            error_code=ErrorCode.NOT_FOUND,
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Plan not found"
        )

    # Store old values for audit log
    old_value = {
        "display_name": plan.display_name,
        "display_name_en": plan.display_name_en,
        "price_monthly_cents": plan.price_monthly_cents,
        "price_yearly_cents": plan.price_yearly_cents,
        "features": plan.features,
        "is_active": plan.is_active,
    }

    # Update fields if provided
    if request.display_name is not None:
        plan.display_name = request.display_name
    if request.display_name_en is not None:
        plan.display_name_en = request.display_name_en
    if request.price_monthly_cents is not None:
        plan.price_monthly_cents = request.price_monthly_cents
    if request.price_yearly_cents is not None:
        plan.price_yearly_cents = request.price_yearly_cents
    if request.features is not None:
        plan.features = request.features
    if request.is_active is not None:
        plan.is_active = request.is_active

    plan.updated_at = utcnow()

    session.add(plan)
    session.commit()
    session.refresh(plan)

    # Audit log
    new_value = {
        "display_name": plan.display_name,
        "display_name_en": plan.display_name_en,
        "price_monthly_cents": plan.price_monthly_cents,
        "price_yearly_cents": plan.price_yearly_cents,
        "features": plan.features,
        "is_active": plan.is_active,
    }
    admin_audit_service.log_action(
        session, current_user.id, "update_plan", "plan", plan_id,
        old_value=old_value,
        new_value=new_value,
        request=http_request
    )

    log_with_context(
        logger,
        logging.INFO,
        "Updated subscription plan",
        user_id=current_user.id,
        plan_id=plan_id,
        plan_name=plan.name,
    )

    return plan
