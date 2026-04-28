"""Add soft delete fields to file table

Revision ID: add_soft_delete_to_file
Revises: add_email_verified_to_user
Create Date: 2026-01-21 05:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'add_soft_delete_to_file'
down_revision: str | None = 'add_email_verified_to_user'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add soft delete columns to file table."""
    # Add soft delete columns to file table
    op.add_column(
        'file',
        sa.Column('is_deleted', sa.Boolean(), nullable=False, server_default='false')
    )
    op.add_column(
        'file',
        sa.Column('deleted_at', sa.TIMESTAMP(timezone=True), nullable=True)
    )
    op.create_index(
        'ix_file_is_deleted',
        'file',
        ['is_deleted']
    )


def downgrade() -> None:
    """Remove soft delete columns from file table."""
    # Remove from file table
    op.drop_index('ix_file_is_deleted', table_name='file')
    op.drop_column('file', 'deleted_at')
    op.drop_column('file', 'is_deleted')
