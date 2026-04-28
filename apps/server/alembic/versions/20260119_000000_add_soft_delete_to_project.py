"""Add soft delete fields to project table

Revision ID: add_soft_delete_to_project
Revises:
Create Date: 2026-01-19 00:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'add_soft_delete_to_project'
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add soft delete columns to project table."""
    # Add is_deleted column
    op.add_column(
        'project',
        sa.Column('is_deleted', sa.Boolean(), nullable=False, server_default='false')
    )

    # Add deleted_at column
    op.add_column(
        'project',
        sa.Column('deleted_at', sa.TIMESTAMP(), nullable=True)
    )

    # Create index on is_deleted
    op.create_index(
        'ix_project_is_deleted',
        'project',
        ['is_deleted']
    )


def downgrade() -> None:
    """Remove soft delete columns from project table."""
    # Drop index
    op.drop_index('ix_project_is_deleted', table_name='project')

    # Drop deleted_at column
    op.drop_column('project', 'deleted_at')

    # Drop is_deleted column
    op.drop_column('project', 'is_deleted')
