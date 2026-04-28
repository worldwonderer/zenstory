"""Add debug correlation fields to user_feedback.

Revision ID: 20260312_120000_add_feedback_debug_fields
Revises: 20260311_120000_add_chat_message_session_created_at_index
Create Date: 2026-03-12 12:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260312_120000_add_feedback_debug_fields"
down_revision: str | Sequence[str] | None = "20260311_120000_add_chat_message_session_created_at_index"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "user_feedback",
        sa.Column("trace_id", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "user_feedback",
        sa.Column("request_id", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "user_feedback",
        sa.Column("agent_run_id", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "user_feedback",
        sa.Column("project_id", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "user_feedback",
        sa.Column("agent_session_id", sa.String(length=128), nullable=True),
    )

    op.create_index("ix_user_feedback_trace_id", "user_feedback", ["trace_id"])
    op.create_index("ix_user_feedback_request_id", "user_feedback", ["request_id"])
    op.create_index("ix_user_feedback_agent_run_id", "user_feedback", ["agent_run_id"])
    op.create_index("ix_user_feedback_project_id", "user_feedback", ["project_id"])


def downgrade() -> None:
    op.drop_index("ix_user_feedback_project_id", table_name="user_feedback")
    op.drop_index("ix_user_feedback_agent_run_id", table_name="user_feedback")
    op.drop_index("ix_user_feedback_request_id", table_name="user_feedback")
    op.drop_index("ix_user_feedback_trace_id", table_name="user_feedback")

    op.drop_column("user_feedback", "agent_session_id")
    op.drop_column("user_feedback", "project_id")
    op.drop_column("user_feedback", "agent_run_id")
    op.drop_column("user_feedback", "request_id")
    op.drop_column("user_feedback", "trace_id")

