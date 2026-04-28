"""
剧情正文生成原子任务

包含所有与剧情正文生成相关的原子任务:
- 准备生成内容记录
- 章节规划
- 单章生成
- 统计与状态更新
"""

from prefect import get_run_logger

from flows.database_session import get_db_session
from flows.utils import api_task, database_task

# ==================== 数据库准备任务 ====================

@database_task(name="prepare_generated_content", retries=1)
def prepare_generated_content_task(
    outline_item_id: int,
    skip_if_exists: bool = False,
) -> dict:
    """
    准备 GeneratedContent 记录

    Args:
        outline_item_id: 大纲条目 ID
        skip_if_exists: 如果已有规划则跳过

    Returns:
        Dict: {
            "generated_content_id": int,
            "outline_item_id": int,
            "has_existing_plan": bool,
            "existing_chapter_plans": List[Dict] | None,
        }
    """
    logger = get_run_logger()
    logger.info(f"准备 GeneratedContent 记录: outline_item_id={outline_item_id}")

    from models.material_models import GeneratedContent, OutlineItem

    with get_db_session() as session:
        # 获取 OutlineItem
        item = session.get(OutlineItem, outline_item_id)
        if not item:
            raise ValueError(f"OutlineItem {outline_item_id} not found")

        # 创建或获取 GeneratedContent
        if not item.generated_content:
            generated = GeneratedContent(
                outline_item_id=outline_item_id,
                content="",
                word_count=0,
                chapter_count=0,
                generation_status="pending",
            )
            session.add(generated)
            session.flush()
            session.commit()

            logger.info(f"创建新的 GeneratedContent 记录: id={generated.id}")

            return {
                "generated_content_id": generated.id,
                "outline_item_id": outline_item_id,
                "has_existing_plan": False,
                "existing_chapter_plans": None,
            }

        generated = item.generated_content

        # 检查是否已有规划
        has_plan = (
            skip_if_exists
            and generated.chapter_plan
            and "chapters" in generated.chapter_plan
        )

        if has_plan:
            logger.info(f"检测到已有规划, skip_if_exists={skip_if_exists}")
            return {
                "generated_content_id": generated.id,
                "outline_item_id": outline_item_id,
                "has_existing_plan": True,
                "existing_chapter_plans": generated.chapter_plan["chapters"],
            }

        logger.info(f"使用已有 GeneratedContent 记录: id={generated.id}")
        return {
            "generated_content_id": generated.id,
            "outline_item_id": outline_item_id,
            "has_existing_plan": False,
            "existing_chapter_plans": None,
        }


# ==================== 章节规划任务 ====================

@api_task(name="plan_chapters", retries=1)
def plan_chapters_task(
    outline_item_id: int,
    generated_content_id: int,
) -> dict:
    """
    章节规划

    Args:
        outline_item_id: 大纲条目 ID
        generated_content_id: GeneratedContent ID

    Returns:
        Dict: {
            "generated_content_id": int,
            "chapter_plans": List[Dict],
        }
    """
    logger = get_run_logger()
    logger.info(f"开始章节规划: outline_item_id={outline_item_id}")

    from services.material.chapter_planner import ChapterPlannerService

    from models.material_models import GeneratedContent

    with get_db_session() as session:
        # 更新状态为 planning
        generated = session.get(GeneratedContent, generated_content_id)
        if not generated:
            raise ValueError(f"GeneratedContent {generated_content_id} not found")

        generated.generation_status = "planning"
        session.flush()

        # 调用规划服务
        planner = ChapterPlannerService()
        chapter_plans = planner.plan_chapters(session, outline_item_id)

        # 保存规划结果
        generated.chapter_plan = {
            "total_chapters": len(chapter_plans),
            "chapters": [dict(plan) for plan in chapter_plans],
        }
        generated.generation_status = "planned"
        session.commit()

        logger.info(f"章节规划完成：共 {len(chapter_plans)} 章")

        return {
            "generated_content_id": generated_content_id,
            "chapter_plans": [dict(plan) for plan in chapter_plans],
        }


# ==================== 单章生成任务 ====================

