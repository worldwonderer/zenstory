#!/usr/bin/env python3
"""
阶段执行器

统一阶段执行逻辑，消除主流程中的重复代码。
提供清晰的接口来执行各个阶段。
"""

from __future__ import annotations

import json
import time
from typing import Any

from prefect import get_run_logger, task

from config.material_settings import material_settings as settings
from flows.database_session import get_prefect_db_session
from flows.pipelines.helpers import ProgressPublisher, ResultBuilder


# 本地实现 _elapsed_ms 函数
def _elapsed_ms(start: float) -> int:
    """计算从 start 到现在的毫秒数"""
    return int((time.perf_counter() - start) * 1000)


def _parse_cp_data(checkpoint) -> dict[str, Any]:
    """安全解析 checkpoint_data（可能是 JSON 字符串或 dict）"""
    if not checkpoint or not getattr(checkpoint, "checkpoint_data", None):
        return {}
    data = checkpoint.checkpoint_data
    if isinstance(data, str):
        try:
            data = json.loads(data)
        except (json.JSONDecodeError, TypeError):
            return {}
    return data if isinstance(data, dict) else {}

# 任务包装器函数定义在此处，避免循环导入
@task(name="run_story_aggregate_subflow", persist_result=False)
def _task_run_story_aggregate(novel_id: int, chapter_ids: list[int], correlation_id: str | None = None) -> dict[str, Any]:
    """任务包装器：执行剧情聚合子流程"""
    from flows.pipelines.subflows.story_aggregate_flow import story_aggregate_flow
    return story_aggregate_flow(novel_id=novel_id, chapter_ids=chapter_ids, correlation_id=correlation_id)

@task(name="run_relationship_subflow", persist_result=False)
def _task_run_relationship(novel_id: int, chapter_ids: list[int], correlation_id: str | None = None) -> dict[str, Any]:
    """任务包装器：执行人物关系子流程"""
    from flows.pipelines.subflows.relationship_flow import relationship_flow
    return relationship_flow(novel_id=novel_id, chapter_ids=chapter_ids, correlation_id=correlation_id)

@task(name="run_character_entity_build_subflow", persist_result=False)
def _task_run_character_entity_build(novel_id: int, correlation_id: str | None = None) -> dict[str, Any]:
    """任务包装器：执行角色实体构建子流程"""
    from flows.pipelines.subflows.character_entity_build_flow import (
        character_entity_build_flow,
    )
    return character_entity_build_flow(novel_id=novel_id, correlation_id=correlation_id)


