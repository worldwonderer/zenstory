"""Add referral system tables

Revision ID: 20260214_000000_add_referral_system_tables
Revises: 9e44de31e71a
Create Date: 2026-02-14

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '20260214_000000_add_referral_system_tables'
down_revision: str | None = '9e44de31e71a'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create referral system tables: invite_code, referral, user_reward, user_stats."""

    # Create invite_code table
    op.create_table(
        'invite_code',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('code', sa.String(), nullable=False),
        sa.Column('owner_id', sa.String(), nullable=False),
        sa.Column('max_uses', sa.Integer(), nullable=False, server_default='3'),
        sa.Column('current_uses', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='1'),
        sa.Column('expires_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['owner_id'], ['user.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_invite_code_code'), 'invite_code', ['code'], unique=True)
    op.create_index(op.f('ix_invite_code_owner_id'), 'invite_code', ['owner_id'], unique=False)
    op.create_index(op.f('ix_invite_code_is_active'), 'invite_code', ['is_active'], unique=False)

    # Create referral table
    op.create_table(
        'referral',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('inviter_id', sa.String(), nullable=False),
        sa.Column('invitee_id', sa.String(), nullable=False),
        sa.Column('invite_code_id', sa.String(), nullable=False),
        sa.Column('status', sa.String(), nullable=False, server_default='PENDING'),
        sa.Column('inviter_rewarded', sa.Boolean(), nullable=False, server_default='0'),
        sa.Column('invitee_rewarded', sa.Boolean(), nullable=False, server_default='0'),
        sa.Column('device_fingerprint', sa.String(), nullable=True),
        sa.Column('ip_address', sa.String(), nullable=True),
        sa.Column('fraud_score', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('rewarded_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['inviter_id'], ['user.id'], ),
        sa.ForeignKeyConstraint(['invitee_id'], ['user.id'], ),
        sa.ForeignKeyConstraint(['invite_code_id'], ['invite_code.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_referral_inviter_id'), 'referral', ['inviter_id'], unique=False)
    op.create_index(op.f('ix_referral_invitee_id'), 'referral', ['invitee_id'], unique=True)
    op.create_index(op.f('ix_referral_invite_code_id'), 'referral', ['invite_code_id'], unique=False)
    op.create_index(op.f('ix_referral_status'), 'referral', ['status'], unique=False)

    # Create user_reward table
    op.create_table(
        'user_reward',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('user_id', sa.String(), nullable=False),
        sa.Column('reward_type', sa.String(), nullable=False),
        sa.Column('amount', sa.Integer(), nullable=False),
        sa.Column('source', sa.String(), nullable=False, server_default='referral'),
        sa.Column('referral_id', sa.String(), nullable=True),
        sa.Column('expires_at', sa.DateTime(), nullable=True),
        sa.Column('is_used', sa.Boolean(), nullable=False, server_default='0'),
        sa.Column('used_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['user.id'], ),
        sa.ForeignKeyConstraint(['referral_id'], ['referral.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_user_reward_user_id'), 'user_reward', ['user_id'], unique=False)
    op.create_index(op.f('ix_user_reward_reward_type'), 'user_reward', ['reward_type'], unique=False)
    op.create_index(op.f('ix_user_reward_source'), 'user_reward', ['source'], unique=False)
    op.create_index(op.f('ix_user_reward_is_used'), 'user_reward', ['is_used'], unique=False)

    # Create user_stats table
    op.create_table(
        'user_stats',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('user_id', sa.String(), nullable=False),
        sa.Column('total_invites', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('successful_invites', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('total_points', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('available_points', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['user.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_user_stats_user_id'), 'user_stats', ['user_id'], unique=True)


def downgrade() -> None:
    """Drop referral system tables."""
    # Drop tables in reverse order (respecting foreign keys)
    op.drop_index(op.f('ix_user_stats_user_id'), table_name='user_stats')
    op.drop_table('user_stats')

    op.drop_index(op.f('ix_user_reward_is_used'), table_name='user_reward')
    op.drop_index(op.f('ix_user_reward_source'), table_name='user_reward')
    op.drop_index(op.f('ix_user_reward_reward_type'), table_name='user_reward')
    op.drop_index(op.f('ix_user_reward_user_id'), table_name='user_reward')
    op.drop_table('user_reward')

    op.drop_index(op.f('ix_referral_status'), table_name='referral')
    op.drop_index(op.f('ix_referral_invite_code_id'), table_name='referral')
    op.drop_index(op.f('ix_referral_invitee_id'), table_name='referral')
    op.drop_index(op.f('ix_referral_inviter_id'), table_name='referral')
    op.drop_table('referral')

    op.drop_index(op.f('ix_invite_code_is_active'), table_name='invite_code')
    op.drop_index(op.f('ix_invite_code_owner_id'), table_name='invite_code')
    op.drop_index(op.f('ix_invite_code_code'), table_name='invite_code')
    op.drop_table('invite_code')
