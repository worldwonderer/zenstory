"""Add email_verified field to user table

Revision ID: add_email_verified_to_user
Revises: add_soft_delete_to_project
Create Date: 2026-01-21 00:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'add_email_verified_to_user'
down_revision: str | None = 'add_soft_delete_to_project'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add email_verified column to user table."""
    # Add email_verified column with default value True
    op.add_column(
        'user',
        sa.Column('email_verified', sa.Boolean(), nullable=False, server_default='true')
    )


def downgrade() -> None:
    """Remove email_verified column from user table."""
    # Drop email_verified column
    op.drop_column('user', 'email_verified')
