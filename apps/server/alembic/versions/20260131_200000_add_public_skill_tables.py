"""Add public_skill and user_added_skill tables for skill discovery system

Revision ID: 20260131_200000_add_public_skill_tables
Revises: 20260131_100000_add_skill_usage_table
Create Date: 2026-01-31 20:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '20260131_200000_add_public_skill_tables'
down_revision: str | None = '20260131_100000_add_skill_usage_table'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create public_skill and user_added_skill tables."""
    # Create public_skill table
    op.create_table(
        'public_skill',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('description', sa.String(length=500), nullable=True),
        sa.Column('instructions', sa.Text(), nullable=False),
        sa.Column('category', sa.String(length=50), nullable=False, default='writing'),
        sa.Column('tags', sa.Text(), nullable=False, default='[]'),
        sa.Column('source', sa.String(length=20), nullable=False, default='official'),
        sa.Column('author_id', sa.String(), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False, default='approved'),
        sa.Column('reviewed_by', sa.String(), nullable=True),
        sa.Column('reviewed_at', sa.DateTime(), nullable=True),
        sa.Column('rejection_reason', sa.String(length=500), nullable=True),
        sa.Column('add_count', sa.Integer(), nullable=False, default=0),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['author_id'], ['user.id']),
        sa.ForeignKeyConstraint(['reviewed_by'], ['user.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_public_skill_category', 'public_skill', ['category'])
    op.create_index('ix_public_skill_source', 'public_skill', ['source'])
    op.create_index('ix_public_skill_status', 'public_skill', ['status'])
    op.create_index('ix_public_skill_author_id', 'public_skill', ['author_id'])

    # Create user_added_skill table
    op.create_table(
        'user_added_skill',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('user_id', sa.String(), nullable=False),
        sa.Column('public_skill_id', sa.String(), nullable=False),
        sa.Column('custom_name', sa.String(length=100), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, default=True),
        sa.Column('added_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['user.id']),
        sa.ForeignKeyConstraint(['public_skill_id'], ['public_skill.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_user_added_skill_user_id', 'user_added_skill', ['user_id'])
    op.create_index('ix_user_added_skill_public_skill_id', 'user_added_skill', ['public_skill_id'])

    # Add sharing columns to user_skill table
    op.add_column('user_skill', sa.Column('is_shared', sa.Boolean(), nullable=False, server_default='0'))
    op.add_column('user_skill', sa.Column('shared_skill_id', sa.String(), nullable=True))
    op.create_foreign_key(
        'fk_user_skill_shared_skill_id',
        'user_skill', 'public_skill',
        ['shared_skill_id'], ['id']
    )


def downgrade() -> None:
    """Drop public_skill and user_added_skill tables."""
    # Remove sharing columns from user_skill
    op.drop_constraint('fk_user_skill_shared_skill_id', 'user_skill', type_='foreignkey')
    op.drop_column('user_skill', 'shared_skill_id')
    op.drop_column('user_skill', 'is_shared')

    # Drop user_added_skill table
    op.drop_index('ix_user_added_skill_public_skill_id', table_name='user_added_skill')
    op.drop_index('ix_user_added_skill_user_id', table_name='user_added_skill')
    op.drop_table('user_added_skill')

    # Drop public_skill table
    op.drop_index('ix_public_skill_author_id', table_name='public_skill')
    op.drop_index('ix_public_skill_status', table_name='public_skill')
    op.drop_index('ix_public_skill_source', table_name='public_skill')
    op.drop_index('ix_public_skill_category', table_name='public_skill')
    op.drop_table('public_skill')
