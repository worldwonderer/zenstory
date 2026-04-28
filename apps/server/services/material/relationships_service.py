"""
CharacterRelationship service - SQLModel version.
Handles CharacterRelationship upsert and query operations.
"""
from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from sqlmodel import Session, select

from models.material_models import Character, CharacterRelationship


class RelationshipsService:
    """CharacterRelationship domain service using SQLModel patterns."""

    def get_relationship(
        self,
        session: Session,
        novel_id: int,
        character_a_id: int,
        character_b_id: int,
    ) -> CharacterRelationship | None:
        """Get relationship between two characters (bidirectional check)."""
        statement = select(CharacterRelationship).where(
            CharacterRelationship.novel_id == novel_id,
            (
                (
                    (CharacterRelationship.character_a_id == character_a_id)
                    & (CharacterRelationship.character_b_id == character_b_id)
                )
                | (
                    (CharacterRelationship.character_a_id == character_b_id)
                    & (CharacterRelationship.character_b_id == character_a_id)
                )
            ),
        )
        return session.exec(statement).first()

    def list_by_character(
        self, session: Session, novel_id: int, character_id: int
    ) -> list[CharacterRelationship]:
        """List all relationships for a character."""
        statement = select(CharacterRelationship).where(
            CharacterRelationship.novel_id == novel_id,
            (
                (CharacterRelationship.character_a_id == character_id)
                | (CharacterRelationship.character_b_id == character_id)
            ),
        )
        return list(session.exec(statement).all())

    def list_relationships_with_names(
        self, session: Session, novel_id: int
    ) -> list[dict[str, Any]]:
        """List all relationships for a novel with character names resolved."""
        from sqlalchemy.orm import aliased

        aliased(Character)
        aliased(Character)

        rels = list(session.exec(
            select(CharacterRelationship).where(
                CharacterRelationship.novel_id == novel_id
            )
        ).all())

        # Build character ID -> name map
        char_ids = set()
        for r in rels:
            char_ids.add(r.character_a_id)
            char_ids.add(r.character_b_id)

        name_map: dict[int, str] = {}
        if char_ids:
            chars = session.exec(
                select(Character).where(Character.id.in_(list(char_ids)))
            ).all()
            name_map = {c.id: c.name for c in chars}

        result = []
        for r in rels:
            result.append({
                "id": r.id,
                "novel_id": r.novel_id,
                "character_a_id": r.character_a_id,
                "character_b_id": r.character_b_id,
                "character_a_name": name_map.get(r.character_a_id, "unknown"),
                "character_b_name": name_map.get(r.character_b_id, "unknown"),
                "relationship_type": r.relationship_type,
                "sentiment": r.sentiment,
                "description": r.description,
            })
        return result

    def upsert_relationships(
        self, session: Session, novel_id: int, items: Iterable[dict[str, Any]]
    ) -> tuple[int, int]:
        """Upsert multiple relationships. Returns (created_count, updated_count)."""
        created = 0
        updated = 0
        for data in items:
            char_a_id = data.get("character_a_id")
            char_b_id = data.get("character_b_id")
            if not char_a_id or not char_b_id:
                continue

            existing = self.get_relationship(session, novel_id, char_a_id, char_b_id)

            if existing:
                # Update existing relationship
                existing.relationship_type = (
                    data.get("relationship_type") or existing.relationship_type
                )
                existing.sentiment = data.get("sentiment") or existing.sentiment
                existing.description = data.get("description") or existing.description
                existing.established_at_plot_id = (
                    data.get("established_at_plot_id")
                    or existing.established_at_plot_id
                )
                session.add(existing)
                updated += 1
            else:
                # Create new relationship
                new_rel = CharacterRelationship(
                    novel_id=novel_id,
                    character_a_id=char_a_id,
                    character_b_id=char_b_id,
                    relationship_type=data.get("relationship_type", "unknown"),
                    sentiment=data.get("sentiment"),
                    description=data.get("description"),
                    established_at_plot_id=data.get("established_at_plot_id"),
                )
                session.add(new_rel)
                created += 1

        session.flush()
        return created, updated
