"""
EventTimeline service - SQLModel version.
Handles EventTimeline bulk insert and query operations.
"""
from __future__ import annotations

from collections.abc import Iterable

from sqlmodel import Session, select

from models.material_models import EventTimeline


class TimelineService:
    """EventTimeline domain service using SQLModel patterns."""

    def bulk_insert(
        self, session: Session, novel_id: int, events: Iterable[dict]
    ) -> int:
        """Bulk insert timeline events for a novel. Returns count of created events."""
        created = 0
        for e in events:
            event = EventTimeline(
                novel_id=novel_id,
                chapter_id=e["chapter_id"],
                plot_id=e["plot_id"],
                rel_order=e.get("rel_order", 0),
                time_tag=e.get("time_tag"),
                uncertain=e.get("uncertain", False),
            )
            session.add(event)
            created += 1
        session.flush()
        return created

    def list_by_novel(
        self, session: Session, novel_id: int
    ) -> list[EventTimeline]:
        """List all timeline events for a novel, ordered by rel_order."""
        statement = (
            select(EventTimeline)
            .where(EventTimeline.novel_id == novel_id)
            .order_by(EventTimeline.rel_order)
        )
        return list(session.exec(statement).all())
