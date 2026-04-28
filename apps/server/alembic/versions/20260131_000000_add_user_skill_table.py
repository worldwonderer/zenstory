"""Add user_skill table for user-defined skills

Revision ID: 20260131_000000_add_user_skill_table
Revises: 20260127_000000_add_reasoning_content_to_chat_message
Create Date: 2026-01-31 00:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '20260131_000000_add_user_skill_table'
down_revision: str | None = '20260127_000000_add_reasoning_content_to_chat_message'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create user_skill table."""
    op.create_table(
        'user_skill',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('user_id', sa.String(), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('description', sa.String(length=500), nullable=True),
        sa.Column('triggers', sa.Text(), nullable=False),
        sa.Column('instructions', sa.Text(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, default=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['user.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(
        op.f('ix_user_skill_user_id'),
        'user_skill',
        ['user_id'],
        unique=False
    )


def downgrade() -> None:
    """Drop user_skill table."""
    op.drop_index(op.f('ix_user_skill_user_id'), table_name='user_skill')
    op.drop_table('user_skill')
