"""Add points and check-in system tables

Revision ID: 20260214_100000_add_points_checkin_system
Revises: 6cd528c0e58c
Create Date: 2026-02-14

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '20260214_100000_add_points_checkin_system'
down_revision: str | Sequence[str] | None = '6cd528c0e58c'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create points_transaction and check_in_record tables, add monthly quota fields to usage_quota."""

    # 1. Create points_transaction table
    op.create_table(
        'points_transaction',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('user_id', sa.String(), nullable=False),
        sa.Column('amount', sa.Integer(), nullable=False),
        sa.Column('balance_after', sa.Integer(), nullable=False),
        sa.Column('transaction_type', sa.String(), nullable=False),
        sa.Column('source_id', sa.String(), nullable=True),
        sa.Column('description', sa.String(), nullable=True),
        sa.Column('expires_at', sa.DateTime(), nullable=True),
        sa.Column('is_expired', sa.Boolean(), nullable=False, server_default='0'),
        sa.Column('expired_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['user.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_points_transaction_user_id'), 'points_transaction', ['user_id'], unique=False)
    op.create_index(op.f('ix_points_transaction_is_expired'), 'points_transaction', ['is_expired'], unique=False)
    op.create_index(op.f('ix_points_transaction_expires_at'), 'points_transaction', ['expires_at'], unique=False)

    # 2. Create check_in_record table
    op.create_table(
        'check_in_record',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('user_id', sa.String(), nullable=False),
        sa.Column('check_in_date', sa.Date(), nullable=False),
        sa.Column('streak_days', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('points_earned', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['user.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_check_in_record_user_id'), 'check_in_record', ['user_id'], unique=False)
    op.create_index(op.f('ix_check_in_record_check_in_date'), 'check_in_record', ['check_in_date'], unique=False)
    # Unique constraint for one check-in per user per day
    op.create_index(
        op.f('ix_check_in_record_user_date'),
        'check_in_record',
        ['user_id', 'check_in_date'],
        unique=True
    )

    # 3. Add monthly quota fields to usage_quota table
    # These fields track monthly feature usage
    op.add_column('usage_quota', sa.Column('material_uploads_used', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('usage_quota', sa.Column('material_decompositions_used', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('usage_quota', sa.Column('skill_creates_used', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('usage_quota', sa.Column('inspiration_copies_used', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('usage_quota', sa.Column('monthly_period_start', sa.DateTime(), nullable=True))
    op.add_column('usage_quota', sa.Column('monthly_period_end', sa.DateTime(), nullable=True))


def downgrade() -> None:
    """Drop points_transaction and check_in_record tables, remove monthly quota fields from usage_quota."""

    # 3. Remove monthly quota fields from usage_quota table
    op.drop_column('usage_quota', 'monthly_period_end')
    op.drop_column('usage_quota', 'monthly_period_start')
    op.drop_column('usage_quota', 'inspiration_copies_used')
    op.drop_column('usage_quota', 'skill_creates_used')
    op.drop_column('usage_quota', 'material_decompositions_used')
    op.drop_column('usage_quota', 'material_uploads_used')

    # 2. Drop check_in_record table
    op.drop_index(op.f('ix_check_in_record_user_date'), table_name='check_in_record')
    op.drop_index(op.f('ix_check_in_record_check_in_date'), table_name='check_in_record')
    op.drop_index(op.f('ix_check_in_record_user_id'), table_name='check_in_record')
    op.drop_table('check_in_record')

    # 1. Drop points_transaction table
    op.drop_index(op.f('ix_points_transaction_expires_at'), table_name='points_transaction')
    op.drop_index(op.f('ix_points_transaction_is_expired'), table_name='points_transaction')
    op.drop_index(op.f('ix_points_transaction_user_id'), table_name='points_transaction')
    op.drop_table('points_transaction')