@api_task(name="generate_chapter", retries=3)
def generate_chapter_task(
    generated_content_id: int,
    outline_item_id: int,
    chapter_plan: dict,
    prev_chapter_tail: str | None = None,
) -> int:
    """
    生成单章正文

    Args:
        generated_content_id: GeneratedContent ID
        outline_item_id: 大纲条目 ID
        chapter_plan: 章节规划（字典格式）
        prev_chapter_tail: 前一章结尾（用于衔接）

    Returns:
        int: ChapterContent ID
    """
    logger = get_run_logger()
    chapter_num = chapter_plan["chapter_number"]
    logger.info(f"开始生成第 {chapter_num} 章：{chapter_plan['title']}")

    from services.material.chapter_generator import ChapterGeneratorService

    from models.material_models import ChapterContent

    with get_db_session() as session:
        # 调用生成服务
        generator = ChapterGeneratorService()
        content = generator.generate_chapter(
            session=session,
            outline_item_id=outline_item_id,
            chapter_plan=chapter_plan,  # type: ignore
            prev_chapter_content=prev_chapter_tail,
        )

        # 保存章节内容
        chapter_content = ChapterContent(
            generated_content_id=generated_content_id,
            chapter_number=chapter_plan["chapter_number"],
            title=chapter_plan["title"],
            content=content,
            word_count=len(content),
            outline=chapter_plan.get("outline", ""),
            plot_point_ids=chapter_plan.get("plot_point_ids", []),
            status="completed",
            generation_params={
                "target_words": chapter_plan.get("target_words", 3000),
            }
        )
        session.add(chapter_content)
        session.commit()

        logger.info(f"第 {chapter_num} 章生成完成：{len(content)} 字")

        return chapter_content.id


# ==================== 辅助任务 ====================

@database_task(name="get_chapter_tail", retries=1)
def get_chapter_tail_task(chapter_id: int, tail_length: int = 200) -> str:
    """
    获取章节结尾内容（用于下一章衔接）

    Args:
        chapter_id: ChapterContent ID
        tail_length: 结尾长度（字符数）

    Returns:
        str: 章节结尾内容
    """
    from models.material_models import ChapterContent

    with get_db_session() as session:
        chapter = session.get(ChapterContent, chapter_id)
        if not chapter:
            return ""

        content = chapter.content
        if len(content) <= tail_length:
            return content
        return content[-tail_length:]


@database_task(name="set_generated_content_status", retries=1)
def set_generated_content_status_task(
    generated_content_id: int,
    status: str,
) -> None:
    """
    更新 GeneratedContent 状态

    Args:
        generated_content_id: GeneratedContent ID
        status: 状态值
    """
    logger = get_run_logger()

    from models.material_models import GeneratedContent

    with get_db_session() as session:
        generated = session.get(GeneratedContent, generated_content_id)
        if generated:
            generated.generation_status = status
            session.commit()
            logger.info(f"更新 GeneratedContent {generated_content_id} 状态为: {status}")


@database_task(name="bind_flow_run_id", retries=1)
def bind_flow_run_id_task(
    generated_content_id: int,
    flow_run_id: str,
) -> None:
    """
    绑定 Prefect Flow Run ID 到 GeneratedContent

    Args:
        generated_content_id: GeneratedContent ID
        flow_run_id: Prefect Flow Run ID
    """
    logger = get_run_logger()

    from models.material_models import GeneratedContent

    with get_db_session() as session:
        generated = session.get(GeneratedContent, generated_content_id)
        if generated:
            generated.task_id = flow_run_id
            session.commit()
            logger.info(f"绑定 flow_run_id: {flow_run_id}")


# ==================== 统计与完成任务 ====================

@database_task(name="update_generated_content_stats", retries=1)
def update_generated_content_stats_task(
    generated_content_id: int,
) -> dict:
    """
    更新 GeneratedContent 统计信息并标记完成

    Args:
        generated_content_id: GeneratedContent ID

    Returns:
        Dict: {
            "chapter_count": int,
            "word_count": int,
        }
    """
    logger = get_run_logger()
    logger.info(f"开始统计生成结果: generated_content_id={generated_content_id}")

    from sqlmodel import select

    from models.material_models import ChapterContent, GeneratedContent

    with get_db_session() as session:
        generated = session.get(GeneratedContent, generated_content_id)
        if not generated:
            raise ValueError(f"GeneratedContent {generated_content_id} not found")

        # 查询所有章节
        chapters = session.exec(
            select(ChapterContent).where(ChapterContent.generated_content_id == generated_content_id)
        ).all()

        total_words = sum(ch.word_count for ch in chapters)

        # 更新统计
        generated.word_count = total_words
        generated.chapter_count = len(chapters)
        generated.generation_status = "completed"
        session.commit()

        logger.info(f"统计完成：{len(chapters)} 章，共 {total_words} 字")

        return {
            "chapter_count": len(chapters),
            "word_count": total_words,
        }


@database_task(name="mark_generated_content_failed", retries=1)
def mark_generated_content_failed_task(
    generated_content_id: int,
    error: str,
) -> None:
    """
    标记 GeneratedContent 为失败状态

    Args:
        generated_content_id: GeneratedContent ID
        error: 错误信息
    """
    logger = get_run_logger()
    logger.error(f"标记 GeneratedContent {generated_content_id} 为失败: {error}")

    from models.material_models import GeneratedContent

    with get_db_session() as session:
        generated = session.get(GeneratedContent, generated_content_id)
        if generated:
            generated.generation_status = "failed"
            session.commit()
