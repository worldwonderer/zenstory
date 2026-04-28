"""
Material library search API endpoints.

Handles search and summary operations across material libraries:
- Library summary for reference panel (completed materials with entity counts)
- Cross-library search for entities (characters, golden fingers, etc.)
"""
from fastapi import APIRouter, Depends, Query
from services.auth import get_current_active_user
from sqlalchemy import func, or_
from sqlalchemy.orm import aliased
from sqlmodel import Session, select

from database import get_session
from models import User
from models.material_models import (
    Character,
    CharacterRelationship,
    GoldenFinger,
    IngestionJob,
    Novel,
    Story,
    StoryLine,
    WorldView,
)
from services.material.ingestion_jobs_service import IngestionJobsService
from utils.logger import get_logger

from .schemas import (
    LibrarySummaryItem,
    MaterialSearchResult,
)

logger = get_logger(__name__)

# Router without prefix/tags - will be set by parent router
router = APIRouter()


def _reconcile_job_if_needed(session: Session, job: IngestionJob | None) -> IngestionJob | None:
    if not job:
        return None
    return IngestionJobsService().reconcile_stale_job(session, job)


# ==================== Library Summary ====================

@router.get("/library-summary", response_model=list[LibrarySummaryItem])
def get_library_summary(
    current_user: User = Depends(get_current_active_user),
    session: Session = Depends(get_session),
):
    """Get all user's completed material libraries with entity counts for reference panel."""

    # Single query to get all novels with their latest job status
    novels_with_jobs = session.exec(
        select(Novel, IngestionJob)
        .outerjoin(IngestionJob, IngestionJob.novel_id == Novel.id)
        .where(Novel.user_id == current_user.id)
        .where(Novel.deleted_at.is_(None))
        .order_by(Novel.created_at.desc(), IngestionJob.created_at.desc())
    ).all()

    # Group by novel and get latest job per novel
    novel_map: dict[int, tuple[Novel, IngestionJob | None]] = {}
    for novel, job in novels_with_jobs:
        if novel.id not in novel_map:
            novel_map[novel.id] = (novel, _reconcile_job_if_needed(session, job))

    result = []
    novel_ids = []

    # Filter completed novels
    for novel_id, (_novel, job) in novel_map.items():
        status = job.status if job else None
        if status == "completed":
            novel_ids.append(novel_id)

    # Batch query for all entity counts
    if novel_ids:
        # Characters count
        char_counts = session.exec(
            select(Character.novel_id, func.count(Character.id))
            .where(Character.novel_id.in_(novel_ids))
            .group_by(Character.novel_id)
        ).all()
        char_counts_dict = dict(char_counts)

        # WorldView existence
        worldview_novels = session.exec(
            select(WorldView.novel_id)
            .where(WorldView.novel_id.in_(novel_ids))
        ).all()
        worldview_set = set(worldview_novels)

        # Golden fingers count
        gf_counts = session.exec(
            select(GoldenFinger.novel_id, func.count(GoldenFinger.id))
            .where(GoldenFinger.novel_id.in_(novel_ids))
            .group_by(GoldenFinger.novel_id)
        ).all()
        gf_counts_dict = dict(gf_counts)

        # Storylines count
        story_counts = session.exec(
            select(StoryLine.novel_id, func.count(StoryLine.id))
            .where(StoryLine.novel_id.in_(novel_ids))
            .group_by(StoryLine.novel_id)
        ).all()
        story_counts_dict = dict(story_counts)

        # Stories count
        stories_counts = session.exec(
            select(StoryLine.novel_id, func.count(Story.id))
            .join(Story, Story.story_line_id == StoryLine.id)
            .where(StoryLine.novel_id.in_(novel_ids))
            .group_by(StoryLine.novel_id)
        ).all()
        stories_counts_dict = dict(stories_counts)

        # Relationships count
        rel_counts = session.exec(
            select(CharacterRelationship.novel_id, func.count(CharacterRelationship.id))
            .where(CharacterRelationship.novel_id.in_(novel_ids))
            .group_by(CharacterRelationship.novel_id)
        ).all()
        rel_counts_dict = dict(rel_counts)

        # Build result
        for novel_id in novel_ids:
            novel, job = novel_map[novel_id]
            result.append(LibrarySummaryItem(
                id=novel.id,
                title=novel.title,
                status=job.status if job else None,
                counts={
                    "characters": char_counts_dict.get(novel_id, 0),
                    "worldview": 1 if novel_id in worldview_set else 0,
                    "golden_fingers": gf_counts_dict.get(novel_id, 0),
                    "storylines": story_counts_dict.get(novel_id, 0),
                    "stories": stories_counts_dict.get(novel_id, 0),
                    "relationships": rel_counts_dict.get(novel_id, 0),
                },
            ))

    return result


# ==================== Search ====================

