"""
关联任务模块

核心任务:
- relationship_tasks: 人物关系提取和构建
- timeline_tasks: 时间线构建
- neo4j_tasks: Neo4j 图数据库写入
"""

from .neo4j_tasks import (
    persist_chapter_relationships_to_neo4j_task,
    persist_novel_relationships_to_neo4j_task,
)
from .relationship_tasks import (
    build_character_relationships_task,
    extract_character_relationships_task,
)

__all__ = [
    # Relationship tasks
    "extract_character_relationships_task",
    "build_character_relationships_task",
    # Neo4j tasks
    "persist_chapter_relationships_to_neo4j_task",
    "persist_novel_relationships_to_neo4j_task",
]
