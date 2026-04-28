"""
Characters service - SQLModel version.
Handles Character upsert and query operations.
"""
from __future__ import annotations

import json
from collections.abc import Iterable
from typing import Any

from sqlmodel import Session, select

from models.material_models import Character


def _serialize_aliases(aliases: Any) -> str | None:
    """Serialize aliases to JSON string."""
    if aliases is None:
        return None
    if isinstance(aliases, str):
        return aliases
    return json.dumps(aliases)


class CharactersService:
    """Character domain service using SQLModel patterns."""

    def get_by_name(
        self, session: Session, novel_id: int, name: str
    ) -> Character | None:
        """Get character by name within a novel."""
        statement = select(Character).where(
            Character.novel_id == novel_id, Character.name == name
        )
        return session.exec(statement).first()

    def list_by_novel(
        self, session: Session, novel_id: int
    ) -> list[Character]:
        """List all characters for a novel."""
        statement = select(Character).where(Character.novel_id == novel_id)
        return list(session.exec(statement).all())

    def upsert_characters(
        self, session: Session, novel_id: int, items: Iterable[dict[str, Any]]
    ) -> tuple[int, int]:
        """Upsert multiple characters. Returns (created_count, updated_count)."""
        created = 0
        updated = 0
        for data in items:
            name = data.get("name")
            if not name:
                continue

            statement = select(Character).where(
                Character.novel_id == novel_id, Character.name == name
            )
            existing = session.exec(statement).first()

            if existing:
                # Update existing character
                existing.aliases = _serialize_aliases(data.get("aliases")) or existing.aliases
                existing.description = data.get("description") or existing.description
                existing.first_appearance_chapter_id = (
                    data.get("first_appearance_chapter_id")
                    or existing.first_appearance_chapter_id
                )
                session.add(existing)
                updated += 1
            else:
                # Create new character
                new_char = Character(
                    novel_id=novel_id,
                    name=name,
                    aliases=_serialize_aliases(data.get("aliases")),
                    description=data.get("description"),
                    first_appearance_chapter_id=data.get("first_appearance_chapter_id"),
                )
                session.add(new_char)
                created += 1

        session.flush()
        return created, updated
