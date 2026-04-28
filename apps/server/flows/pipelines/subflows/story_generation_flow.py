"""
剧情正文生成流程

流程设计：
┌─────────────────────────────────────────────────────────────┐
│ 阶段1: 准备与规划                                            │
│  - 准备 GeneratedContent 记录                                │
│  - 章节规划（如已有则跳过）                                   │
└─────────────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────────────┐
│ 阶段2: 顺序生成章节                                          │
│  - 逐章生成正文                                              │
│  - 保存到 ChapterContent 表                                  │
│  - 传递前章结尾用于衔接                                       │
└─────────────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────────────┐
│ 阶段3: 统计与完成                                            │
│  - 统计总字数、章节数                                         │
│  - 更新 GeneratedContent 状态为 completed                    │
└─────────────────────────────────────────────────────────────┘

重试策略：
- 章节生成失败：单个 task 最多重试 3 次
- 整个流程失败：标记 GeneratedContent.generation_status = "failed"
"""

from prefect import flow, get_run_logger
from prefect.task_runners import ConcurrentTaskRunner

from flows.atomic_tasks.narrative.story_generation_tasks import (
    bind_flow_run_id_task,
    generate_chapter_task,
    get_chapter_tail_task,
    mark_generated_content_failed_task,
    plan_chapters_task,
    prepare_generated_content_task,
    set_generated_content_status_task,
    update_generated_content_stats_task,
)


@flow(
    name="story_generation_flow",
    task_runner=ConcurrentTaskRunner(),
    retries=0,  # 流程级别不重试，让各 task 自己重试
)
def story_generation_flow(
    outline_item_id: int,
    flow_run_id: str | None = None,
) -> dict:
    """
    剧情正文生成主流程

    Args:
        outline_item_id: 大纲条目 ID
        flow_run_id: Prefect Flow Run ID（可选）

    Returns:
        Dict: {
            "generated_content_id": int,
            "chapter_count": int,
            "word_count": int,
        }
    """
    logger = get_run_logger()
    logger.info(f"开始剧情生成流程：outline_item_id={outline_item_id}")

    generated_content_id = None  # 用于异常处理时更新状态

    try:
        # ===================================================================
        # 阶段1: 准备与规划
        # ===================================================================

        # 1.1 准备 GeneratedContent 记录
        logger.info("阶段1.1: 准备 GeneratedContent 记录")
        prepare_result = prepare_generated_content_task(
            outline_item_id=outline_item_id,
            skip_if_exists=True,
        )

        generated_content_id = prepare_result["generated_content_id"]
        has_existing_plan = prepare_result["has_existing_plan"]

        # 1.2 绑定 flow_run_id
        if flow_run_id:
            bind_flow_run_id_task(
                generated_content_id=generated_content_id,
                flow_run_id=flow_run_id,
            )

        # 1.3 章节规划（如已有则跳过）
        if has_existing_plan:
            logger.info("检测到已有规划，跳过规划步骤")
            chapter_plans = prepare_result["existing_chapter_plans"]
        else:
            logger.info("阶段1.3: 开始章节规划")
            plan_result = plan_chapters_task(
                outline_item_id=outline_item_id,
                generated_content_id=generated_content_id,
            )
            chapter_plans = plan_result["chapter_plans"]

        logger.info(f"章节规划完成：共 {len(chapter_plans)} 章")

        # ===================================================================
        # 阶段2: 顺序生成章节
        # ===================================================================

        logger.info(f"阶段2: 开始生成 {len(chapter_plans)} 章（顺序生成以保持衔接）")

        # 更新状态为 generating
        set_generated_content_status_task(
            generated_content_id=generated_content_id,
            status="generating",
        )

        chapter_ids = []
        prev_tail = None

        for idx, chapter_plan in enumerate(chapter_plans, 1):
            logger.info(f"生成进度: {idx}/{len(chapter_plans)}")

            # 生成单章
            chapter_id = generate_chapter_task(
                generated_content_id=generated_content_id,
                outline_item_id=outline_item_id,
                chapter_plan=chapter_plan,
                prev_chapter_tail=prev_tail,
            )
            chapter_ids.append(chapter_id)

            # 获取章节结尾，供下一章使用
            prev_tail = get_chapter_tail_task(
                chapter_id=chapter_id,
                tail_length=200,
            )

        logger.info(f"所有章节生成完成：{len(chapter_ids)} 章")

        # ===================================================================
        # 阶段3: 统计与完成
        # ===================================================================

        logger.info("阶段3: 统计并标记完成")
        stats_result = update_generated_content_stats_task(
            generated_content_id=generated_content_id,
        )

        logger.info(
            f"剧情生成流程完成：{stats_result['chapter_count']} 章，"
            f"共 {stats_result['word_count']} 字"
        )

        return {
            "generated_content_id": generated_content_id,
            "chapter_count": stats_result["chapter_count"],
            "word_count": stats_result["word_count"],
        }

    except Exception as e:
        logger.error(f"剧情生成流程失败：{e}")

        # 标记失败状态
        if generated_content_id:
            try:
                mark_generated_content_failed_task(
                    generated_content_id=generated_content_id,
                    error=str(e),
                )
            except Exception as db_error:
                logger.error(f"更新失败状态时出错：{db_error}")

        raise


# 用于测试和手动调用
if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("用法: python story_generation_flow.py <outline_item_id>")
        sys.exit(1)

    outline_item_id = int(sys.argv[1])
    result = story_generation_flow(outline_item_id)
    print(f"生成结果：{result}")
