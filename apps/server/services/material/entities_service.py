"""
Entities service - SQLModel version.
Handles entity queries (Character, WorldView, GoldenFinger).
"""
from __future__ import annotations

from sqlmodel import Session, select

from models.material_models import Character, GoldenFinger, WorldView


class EntitiesService:
    """Entity service using SQLModel patterns."""

    def get_characters_by_novel(
        self, session: Session, novel_id: int
    ) -> list[Character]:
        """Get all characters for a novel."""
        return list(session.exec(
            select(Character).where(Character.novel_id == novel_id)
        ).all())

    def get_world_views_by_novel(
        self, session: Session, novel_id: int
    ) -> list[WorldView]:
        """Get all world view settings for a novel."""
        return list(session.exec(
            select(WorldView).where(WorldView.novel_id == novel_id)
        ).all())

    def get_golden_fingers_by_novel(
        self, session: Session, novel_id: int
    ) -> list[GoldenFinger]:
        """Get all golden fingers for a novel."""
        return list(session.exec(
            select(GoldenFinger).where(GoldenFinger.novel_id == novel_id)
        ).all())