class StageExecutor:
    """
    阶段执行器

    封装阶段1和阶段2的执行逻辑，提供统一的接口。
    消除主流程和恢复函数之间的重复代码。

    使用示例:
        >>> executor = StageExecutor(novel_id, chapter_ids, checkpoint_manager, correlation_id)
        >>> stage1_result = executor.execute_stage1()
        >>> final_result = executor.execute_stage2(stage1_result, flow_start)
    """

    def __init__(
        self,
        novel_id: int,
        chapter_ids: list[int],
        checkpoint_manager: Any,
        correlation_id: str | None = None,
    ):
        """
        初始化阶段执行器

        Args:
            novel_id: 小说ID
            chapter_ids: 章节ID列表
            checkpoint_manager: checkpoint管理器
            correlation_id: 关联ID（用于进度推送）
        """
        self.novel_id = novel_id
        self.chapter_ids = chapter_ids
        self.checkpoint_manager = checkpoint_manager
        self.correlation_id = correlation_id
        self.logger = get_run_logger()
        self.publisher = ProgressPublisher(correlation_id, self.logger)

    def execute_stage1(self) -> dict[str, Any]:
        """
        执行阶段1：章节并行提取

        执行章节摘要、情节点、角色提及、元信息的并行提取。
        统一处理阶段1的逻辑，供主流程和恢复函数共用。

        Returns:
            Dict[str, Any]: 阶段1结果
        """
        self.logger.info("=" * 60)
        self.logger.info("[阶段1] 按章节并行提取 (章节摘要 + 情节点 + 实体)")
        self.logger.info(f"[阶段1] novel_id={self.novel_id}, chapters_count={len(self.chapter_ids)}")
        self.logger.info("=" * 60)
        self.publisher.publish("stage1_started", status="processing", novel_id=self.novel_id)
        self._sync_job_stage(
            "stage1",
            "processing",
            payload={"chapters_total": len(self.chapter_ids)},
        )

        from flows.pipelines.subflows.chapter_extraction_flow import (
            chapter_extraction_flow,
        )

        stage1_start = time.perf_counter()

        # 并行触发元信息提取（统一逻辑）
        meta_future = self._handle_meta_extraction(is_parallel=True)

        # 执行章节提取流程
        stage1_result = chapter_extraction_flow(
            novel_id=self.novel_id,
            chapter_ids=self.chapter_ids,
            correlation_id=self.correlation_id,  # 【修复】统一传递关联ID
        )

        # 处理元信息提取结果
        if meta_future is not None:
            try:
                meta_result = meta_future.result()
                self._save_meta_result(meta_result)
            except Exception as e:
                self.logger.warning(f"[阶段1] 元信息并行提取失败: {e}")

        stage1_elapsed = int((time.perf_counter() - stage1_start) * 1000)
        failed_count = stage1_result.get("failed_count", 0)
        stage1_status = stage1_result.get("status", "completed")

        # 更新 checkpoint
        self.checkpoint_manager.mark_stage_completed("stage1", {
            "summaries_count": stage1_result.get("summaries_count", 0),
            "plots_count": stage1_result.get("plots_count", 0),
            "failed_count": failed_count,
            "failed_chapters": stage1_result.get("failed_chapters", []),
            "failed_mention_chapters": stage1_result.get("failed_mention_chapters", []),
            "status": stage1_status,
        })

        # 记录日志
        self.logger.info(
            "[阶段1] 完成: summaries=%s, plots=%s, mentions=%s, failed=%s, elapsed_ms=%s, status=%s",
            stage1_result.get("summaries_count", 0),
            stage1_result.get("plots_count", 0),
            stage1_result.get("mentions_extracted", False),
            failed_count,
            stage1_elapsed,
            stage1_result.get("status", "completed"),
        )

        # 发布进度
        self.publisher.publish(
            "stage1_completed",
            status="processing",
            novel_id=self.novel_id,
            elapsed_ms=stage1_elapsed,
            summaries_count=stage1_result.get("summaries_count", 0),
            plots_count=stage1_result.get("plots_count", 0),
            failed_count=failed_count,
            progress=50,
            message=f"阶段1完成: 已提取 {stage1_result.get('summaries_count', 0)} 个章节摘要"
        )
        self._sync_job_stage(
            "stage1",
            stage1_status,
            payload={
                "summaries_count": stage1_result.get("summaries_count", 0),
                "plots_count": stage1_result.get("plots_count", 0),
                "failed_count": failed_count,
                "failed_mention_chapters": stage1_result.get("failed_mention_chapters", []),
                "elapsed_ms": stage1_elapsed,
            },
            processed_chapters=max(0, len(self.chapter_ids) - failed_count),
            status="processing",
        )

        if failed_count > 0:
            self.logger.warning(
                "[阶段1] 部分章节处理失败: failed_count=%s, failed_chapters=%s",
                failed_count,
                stage1_result.get("failed_chapters", []),
            )

        return stage1_result

    def execute_stage2(
        self,
        stage1_result: dict[str, Any] | None = None,
        flow_start: float | None = None,
    ) -> dict[str, Any]:
        """
        执行阶段2：剧情聚合 + 角色实体 + 人物关系

        当检测到阶段1已完成但阶段2未完成时，从此处恢复。
        执行三个子阶段：
        - 阶段2A（剧情聚合）和 阶段2C（角色实体）并行执行
        - 阶段2B（人物关系）依赖 阶段2C 完成后执行

        Args:
            stage1_result: 阶段1的结果（如果为None，会从checkpoint或数据库加载）
            flow_start: 流程开始时间（用于计算总耗时）

        Returns:
            Dict[str, Any]: 最终结果（包含所有阶段的统计信息）
        """
        # 如果没有 stage1_result，优先从 checkpoint 获取，降级到数据库统计
        if stage1_result is None:
            stage1_result = self._load_stage1_result()

        self.logger.info("=" * 60)
        self.logger.info("[阶段2] 并行执行剧情聚合和人物关系")
        self.logger.info(f"[阶段2] novel_id={self.novel_id}, chapters_count={len(self.chapter_ids)}")
        self.logger.info("=" * 60)
        self.publisher.publish(
            "stage2_started",
            status="processing",
            novel_id=self.novel_id,
            progress=60,
            message="阶段2: 开始剧情聚合和人物关系分析..."
        )
        self._sync_job_stage(
            "stage2",
            "processing",
            payload={"chapters_total": len(self.chapter_ids)},
            status="processing",
        )

        stage2_start = time.perf_counter()

        # 获取阶段2各个子阶段的完成状态
        stage2a_done, stage2b_done, stage2c_done = self._check_stage2_completion()

        # 并行执行阶段2A（剧情）和阶段2C（角色实体）
        story_result, character_entity_result = self._execute_parallel_stages(
            stage2a_done, stage2c_done
        )

        # 执行阶段2B（人物关系），依赖阶段2C完成
        relationship_result = self._execute_relationship_stage(stage2b_done)

        stage2_elapsed = int((time.perf_counter() - stage2_start) * 1000)

        # 更新所有子阶段的 checkpoint
        self._update_stage2_checkpoints(story_result, relationship_result, character_entity_result)

        # 记录日志
        self.logger.info(
            "[阶段2] 完成: stories=%s, storylines=%s, relationships=%s, characters=%s/%s, elapsed_ms=%s",
            story_result.get("stories_count", 0),
            story_result.get("storylines_count", 0),
            relationship_result.get("relationships_count", 0),
            character_entity_result.get("created_count", 0),
            character_entity_result.get("updated_count", 0),
            stage2_elapsed,
        )

        # 发布进度
        self.publisher.publish(
            "stage2_completed",
            status="processing",
            novel_id=self.novel_id,
            elapsed_ms=stage2_elapsed,
            stories_count=story_result.get("stories_count", 0),
            storylines_count=story_result.get("storylines_count", 0),
            relationships_count=relationship_result.get("relationships_count", 0),
            neo4j_persisted=relationship_result.get("neo4j_persisted", False),
            characters_created=character_entity_result.get("created_count", 0),
            characters_updated=character_entity_result.get("updated_count", 0),
            progress=90,
            message=f"阶段2完成: 已生成 {story_result.get('stories_count', 0)} 个剧情点, {character_entity_result.get('created_count', 0) + character_entity_result.get('updated_count', 0)} 个角色"
        )
        self._sync_job_stage(
            "stage2",
            self._derive_final_status(
                stage1_result,
                story_result,
                relationship_result,
                character_entity_result,
            ),
            payload={
                "stories_count": story_result.get("stories_count", 0),
                "storylines_count": story_result.get("storylines_count", 0),
                "relationships_count": relationship_result.get("relationships_count", 0),
                "failed_stories": story_result.get("failed_stories", []),
                "neo4j_failed_chapters": relationship_result.get("neo4j_failed_chapters", []),
                "character_failed_count": character_entity_result.get("failed_count", 0),
                "elapsed_ms": stage2_elapsed,
            },
            status="processing",
        )

        final_status = self._derive_final_status(
            stage1_result,
            story_result,
            relationship_result,
            character_entity_result,
        )

        # 更新 IngestionJob 状态
        self._update_job_status(
            final_status,
            stage1_result,
            story_result,
            relationship_result,
            character_entity_result,
        )

        # 构建最终结果（使用 ResultBuilder）
        elapsed_ms = _elapsed_ms(flow_start) if flow_start else 0
        result = ResultBuilder.build_final_result(
            novel_id=self.novel_id,
            job_id=self._get_job_id(),
            chapter_ids=self.chapter_ids,
            stage1_result=stage1_result,
            story_result=story_result,
            relationship_result=relationship_result,
            character_entity_result=character_entity_result,
            status=final_status,
            elapsed_ms=elapsed_ms,
        )

        # 标记完成，保存完整的结果数据到 checkpoint
        self._save_final_checkpoint(stage1_result, story_result, relationship_result, character_entity_result)

        # 发送完成消息（使用 ProgressPublisher）
        self.publisher.publish_completion(self.novel_id, self.chapter_ids, result)

        return result

    def _handle_meta_extraction(self, is_parallel: bool = True) -> Any | None:
        """
        统一处理元信息提取逻辑

        Args:
            is_parallel: 是否并行执行（True=submit, False=直接执行）

        Returns:
            Future对象（并行模式）或 None
        """
        if not settings.ENABLE_ENTITY_EXTRACTION:
            return None

        # 检查是否已完成
        resume_cp = self.checkpoint_manager.get_checkpoint("stage2")
        cp_data = _parse_cp_data(resume_cp)

        if cp_data.get("meta_extracted"):
            self.logger.info("[元信息] 已完成，跳过")
            return None

        try:
            from flows.atomic_tasks.entities import extract_novel_meta_task
            self.logger.info("[元信息] 开始提取...")

            if is_parallel:
                # 并行模式：返回 Future
                return extract_novel_meta_task.submit(novel_id=self.novel_id)
            else:
                # 同步模式：直接执行
                meta_result = extract_novel_meta_task(novel_id=self.novel_id)
                self._save_meta_result(meta_result)
                return None
        except Exception as e:
            self.logger.warning(f"[元信息] 提取失败: {e}")
            return None

    def _save_meta_result(self, meta_result: dict[str, Any]) -> None:
        """
        保存元信息提取结果

        Args:
            meta_result: 元信息提取结果
        """
        try:
            from sqlmodel import select

            from flows.atomic_tasks.entities import build_meta_entities_task
            from models.material_models import Chapter

            # 1. 查询 first_chapter
            with get_prefect_db_session() as session:
                first_chapter = session.exec(
                    select(Chapter).where(Chapter.novel_id == self.novel_id).order_by(Chapter.chapter_number)
                ).first()
                first_chapter_id = first_chapter.id if first_chapter else None

            # 2. 构建实体（可能失败）
            build_meta_entities_task(
                meta_data=meta_result,
                novel_id=self.novel_id,
                first_chapter_id=first_chapter_id
            )

            # 【修复 Bug #3】只有成功后才更新 checkpoint
            self.checkpoint_manager.update_checkpoint(
                "stage2",
                status="processing",
                data={"meta_extracted": True}
            )
            self.logger.info("[元信息] 提取与入库完成")

        except Exception as e:
            self.logger.error(f"[元信息] 保存失败: {e}", exc_info=True)
            # 【修复 Bug #3】不要 raise，让上层流程继续（元信息是可选的）
            # 标记为部分失败
            try:
                self.checkpoint_manager.update_checkpoint(
                    "stage2",
                    status="processing",
                    data={"meta_extracted": False, "meta_error": str(e)}
                )
            except Exception as cp_err:
                self.logger.warning(f"[元信息] 更新 checkpoint 失败: {cp_err}")

    def _load_stage1_result(self) -> dict[str, Any]:
        """
        从 checkpoint 或数据库加载阶段1结果

        Returns:
            阶段1结果字典
        """
        self.logger.info("[阶段2] 从 checkpoint 和数据库加载阶段1统计信息")

        # 1. 优先从 checkpoint 获取
        stage1_cp = self.checkpoint_manager.get_checkpoint("stage1")
        stage1_cp_data = _parse_cp_data(stage1_cp)
        if stage1_cp_data:
            stage1_result = stage1_cp_data.copy()
            self.logger.debug(f"[阶段2] 从 checkpoint 加载: {stage1_result}")
        else:
            # 2. 降级到数据库统计
            from services.material.stats_service import StatsService
            stats_service = StatsService()
            with get_prefect_db_session() as session:
                stage1_result = stats_service.count_stage1(session, self.novel_id)
            self.logger.debug(f"[阶段2] 从数据库加载: {stage1_result}")

        # 3. 检查角色提及提取状态（从 stage1 checkpoint）
        mentions_extracted = stage1_result.get("mentions_extracted", False)
        if not mentions_extracted:
            # 降级：从 checkpoint 获取
            stage1_cp = self.checkpoint_manager.get_checkpoint("stage1")
            _cp_data = _parse_cp_data(stage1_cp)
            mentions_extracted = _cp_data.get("mentions_extracted", False)

        if stage1_result:
            stage1_result["mentions_extracted"] = mentions_extracted
        else:
            stage1_result = {"mentions_extracted": mentions_extracted}
        self.logger.debug(f"[阶段2] 最终 stage1_result: {stage1_result}")

        return stage1_result

    def _check_stage2_completion(self) -> tuple[bool, bool, bool]:
        """
        检查阶段2各个子阶段的完成状态

        Returns:
            (stage2a_done, stage2b_done, stage2c_done)
        """
        # 获取各子阶段的 checkpoint
        stage2a_cp = self.checkpoint_manager.get_checkpoint("stage2a")
        stage2b_cp = self.checkpoint_manager.get_checkpoint("stage2b")
        stage2c_cp = self.checkpoint_manager.get_checkpoint("stage2c")

        stage2a_needed = (
            settings.ENABLE_NOVEL_SYNOPSIS
            or settings.ENABLE_STORY_AGGREGATION
            or settings.ENABLE_STORYLINE_GENERATION
        )
        stage2b_needed = settings.ENABLE_RELATIONSHIP_EXTRACTION
        stage2c_needed = settings.ENABLE_ENTITY_EXTRACTION

        stage2a_done = (not stage2a_needed) or bool(
            stage2a_cp and getattr(stage2a_cp, "stage_status", None) == "completed"
        )
        stage2b_done = (not stage2b_needed) or bool(
            stage2b_cp and getattr(stage2b_cp, "stage_status", None) == "completed"
        )
        stage2c_done = (not stage2c_needed) or bool(
            stage2c_cp and getattr(stage2c_cp, "stage_status", None) == "completed"
        )

        return stage2a_done, stage2b_done, stage2c_done

    def _execute_parallel_stages(self, stage2a_done: bool, stage2c_done: bool) -> tuple[dict[str, Any], dict[str, Any]]:
        """
        并行执行阶段2A（剧情）和阶段2C（角色实体）

        Args:
            stage2a_done: 阶段2A是否已完成
            stage2c_done: 阶段2C是否已完成

        Returns:
            (story_result, character_entity_result)
        """
        # 使用本地定义的任务包装器

        story_future = None
        character_entity_future = None

        # 启动任务
        if not stage2a_done:
            self.logger.info("[阶段2-剧情] 子流未完成，并行执行 story_aggregate_flow")
            story_future = _task_run_story_aggregate.submit(self.novel_id, self.chapter_ids, self.correlation_id)  # 【修复】传递关联ID
        else:
            self.logger.info("[阶段2-剧情] 子流已完成，跳过执行")

        if not stage2c_done and settings.ENABLE_ENTITY_EXTRACTION:
            self.logger.info("[阶段2-角色] 子流未完成，并行执行 character_entity_build_flow")
            character_entity_future = _task_run_character_entity_build.submit(self.novel_id, self.correlation_id)  # 【修复】传递关联ID
        else:
            if not settings.ENABLE_ENTITY_EXTRACTION:
                self.logger.info("[阶段2-角色] 角色提取功能未启用，跳过执行")
            else:
                self.logger.info("[阶段2-角色] 子流已完成，跳过执行")

        # 获取结果
        if story_future is not None:
            story_result = story_future.result()
            self.logger.info("[阶段2-剧情] 完成")
        else:
            # 从 checkpoint 获取结果
            stage2a_data = _parse_cp_data(self.checkpoint_manager.get_checkpoint("stage2a"))
            story_result = {
                "synopsis_generated": stage2a_data.get("synopsis_generated", False),
                "stories_count": stage2a_data.get("stories_count", 0),
                "storylines_count": stage2a_data.get("storylines_count", 0),
                "failed_stories": stage2a_data.get("failed_stories", []),
                "status": stage2a_data.get("status", "completed"),
            }

        if character_entity_future is not None:
            character_entity_result = character_entity_future.result()
            self.logger.info("[阶段2-角色] 完成")
        else:
            # 从 checkpoint 获取结果
            stage2c_data = _parse_cp_data(self.checkpoint_manager.get_checkpoint("stage2c"))
            character_entity_result = {
                "created_count": stage2c_data.get("created_count", 0),
                "updated_count": stage2c_data.get("updated_count", 0),
                "failed_count": stage2c_data.get("failed_count", 0),
                "failed_characters": stage2c_data.get("failed_characters", []),
                "status": stage2c_data.get("status", "completed"),
            }

        self.logger.info("[阶段2] 剧情聚合和角色实体构建完成，开始人物关系提取...")

        return story_result, character_entity_result

    def _execute_relationship_stage(self, stage2b_done: bool) -> dict[str, Any]:
        """
        执行阶段2B（人物关系）

        Args:
            stage2b_done: 阶段2B是否已完成

        Returns:
            relationship_result: 关系结果
        """
        # 使用本地定义的任务包装器

        if not stage2b_done:
            self.logger.info("[阶段2-关系] 子流未完成，执行 relationship_flow")
            relationship_future = _task_run_relationship.submit(self.novel_id, self.chapter_ids, self.correlation_id)  # 【修复】传递关联ID
            relationship_result = relationship_future.result()
            self.logger.info("[阶段2-关系] 完成")
        else:
            self.logger.info("[阶段2-关系] 子流已完成，跳过执行")
            # 从 checkpoint 获取结果
            stage2b_data = _parse_cp_data(self.checkpoint_manager.get_checkpoint("stage2b"))
            relationship_result = {
                "relationships_count": stage2b_data.get("relationships_count", 0),
                "neo4j_persisted": stage2b_data.get("neo4j_persisted", False),
                "neo4j_failed_chapters": stage2b_data.get("neo4j_failed_chapters", []),
                "status": stage2b_data.get("status", "completed"),
            }

        return relationship_result

    def _update_stage2_checkpoints(
        self,
        story_result: dict[str, Any],
        relationship_result: dict[str, Any],
        character_entity_result: dict[str, Any],
    ) -> None:
        """
        更新阶段2所有子阶段的 checkpoint

        Args:
            story_result: 剧情结果
            relationship_result: 关系结果
            character_entity_result: 角色实体结果
        """
        # 更新 stage2a
        self.checkpoint_manager.mark_stage_completed("stage2a", {
            "synopsis_generated": story_result.get("synopsis_generated", False),
            "stories_count": story_result.get("stories_count", 0),
            "storylines_count": story_result.get("storylines_count", 0),
            "failed_stories": story_result.get("failed_stories", []),
            "status": story_result.get("status", "completed"),
        })

        # 更新 stage2b
        self.checkpoint_manager.mark_stage_completed("stage2b", {
            "relationships_count": relationship_result.get("relationships_count", 0),
            "neo4j_persisted": relationship_result.get("neo4j_persisted", False),
            "neo4j_failed_chapters": relationship_result.get("neo4j_failed_chapters", []),
            "status": relationship_result.get("status", "completed"),
        })

        # 更新 stage2c
        self.checkpoint_manager.mark_stage_completed("stage2c", {
            "characters_built": True,
            "created_count": character_entity_result.get("created_count", 0),
            "updated_count": character_entity_result.get("updated_count", 0),
            "failed_count": character_entity_result.get("failed_count", 0),
            "failed_characters": character_entity_result.get("failed_characters", []),
            "status": character_entity_result.get("status", "completed"),
        })

        # 汇总到 stage2（用于整体状态追踪）
        self.checkpoint_manager.mark_stage_completed("stage2", {
            "synopsis_generated": story_result.get("synopsis_generated", False),
            "stories_count": story_result.get("stories_count", 0),
            "storylines_count": story_result.get("storylines_count", 0),
            "relationships_count": relationship_result.get("relationships_count", 0),
            "neo4j_persisted": relationship_result.get("neo4j_persisted", False),
            "characters_built": True,
            "characters_created": character_entity_result.get("created_count", 0),
            "characters_updated": character_entity_result.get("updated_count", 0),
            "failed_count": len(story_result.get("failed_stories", []))
            + len(relationship_result.get("neo4j_failed_chapters", []))
            + character_entity_result.get("failed_count", 0),
            "failed_stories": story_result.get("failed_stories", []),
            "neo4j_failed_chapters": relationship_result.get("neo4j_failed_chapters", []),
            "failed_chapters": [],
            "failed_mention_chapters": [],
            "failed_characters": character_entity_result.get("failed_characters", []),
        })

    def _get_job_id(self) -> int | None:
        """
        获取最新的 IngestionJob ID

        Returns:
            job_id 或 None
        """
        try:
            from services.material.ingestion_jobs_service import IngestionJobsService
            with get_prefect_db_session() as session:
                job = IngestionJobsService().get_latest_by_novel(session, self.novel_id)
                return job.id if job else None
        except Exception as e:
            self.logger.warning(f"[Job] 获取 Job ID 失败: {e}")
            return None

    def _sync_job_stage(
        self,
        stage: str,
        stage_status: str,
        *,
        payload: dict[str, Any] | None = None,
        processed_chapters: int | None = None,
        status: str | None = None,
    ) -> None:
        """同步 IngestionJob 的阶段进度，失败时仅记录 warning。"""
        try:
            from services.material.ingestion_jobs_service import IngestionJobsService

            with get_prefect_db_session() as session:
                svc = IngestionJobsService()
                job = svc.get_latest_by_novel(session, self.novel_id)
                if not job:
                    return
                svc.update_processed(
                    session,
                    job.id,
                    processed_chapters=processed_chapters,
                    status=status,
                    stage=stage,
                    stage_status=stage_status,
                    stage_data=payload or {},
                )
                session.commit()
        except Exception as e:
            self.logger.warning(f"[Job] 同步阶段进度失败: stage={stage}, status={stage_status}, err={e}")

    def _derive_final_status(
        self,
        stage1_result: dict[str, Any] | None,
        story_result: dict[str, Any],
        relationship_result: dict[str, Any],
        character_entity_result: dict[str, Any],
    ) -> str:
        """Derive overall flow status from stage-level failures."""
        if (stage1_result or {}).get("failed_count", 0) > 0:
            return "completed_with_errors"
        if story_result.get("failed_stories"):
            return "completed_with_errors"
        if relationship_result.get("neo4j_failed_chapters"):
            return "completed_with_errors"
        if character_entity_result.get("failed_count", 0) > 0:
            return "completed_with_errors"
        return "completed"

    def _update_job_status(
        self,
        final_status: str,
        stage1_result: dict[str, Any] | None,
        story_result: dict[str, Any],
        relationship_result: dict[str, Any],
        character_entity_result: dict[str, Any],
    ) -> None:
        """
        更新 IngestionJob 最终状态
        """
        try:
            from services.material.ingestion_jobs_service import IngestionJobsService
            with get_prefect_db_session() as session:
                svc = IngestionJobsService()
                job = svc.get_latest_by_novel(session, self.novel_id)
                if job:
                    svc.update_processed(
                        session,
                        job.id,
                        processed_chapters=len(self.chapter_ids),
                        status=final_status,
                        stage="completed",
                        stage_status=final_status,
                        stage_data={
                            "chapters_total": len(self.chapter_ids),
                            "failed_count": (stage1_result or {}).get("failed_count", 0)
                            + character_entity_result.get("failed_count", 0),
                            "failed_stories": story_result.get("failed_stories", []),
                            "neo4j_failed_chapters": relationship_result.get("neo4j_failed_chapters", []),
                            "failed_chapters": (stage1_result or {}).get("failed_chapters", []),
                            "failed_mention_chapters": (stage1_result or {}).get("failed_mention_chapters", []),
                            "failed_characters": character_entity_result.get("failed_characters", []),
                        },
                    )
                    session.commit()
        except Exception as e:
            self.logger.warning(f"[Job] 更新 Job 状态失败: {e}")

    def _save_final_checkpoint(
        self,
        stage1_result: dict[str, Any] | None,
        story_result: dict[str, Any],
        relationship_result: dict[str, Any],
        character_entity_result: dict[str, Any],
    ) -> None:
        """
        保存最终 checkpoint

        Args:
            stage1_result: 阶段1结果
            story_result: 剧情结果
            relationship_result: 关系结果
            character_entity_result: 角色实体结果
        """
        self.checkpoint_manager.mark_stage_completed("completed", {
            "novel_id": self.novel_id,
            "chapters_count": len(self.chapter_ids),
            "summaries_count": stage1_result.get("summaries_count", 0) if stage1_result else 0,
            "plots_count": stage1_result.get("plots_count", 0) if stage1_result else 0,
            "mentions_extracted": stage1_result.get("mentions_extracted", False) if stage1_result else False,
            "failed_count": stage1_result.get("failed_count", 0) if stage1_result else 0,
            "failed_chapters": stage1_result.get("failed_chapters", []) if stage1_result else [],
            "failed_mention_chapters": stage1_result.get("failed_mention_chapters", []) if stage1_result else [],
            "synopsis_generated": story_result.get("synopsis_generated", False) if story_result else False,
            "stories_count": story_result.get("stories_count", 0) if story_result else 0,
            "storylines_count": story_result.get("storylines_count", 0) if story_result else 0,
            "failed_stories": story_result.get("failed_stories", []) if story_result else [],
            "relationships_count": relationship_result.get("relationships_count", 0) if relationship_result else 0,
            "neo4j_persisted": relationship_result.get("neo4j_persisted", False) if relationship_result else False,
            "neo4j_failed_chapters": relationship_result.get("neo4j_failed_chapters", []) if relationship_result else [],
            "characters_created": character_entity_result.get("created_count", 0) if character_entity_result else 0,
            "characters_updated": character_entity_result.get("updated_count", 0) if character_entity_result else 0,
            "character_failed_count": character_entity_result.get("failed_count", 0) if character_entity_result else 0,
            "failed_characters": character_entity_result.get("failed_characters", []) if character_entity_result else [],
        })
