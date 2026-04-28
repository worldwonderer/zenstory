"""Add agent artifact ledger table for handoff traceability.

Revision ID: 20260301_160000_add_agent_artifact_ledger
Revises: 20260220_230000_update_free_plan_display_name
Create Date: 2026-03-01 16:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260301_160000_add_agent_artifact_ledger"
down_revision: str | Sequence[str] | None = "20260220_230000_update_free_plan_display_name"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create agent_artifact_ledger table and indexes."""
    op.create_table(
        "agent_artifact_ledger",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("project_id", sa.String(), nullable=False),
        sa.Column("session_id", sa.String(), nullable=True),
        sa.Column("user_id", sa.String(), nullable=True),
        sa.Column("action", sa.String(), nullable=False),
        sa.Column("tool_name", sa.String(), nullable=False),
        sa.Column("artifact_ref", sa.String(), nullable=False),
        sa.Column("payload", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["project.id"]),
        sa.ForeignKeyConstraint(["session_id"], ["chat_session.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index(
        "ix_agent_artifact_ledger_project_id",
        "agent_artifact_ledger",
        ["project_id"],
    )
    op.create_index(
        "ix_agent_artifact_ledger_session_id",
        "agent_artifact_ledger",
        ["session_id"],
    )
    op.create_index(
        "ix_agent_artifact_ledger_user_id",
        "agent_artifact_ledger",
        ["user_id"],
    )
    op.create_index(
        "ix_agent_artifact_ledger_action",
        "agent_artifact_ledger",
        ["action"],
    )
    op.create_index(
        "ix_agent_artifact_ledger_tool_name",
        "agent_artifact_ledger",
        ["tool_name"],
    )
    op.create_index(
        "ix_agent_artifact_ledger_artifact_ref",
        "agent_artifact_ledger",
        ["artifact_ref"],
    )
    op.create_index(
        "ix_agent_artifact_ledger_created_at",
        "agent_artifact_ledger",
        ["created_at"],
    )


def downgrade() -> None:
    """Drop agent_artifact_ledger table and indexes."""
    op.drop_index("ix_agent_artifact_ledger_created_at", table_name="agent_artifact_ledger")
    op.drop_index("ix_agent_artifact_ledger_artifact_ref", table_name="agent_artifact_ledger")
    op.drop_index("ix_agent_artifact_ledger_tool_name", table_name="agent_artifact_ledger")
    op.drop_index("ix_agent_artifact_ledger_action", table_name="agent_artifact_ledger")
    op.drop_index("ix_agent_artifact_ledger_user_id", table_name="agent_artifact_ledger")
    op.drop_index("ix_agent_artifact_ledger_session_id", table_name="agent_artifact_ledger")
    op.drop_index("ix_agent_artifact_ledger_project_id", table_name="agent_artifact_ledger")
    op.drop_table("agent_artifact_ledger")
