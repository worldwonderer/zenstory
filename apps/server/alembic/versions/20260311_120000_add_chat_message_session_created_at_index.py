"""Add composite index for chat_message history queries.

Revision ID: 20260311_120000_add_chat_message_session_created_at_index
Revises: 20260308_120000_add_upgrade_funnel_event_table
Create Date: 2026-03-11 12:00:00.000000
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260311_120000_add_chat_message_session_created_at_index"
down_revision: str | Sequence[str] | None = "20260308_120000_add_upgrade_funnel_event_table"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Speed up newest-first chat history window queries."""
    op.create_index(
        "ix_chat_message_session_created_at_id",
        "chat_message",
        ["session_id", "created_at", "id"],
    )


def downgrade() -> None:
    """Drop composite index."""
    op.drop_index(
        "ix_chat_message_session_created_at_id",
        table_name="chat_message",
    )

