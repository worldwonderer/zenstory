"""Add writing stats and streak tables

Revision ID: 20260215_000000_add_writing_stats_tables
Revises: 20260214_110000_add_agent_api_key_table
Create Date: 2026-02-15

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '20260215_000000_add_writing_stats_tables'
down_revision: str | Sequence[str] | None = '20260214_110000_add_agent_api_key_table'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create writing_stats and writing_streak tables for project dashboard."""

    # 1. Create writing_stats table for daily word count tracking
    op.create_table(
        'writing_stats',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('user_id', sa.String(), nullable=False),
        sa.Column('project_id', sa.String(), nullable=False),
        sa.Column('stats_date', sa.Date(), nullable=False),
        sa.Column('word_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('words_added', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('words_deleted', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('edit_sessions', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('total_edit_time_seconds', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['user.id'], ),
        sa.ForeignKeyConstraint(['project_id'], ['project.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_writing_stats_user_id'), 'writing_stats', ['user_id'], unique=False)
    op.create_index(op.f('ix_writing_stats_project_id'), 'writing_stats', ['project_id'], unique=False)
    op.create_index(op.f('ix_writing_stats_stats_date'), 'writing_stats', ['stats_date'], unique=False)
    # Unique constraint for one stats record per user/project per day
    op.create_index(
        op.f('ix_writing_stats_user_project_date'),
        'writing_stats',
        ['user_id', 'project_id', 'stats_date'],
        unique=True
    )

    # 2. Create writing_streak table for project-specific streak tracking
    op.create_table(
        'writing_streak',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('user_id', sa.String(), nullable=False),
        sa.Column('project_id', sa.String(), nullable=False),
        sa.Column('current_streak', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('longest_streak', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('last_writing_date', sa.Date(), nullable=True),
        sa.Column('streak_start_date', sa.Date(), nullable=True),
        sa.Column('streak_recovery_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['user.id'], ),
        sa.ForeignKeyConstraint(['project_id'], ['project.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_writing_streak_user_id'), 'writing_streak', ['user_id'], unique=False)
    op.create_index(op.f('ix_writing_streak_project_id'), 'writing_streak', ['project_id'], unique=False)
    op.create_index(op.f('ix_writing_streak_last_writing_date'), 'writing_streak', ['last_writing_date'], unique=False)
    # Unique constraint for one streak record per user/project
    op.create_index(
        op.f('ix_writing_streak_user_project'),
        'writing_streak',
        ['user_id', 'project_id'],
        unique=True
    )


def downgrade() -> None:
    """Drop writing_stats and writing_streak tables."""

    # 2. Drop writing_streak table
    op.drop_index(op.f('ix_writing_streak_user_project'), table_name='writing_streak')
    op.drop_index(op.f('ix_writing_streak_last_writing_date'), table_name='writing_streak')
    op.drop_index(op.f('ix_writing_streak_project_id'), table_name='writing_streak')
    op.drop_index(op.f('ix_writing_streak_user_id'), table_name='writing_streak')
    op.drop_table('writing_streak')

    # 1. Drop writing_stats table
    op.drop_index(op.f('ix_writing_stats_user_project_date'), table_name='writing_stats')
    op.drop_index(op.f('ix_writing_stats_stats_date'), table_name='writing_stats')
    op.drop_index(op.f('ix_writing_stats_project_id'), table_name='writing_stats')
    op.drop_index(op.f('ix_writing_stats_user_id'), table_name='writing_stats')
    op.drop_table('writing_stats')
