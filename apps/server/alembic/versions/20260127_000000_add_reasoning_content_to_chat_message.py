"""Add reasoning_content field to chat_message table

Revision ID: 20260127_000000_add_reasoning_content_to_chat_message
Revises: c4b0247ec5dd
Create Date: 2026-01-27 00:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '20260127_000000_add_reasoning_content_to_chat_message'
down_revision: str | None = 'c4b0247ec5dd'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add reasoning_content column to chat_message table."""
    op.add_column(
        'chat_message',
        sa.Column('reasoning_content', sa.Text(), nullable=True)
    )


def downgrade() -> None:
    """Remove reasoning_content column from chat_message table."""
    op.drop_column('chat_message', 'reasoning_content')
