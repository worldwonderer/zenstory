"""add_agent_api_key_table

Revision ID: 20260214_110000_add_agent_api_key_table
Revises: merge_heads_20260214
Create Date: 2026-02-14

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '20260214_110000_add_agent_api_key_table'
down_revision: str | Sequence[str] | None = 'merge_heads_20260214'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create agent_api_key table."""
    op.create_table(
        'agent_api_key',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('user_id', sa.String(), nullable=False),
        sa.Column('key_prefix', sa.String(length=8), nullable=False),
        sa.Column('key_hash', sa.String(), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('description', sa.String(length=500), nullable=True),
        sa.Column('scopes', sa.JSON(), nullable=False),
        sa.Column('project_ids', sa.JSON(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='1'),
        sa.Column('last_used_at', sa.DateTime(), nullable=True),
        sa.Column('expires_at', sa.DateTime(), nullable=True),
        sa.Column('request_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['user.id'], ),
        sa.PrimaryKeyConstraint('id')
    )

    # Create indexes for frequently queried columns
    op.create_index(op.f('ix_agent_api_key_user_id'), 'agent_api_key', ['user_id'], unique=False)
    op.create_index(op.f('ix_agent_api_key_key_hash'), 'agent_api_key', ['key_hash'], unique=True)
    op.create_index(op.f('ix_agent_api_key_is_active'), 'agent_api_key', ['is_active'], unique=False)


def downgrade() -> None:
    """Drop agent_api_key table."""
    op.drop_index(op.f('ix_agent_api_key_is_active'), table_name='agent_api_key')
    op.drop_index(op.f('ix_agent_api_key_key_hash'), table_name='agent_api_key')
    op.drop_index(op.f('ix_agent_api_key_user_id'), table_name='agent_api_key')
    op.drop_table('agent_api_key')
