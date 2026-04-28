"""Add composite index for artifact-ledger compaction checkpoint queries.

Revision ID: 20260306_120000_add_compaction_checkpoint_index
Revises: 20260301_160000_add_agent_artifact_ledger
Create Date: 2026-03-06 12:00:00.000000
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260306_120000_add_compaction_checkpoint_index"
down_revision: str | Sequence[str] | None = "20260301_160000_add_agent_artifact_ledger"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create composite index to speed up session-scoped ledger lookups."""
    op.create_index(
        "ix_agent_artifact_ledger_project_session_action_created_at",
        "agent_artifact_ledger",
        ["project_id", "session_id", "action", "created_at"],
    )


def downgrade() -> None:
    """Drop composite index."""
    op.drop_index(
        "ix_agent_artifact_ledger_project_session_action_created_at",
        table_name="agent_artifact_ledger",
    )

