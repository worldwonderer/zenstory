"""
Helper functions for materials API.

Contains shared utility functions used across material library endpoints.
"""
import asyncio
import json

from sqlmodel import Session, select

from config.datetime_utils import utcnow
from core.error_codes import ErrorCode
from core.error_handler import APIException
from database import create_session
from models.material_models import IngestionJob, Novel
from utils.logger import get_logger

logger = get_logger(__name__)


def _get_novel_or_404(session: Session, novel_id: int, user_id: str) -> Novel:
    """
    Get novel with ownership and soft delete check.

    Args:
        session: Database session
        novel_id: Novel ID to retrieve
        user_id: User ID for ownership verification

    Returns:
        Novel instance if found and authorized

    Raises:
        APIException: 403 if novel not found, not owned by user, or soft deleted
    """
    novel = session.get(Novel, novel_id)
    if not novel or novel.user_id != user_id or novel.deleted_at is not None:
        raise APIException(error_code=ErrorCode.NOT_AUTHORIZED, status_code=403)
    return novel


def _start_flow_in_background(
    file_path: str,
    novel_title: str,
    author: str | None,
    user_id: str,
    novel_id: int
):
    """
    Wrapper to run flow deployment in background task.

    This function handles the event loop setup required for running
    async flow deployment in a background thread.

    Args:
        file_path: Path to the uploaded novel file
        novel_title: Title of the novel
        author: Author name (optional)
        user_id: User ID who uploaded the novel
        novel_id: Novel ID in the database
    """
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    loop.run_until_complete(
        _start_flow_deployment(file_path, novel_title, author, user_id, novel_id)
    )


async def _start_flow_deployment(
    file_path: str,
    novel_title: str,
    author: str | None,
    user_id: str,
    novel_id: int
):
    """
    Start the novel ingestion flow via Prefect deployment.

    This async function triggers the Prefect flow for processing
    the uploaded novel. The flow runs asynchronously and does not
    block the API response.

    Args:
        file_path: Path to the uploaded novel file
        novel_title: Title of the novel
        author: Author name (optional)
        user_id: User ID who uploaded the novel
        novel_id: Novel ID in the database

    Returns:
        Flow run ID if successful, None if failed
    """
    def _mark_latest_job_failed(error_message: str) -> None:
        session = create_session()
        try:
            latest_job = session.exec(
                select(IngestionJob)
                .where(IngestionJob.novel_id == novel_id)
                .order_by(IngestionJob.created_at.desc())
            ).first()
            if not latest_job:
                return

            latest_job.status = "failed"
            latest_job.error_message = error_message
            latest_job.error_details = json.dumps(
                {"stage": "deployment_start", "message": error_message},
                ensure_ascii=False,
            )
            if hasattr(latest_job, "update_stage_progress"):
                latest_job.update_stage_progress("queue", "failed", message=error_message)
            latest_job.completed_at = utcnow()
            session.add(latest_job)
            session.commit()
        finally:
            session.close()

    def _mark_latest_job_dispatched(flow_run_id: str) -> None:
        session = create_session()
        try:
            latest_job = session.exec(
                select(IngestionJob)
                .where(IngestionJob.novel_id == novel_id)
                .order_by(IngestionJob.created_at.desc())
            ).first()
            if not latest_job:
                return

            latest_job.correlation_id = flow_run_id
            if hasattr(latest_job, "update_stage_progress"):
                latest_job.update_stage_progress(
                    "queue",
                    "processing",
                    message="调度成功，等待工作流执行",
                    flow_run_id=flow_run_id,
                )
            latest_job.updated_at = utcnow()
            session.add(latest_job)
            session.commit()
        finally:
            session.close()

    try:
        from prefect.deployments import run_deployment

        logger.info(f"Starting novel ingestion deployment for user {user_id}: {novel_title}")

        # Run deployment asynchronously (non-blocking)
        # Use timeout=None to not wait for completion
        flow_run = await run_deployment(
            name="novel_ingestion_v3/novel_ingestion_v3",
            parameters={
                "file_path": file_path,
                "user_id": user_id,
                "novel_title": novel_title,
                "author": author,
                "resume_from_checkpoint": True,
                "novel_id": novel_id,
            },
            timeout=None,  # Don't wait for completion
        )

        logger.info(f"Novel ingestion deployment started: flow_run_id={flow_run.id}")
        try:
            _mark_latest_job_dispatched(str(flow_run.id))
        except Exception as db_err:
            logger.error(f"Failed to persist flow run correlation id: {db_err}", exc_info=True)
        return flow_run.id

    except Exception as e:
        logger.error(f"Failed to start novel ingestion deployment: {e}", exc_info=True)
        try:
            _mark_latest_job_failed(f"Failed to start ingestion flow: {e}")
        except Exception as db_err:
            logger.error(f"Failed to mark ingestion job as failed: {db_err}", exc_info=True)
        # In production, don't fallback to direct execution - fail fast and allow retry.
        return None


__all__ = [
    "_get_novel_or_404",
    "_start_flow_in_background",
    "_start_flow_deployment",
]
