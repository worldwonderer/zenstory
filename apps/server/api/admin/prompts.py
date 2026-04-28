"""
Admin System Prompt Configuration API endpoints.

This module contains all system prompt configuration endpoints for admin operations.
"""
import logging

from fastapi import APIRouter, Depends, status
from sqlmodel import Session, select

from config.datetime_utils import utcnow
from core.error_codes import ErrorCode
from core.error_handler import APIException
from database import get_session
from models import SystemPromptConfig, User
from services.core.auth_service import get_current_superuser
from utils.logger import get_logger, log_with_context

from .schemas import SystemPromptConfigRequest

logger = get_logger(__name__)

router = APIRouter(tags=["admin-prompts"])


# ==================== System Prompt Management ====================

@router.get("/prompts", response_model=list[SystemPromptConfig])
def get_prompts(
    current_user: User = Depends(get_current_superuser),
    session: Session = Depends(get_session),
):
    """
    Get all system prompt configurations.

    Requires superuser privileges.
    """
    prompts = session.exec(select(SystemPromptConfig)).all()

    log_with_context(
        logger,
        logging.INFO,
        "Retrieved all system prompt configurations",
        user_id=current_user.id,
        count=len(prompts),
    )

    return prompts


@router.get("/prompts/{project_type}", response_model=SystemPromptConfig)
def get_prompt(
    project_type: str,
    current_user: User = Depends(get_current_superuser),
    session: Session = Depends(get_session),
):
    """
    Get a specific system prompt configuration by project type.

    Requires superuser privileges.
    """
    prompt = session.exec(
        select(SystemPromptConfig).where(SystemPromptConfig.project_type == project_type)
    ).first()

    if not prompt:
        raise APIException(
            error_code=ErrorCode.NOT_AUTHORIZED,
            status_code=status.HTTP_404_NOT_FOUND,
        )

    log_with_context(
        logger,
        logging.INFO,
        "Retrieved system prompt configuration",
        user_id=current_user.id,
        project_type=project_type,
    )

    return prompt


@router.put("/prompts/{project_type}", response_model=SystemPromptConfig)
def upsert_prompt(
    project_type: str,
    prompt_request: SystemPromptConfigRequest,
    current_user: User = Depends(get_current_superuser),
    session: Session = Depends(get_session),
):
    """
    Create or update a system prompt configuration.

    Requires superuser privileges.
    """
    # Check if configuration already exists
    existing_prompt = session.exec(
        select(SystemPromptConfig).where(SystemPromptConfig.project_type == project_type)
    ).first()

    if existing_prompt:
        # Update existing configuration
        update_data = prompt_request.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(existing_prompt, field, value)

        existing_prompt.updated_by = current_user.id
        existing_prompt.updated_at = utcnow()
        existing_prompt.version += 1

        session.add(existing_prompt)
        session.commit()
        session.refresh(existing_prompt)

        log_with_context(
            logger,
            logging.INFO,
            "Updated system prompt configuration",
            user_id=current_user.id,
            project_type=project_type,
            version=existing_prompt.version,
        )

        return existing_prompt
    else:
        # Create new configuration
        new_prompt = SystemPromptConfig(
            project_type=project_type,
            role_definition=prompt_request.role_definition,
            capabilities=prompt_request.capabilities,
            directory_structure=prompt_request.directory_structure,
            content_structure=prompt_request.content_structure,
            file_types=prompt_request.file_types,
            writing_guidelines=prompt_request.writing_guidelines,
            include_dialogue_guidelines=prompt_request.include_dialogue_guidelines,
            primary_content_type=prompt_request.primary_content_type,
            is_active=prompt_request.is_active,
            created_by=current_user.id,
            updated_by=current_user.id,
        )

        session.add(new_prompt)
        session.commit()
        session.refresh(new_prompt)

        log_with_context(
            logger,
            logging.INFO,
            "Created system prompt configuration",
            user_id=current_user.id,
            project_type=project_type,
        )

        return new_prompt


@router.delete("/prompts/{project_type}")
def delete_prompt(
    project_type: str,
    current_user: User = Depends(get_current_superuser),
    session: Session = Depends(get_session),
):
    """
    Delete a system prompt configuration.

    Requires superuser privileges.
    """
    prompt = session.exec(
        select(SystemPromptConfig).where(SystemPromptConfig.project_type == project_type)
    ).first()

    if not prompt:
        raise APIException(
            error_code=ErrorCode.NOT_AUTHORIZED,
            status_code=status.HTTP_404_NOT_FOUND,
        )

    session.delete(prompt)
    session.commit()

    log_with_context(
        logger,
        logging.INFO,
        "Deleted system prompt configuration",
        user_id=current_user.id,
        project_type=project_type,
    )

    return {"message": "System prompt configuration deleted successfully"}


@router.post("/prompts/reload")
def reload_prompts_endpoint(
    current_user: User = Depends(get_current_superuser),
):
    """
    Reload system prompt configurations from database.

    This endpoint clears any in-memory cache and triggers a reload
    of system prompt configurations from the database.

    Requires superuser privileges.
    """
    # Import and call the reload function from agent.prompts module
    from agent.prompts import reload_prompts

    reload_prompts()

    log_with_context(
        logger,
        logging.INFO,
        "Reloaded system prompt configurations",
        user_id=current_user.id,
    )

    return {"message": "System prompt configurations reloaded successfully"}