@router.get("/search", response_model=list[MaterialSearchResult])
def search_materials(
    q: str = Query(..., min_length=1, max_length=100),
    limit: int = Query(50, ge=1, le=200),
    current_user: User = Depends(get_current_active_user),
    session: Session = Depends(get_session),
):
    """Search across all material libraries for entities matching the query."""
    results: list[MaterialSearchResult] = []
    query = q.strip().lower()

    # Get all completed novels for this user in a single query

    novels_with_jobs = session.exec(
        select(Novel, IngestionJob)
        .outerjoin(IngestionJob, IngestionJob.novel_id == Novel.id)
        .where(Novel.user_id == current_user.id)
        .where(Novel.deleted_at.is_(None))
        .order_by(Novel.created_at.desc(), IngestionJob.created_at.desc())
    ).all()

    # Group by novel and filter completed
    novel_map: dict[int, tuple[Novel, IngestionJob | None]] = {}
    for novel, job in novels_with_jobs:
        if novel.id not in novel_map:
            novel_map[novel.id] = (novel, job)

    novel_ids = [
        nid for nid, (novel, job) in novel_map.items()
        if job and job.status == "completed"
    ]

    if not novel_ids:
        return []

    def _remaining() -> int:
        return limit - len(results)

    # Search characters in database
    remaining = _remaining()
    if remaining > 0:
        characters = session.exec(
            select(Character)
            .where(Character.novel_id.in_(novel_ids))
            .where(
                or_(
                    func.lower(func.coalesce(Character.name, "")).contains(query),
                    func.lower(func.coalesce(Character.description, "")).contains(query),
                )
            )
            .limit(remaining)
        ).all()
        for c in characters:
            novel = novel_map[c.novel_id][0]
            results.append(MaterialSearchResult(
                novel_id=novel.id, novel_title=novel.title,
                entity_type="characters", entity_id=c.id, name=c.name
            ))

    # Search golden fingers in database
    remaining = _remaining()
    if remaining > 0:
        golden_fingers = session.exec(
            select(GoldenFinger)
            .where(GoldenFinger.novel_id.in_(novel_ids))
            .where(
                or_(
                    func.lower(func.coalesce(GoldenFinger.name, "")).contains(query),
                    func.lower(func.coalesce(GoldenFinger.description, "")).contains(query),
                )
            )
            .limit(remaining)
        ).all()
        for g in golden_fingers:
            novel = novel_map[g.novel_id][0]
            results.append(MaterialSearchResult(
                novel_id=novel.id, novel_title=novel.title,
                entity_type="goldenfingers", entity_id=g.id, name=g.name
            ))

    # Search storylines in database
    remaining = _remaining()
    if remaining > 0:
        storylines = session.exec(
            select(StoryLine)
            .where(StoryLine.novel_id.in_(novel_ids))
            .where(
                or_(
                    func.lower(func.coalesce(StoryLine.title, "")).contains(query),
                    func.lower(func.coalesce(StoryLine.description, "")).contains(query),
                )
            )
            .limit(remaining)
        ).all()
        for s in storylines:
            novel = novel_map[s.novel_id][0]
            results.append(MaterialSearchResult(
                novel_id=novel.id, novel_title=novel.title,
                entity_type="storylines", entity_id=s.id, name=s.title
            ))

    # Search worldview in database
    remaining = _remaining()
    if remaining > 0:
        worldviews = session.exec(
            select(WorldView)
            .where(WorldView.novel_id.in_(novel_ids))
            .where(
                or_(
                    func.lower(func.coalesce(WorldView.world_structure, "")).contains(query),
                    func.lower(func.coalesce(WorldView.power_system, "")).contains(query),
                )
            )
            .limit(remaining)
        ).all()
        for w in worldviews:
            novel = novel_map[w.novel_id][0]
            results.append(MaterialSearchResult(
                novel_id=novel.id, novel_title=novel.title,
                entity_type="worldview", entity_id=w.id,
                name=w.world_structure[:30] if w.world_structure else "World View"
            ))

    # Search relationships in batch
    CharacterA = aliased(Character, name="character_a")
    CharacterB = aliased(Character, name="character_b")

    remaining = _remaining()
    if remaining > 0:
        stmt = (
            select(
                CharacterRelationship,
                CharacterA.name.label("character_a_name"),
                CharacterB.name.label("character_b_name")
            )
            .join(CharacterA, CharacterRelationship.character_a_id == CharacterA.id)
            .join(CharacterB, CharacterRelationship.character_b_id == CharacterB.id)
            .where(CharacterRelationship.novel_id.in_(novel_ids))
            .where(
                or_(
                    func.lower(func.coalesce(CharacterA.name, "")).contains(query),
                    func.lower(func.coalesce(CharacterB.name, "")).contains(query),
                    func.lower(func.coalesce(CharacterRelationship.relationship_type, "")).contains(query),
                    func.lower(func.coalesce(CharacterRelationship.description, "")).contains(query),
                )
            )
            .limit(remaining)
        )

        relationships = session.exec(stmt).all()
        for r, char_a_name, char_b_name in relationships:
            novel = novel_map[r.novel_id][0]
            results.append(MaterialSearchResult(
                novel_id=novel.id, novel_title=novel.title,
                entity_type="relationships", entity_id=r.id,
                name=f"{char_a_name} ↔ {char_b_name}"
            ))

    return results


__all__ = ["router"]
