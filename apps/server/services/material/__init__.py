"""
Material services for novel ingestion and analysis.
Rewritten from DeepNovel to use SQLModel patterns.
"""
from __future__ import annotations

from .chapters_service import ChaptersService
from .characters_service import CharactersService
from .checkpoint_service import CheckpointService
from .golden_finger_service import GoldenFingerService
from .ingestion_jobs_service import IngestionJobsService
from .novels_service import NovelsService
from .plots_service import PlotsService
from .relationships_service import RelationshipsService
from .stats_service import StatsService
from .stories_service import StoriesService
from .timeline_service import TimelineService
from .world_view_service import WorldViewService

__all__ = [
    "NovelsService",
    "ChaptersService",
    "CharactersService",
    "PlotsService",
    "StoriesService",
    "IngestionJobsService",
    "CheckpointService",
    "GoldenFingerService",
    "RelationshipsService",
    "StatsService",
    "TimelineService",
    "WorldViewService",
]
