"""Add user feedback table for in-app issue reports.

Revision ID: 20260306_001000_add_user_feedback_table
Revises: 20260301_160000_add_agent_artifact_ledger
Create Date: 2026-03-06 00:10:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260306_001000_add_user_feedback_table"
down_revision: str | Sequence[str] | None = "20260301_160000_add_agent_artifact_ledger"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create user_feedback table and indexes."""
    op.create_table(
        "user_feedback",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("source_page", sa.String(length=32), nullable=False),
        sa.Column("source_route", sa.String(length=255), nullable=True),
        sa.Column("issue_text", sa.Text(), nullable=False),
        sa.Column("screenshot_path", sa.String(length=512), nullable=True),
        sa.Column("screenshot_original_name", sa.String(length=255), nullable=True),
        sa.Column("screenshot_content_type", sa.String(length=100), nullable=True),
        sa.Column("screenshot_size_bytes", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="open"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index("ix_user_feedback_user_id", "user_feedback", ["user_id"])
    op.create_index("ix_user_feedback_source_page", "user_feedback", ["source_page"])
    op.create_index("ix_user_feedback_status", "user_feedback", ["status"])
    op.create_index("ix_user_feedback_created_at", "user_feedback", ["created_at"])


def downgrade() -> None:
    """Drop user_feedback table and indexes."""
    op.drop_index("ix_user_feedback_created_at", table_name="user_feedback")
    op.drop_index("ix_user_feedback_status", table_name="user_feedback")
    op.drop_index("ix_user_feedback_source_page", table_name="user_feedback")
    op.drop_index("ix_user_feedback_user_id", table_name="user_feedback")
    op.drop_table("user_feedback")

