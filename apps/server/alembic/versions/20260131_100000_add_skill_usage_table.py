"""Add skill_usage table for tracking skill usage statistics

Revision ID: 20260131_100000_add_skill_usage_table
Revises: 20260131_000000_add_user_skill_table
Create Date: 2026-01-31 10:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '20260131_100000_add_skill_usage_table'
down_revision: str | None = '20260131_000000_add_user_skill_table'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create skill_usage table."""
    op.create_table(
        'skill_usage',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('user_id', sa.String(), nullable=True),
        sa.Column('project_id', sa.String(), nullable=False),
        sa.Column('skill_id', sa.String(), nullable=False),
        sa.Column('skill_name', sa.String(length=100), nullable=False),
        sa.Column('skill_source', sa.String(length=20), nullable=False),
        sa.Column('matched_trigger', sa.String(length=200), nullable=False),
        sa.Column('confidence', sa.Float(), nullable=False, default=1.0),
        sa.Column('user_message', sa.String(length=500), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['user.id']),
        sa.ForeignKeyConstraint(['project_id'], ['project.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_skill_usage_user_id', 'skill_usage', ['user_id'])
    op.create_index('ix_skill_usage_project_id', 'skill_usage', ['project_id'])
    op.create_index('ix_skill_usage_skill_id', 'skill_usage', ['skill_id'])
    op.create_index('ix_skill_usage_created_at', 'skill_usage', ['created_at'])


def downgrade() -> None:
    """Drop skill_usage table."""
    op.drop_index('ix_skill_usage_created_at', table_name='skill_usage')
    op.drop_index('ix_skill_usage_skill_id', table_name='skill_usage')
    op.drop_index('ix_skill_usage_project_id', table_name='skill_usage')
    op.drop_index('ix_skill_usage_user_id', table_name='skill_usage')
    op.drop_table('skill_usage')
