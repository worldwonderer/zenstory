"""Add upgrade funnel event table for monetization analytics.

Revision ID: 20260308_120000_add_upgrade_funnel_event_table
Revises: 20260307_230000_add_unique_active_chat_session_index
Create Date: 2026-03-08 12:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260308_120000_add_upgrade_funnel_event_table"
down_revision: str | Sequence[str] | None = "20260307_230000_add_unique_active_chat_session_index"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create upgrade_funnel_event table and supporting indexes."""
    op.create_table(
        "upgrade_funnel_event",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("event_name", sa.String(length=64), nullable=False),
        sa.Column("action", sa.String(length=24), nullable=False),
        sa.Column("source", sa.String(length=128), nullable=False),
        sa.Column("surface", sa.String(length=24), nullable=False),
        sa.Column("cta", sa.String(length=24), nullable=True),
        sa.Column("destination", sa.String(length=128), nullable=True),
        sa.Column("event_metadata", sa.JSON(), nullable=True),
        sa.Column("occurred_at", sa.DateTime(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index("ix_upgrade_funnel_event_user_id", "upgrade_funnel_event", ["user_id"])
    op.create_index("ix_upgrade_funnel_event_event_name", "upgrade_funnel_event", ["event_name"])
    op.create_index("ix_upgrade_funnel_event_action", "upgrade_funnel_event", ["action"])
    op.create_index("ix_upgrade_funnel_event_source", "upgrade_funnel_event", ["source"])
    op.create_index("ix_upgrade_funnel_event_occurred_at", "upgrade_funnel_event", ["occurred_at"])
    op.create_index("ix_upgrade_funnel_event_created_at", "upgrade_funnel_event", ["created_at"])
    op.create_index(
        "ix_upgrade_funnel_event_source_action_occurred",
        "upgrade_funnel_event",
        ["source", "action", "occurred_at"],
    )


def downgrade() -> None:
    """Drop upgrade_funnel_event table and indexes."""
    op.drop_index("ix_upgrade_funnel_event_source_action_occurred", table_name="upgrade_funnel_event")
    op.drop_index("ix_upgrade_funnel_event_created_at", table_name="upgrade_funnel_event")
    op.drop_index("ix_upgrade_funnel_event_occurred_at", table_name="upgrade_funnel_event")
    op.drop_index("ix_upgrade_funnel_event_source", table_name="upgrade_funnel_event")
    op.drop_index("ix_upgrade_funnel_event_action", table_name="upgrade_funnel_event")
    op.drop_index("ix_upgrade_funnel_event_event_name", table_name="upgrade_funnel_event")
    op.drop_index("ix_upgrade_funnel_event_user_id", table_name="upgrade_funnel_event")
    op.drop_table("upgrade_funnel_event")
