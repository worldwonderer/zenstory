"""
摘要任务模块
"""

from .chapter_summary_tasks import (
    generate_chapter_summary_task,
    update_chapter_summary_task,
)
from .novel_synopsis_tasks import (
    generate_novel_synopsis_task,
    update_novel_synopsis_task,
)

__all__ = [
    # Chapter summary tasks
    "generate_chapter_summary_task",
    "update_chapter_summary_task",
    # Novel synopsis tasks
    "generate_novel_synopsis_task",
    "update_novel_synopsis_task",
]
