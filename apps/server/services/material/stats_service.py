"""
Stats service - SQLModel version.
Handles statistics and aggregation queries for material library.
"""
from __future__ import annotations

from typing import Any

from sqlmodel import Session, func, select

from models.material_models import (
    Chapter,
    Character,
    CharacterRelationship,
    EventTimeline,
    GoldenFinger,
    Plot,
    Story,
)


class StatsService:
    """Statistics domain service using SQLModel patterns."""

    def get_novel_stats(self, session: Session, novel_id: int) -> dict[str, Any]:
        """Get comprehensive statistics for a novel."""
        # Count chapters
        chapter_count = session.exec(
            select(func.count(Chapter.id)).where(Chapter.novel_id == novel_id)
        ).one()

        # Count plots
        plot_count = session.exec(
            select(func.count(Plot.id))
            .join(Chapter, Plot.chapter_id == Chapter.id)
            .where(Chapter.novel_id == novel_id)
        ).one()

        # Count stories
        story_count = session.exec(
            select(func.count(Story.id))
            .where(Story.story_line_id.in_(
                select(func.distinct(Story.story_line_id))
                .join(Chapter, Chapter.novel_id == novel_id)
            ))
        ).one() if session.exec(select(Story.id).limit(1)).first() else 0

        # Count characters
        character_count = session.exec(
            select(func.count(Character.id)).where(Character.novel_id == novel_id)
        ).one()

        # Count relationships
        relationship_count = session.exec(
            select(func.count(CharacterRelationship.id)).where(
                CharacterRelationship.novel_id == novel_id
            )
        ).one()

        # Count golden fingers
        golden_finger_count = session.exec(
            select(func.count(GoldenFinger.id)).where(
                GoldenFinger.novel_id == novel_id
            )
        ).one()

        # Count timeline events
        timeline_event_count = session.exec(
            select(func.count(EventTimeline.id)).where(
                EventTimeline.novel_id == novel_id
            )
        ).one()

        return {
            "novel_id": novel_id,
            "chapter_count": chapter_count,
            "plot_count": plot_count,
            "story_count": story_count,
            "character_count": character_count,
            "relationship_count": relationship_count,
            "golden_finger_count": golden_finger_count,
            "timeline_event_count": timeline_event_count,
        }

    def get_chapter_stats(self, session: Session, chapter_id: int) -> dict[str, Any]:
        """Get statistics for a specific chapter."""
        # Get chapter
        chapter = session.exec(
            select(Chapter).where(Chapter.id == chapter_id)
        ).first()

        if not chapter:
            return {}

        # Count plots in this chapter
        plot_count = session.exec(
            select(func.count(Plot.id)).where(Plot.chapter_id == chapter_id)
        ).one()

        return {
            "chapter_id": chapter_id,
            "chapter_number": chapter.chapter_number,
            "title": chapter.title,
            "plot_count": plot_count,
        }

    def count_stage1(self, session: Session, novel_id: int) -> dict[str, int]:
        """
        Count stage1 completion: chapter summaries and plot points.
        Required by stage_executor.py.
        """
        # Count chapters with summaries
        summaries_count = session.exec(
            select(func.count(Chapter.id))
            .where(Chapter.novel_id == novel_id)
            .where(Chapter.summary.isnot(None))
        ).one()

        # Count plot points (via Chapter join)
        plots_count = session.exec(
            select(func.count(Plot.id))
            .join(Chapter, Plot.chapter_id == Chapter.id)
            .where(Chapter.novel_id == novel_id)
        ).one()

        return {"summaries_count": summaries_count, "plots_count": plots_count}
