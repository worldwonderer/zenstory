"""
检查点管理器（helpers 归档）
"""
import json
from typing import Any

from prefect import get_run_logger

from services.material.checkpoint_service import CheckpointService


class CheckpointManager:
    """检查点管理器"""

    def __init__(self, novel_id: int, job_id: int | None = None):
        self.novel_id = novel_id
        self.job_id = job_id
        self.logger = get_run_logger()

    def create_checkpoint(
        self,
        stage: str,
        status: str = "processing",
        data: dict[str, Any] | None = None,
    ) -> None:
        """创建检查点"""
        from flows.database_session import get_prefect_db_session

        with get_prefect_db_session() as session:
            svc = CheckpointService()
            svc.upsert(
                session,
                self.novel_id,
                stage,
                data or {},
                status=status,
                job_id=self.job_id,
            )
            session.commit()
            self.logger.info(f"创建检查点: stage={stage}, status={status}")

    def update_checkpoint(
        self,
        stage: str,
        status: str | None = None,
        data: dict[str, Any] | None = None,
        error: str | None = None,
    ) -> None:
        """更新检查点"""
        from flows.database_session import get_prefect_db_session

        with get_prefect_db_session() as session:
            svc = CheckpointService()
            checkpoint = svc.get(session, self.novel_id, stage)

            # 【修复】明确传递 None 而不是空字典，避免混淆
            checkpoint = svc.upsert(
                session,
                self.novel_id,
                stage,
                data,  # 直接传递，让 upsert 处理 None 的情况
                status=status,
                job_id=self.job_id,
                error=error,
            )
            session.commit()

            self.logger.info(
                f"更新检查点: stage={stage}, status={status or checkpoint.stage_status}"
            )

    def _parse_checkpoint_data(self, checkpoint) -> dict[str, Any]:
        """解析 checkpoint_data（JSON字符串 → dict）"""
        if not checkpoint or not checkpoint.checkpoint_data:
            return {}
        data = checkpoint.checkpoint_data
        if isinstance(data, str):
            try:
                return json.loads(data)
            except (json.JSONDecodeError, TypeError):
                return {}
        return data if isinstance(data, dict) else {}

    def get_checkpoint(self, stage: str) -> Any | None:
        """获取检查点"""
        from flows.database_session import get_prefect_db_session

        with get_prefect_db_session() as session:
            svc = CheckpointService()
            checkpoint = svc.get(session, self.novel_id, stage)

            if checkpoint:
                # 需要 detach from session
                session.expunge(checkpoint)

            return checkpoint

    def get_latest_checkpoint(self) -> Any | None:
        """获取最新的检查点"""
        from flows.database_session import get_prefect_db_session

        with get_prefect_db_session() as session:
            svc = CheckpointService()
            checkpoint = svc.get_latest(session, self.novel_id)
            if checkpoint:
                session.expunge(checkpoint)
            return checkpoint

    def can_resume(self) -> bool:
        """是否可以恢复"""
        checkpoint = self.get_latest_checkpoint()

        if not checkpoint:
            return False

        # 只有 processing 或 failed 状态可以恢复
        return checkpoint.stage_status in ["processing", "failed"]

    def get_resume_point(self) -> dict[str, Any] | None:
        """获取恢复点信息"""
        checkpoint = self.get_latest_checkpoint()

        if not checkpoint or not self.can_resume():
            return None

        return {
            "stage": checkpoint.stage,
            "status": checkpoint.stage_status,
            "data": self._parse_checkpoint_data(checkpoint),
            "can_retry": checkpoint.can_retry(),
            "retry_count": checkpoint.retry_count,
            "error": checkpoint.error_message,
        }

    def mark_stage_completed(self, stage: str, data: dict[str, Any] | None = None) -> None:
        """标记阶段完成"""
        self.update_checkpoint(stage, status="completed", data=data)

    def mark_stage_failed(self, stage: str, error: str) -> None:
        """标记阶段失败"""
        self.update_checkpoint(stage, status="failed", error=error)

    def get_completed_chapters(self, stage: str) -> list[int]:
        """获取已完成的章节ID列表"""
        checkpoint = self.get_checkpoint(stage)
        data = self._parse_checkpoint_data(checkpoint)
        return data.get("completed_chapter_ids", [])

    def get_failed_chapters(self, stage: str) -> list[int]:
        """获取失败的章节ID列表"""
        checkpoint = self.get_checkpoint(stage)
        data = self._parse_checkpoint_data(checkpoint)
        return data.get("failed_chapter_ids", [])

    def get_pending_chapters(self, stage: str, all_chapter_ids: list[int]) -> list[int]:
        """获取待处理的章节ID列表"""
        completed = set(self.get_completed_chapters(stage))
        failed = set(self.get_failed_chapters(stage))

        # 待处理 = 全部 - 已完成 - 失败
        pending = [
            cid for cid in all_chapter_ids if cid not in completed and cid not in failed
        ]

        return pending

    def clear_checkpoints(self) -> None:
        """清除所有检查点"""
        from flows.database_session import get_prefect_db_session

        with get_prefect_db_session() as session:
            svc = CheckpointService()
            svc.delete_all(session, self.novel_id)
            session.commit()

            self.logger.info(f"清除所有检查点: novel_id={self.novel_id}")


def create_checkpoint_manager(novel_id: int, job_id: int | None = None) -> CheckpointManager:
    """创建检查点管理器的工厂函数"""
    return CheckpointManager(novel_id, job_id)
