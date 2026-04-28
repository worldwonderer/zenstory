"""
Stories service - SQLModel version.
Handles Story, StoryLine, and StoryPlotLink operations.
"""
from __future__ import annotations

import json
from typing import Any

from sqlmodel import Session, select

from models.material_models import Plot, Story, StoryLine, StoryPlotLink


def _serialize_json(value: Any) -> str | None:
    """Serialize value to JSON string if it's a dict/list."""
    if value is None:
        return None
    if isinstance(value, str):
        return value
    return json.dumps(value)


class StoriesService:
    """Story aggregation service using SQLModel patterns."""

    def upsert_story(self, session: Session, _novel_id: int, story_data: dict) -> int:
        """Upsert a story. Returns story ID."""
        title = story_data.get("title")
        synopsis = story_data.get("synopsis")

        # Check for existing story
        statement = select(Story).where(
            Story.title == title, Story.synopsis == synopsis
        )
        existing = session.exec(statement).first()

        if existing:
            # Update existing story
            existing.core_objective = story_data.get("core_objective") or existing.core_objective
            existing.core_conflict = story_data.get("core_conflict") or existing.core_conflict
            existing.story_type = story_data.get("story_type") or existing.story_type
            existing.chapter_range = story_data.get("chapter_range") or existing.chapter_range
            existing.themes = _serialize_json(story_data.get("themes")) or existing.themes
            session.add(existing)
            session.flush()
            return existing.id

        # Create new story
        new_story = Story(
            title=title,
            synopsis=synopsis,
            core_objective=story_data.get("core_objective"),
            core_conflict=story_data.get("core_conflict"),
            story_type=story_data.get("story_type"),
            chapter_range=story_data.get("chapter_range"),
            themes=_serialize_json(story_data.get("themes")),
        )
        session.add(new_story)
        session.flush()
        return new_story.id

    def attach_plots_to_story(
        self, session: Session, story_id: int, plot_ids: list[int]
    ) -> int:
        """Attach plots to a story. Returns count of links created."""
        count = 0
        for order_index, plot_id in enumerate(plot_ids):
            plot = session.get(Plot, plot_id)
            if not plot:
                continue

            link = StoryPlotLink(
                story_id=story_id,
                plot_id=plot_id,
                order_index=order_index,
                role="MAIN",
            )
            session.add(link)
            count += 1

        session.flush()
        return count

    def create_storyline(self, session: Session, novel_id: int, data: dict) -> int:
        """Create a storyline. Returns storyline ID."""
        storyline = StoryLine(
            novel_id=novel_id,
            title=data.get("title"),
            description=data.get("description"),
            main_characters=_serialize_json(data.get("main_characters")),
            themes=_serialize_json(data.get("themes")),
        )
        session.add(storyline)
        session.flush()
        return storyline.id

    def attach_stories_to_storyline(
        self, session: Session, storyline_id: int, story_ids: list[int]
    ) -> int:
        """Attach stories to a storyline. Returns count of updated stories."""
        updated = 0
        for sid in story_ids:
            story = session.get(Story, sid)
            if story:
                story.story_line_id = storyline_id
                session.add(story)
                updated += 1

        session.flush()
        return updated
