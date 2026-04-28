"""
原子任务模块

包含所有原子级别的任务:
- parsing: 解析任务(情节点提取)
- entities: 实体任务(人物、金手指、世界观)
- narrative: 叙事任务(剧情聚合、剧情线生成)
- linking: 关联任务(人物关系、时间线)
"""

# Entity tasks
from .entities import (
    build_all_character_entities_task,
    build_character_entity_task,
    build_meta_entities_task,
    extract_character_mentions_task,
    extract_novel_meta_task,
)

# Linking tasks
from .linking import (
    build_character_relationships_task,
    extract_character_relationships_task,
)

# Narrative tasks
from .narrative import (
    # 保留旧任务以兼容（已废弃，请使用 summary_based_story_aggregation）
    aggregate_plots_to_stories_task,
    generate_storylines_task,
    save_stories_task,
    save_storylines_task,
    summary_based_story_aggregation,
)
from .parsing import extract_chapter_plots_task, validate_plots_task

__all__ = [
    # Parsing
    "extract_chapter_plots_task",
    "validate_plots_task",
    # Entities (Character V2 - 两阶段提取)
    "extract_character_mentions_task",
    "build_character_entity_task",
    "build_all_character_entities_task",
    "extract_novel_meta_task",
    "build_meta_entities_task",
    # Narrative (推荐使用新方案)
    "summary_based_story_aggregation",
    # 旧任务（已废弃，保留以兼容）
    "aggregate_plots_to_stories_task",
    "save_stories_task",
    "generate_storylines_task",
    "save_storylines_task",
    # Linking
    "extract_character_relationships_task",
    "build_character_relationships_task",
]
