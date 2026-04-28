"""
Skill usage tracking service.

Provides functions for recording and querying skill usage statistics.
"""

from datetime import datetime, timedelta
from typing import TypedDict

from sqlmodel import Session, func, select

from config.datetime_utils import utcnow
from models import SkillUsage
from utils.logger import get_logger

logger = get_logger(__name__)


class SkillUsageStats(TypedDict):
    """Statistics for skill usage."""

    total_triggers: int
    builtin_count: int
    user_count: int
    avg_confidence: float
    top_skills: list[dict]
    daily_usage: list[dict]


def _get_stats_window(days: int) -> tuple[datetime, datetime]:
    """Get UTC calendar-day window bounds [start, end) for stats queries."""
    today = utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    start = today - timedelta(days=days - 1)
    end = today + timedelta(days=1)
    return start, end


def record_skill_usage(
    session: Session,
    project_id: str,
    skill_id: str,
    skill_name: str,
    skill_source: str,
    matched_trigger: str,
    confidence: float = 1.0,
    user_id: str | None = None,
    user_message: str | None = None,
) -> SkillUsage:
    """
    Record a skill usage event.

    Args:
        session: Database session
        project_id: Project ID
        skill_id: Skill ID
        skill_name: Skill name
        skill_source: 'builtin' or 'user'
        matched_trigger: The trigger that matched
        confidence: Match confidence score
        user_id: Optional user ID
        user_message: Optional truncated user message

    Returns:
        Created SkillUsage record
    """
    from models import Project

    # Verify project ownership (if user_id is provided)
    if user_id:
        project = session.get(Project, project_id)
        if not project or project.owner_id != user_id:
            logger.warning(
                f"Skill usage recording blocked: user {user_id} does not own project {project_id}"
            )
            raise ValueError(f"User {user_id} does not own project {project_id}")

    # Truncate user message if too long
    truncated_message = None
    if user_message:
        truncated_message = user_message[:500] if len(user_message) > 500 else user_message

    usage = SkillUsage(
        project_id=project_id,
        user_id=user_id,
        skill_id=skill_id,
        skill_name=skill_name,
        skill_source=skill_source,
        matched_trigger=matched_trigger,
        confidence=confidence,
        user_message=truncated_message,
    )
    session.add(usage)
    session.commit()

    logger.debug(f"Recorded skill usage: {skill_name} ({skill_source})")
    return usage


def get_skill_usage_stats(
    session: Session,
    project_id: str,
    days: int = 30,
) -> SkillUsageStats:
    """
    Get skill usage statistics for a project.

    Args:
        session: Database session
        project_id: Project ID
        days: Number of days to look back (default 30)

    Returns:
        SkillUsageStats with aggregated statistics
    """
    start_date, end_date = _get_stats_window(days)

    # Base query filter
    base_filter = [
        SkillUsage.project_id == project_id,
        SkillUsage.created_at >= start_date,
        SkillUsage.created_at < end_date,
    ]

    # Total triggers count
    total_stmt = select(func.count(SkillUsage.id)).where(*base_filter)
    total_triggers = session.exec(total_stmt).one() or 0

    # Builtin vs user count
    builtin_stmt = select(func.count(SkillUsage.id)).where(
        *base_filter,
        SkillUsage.skill_source == "builtin",
    )
    builtin_count = session.exec(builtin_stmt).one() or 0

    user_stmt = select(func.count(SkillUsage.id)).where(
        *base_filter,
        SkillUsage.skill_source.in_(("user", "added")),
    )
    user_count = session.exec(user_stmt).one() or 0

    # Average confidence
    avg_stmt = select(func.avg(SkillUsage.confidence)).where(*base_filter)
    avg_confidence = session.exec(avg_stmt).one() or 0.0

    # Top skills (most used)
    top_skills_stmt = (
        select(
            SkillUsage.skill_id,
            func.max(SkillUsage.skill_name).label("skill_name"),
            SkillUsage.skill_source,
            func.count(SkillUsage.id).label("count"),
        )
        .where(*base_filter)
        .group_by(SkillUsage.skill_id, SkillUsage.skill_source)
        .order_by(func.count(SkillUsage.id).desc(), func.max(SkillUsage.created_at).desc())
        .limit(10)
    )
    top_skills_result = session.exec(top_skills_stmt).all()
    top_skills = [
        {
            "skill_id": row[0],
            "skill_name": row[1],
            "skill_source": row[2],
            "count": row[3],
        }
        for row in top_skills_result
    ]

    # Daily usage for chart
    daily_usage = _get_daily_usage(session, project_id, days)

    return SkillUsageStats(
        total_triggers=total_triggers,
        builtin_count=builtin_count,
        user_count=user_count,
        avg_confidence=round(avg_confidence, 2) if avg_confidence else 0.0,
        top_skills=top_skills,
        daily_usage=daily_usage,
    )


def _get_daily_usage(
    session: Session,
    project_id: str,
    days: int,
) -> list[dict]:
    """Get daily usage counts for the past N days."""
    start_date, end_date = _get_stats_window(days)

    grouped_stmt = (
        select(
            func.date(SkillUsage.created_at).label("usage_date"),
            func.count(SkillUsage.id).label("count"),
        )
        .where(
            SkillUsage.project_id == project_id,
            SkillUsage.created_at >= start_date,
            SkillUsage.created_at < end_date,
        )
        .group_by(func.date(SkillUsage.created_at))
    )
    grouped_rows = session.exec(grouped_stmt).all()

    counts_by_date: dict[str, int] = {}
    for usage_date, count in grouped_rows:
        day_key = usage_date.strftime("%Y-%m-%d") if hasattr(usage_date, "strftime") else str(usage_date)
        counts_by_date[day_key] = int(count or 0)

    result = []
    current_day = start_date
    for _ in range(days):
        day_key = current_day.strftime("%Y-%m-%d")
        result.append({
            "date": day_key,
            "count": counts_by_date.get(day_key, 0),
        })
        current_day += timedelta(days=1)

    return result
