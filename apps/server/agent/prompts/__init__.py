"""
AI Prompt templates for different project types.

This module provides modular prompt templates that can be customized
based on project type (novel, short story, screenplay).

The module supports loading prompt configurations from:
1. Remote database (PROMPT_DATABASE_URL) - highest priority
2. Local database (DATABASE_URL) - fallback
3. Default Python constants - final fallback when no DB config exists
"""

import os
from typing import Any

from sqlalchemy import create_engine
from sqlmodel import Session, select

from database import sync_engine

from .base import get_base_prompt
from .novel import NOVEL_PROMPT_CONFIG
from .screenplay import SCREENPLAY_PROMPT_CONFIG
from .short_story import SHORT_STORY_PROMPT_CONFIG
from .subagents import PLANNER_PROMPT, QUALITY_REVIEWER_PROMPT, WRITER_PROMPT
from .suggestions import get_suggestion_prompt

# Map project types to their prompt configurations (fallback defaults)
PROMPT_CONFIGS: dict[str, dict[str, Any]] = {
    "novel": NOVEL_PROMPT_CONFIG,
    "short": SHORT_STORY_PROMPT_CONFIG,
    "screenplay": SCREENPLAY_PROMPT_CONFIG,
}

# In-memory cache for database configurations
_db_config_cache: dict[str, dict[str, Any]] | None = None

# Remote prompt database engine (lazy initialization)
_remote_engine = None


def _get_remote_engine():
    """
    Get or create the remote prompt database engine.

    Uses PROMPT_DATABASE_URL environment variable for remote prompt management.
    Returns None if not configured.
    """
    global _remote_engine

    if _remote_engine is not None:
        return _remote_engine

    remote_url = os.getenv("PROMPT_DATABASE_URL")
    if not remote_url:
        return None

    try:
        _remote_engine = create_engine(remote_url, pool_size=5, max_overflow=0)
        return _remote_engine
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.warning(f"Failed to create remote prompt database engine: {e}")
        return None


def _load_db_configs() -> dict[str, dict[str, Any]]:
    """
    Load all active system prompt configurations from database.

    Priority order:
    1. Remote database (PROMPT_DATABASE_URL) - for centralized prompt management
    2. Local database (DATABASE_URL) - fallback
    3. Returns empty dict if both fail (will use file-based defaults)

    Returns:
        Dict mapping project_type to config dict
    """
    global _db_config_cache

    # Return cached configs if available
    if _db_config_cache is not None:
        return _db_config_cache

    db_configs = {}
    import logging
    logger = logging.getLogger(__name__)

    # Try remote database first
    remote_engine = _get_remote_engine()
    if remote_engine is not None:
        try:
            db_configs = _load_configs_from_engine(remote_engine, "remote")
            if db_configs:
                logger.info(f"Loaded {len(db_configs)} prompt configs from remote database")
                _db_config_cache = db_configs
                return db_configs
        except Exception as e:
            logger.warning(f"Failed to load from remote database: {e}")

    # Fallback to local database
    try:
        db_configs = _load_configs_from_engine(sync_engine, "local")
        if db_configs:
            logger.info(f"Loaded {len(db_configs)} prompt configs from local database")
    except Exception as e:
        logger.error(f"Failed to load from local database: {e}")
        db_configs = {}

    # Cache the loaded configs
    _db_config_cache = db_configs
    return db_configs


def _load_configs_from_engine(engine, _source: str) -> dict[str, dict[str, Any]]:
    """
    Load prompt configurations from a specific database engine.

    Args:
        engine: SQLAlchemy engine to use
        source: Source name for logging ("remote" or "local")

    Returns:
        Dict mapping project_type to config dict
    """
    configs = {}

    with Session(engine) as session:
        from models import SystemPromptConfig

        results = session.exec(
            select(SystemPromptConfig).where(SystemPromptConfig.is_active)
        ).all()

        for config in results:
            configs[config.project_type] = {
                "role_definition": config.role_definition,
                "capabilities": config.capabilities,
                "directory_structure": config.directory_structure or "",
                "content_structure": config.content_structure or "",
                "file_types": config.file_types or "",
                "writing_guidelines": config.writing_guidelines or "",
                "include_dialogue_guidelines": config.include_dialogue_guidelines,
                "primary_content_type": config.primary_content_type or "draft",
            }

    return configs


def get_prompt_for_project_type(
    project_type: str,
    project_id: str,
    folder_ids: dict[str, str],
) -> str:
    """
    Get the complete system prompt for a project type.

    This function first tries to load the configuration from the database.
    If no database configuration exists, it falls back to the default
    file-based configuration.

    Args:
        project_type: Type of project (novel, short, screenplay)
        project_id: The project ID
        folder_ids: Dict mapping folder names to their IDs

    Returns:
        Complete system prompt string
    """
    # Try to get config from database first
    db_configs = _load_db_configs()
    config = db_configs.get(project_type)

    # Fall back to default file-based config if not in database
    if config is None:
        config = PROMPT_CONFIGS.get(project_type, PROMPT_CONFIGS["novel"])

    # Get base prompt with common sections
    base_prompt = get_base_prompt(project_id, folder_ids, config)

    return base_prompt


def reload_prompts() -> None:
    """
    Clear the in-memory cache and reload prompt configurations from database.

    This function should be called when system prompt configurations are
    updated through the admin interface to ensure changes take effect immediately.
    """
    global _db_config_cache
    _db_config_cache = None


__all__ = [
    "get_prompt_for_project_type",
    "get_suggestion_prompt",
    "reload_prompts",
    "PROMPT_CONFIGS",
    "PLANNER_PROMPT",
    "WRITER_PROMPT",
    "QUALITY_REVIEWER_PROMPT",
]
