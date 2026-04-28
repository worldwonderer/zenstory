"""
User skill service for loading and managing user-defined skills.

Provides functions to load user skills from the database and convert
them to Skill objects for use in the matcher.
"""

import json

from sqlmodel import Session, select

from models import UserSkill
from utils.logger import get_logger, log_with_context

from .schemas import Skill, SkillSource

logger = get_logger(__name__)


def get_user_skills(session: Session, user_id: str) -> list[Skill]:
    """
    Load user-defined skills from the database.

    Args:
        session: Database session
        user_id: User ID to load skills for

    Returns:
        List of Skill objects
    """
    try:
        stmt = select(UserSkill).where(
            UserSkill.user_id == user_id,
            UserSkill.is_active == True,  # noqa: E712
        )
        db_skills = session.exec(stmt).all()

        skills = []
        for db_skill in db_skills:
            skill = _convert_db_skill(db_skill)
            if skill:
                skills.append(skill)

        log_with_context(
            logger, 20, "User skills loaded",
            user_id=user_id,
            count=len(skills),
        )
        return skills

    except Exception as e:
        log_with_context(
            logger, 40, "Failed to load user skills",
            user_id=user_id,
            error=str(e),
        )
        return []


def _convert_db_skill(db_skill: UserSkill) -> Skill | None:
    """
    Convert a database UserSkill to a Skill object.

    Args:
        db_skill: Database skill model

    Returns:
        Skill object or None if conversion fails
    """
    try:
        # Parse triggers from JSON string
        triggers = json.loads(db_skill.triggers) if db_skill.triggers else []

        return Skill(
            id=db_skill.id,
            name=db_skill.name,
            description=db_skill.description or "",
            triggers=triggers,
            instructions=db_skill.instructions,
            source=SkillSource.USER,
            user_id=db_skill.user_id,
        )
    except Exception as e:
        log_with_context(
            logger, 30, "Failed to convert user skill",
            skill_id=db_skill.id,
            error=str(e),
        )
        return None
