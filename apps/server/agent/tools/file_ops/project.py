"""
Project operations for agent tools.

This module provides operations related to project management:
- update_project_status: Update project status information for AI context
- execute_update_plan: Save tasks to Redis task board

Extracted from the monolithic file_executor.py for better maintainability.
"""

from typing import Any, cast

from sqlmodel import Session

from agent.tools.permissions import check_project_ownership
from config.datetime_utils import utcnow
from config.project_status import normalize_project_status_payload
from models import Project
from utils.logger import get_logger, log_with_context

logger = get_logger(__name__)


class ProjectOperations:
    """
    Project-related operations for AI agent tools.

    This class provides operations for managing project status and task plans,
    with permission checking and logging.
    """

    def __init__(self, session: Session, user_id: str | None = None):
        """
        Initialize project operations.

        Args:
            session: Database session
            user_id: Current user ID (UUID string, for permission checks)
        """
        self.session = session
        self.user_id = user_id

    @staticmethod
    def _normalize_task_phase(task: dict[str, Any]) -> str | None:
        """Return normalized phase identity key if available."""
        phase_id = task.get("phase_id")
        if not isinstance(phase_id, str):
            return None
        normalized_phase = phase_id.strip()
        if not normalized_phase:
            return None
        return f"phase:{normalized_phase}"

    @classmethod
    def _normalize_task_phase_identity(cls, task: dict[str, Any]) -> str | None:
        """Return normalized phase identity key with task name to avoid phase_id reuse collisions."""
        phase_key = cls._normalize_task_phase(task)
        if not phase_key:
            return None

        task_key = cls._normalize_task_name(task)
        if not task_key:
            return phase_key

        return f"{phase_key}|{task_key}"

    @staticmethod
    def _normalize_task_name(task: dict[str, Any]) -> str | None:
        """Return normalized legacy task-name identity key if available."""
        task_name = task.get("task")
        if not isinstance(task_name, str):
            return None
        normalized_task = task_name.strip()
        if not normalized_task:
            return None
        return f"task:{normalized_task}"

    @staticmethod
    def _coerce_task_name_field(task: dict[str, Any]) -> None:
        """
        Best-effort normalization for task-board payloads.

        In production we occasionally see LLM tool calls (or legacy clients)
        sending task objects that use `title` / `name` instead of `task`.
        The task board is non-critical metadata; we normalize common aliases
        into the canonical `task` field before validation to reduce noisy
        warnings and keep the board usable.
        """
        task_name = task.get("task")
        if isinstance(task_name, str) and task_name.strip():
            return

        for alias_key in ("title", "name", "text", "description"):
            alias_value = task.get(alias_key)
            if isinstance(alias_value, str) and alias_value.strip():
                task["task"] = alias_value
                return

    def _validate_update_plan_tasks(
        self,
        tasks: list[Any],
        previous_tasks: list[dict[str, Any]] | None = None,
    ) -> None:
        """
        Validate update_plan tasks for lightweight phase-state-machine rules.

        Rules:
        1) At most one in_progress task in the current batch.
        2) Block rollback from done -> in_progress compared with previous board.
        3) Keep legacy format compatible (task/status remains sufficient).
        """
        in_progress_count = 0
        valid_statuses = {"pending", "in_progress", "done"}

        for index, task in enumerate(tasks):
            if not isinstance(task, dict):
                raise ValueError(f"Invalid task at index {index}: expected object")

            task_name = task.get("task")
            if not isinstance(task_name, str) or not task_name.strip():
                raise ValueError(f"Invalid task at index {index}: 'task' is required")

            status = task.get("status")
            if status not in valid_statuses:
                raise ValueError(
                    f"Invalid task at index {index}: status must be one of {sorted(valid_statuses)}"
                )

            if status == "in_progress":
                in_progress_count += 1

        if in_progress_count > 1:
            raise ValueError("Invalid task plan: at most one in_progress task is allowed")

        historical_tasks = previous_tasks or []
        done_phase_keys: set[str] = set()
        done_legacy_task_keys: set[str] = set()
        for previous in historical_tasks:
            if not isinstance(previous, dict) or previous.get("status") != "done":
                continue

            # Prefer phase identity (phase_id + task). Only fallback to task-name
            # identity when historical entry has no phase_id (legacy payload).
            phase_key = self._normalize_task_phase_identity(previous)
            if phase_key:
                done_phase_keys.add(phase_key)
                continue

            task_key = self._normalize_task_name(previous)
            if task_key:
                done_legacy_task_keys.add(task_key)

        if not done_phase_keys and not done_legacy_task_keys:
            return

        rollback_targets: list[str] = []
        for index, task in enumerate(tasks):
            if task.get("status") != "in_progress":
                continue

            phase_key = self._normalize_task_phase_identity(task)
            task_key = self._normalize_task_name(task)

            # If current task has phase_id, match by (phase_id + task name).
            # This prevents false positives when phase_id is reused, while still
            # allowing same task names across different phases.
            is_rollback = (
                bool(phase_key and phase_key in done_phase_keys)
                or bool(not phase_key and task_key and task_key in done_legacy_task_keys)
            )

            if is_rollback:
                rollback_targets.append(
                    str(task.get("phase_id") or task.get("task") or f"index-{index}")
                )

        if rollback_targets:
            targets = ", ".join(rollback_targets)
            raise ValueError(
                f"Invalid task transition: done -> in_progress rollback is not allowed ({targets})"
            )

    def update_project_status(
        self,
        project_id: str,
        summary: str | None = None,
        current_phase: str | None = None,
        writing_style: str | None = None,
        notes: str | None = None,
    ) -> dict[str, Any]:
        """
        Update project status information for AI context awareness.

        Args:
            project_id: Project ID
            summary: Project summary/background
            current_phase: Current writing phase description
            writing_style: Writing style guidelines
            notes: Additional notes for AI assistant

        Returns:
            Updated project status fields

        Raises:
            PermissionError: If user doesn't have permission
            ValueError: If project not found
        """
        # Check project permission
        check_project_ownership(self.session, project_id, self.user_id)

        # Get project
        project = self.session.get(Project, project_id)
        if not project:
            raise ValueError(f"Project not found: {project_id}")

        # Track what was updated
        updated_fields = []

        # Normalize and validate status fields.
        # Empty string is preserved so callers can explicitly clear a field.
        raw_updates = {
            "summary": summary,
            "current_phase": current_phase,
            "writing_style": writing_style,
            "notes": notes,
        }
        normalized_updates = normalize_project_status_payload(raw_updates)

        for field_name, raw_value in raw_updates.items():
            if raw_value is not None:
                setattr(project, field_name, normalized_updates.get(field_name, ""))
                updated_fields.append(field_name)

        # Update timestamp
        project.updated_at = utcnow()

        self.session.commit()
        self.session.refresh(project)

        return {
            "project_id": project.id,
            "updated_fields": updated_fields,
            "current_status": {
                "summary": project.summary,
                "current_phase": project.current_phase,
                "writing_style": project.writing_style,
                "notes": project.notes,
            },
        }

    def execute_update_plan(
        self,
        session_id: str,
        tasks: list[dict[str, Any]],
        user_id: str | None = None,
        project_id: str | None = None,
    ) -> dict[str, Any]:
        """
        Execute update_plan tool - save tasks to Redis task board.

        Args:
            session_id: Session identifier for task board
            tasks: List of task dictionaries with 'task' and 'status' fields
            user_id: Current user ID for runtime isolation
            project_id: Current project ID for runtime isolation

        Returns:
            Success message with task list summary
        """
        task_count = len(tasks) if isinstance(tasks, list) else 0
        log_with_context(
            logger,
            20,  # INFO
            "execute_update_plan started",
            session_id=session_id,
            task_count=task_count,
        )

        try:
            from services.infra.task_board_service import task_board_service

            if not isinstance(tasks, list):
                log_with_context(
                    logger,
                    30,  # WARNING
                    "execute_update_plan invalid tasks payload",
                    session_id=session_id,
                    user_id=user_id,
                    project_id=project_id,
                    tasks_type=type(tasks).__name__,
                )
                return {
                    "status": "ignored",
                    "message": "任务计划板未更新（tasks 参数类型错误）",
                    "reason": "invalid_tasks_payload",
                    "error": f"tasks must be an array, got {type(tasks).__name__}",
                    "task_summary": {
                        "total": 0,
                        "pending": 0,
                        "in_progress": 0,
                        "done": 0,
                    },
                    "tasks": [],
                }

            # Normalize common alias fields (e.g. title/name -> task) before validation.
            normalized_tasks: list[Any] = []
            for task in tasks:
                if not isinstance(task, dict):
                    normalized_tasks.append(task)
                    continue

                normalized_task = dict(task)
                self._coerce_task_name_field(normalized_task)
                normalized_tasks.append(normalized_task)

            tasks_payload = normalized_tasks

            # Lightweight phase-state-machine validation (backward compatible).
            previous_tasks = task_board_service.get_tasks(
                session_id,
                user_id=user_id,
                project_id=project_id,
            ) or []

            try:
                self._validate_update_plan_tasks(tasks=tasks_payload, previous_tasks=previous_tasks)
            except ValueError as validation_error:
                # Task board is best-effort metadata. Validation failures should not
                # crash the writing workflow; keep the previous board unchanged.
                pending = sum(
                    1
                    for t in tasks_payload
                    if isinstance(t, dict) and t.get("status") == "pending"
                )
                in_progress = sum(
                    1
                    for t in tasks_payload
                    if isinstance(t, dict) and t.get("status") == "in_progress"
                )
                done = sum(
                    1 for t in tasks_payload if isinstance(t, dict) and t.get("status") == "done"
                )

                log_with_context(
                    logger,
                    30,  # WARNING
                    "execute_update_plan validation rejected",
                    session_id=session_id,
                    user_id=user_id,
                    project_id=project_id,
                    error=str(validation_error),
                    error_type=type(validation_error).__name__,
                )

                return {
                    "status": "ignored",
                    "message": "任务计划板未更新（校验未通过）",
                    "reason": "validation_rejected",
                    "error": str(validation_error),
                    "task_summary": {
                        "total": len(tasks_payload),
                        "pending": pending,
                        "in_progress": in_progress,
                        "done": done,
                    },
                    "tasks": tasks_payload,
                }

            # Now safe to treat payload as list[dict], because validation succeeded.
            validated_tasks = cast(list[dict[str, Any]], tasks_payload)

            # Save tasks to Redis
            success = task_board_service.save_tasks(
                session_id,
                validated_tasks,
                user_id=user_id,
                project_id=project_id,
            )

            if not success:
                raise ValueError("Failed to save tasks to Redis")

            # Build task summary
            pending = sum(1 for t in validated_tasks if t.get("status") == "pending")
            in_progress = sum(1 for t in validated_tasks if t.get("status") == "in_progress")
            done = sum(1 for t in validated_tasks if t.get("status") == "done")

            log_with_context(
                logger,
                20,  # INFO
                "execute_update_plan completed",
                session_id=session_id,
                pending=pending,
                in_progress=in_progress,
                done=done,
            )

            return {
                "status": "success",
                "message": "任务计划板已更新",
                "task_summary": {
                    "total": len(validated_tasks),
                    "pending": pending,
                    "in_progress": in_progress,
                    "done": done,
                },
                "tasks": validated_tasks,
            }

        except Exception as e:
            log_with_context(
                logger,
                40,  # ERROR
                "Error executing update_plan",
                session_id=session_id,
                error=str(e),
                error_type=type(e).__name__,
            )
            tasks_list: list[Any] = tasks if isinstance(tasks, list) else []
            pending = sum(
                1 for t in tasks_list if isinstance(t, dict) and t.get("status") == "pending"
            )
            in_progress = sum(
                1 for t in tasks_list if isinstance(t, dict) and t.get("status") == "in_progress"
            )
            done = sum(1 for t in tasks_list if isinstance(t, dict) and t.get("status") == "done")

            # Task plan is best-effort metadata. Never raise: keep the writing workflow running.
            return {
                "status": "error",
                "message": "任务计划板更新失败（已忽略，不影响写作流程）",
                "reason": "internal_error",
                "error": str(e),
                "task_summary": {
                    "total": task_count,
                    "pending": pending,
                    "in_progress": in_progress,
                    "done": done,
                },
                "tasks": tasks_list,
            }


__all__ = [
    "ProjectOperations",
]
