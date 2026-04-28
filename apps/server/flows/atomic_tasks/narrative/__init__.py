"""
叙事任务模块

推荐使用 summary_based_aggregation 进行剧情聚合。
详见 README.md
"""

# 注意：这些函数已废弃或移至其他模块
# - generate_chapter_summary_task 在 flows.atomic_tasks.summaries
# - aggregate_stories_task, generate_story_lines_task, persist_story_lines_task 已被新方案替代

# 推荐方案：基于章节摘要的剧情聚合
# 孤儿情节点处理
from .handle_orphan_plots import (
    assign_orphans_with_llm_task,
    handle_orphan_plots_task,
)

# 智能分块工具
from .intelligent_chunking import (
    get_chunk_chapters,
    get_novel_chunks,
    intelligent_chunking_task,
)

# 剧情正文生成任务
from .story_generation_tasks import (
    bind_flow_run_id_task,
    generate_chapter_task,
    get_chapter_tail_task,
    mark_generated_content_failed_task,
    plan_chapters_task,
    prepare_generated_content_task,
    set_generated_content_status_task,
    update_generated_content_stats_task,
)
from .summary_based_aggregation import (
    aggregate_plots_for_story_framework,
    extract_storylines_from_stories,
    identify_story_frameworks_from_summaries,
    identify_story_frameworks_with_chunking,  # 新增：智能分块版本
    save_stories_with_plots,
    save_storylines_with_stories,
    summary_based_story_aggregation,
)

# 别名：适配流程调用
aggregate_plots_to_stories_task = aggregate_plots_for_story_framework
save_stories_task = save_stories_with_plots
generate_storylines_task = extract_storylines_from_stories
save_storylines_task = save_storylines_with_stories

# 注意：以下备选方案暂未实现
# - hierarchical_aggregation (层次化聚合)
# - semantic_clustering (语义聚类)

__all__ = [
    # 推荐方案：基于章节摘要的剧情聚合
    "summary_based_story_aggregation",
    "identify_story_frameworks_from_summaries",
    "identify_story_frameworks_with_chunking",  # 新增：智能分块版本
    "aggregate_plots_for_story_framework",
    "extract_storylines_from_stories",
    "save_stories_with_plots",
    "save_storylines_with_stories",
    # 孤儿情节点处理
    "handle_orphan_plots_task",
    "assign_orphans_with_llm_task",

    # 智能分块工具
    "intelligent_chunking_task",
    "get_novel_chunks",
    "get_chunk_chapters",

    # 剧情正文生成任务
    "prepare_generated_content_task",
    "plan_chapters_task",
    "generate_chapter_task",
    "get_chapter_tail_task",
    "set_generated_content_status_task",
    "bind_flow_run_id_task",
    "update_generated_content_stats_task",
    "mark_generated_content_failed_task",

    # 别名：适配流程调用
    "aggregate_plots_to_stories_task",
    "save_stories_task",
    "generate_storylines_task",
    "save_storylines_task",
]
