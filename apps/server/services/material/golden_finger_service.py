"""
GoldenFinger service - SQLModel version.
Handles GoldenFinger upsert and query operations.
"""
from __future__ import annotations

import json
from collections.abc import Iterable
from typing import Any

from sqlmodel import Session, select

from models.material_models import GoldenFinger


def _serialize_json(value: Any) -> str | None:
    """Serialize value to JSON string if it's a dict/list."""
    if value is None:
        return None
    if isinstance(value, str):
        return value
    return json.dumps(value)


class GoldenFingerService:
    """GoldenFinger domain service using SQLModel patterns."""

    def get_by_name(
        self, session: Session, novel_id: int, name: str
    ) -> GoldenFinger | None:
        """Get golden finger by name within a novel."""
        statement = select(GoldenFinger).where(
            GoldenFinger.novel_id == novel_id, GoldenFinger.name == name
        )
        return session.exec(statement).first()

    def upsert(
        self, session: Session, novel_id: int, data: dict[str, Any]
    ) -> str:
        """Upsert a single golden finger. Returns 'created' or 'updated'."""
        name = data.get("name")
        if not name:
            raise ValueError("Golden finger name is required")

        existing = self.get_by_name(session, novel_id, name)
        if existing:
            existing.type = data.get("type") or existing.type
            existing.description = data.get("description") or existing.description
            existing.first_appearance_chapter_id = (
                data.get("first_appearance_chapter_id")
                or existing.first_appearance_chapter_id
            )
            existing.evolution_history = (
                _serialize_json(data.get("evolution_history")) or existing.evolution_history
            )
            session.add(existing)
            session.flush()
            return "updated"
        else:
            new_gf = GoldenFinger(
                novel_id=novel_id,
                name=name,
                type=data.get("type"),
                description=data.get("description"),
                first_appearance_chapter_id=data.get("first_appearance_chapter_id"),
                evolution_history=_serialize_json(data.get("evolution_history")),
            )
            session.add(new_gf)
            session.flush()
            return "created"

    def upsert_golden_fingers(
        self, session: Session, novel_id: int, items: Iterable[dict[str, Any]]
    ) -> tuple[int, int]:
        """Upsert multiple golden fingers. Returns (created_count, updated_count)."""
        created = 0
        updated = 0
        for data in items:
            name = data.get("name")
            if not name:
                continue

            statement = select(GoldenFinger).where(
                GoldenFinger.novel_id == novel_id, GoldenFinger.name == name
            )
            existing = session.exec(statement).first()

            if existing:
                # Update existing golden finger
                existing.type = data.get("type") or existing.type
                existing.description = data.get("description") or existing.description
                existing.first_appearance_chapter_id = (
                    data.get("first_appearance_chapter_id")
                    or existing.first_appearance_chapter_id
                )
                existing.evolution_history = (
                    _serialize_json(data.get("evolution_history")) or existing.evolution_history
                )
                session.add(existing)
                updated += 1
            else:
                # Create new golden finger
                new_gf = GoldenFinger(
                    novel_id=novel_id,
                    name=name,
                    type=data.get("type"),
                    description=data.get("description"),
                    first_appearance_chapter_id=data.get("first_appearance_chapter_id"),
                    evolution_history=_serialize_json(data.get("evolution_history")),
                )
                session.add(new_gf)
                created += 1

        session.flush()
        return created, updated
