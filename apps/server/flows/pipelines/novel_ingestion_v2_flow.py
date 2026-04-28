#!/usr/bin/env python3
"""
小说导入主流程 V2

流程设计:
阶段1: 按章节并行提取 (章节摘要 + 情节点 + 实体)
阶段2A: 剧情相关 (小说概要 → 剧情聚合 → 剧情线)
阶段2B: 人物关系 (关系提取 → Neo4j存储)

流程图:
novel_ingestion_v2
  │
  ├─> 文件验证 + 章节解析 + 创建 Novel/Chapter
  │
  ├─────────────────────────────────────────────────────────┐
  │                                                         │
  ▼ 阶段1: 按章节并行提取 (3类任务)                           │
  ├─> 章节摘要生成 (× N)                                     │
  ├─> 情节点提取 (× N)                                       │
  └─> 实体提取 (× N) [可选]                                  │
  │                                                         │
  └─────────────────────┬─────────────────────────────────┘
                        ▼
                  等待阶段1完成
                        │
  ├─────────────────────┴─────────────────────────────────┐
  │                                                       │
  ▼ 阶段2A: 剧情相关 (串行)                                ▼ 阶段2B: 人物关系 (串行)
  ├─> 小说概要生成 (基于章节摘要)                          ├─> 人物关系提取 (基于实体)
  ├─> 剧情聚合 (基于摘要+情节点)                           └─> 按章节存储到 Neo4j
  └─> 剧情线生成 (基于剧情)                                │
  │                                                       │
  └─────────────────────┬─────────────────────────────────┘
                        ▼
                    全部完成
"""

from __future__ import annotations

import hashlib
import time
from typing import Any

from prefect import flow, get_run_logger
from prefect.task_runners import ConcurrentTaskRunner

from config.material_settings import material_settings as settings
from flows.database_session import get_prefect_db_session
from flows.utils.helpers import (
    calculate_checksum,
    create_checkpoint_manager,
    detect_encoding,
    parse_novel_chapters,
    validate_input,
)

# 并发任务运行器
RUNTIME_TASK_RUNNER: Any = ConcurrentTaskRunner(max_workers=settings.MAX_CONCURRENT_WORKFLOWS)

_def_now = time.perf_counter


def _elapsed_ms(start: float) -> int:
    return int((time.perf_counter() - start) * 1000)


def _resume_from_stage1(
    novel_id: int,
    chapter_ids: list[int],
    checkpoint_manager: Any,
    flow_start: float,
) -> dict[str, Any]:
    """从阶段1恢复执行"""
    logger = get_run_logger()

    logger.info("=" * 60)
    logger.info("阶段1: 按章节并行提取 (章节摘要 + 情节点 + 实体)")
    logger.info("=" * 60)

    from .subflows.chapter_extraction_flow import chapter_extraction_flow

    stage1_result = chapter_extraction_flow(
        novel_id=novel_id,
        chapter_ids=chapter_ids,
    )

    checkpoint_manager.mark_stage_completed("stage1", {
        "summaries_count": stage1_result.get("summaries_count", 0),
        "plots_count": stage1_result.get("plots_count", 0),
    })

    logger.info(
        "阶段1完成: summaries=%s, plots=%s, entities=%s",
        stage1_result.get("summaries_count", 0),
        stage1_result.get("plots_count", 0),
        stage1_result.get("entities_extracted", False),
    )

    # 继续执行阶段2
    return _resume_from_stage2(
        novel_id=novel_id,
        chapter_ids=chapter_ids,
        checkpoint_manager=checkpoint_manager,
        flow_start=flow_start,
        stage1_result=stage1_result,
    )


