"""
Admin User Management API endpoints.

This module contains all user management endpoints for admin operations.
"""
import logging

from fastapi import APIRouter, Depends, Query, status
from sqlmodel import Session, select

from config.datetime_utils import utcnow
from core.error_codes import ErrorCode
from core.error_handler import APIException
from database import get_session
from models import User
from services.core.auth_service import get_current_superuser
from utils.logger import get_logger, log_with_context

from .schemas import UserUpdateRequest

logger = get_logger(__name__)

router = APIRouter(tags=["admin-users"])


# ==================== User Management ====================

@router.get("/users", response_model=list[User])
def get_users(
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(20, ge=1, le=1000, description="Number of records to return"),
    search: str | None = Query(None, description="Search by username or email"),
    current_user: User = Depends(get_current_superuser),
    session: Session = Depends(get_session),
):
    """
    Get all users with pagination and search support.

    Requires superuser privileges.
    """
    query = select(User)

    # Apply search filter if provided
    if search:
        search_pattern = f"%{search}%"
        query = query.where(
            (User.username.ilike(search_pattern)) | (User.email.ilike(search_pattern))
        )

    # Apply pagination
    query = query.offset(skip).limit(limit)

    users = session.exec(query).all()

    log_with_context(
        logger,
        logging.INFO,
        "Retrieved users list",
        user_id=current_user.id,
        count=len(users),
        skip=skip,
        limit=limit,
        search=search,
    )

    return users


@router.get("/users/{user_id}", response_model=User)
def get_user(
    user_id: str,
    current_user: User = Depends(get_current_superuser),
    session: Session = Depends(get_session),
):
    """
    Get a specific user by ID.

    Requires superuser privileges.
    """
    user = session.get(User, user_id)
    if not user:
        raise APIException(
            error_code=ErrorCode.NOT_AUTHORIZED,
            status_code=status.HTTP_404_NOT_FOUND,
        )

    log_with_context(
        logger,
        logging.INFO,
        "Retrieved user details",
        user_id=current_user.id,
        target_user_id=user_id,
    )

    return user


@router.put("/users/{user_id}", response_model=User)
def update_user(
    user_id: str,
    user_update: UserUpdateRequest,
    current_user: User = Depends(get_current_superuser),
    session: Session = Depends(get_session),
):
    """
    Update a user's information.

    Requires superuser privileges.
    """
    user = session.get(User, user_id)
    if not user:
        raise APIException(
            error_code=ErrorCode.NOT_AUTHORIZED,
            status_code=status.HTTP_404_NOT_FOUND,
        )

    # Update fields if provided
    update_data = user_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(user, field, value)

    user.updated_at = utcnow()

    session.add(user)
    session.commit()
    session.refresh(user)

    log_with_context(
        logger,
        logging.INFO,
        "Updated user",
        user_id=current_user.id,
        target_user_id=user_id,
        updated_fields=list(update_data.keys()),
    )

    return user


@router.delete("/users/{user_id}", response_model=User)
def delete_user(
    user_id: str,
    current_user: User = Depends(get_current_superuser),
    session: Session = Depends(get_session),
):
    """
    Soft delete a user by setting is_active to False.

    Requires superuser privileges.
    """
    user = session.get(User, user_id)
    if not user:
        raise APIException(
            error_code=ErrorCode.NOT_AUTHORIZED,
            status_code=status.HTTP_404_NOT_FOUND,
        )

    # Prevent self-deletion
    if user_id == current_user.id:
        raise APIException(
            error_code=ErrorCode.NOT_AUTHORIZED,
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    user.is_active = False
    user.updated_at = utcnow()

    session.add(user)
    session.commit()
    session.refresh(user)

    log_with_context(
        logger,
        logging.INFO,
        "Soft deleted user",
        user_id=current_user.id,
        target_user_id=user_id,
    )

    return user
