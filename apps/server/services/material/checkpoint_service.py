"""
Checkpoint service - SQLModel version.
Handles ProcessCheckpoint tracking for ingestion stages.
"""
from __future__ import annotations

import json
from typing import Any

from sqlmodel import Session, select

from models.material_models import ProcessCheckpoint


class CheckpointService:
    """Process checkpoint service using SQLModel patterns."""

    def get(
        self, session: Session, novel_id: int, stage: str
    ) -> ProcessCheckpoint | None:
        """Get the latest checkpoint for a specific stage."""
        statement = (
            select(ProcessCheckpoint)
            .where(
                ProcessCheckpoint.novel_id == novel_id,
                ProcessCheckpoint.stage == stage,
            )
            .order_by(ProcessCheckpoint.created_at.desc())
        )
        return session.exec(statement).first()

    def get_latest(
        self, session: Session, novel_id: int
    ) -> ProcessCheckpoint | None:
        """Get the latest checkpoint for a novel (any stage)."""
        statement = (
            select(ProcessCheckpoint)
            .where(ProcessCheckpoint.novel_id == novel_id)
            .order_by(ProcessCheckpoint.created_at.desc())
        )
        return session.exec(statement).first()

    def upsert(
        self,
        session: Session,
        novel_id: int,
        stage: str,
        data: dict[str, Any] | None,
        *,
        status: str | None = None,
        job_id: int | None = None,
        error: str | None = None,
    ) -> ProcessCheckpoint:
        """Upsert a checkpoint. Creates new or updates existing."""
        statement = (
            select(ProcessCheckpoint)
            .where(
                ProcessCheckpoint.novel_id == novel_id,
                ProcessCheckpoint.stage == stage,
            )
            .order_by(ProcessCheckpoint.created_at.desc())
        )
        cp = session.exec(statement).first()

        if cp is None:
            # Create new checkpoint
            checkpoint_data_str = json.dumps(data) if data else "{}"
            cp = ProcessCheckpoint(
                novel_id=novel_id,
                job_id=job_id,
                stage=stage,
                stage_status=status or "processing",
                checkpoint_data=checkpoint_data_str,
            )
            session.add(cp)
            session.flush()
            return cp

        # Update existing checkpoint
        if status:
            cp.stage_status = status
        if data:
            # Parse existing data, update, and serialize back
            existing_data = {}
            if cp.checkpoint_data:
                try:
                    existing_data = json.loads(cp.checkpoint_data) if isinstance(cp.checkpoint_data, str) else cp.checkpoint_data
                except (json.JSONDecodeError, TypeError):
                    existing_data = {}
            existing_data.update(data)
            cp.checkpoint_data = json.dumps(existing_data)
        if error:
            cp.mark_failed(error)

        session.add(cp)
        session.flush()
        return cp

    def delete_all(self, session: Session, novel_id: int) -> None:
        """Delete all checkpoints for a novel."""
        statement = select(ProcessCheckpoint).where(
            ProcessCheckpoint.novel_id == novel_id
        )
        checkpoints = session.exec(statement).all()
        for cp in checkpoints:
            session.delete(cp)
        session.flush()