def _resume_from_stage2(
    novel_id: int,
    chapter_ids: list[int],
    checkpoint_manager: Any,
    flow_start: float,
    stage1_result: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """从阶段2恢复执行"""
    logger = get_run_logger()

    # 如果没有 stage1_result，从数据库获取统计信息（通过 service）
    if stage1_result is None:
        from services.material.stats_service import StatsService
        stats_service = StatsService()
        with get_prefect_db_session() as session:
            stage1_result = stats_service.count_stage1(session, novel_id)
            stage1_result["entities_extracted"] = True  # 保持原有语义

    logger.info("=" * 60)
    logger.info("阶段2: 并行执行剧情聚合和人物关系")
    logger.info("=" * 60)

    from .subflows.relationship_flow import relationship_flow
    from .subflows.story_aggregate_flow import story_aggregate_flow

    # 基于 checkpoint_data 决定是否跳过已完成子阶段
    resume_cp = checkpoint_manager.get_checkpoint("stage2")
    cp_data: dict[str, Any] = {}
    if resume_cp and resume_cp.checkpoint_data:
        import json
        if isinstance(resume_cp.checkpoint_data, str):
            try:
                cp_data = json.loads(resume_cp.checkpoint_data)
            except (json.JSONDecodeError, TypeError):
                cp_data = {}
        elif isinstance(resume_cp.checkpoint_data, dict):
            cp_data = resume_cp.checkpoint_data

    story_done = (
        (not settings.ENABLE_NOVEL_SYNOPSIS or cp_data.get("synopsis_generated")) and
        (not settings.ENABLE_STORY_AGGREGATION or cp_data.get("stories_saved", 0) > 0 or cp_data.get("stories_count", 0) > 0) and
        (not settings.ENABLE_STORYLINE_GENERATION or cp_data.get("storylines_saved", 0) > 0 or cp_data.get("storylines_count", 0) > 0)
    )

    relationship_done = (
        (not settings.ENABLE_RELATIONSHIP_EXTRACTION or cp_data.get("relationships_count", 0) > 0) and
        (not settings.ENABLE_NEO4J_STORAGE or cp_data.get("neo4j_persisted") is True or (
            cp_data.get("neo4j_total_batches", 0) > 0 and cp_data.get("neo4j_batches_completed", 0) >= cp_data.get("neo4j_total_batches", 0)
        ))
    )

    story_result: dict[str, Any]
    relationship_result: dict[str, Any]

    if not story_done:
        logger.info("阶段2-剧情子流未完成，重新执行 story_aggregate_flow")
        story_result = story_aggregate_flow(
            novel_id=novel_id,
            chapter_ids=chapter_ids,
        )
    else:
        logger.info("阶段2-剧情子流已完成，跳过执行")
        story_result = {
            "synopsis_generated": cp_data.get("synopsis_generated", False),
            "stories_count": cp_data.get("stories_saved", cp_data.get("stories_count", 0)),
            "storylines_count": cp_data.get("storylines_saved", cp_data.get("storylines_count", 0)),
            "failed_stories": cp_data.get("failed_stories", []),
        }

    if not relationship_done:
        logger.info("阶段2-关系子流未完成，重新执行 relationship_flow")
        relationship_result = relationship_flow(
            novel_id=novel_id,
            chapter_ids=chapter_ids,
        )
    else:
        logger.info("阶段2-关系子流已完成，跳过执行")
        relationship_result = {
            "relationships_count": cp_data.get("relationships_count", 0),
            "neo4j_persisted": bool(cp_data.get("neo4j_persisted") or (
                cp_data.get("neo4j_total_batches", 0) > 0 and cp_data.get("neo4j_batches_completed", 0) >= cp_data.get("neo4j_total_batches", 0)
            )),
            "neo4j_failed_chapters": cp_data.get("neo4j_failed_chapters", []),
        }

    checkpoint_manager.mark_stage_completed("stage2", {
        "stories_count": story_result.get("stories_count", 0),
        "storylines_count": story_result.get("storylines_count", 0),
        "relationships_count": relationship_result.get("relationships_count", 0),
    })

    logger.info(
        "阶段2完成: stories=%s, storylines=%s, relationships=%s",
        story_result.get("stories_count", 0),
        story_result.get("storylines_count", 0),
        relationship_result.get("relationships_count", 0),
    )

    # 更新 IngestionJob 状态
    from services.material.ingestion_jobs_service import IngestionJobsService
    with get_prefect_db_session() as session:
        job = IngestionJobsService().get_latest_by_novel(session, novel_id)
        if job:
            IngestionJobsService().update_processed(session, job.id, processed_chapters=len(chapter_ids), status="completed")
            session.commit()

    # 标记完成
    checkpoint_manager.mark_stage_completed("completed")

    # 返回结果
    result = {
        "novel_id": novel_id,
        "chapters_count": len(chapter_ids),
        "summaries_count": stage1_result.get("summaries_count", 0),
        "plots_count": stage1_result.get("plots_count", 0),
        "entities_extracted": stage1_result.get("entities_extracted", False),
        "synopsis_generated": story_result.get("synopsis_generated", False),
        "stories_count": story_result.get("stories_count", 0),
        "storylines_count": story_result.get("storylines_count", 0),
        "relationships_count": relationship_result.get("relationships_count", 0),
        "neo4j_persisted": relationship_result.get("neo4j_persisted", False),
        "status": "completed",
        "elapsed_ms": _elapsed_ms(flow_start),
    }

    logger.info(
        "event=novel_ingestion_v2_done novel_id=%s chapters=%s total_ms=%s",
        novel_id,
        len(chapter_ids),
        _elapsed_ms(flow_start),
    )

    return result


@flow(
    name="novel_ingestion_v2",
    retries=1,
    retry_delay_seconds=30,
    task_runner=RUNTIME_TASK_RUNNER,  # type: ignore[arg-type]
    persist_result=False,
)
def novel_ingestion_v2(
    file_path: str,
    user_id: str,
    novel_title: str | None = None,
    author: str | None = None,
    resume_from_checkpoint: bool = True,
) -> dict[str, Any]:
    """
    小说导入主流程 V2（支持断点续传）

    流程:
    阶段0: 文件摄取与章节建立
    阶段1: 按章节并行提取 (章节摘要 + 情节点 + 实体)
    阶段2A: 剧情相关 (小说概要 → 剧情聚合 → 剧情线)
    阶段2B: 人物关系 (关系提取 → Neo4j存储)

    Args:
        file_path: 小说文件路径（txt）
        user_id: 用户ID
        novel_title: 小说标题（可选，从文件推断）
        author: 作者（可选）
        resume_from_checkpoint: 是否从检查点恢复（默认True）

    Returns:
        Dict: 导入结果统计
    """
    logger = get_run_logger()
    flow_start = _def_now()

    logger.info(
        "event=novel_ingestion_v2_start file=%s title=%s author=%s t_ms=0",
        file_path,
        novel_title,
        author,
    )

    # 初始化变量
    novel_id = None
    job_id = None
    checkpoint_manager = None

    try:
        # ========================================
        # 检查是否可以从检查点恢复
        # ========================================

        if resume_from_checkpoint:
            # 先计算文件hash，看是否已经导入过
            checksums = calculate_checksum(file_path)
            content_hash = checksums["md5_checksum"]

            from services.material.novels_service import NovelsService
            with get_prefect_db_session() as session:
                existing_novel = NovelsService().get_by_content_hash(session, content_hash, user_id)

                if existing_novel:
                    novel_id = existing_novel.id

                    # 创建检查点管理器
                    checkpoint_manager = create_checkpoint_manager(novel_id)

                    # 检查是否可以恢复
                    if checkpoint_manager.can_resume():
                        resume_point = checkpoint_manager.get_resume_point()
                        logger.info(
                            "发现未完成的导入任务，从检查点恢复: "
                            f"stage={resume_point['stage']}, "
                            f"status={resume_point['status']}"
                        )

                        from services.material.novels_service import NovelsService
                        chapter_ids = NovelsService().list_chapter_ids(session, novel_id)

                        # 根据恢复点跳转到对应阶段
                        stage = resume_point['stage']

                        if stage == 'stage0':
                            logger.info("阶段0未完成，重新开始")
                            # 继续执行下面的阶段0代码

                        elif stage == 'stage1':
                            logger.info(f"跳过阶段0，从阶段1恢复（共 {len(chapter_ids)} 个章节）")
                            # 直接跳转到阶段1
                            return _resume_from_stage1(
                                novel_id=novel_id,
                                chapter_ids=chapter_ids,
                                checkpoint_manager=checkpoint_manager,
                                flow_start=flow_start,
                            )

                        elif stage in ['stage2', 'stage2a', 'stage2b']:
                            logger.info("跳过阶段0和1，从阶段2恢复")
                            # 直接跳转到阶段2
                            return _resume_from_stage2(
                                novel_id=novel_id,
                                chapter_ids=chapter_ids,
                                checkpoint_manager=checkpoint_manager,
                                flow_start=flow_start,
                            )

                        elif stage == 'completed':
                            logger.info("任务已完成，返回结果")
                            return {
                                "novel_id": novel_id,
                                "chapters_count": len(chapter_ids),
                                "status": "already_completed",
                                "elapsed_ms": _elapsed_ms(flow_start),
                            }

        # ========================================
        # 阶段0: 文件摄取与章节建立
        # ========================================

        # 1. 文件验证
        validated = validate_input(file_path)
        logger.info("文件验证通过: %s", validated["file_path"])

        # 2. 计算校验和（如果之前没计算过）
        if 'content_hash' not in locals():
            checksums = calculate_checksum(file_path)
            content_hash = checksums["md5_checksum"]

        # 3. 检测编码
        encoding_info = detect_encoding(file_path)
        encoding = encoding_info["encoding"] or "utf-8"

        # 4. 解析章节
        parse_result = parse_novel_chapters(file_path, encoding)
        chapters_data = parse_result["chapters"]
        inferred_title = parse_result["novel_title"]

        logger.info("解析完成: %d 个章节", len(chapters_data))

        # 5. 创建 Novel 和 Chapter 记录
        with get_prefect_db_session() as session:
            # 检查是否已存在（基于 content_hash + user_id）
            from services.material.novels_service import NovelsService
            existing_novel = NovelsService().get_by_content_hash(session, content_hash, user_id)

            if existing_novel:
                logger.warning("小说已存在: novel_id=%s", existing_novel.id)
                return {
                    "novel_id": existing_novel.id,
                    "chapters_count": len(existing_novel.chapters),
                    "status": "already_exists",
                }

            # 创建新小说
            from services.material.novels_service import NovelsService
            novel = NovelsService().create_novel(session, {
                "title": novel_title or inferred_title,
                "author": author,
                "user_id": user_id,
                "source_meta": {
                    "file_path": file_path,
                    "file_size": validated["file_size"],
                    "encoding": encoding,
                    "md5_checksum": content_hash,
                },
            })
            novel_id = novel.id
            logger.info("创建小说: novel_id=%s, title=%s", novel_id, novel.title)

            # 创建 IngestionJob
            from services.material.ingestion_jobs_service import IngestionJobsService
            job = IngestionJobsService().create_job(session, novel_id, total_chapters=len(chapters_data), status="processing", source_path=file_path)
            job_id = job.id

            # 6. 创建章节记录
            from services.material.chapters_service import ChaptersService
            chapter_ids = ChaptersService().create_chapters(
                session,
                novel,
                [
                    {
                        "chapter_number": ch["chapter_number"],
                        "title": ch["title"],
                        "content": ch["content"],
                        "content_hash": hashlib.md5(ch["content"].encode()).hexdigest(),
                    }
                    for ch in chapters_data
                ],
            )
            session.commit()

            logger.info("创建 %d 个章节记录", len(chapter_ids))

        # 创建检查点管理器（在 session 提交后，避免嵌套会话死锁）
        checkpoint_manager = create_checkpoint_manager(novel_id)
        checkpoint_manager.create_checkpoint("stage0", "completed")

        # ========================================
        # 阶段1: 按章节并行提取
        # ========================================

        checkpoint_manager.create_checkpoint("stage1", "processing")

        logger.info("=" * 60)
        logger.info("阶段1: 按章节并行提取 (章节摘要 + 情节点 + 实体)")
        logger.info("=" * 60)

        from .subflows.chapter_extraction_flow import chapter_extraction_flow

        stage1_result = chapter_extraction_flow(
            novel_id=novel_id,
            chapter_ids=chapter_ids,
        )

        checkpoint_manager.mark_stage_completed("stage1", {
            "summaries_count": stage1_result.get("summaries_count", 0),
            "plots_count": stage1_result.get("plots_count", 0),
        })

        logger.info(
            "阶段1完成: summaries=%s, plots=%s, entities=%s",
            stage1_result.get("summaries_count", 0),
            stage1_result.get("plots_count", 0),
            stage1_result.get("entities_extracted", False),
        )

        # ========================================
        # 阶段2: 并行执行剧情聚合和人物关系
        # ========================================

        checkpoint_manager.create_checkpoint("stage2", "processing")

        logger.info("=" * 60)
        logger.info("阶段2: 并行执行剧情聚合和人物关系")
        logger.info("=" * 60)

        from concurrent.futures import ThreadPoolExecutor

        from .subflows.relationship_flow import relationship_flow
        from .subflows.story_aggregate_flow import story_aggregate_flow

        # 使用线程池并行执行两个子流程
        with ThreadPoolExecutor(max_workers=2) as executor:
            story_future = executor.submit(
                story_aggregate_flow,
                novel_id=novel_id,
                chapter_ids=chapter_ids,
            )
            relationship_future = executor.submit(
                relationship_flow,
                novel_id=novel_id,
                chapter_ids=chapter_ids,
            )

            # 等待完成
            story_result = story_future.result()
            relationship_result = relationship_future.result()

        checkpoint_manager.mark_stage_completed("stage2", {
            "stories_count": story_result.get("stories_count", 0),
            "storylines_count": story_result.get("storylines_count", 0),
            "relationships_count": relationship_result.get("relationships_count", 0),
        })

        logger.info(
            "阶段2完成: stories=%s, storylines=%s, relationships=%s",
            story_result.get("stories_count", 0),
            story_result.get("storylines_count", 0),
            relationship_result.get("relationships_count", 0),
        )

        # ========================================
        # 更新 IngestionJob 状态
        # ========================================

        from services.material.ingestion_jobs_service import IngestionJobsService
        with get_prefect_db_session() as session:
            IngestionJobsService().update_processed(session, job_id, processed_chapters=len(chapter_ids), status="completed")
            session.commit()

        # 标记完成
        checkpoint_manager.mark_stage_completed("completed")

        # ========================================
        # 返回结果
        # ========================================

        result = {
            "novel_id": novel_id,
            "job_id": job_id,
            "chapters_count": len(chapter_ids),
            "summaries_count": stage1_result.get("summaries_count", 0),
            "plots_count": stage1_result.get("plots_count", 0),
            "entities_extracted": stage1_result.get("entities_extracted", False),
            "synopsis_generated": story_result.get("synopsis_generated", False),
            "stories_count": story_result.get("stories_count", 0),
            "storylines_count": story_result.get("storylines_count", 0),
            "relationships_count": relationship_result.get("relationships_count", 0),
            "neo4j_persisted": relationship_result.get("neo4j_persisted", False),
            "status": "completed",
            "elapsed_ms": _elapsed_ms(flow_start),
        }

        logger.info(
            "event=novel_ingestion_v2_done novel_id=%s chapters=%s total_ms=%s",
            novel_id,
            len(chapter_ids),
            _elapsed_ms(flow_start),
        )

        return result

    except Exception as e:
        logger.error("小说导入失败: %s", str(e), exc_info=True)

        # 更新 Job 状态为失败
        try:
            from services.material.ingestion_jobs_service import IngestionJobsService
            with get_prefect_db_session() as session:
                IngestionJobsService().update_status(session, job_id, "failed")
        except Exception:
            pass

        # 标记检查点失败（若可用）
        try:
            if checkpoint_manager is not None:
                checkpoint_manager.mark_stage_failed("failed", str(e))
        except Exception:
            pass

        raise


if __name__ == "__main__":
    # CLI 入口
    import argparse

    parser = argparse.ArgumentParser(description="Run novel ingestion V2")
    parser.add_argument("--file", required=True, help="Novel file path")
    parser.add_argument("--user-id", required=True, help="User ID")
    parser.add_argument("--title", help="Novel title (optional)")
    parser.add_argument("--author", help="Author name (optional)")
    args = parser.parse_args()

    result = novel_ingestion_v2(
        file_path=args.file,
        user_id=args.user_id,
        novel_title=args.title,
        author=args.author,
    )
    print(f"[OK] Novel ingestion done. novel_id={result['novel_id']}")
