"""
Story plots service - SQLModel version.
Handles StoryPlotLink operations for story-plot relationships.
"""
from __future__ import annotations

from sqlmodel import Session, select

from models.material_models import Plot, Story, StoryPlotLink


class StoryPlotsService:
    """Story-plot relationship service using SQLModel patterns."""

    def link_plot_to_story(
        self,
        session: Session,
        story_id: int,
        plot_id: int,
        order_index: int | None = None,
        role: str | None = None
    ) -> StoryPlotLink:
        """Link a plot to a story."""
        link = StoryPlotLink(
            story_id=story_id,
            plot_id=plot_id,
            order_index=order_index,
            role=role
        )
        session.add(link)
        session.flush()
        return link

    def get_plots_by_story(self, session: Session, story_id: int) -> list[Plot]:
        """Get all plots linked to a story."""
        links = session.exec(
            select(StoryPlotLink).where(StoryPlotLink.story_id == story_id)
        ).all()
        plot_ids = [link.plot_id for link in links]
        if not plot_ids:
            return []
        return list(session.exec(
            select(Plot).where(Plot.id.in_(plot_ids))
        ).all())

    def get_stories_by_plot(self, session: Session, plot_id: int) -> list[Story]:
        """Get all stories linked to a plot."""
        links = session.exec(
            select(StoryPlotLink).where(StoryPlotLink.plot_id == plot_id)
        ).all()
        story_ids = [link.story_id for link in links]
        if not story_ids:
            return []
        return list(session.exec(
            select(Story).where(Story.id.in_(story_ids))
        ).all())

    def unlink_plot_from_story(
        self,
        session: Session,
        story_id: int,
        plot_id: int
    ) -> bool:
        """Remove link between story and plot."""
        link = session.exec(
            select(StoryPlotLink).where(
                StoryPlotLink.story_id == story_id,
                StoryPlotLink.plot_id == plot_id
            )
        ).first()
        if link:
            session.delete(link)
            session.flush()
            return True
        return False
