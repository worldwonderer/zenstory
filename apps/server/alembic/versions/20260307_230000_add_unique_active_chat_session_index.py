"""Enforce one active chat session per user+project.

Revision ID: 20260307_230000_add_unique_active_chat_session_index
Revises: 20260306_001000_add_user_feedback_table, 20260306_120000_add_compaction_checkpoint_index
Create Date: 2026-03-07 23:00:00.000000
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260307_230000_add_unique_active_chat_session_index"
down_revision: str | Sequence[str] | None = (
    "20260306_001000_add_user_feedback_table",
    "20260306_120000_add_compaction_checkpoint_index",
)
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _deactivate_stale_active_sessions() -> None:
    """Keep only latest active session for each (user_id, project_id)."""
    op.execute(
        """
        WITH ranked_sessions AS (
            SELECT
                id,
                ROW_NUMBER() OVER (
                    PARTITION BY user_id, project_id
                    ORDER BY updated_at DESC, created_at DESC, id DESC
                ) AS rn
            FROM chat_session
            WHERE is_active = true
        )
        UPDATE chat_session
        SET is_active = false
        WHERE id IN (
            SELECT id
            FROM ranked_sessions
            WHERE rn > 1
        )
        """
    )


def upgrade() -> None:
    """Backfill stale states and add unique partial index for active sessions."""
    bind = op.get_bind()
    dialect = bind.dialect.name

    _deactivate_stale_active_sessions()

    if dialect == "postgresql":
        op.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS uq_chat_session_user_project_active
            ON chat_session (user_id, project_id)
            WHERE is_active = true
            """
        )
    elif dialect == "sqlite":
        op.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS uq_chat_session_user_project_active
            ON chat_session (user_id, project_id)
            WHERE is_active = 1
            """
        )


def downgrade() -> None:
    """Drop unique partial index."""
    op.execute("DROP INDEX IF EXISTS uq_chat_session_user_project_active")
