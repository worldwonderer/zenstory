"""Add deleted_at soft delete field to novels table

Revision ID: add_deleted_at_to_novels
Revises:
Create Date: 2026-02-04

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'add_deleted_at_to_novels'
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add deleted_at column to novels table for soft delete."""
    op.add_column(
        'novels',
        sa.Column('deleted_at', sa.TIMESTAMP(), nullable=True)
    )

    # Create index on deleted_at for efficient filtering
    op.create_index(
        'ix_novels_deleted_at',
        'novels',
        ['deleted_at']
    )


def downgrade() -> None:
    """Remove deleted_at column from novels table."""
    op.drop_index('ix_novels_deleted_at', table_name='novels')
    op.drop_column('novels', 'deleted_at')
