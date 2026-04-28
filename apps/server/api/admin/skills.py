"""
Admin Skill Review Management API endpoints.

This module contains all skill review management endpoints for admin operations.
"""
import logging

from fastapi import APIRouter, Depends, status
from sqlmodel import Session, select

from config.datetime_utils import utcnow
from core.error_codes import ErrorCode
from core.error_handler import APIException
from database import get_session
from models import PublicSkill, User, UserSkill
from services.core.auth_service import get_current_superuser
from utils.logger import get_logger, log_with_context

from .schemas import PendingSkillResponse, SkillReviewRequest

logger = get_logger(__name__)

router = APIRouter(tags=["admin-skills"])


# ==================== Skill Review Management ====================


@router.get("/skills/pending", response_model=list[PendingSkillResponse])
def get_pending_skills(
    current_user: User = Depends(get_current_superuser),
    session: Session = Depends(get_session),
):
    """
    Get all pending skills awaiting review.

    Requires superuser privileges.
    """
    stmt = (
        select(PublicSkill)
        .where(PublicSkill.status == "pending")
        .order_by(PublicSkill.created_at.asc())
    )
    skills = session.exec(stmt).all()

    result = []
    for skill in skills:
        author_name = None
        if skill.author_id:
            author = session.get(User, skill.author_id)
            author_name = author.username if author else None

        result.append(PendingSkillResponse(
            id=skill.id,
            name=skill.name,
            description=skill.description,
            instructions=skill.instructions,
            category=skill.category,
            author_id=skill.author_id,
            author_name=author_name,
            created_at=skill.created_at,
        ))

    log_with_context(
        logger,
        logging.INFO,
        "Retrieved pending skills",
        user_id=current_user.id,
        count=len(result),
    )

    return result


@router.post("/skills/{skill_id}/approve")
def approve_skill(
    skill_id: str,
    current_user: User = Depends(get_current_superuser),
    session: Session = Depends(get_session),
):
    """
    Approve a pending skill.

    Requires superuser privileges.
    """
    skill = session.get(PublicSkill, skill_id)
    if not skill:
        raise APIException(
            error_code=ErrorCode.NOT_FOUND,
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Skill not found",
        )

    if skill.status != "pending":
        raise APIException(
            error_code=ErrorCode.VALIDATION_ERROR,
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Skill is not pending review",
        )

    skill.status = "approved"
    skill.reviewed_by = current_user.id
    skill.reviewed_at = utcnow()
    skill.updated_at = utcnow()

    session.add(skill)
    session.commit()

    log_with_context(
        logger,
        logging.INFO,
        "Approved skill",
        user_id=current_user.id,
        skill_id=skill_id,
        skill_name=skill.name,
    )

    return {"message": "Skill approved successfully", "skill_id": skill_id}


@router.post("/skills/{skill_id}/reject")
def reject_skill(
    skill_id: str,
    request: SkillReviewRequest,
    current_user: User = Depends(get_current_superuser),
    session: Session = Depends(get_session),
):
    """
    Reject a pending skill.

    Requires superuser privileges.
    """
    skill = session.get(PublicSkill, skill_id)
    if not skill:
        raise APIException(
            error_code=ErrorCode.NOT_FOUND,
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Skill not found",
        )

    if skill.status != "pending":
        raise APIException(
            error_code=ErrorCode.VALIDATION_ERROR,
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Skill is not pending review",
        )

    skill.status = "rejected"
    skill.reviewed_by = current_user.id
    skill.reviewed_at = utcnow()
    skill.rejection_reason = request.rejection_reason
    skill.updated_at = utcnow()

    # Reset original user skill sharing state so author can resubmit after edits.
    user_skills = session.exec(
        select(UserSkill).where(UserSkill.shared_skill_id == skill.id)
    ).all()
    for user_skill in user_skills:
        user_skill.is_shared = False
        user_skill.shared_skill_id = None
        user_skill.updated_at = utcnow()
        session.add(user_skill)

    session.add(skill)
    session.commit()

    log_with_context(
        logger,
        logging.INFO,
        "Rejected skill",
        user_id=current_user.id,
        skill_id=skill_id,
        skill_name=skill.name,
        reason=request.rejection_reason,
    )

    return {"message": "Skill rejected", "skill_id": skill_id}
