"""add subscription system

Revision ID: 827c8c6578d3
Revises: 9e44de31e71a
Create Date: 2026-02-14 13:30:59.625219

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '827c8c6578d3'
down_revision: Union[str, Sequence[str], None] = '9e44de31e71a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'subscription_plan',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('display_name', sa.String(), nullable=False),
        sa.Column('display_name_en', sa.String(), nullable=True),
        sa.Column('price_monthly_cents', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('price_yearly_cents', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('stripe_price_id_monthly', sa.String(), nullable=True),
        sa.Column('stripe_price_id_yearly', sa.String(), nullable=True),
        sa.Column('features', sa.JSON(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='1'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name')
    )
    op.create_index(op.f('ix_subscription_plan_name'), 'subscription_plan', ['name'], unique=True)

    op.create_table(
        'user_subscription',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('user_id', sa.String(), nullable=False),
        sa.Column('plan_id', sa.String(), nullable=False),
        sa.Column('status', sa.String(), nullable=False, server_default='active'),
        sa.Column('current_period_start', sa.DateTime(), nullable=False),
        sa.Column('current_period_end', sa.DateTime(), nullable=False),
        sa.Column('cancel_at_period_end', sa.Boolean(), nullable=False, server_default='0'),
        sa.Column('stripe_subscription_id', sa.String(), nullable=True),
        sa.Column('stripe_customer_id', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['plan_id'], ['subscription_plan.id']),
        sa.ForeignKeyConstraint(['user_id'], ['user.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id')
    )
    op.create_index(op.f('ix_user_subscription_user_id'), 'user_subscription', ['user_id'], unique=True)

    op.create_table(
        'redemption_code',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('code', sa.String(), nullable=False),
        sa.Column('code_type', sa.String(), nullable=False, server_default='single_use'),
        sa.Column('tier', sa.String(), nullable=False),
        sa.Column('duration_days', sa.Integer(), nullable=False),
        sa.Column('max_uses', sa.Integer(), nullable=True),
        sa.Column('current_uses', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_by', sa.String(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='1'),
        sa.Column('expires_at', sa.DateTime(), nullable=True),
        sa.Column('notes', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('redeemed_by', sa.JSON(), nullable=True),
        sa.ForeignKeyConstraint(['created_by'], ['user.id']),
        sa.ForeignKeyConstraint(['tier'], ['subscription_plan.name']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('code')
    )
    op.create_index(op.f('ix_redemption_code_code'), 'redemption_code', ['code'], unique=True)

    op.create_table(
        'usage_quota',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('user_id', sa.String(), nullable=False),
        sa.Column('period_start', sa.DateTime(), nullable=False),
        sa.Column('period_end', sa.DateTime(), nullable=False),
        sa.Column('ai_conversations_used', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('last_reset_at', sa.DateTime(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['user.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id')
    )
    op.create_index(op.f('ix_usage_quota_user_id'), 'usage_quota', ['user_id'], unique=True)

    op.create_table(
        'subscription_history',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('user_id', sa.String(), nullable=False),
        sa.Column('action', sa.String(), nullable=False),
        sa.Column('plan_name', sa.String(), nullable=False),
        sa.Column('start_date', sa.DateTime(), nullable=False),
        sa.Column('end_date', sa.DateTime(), nullable=True),
        sa.Column('event_metadata', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['user.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_subscription_history_user_id'), 'subscription_history', ['user_id'], unique=False)

    op.create_table(
        'admin_audit_log',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('admin_user_id', sa.String(), nullable=False),
        sa.Column('action', sa.String(), nullable=False),
        sa.Column('resource_type', sa.String(), nullable=False),
        sa.Column('resource_id', sa.String(), nullable=True),
        sa.Column('old_value', sa.JSON(), nullable=True),
        sa.Column('new_value', sa.JSON(), nullable=True),
        sa.Column('ip_address', sa.String(), nullable=True),
        sa.Column('user_agent', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['admin_user_id'], ['user.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_admin_audit_log_admin_user_id'), 'admin_audit_log', ['admin_user_id'], unique=False)
    op.create_index(op.f('ix_admin_audit_log_resource_type'), 'admin_audit_log', ['resource_type'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_admin_audit_log_resource_type'), table_name='admin_audit_log')
    op.drop_index(op.f('ix_admin_audit_log_admin_user_id'), table_name='admin_audit_log')
    op.drop_table('admin_audit_log')

    op.drop_index(op.f('ix_subscription_history_user_id'), table_name='subscription_history')
    op.drop_table('subscription_history')

    op.drop_index(op.f('ix_usage_quota_user_id'), table_name='usage_quota')
    op.drop_table('usage_quota')

    op.drop_index(op.f('ix_redemption_code_code'), table_name='redemption_code')
    op.drop_table('redemption_code')

    op.drop_index(op.f('ix_user_subscription_user_id'), table_name='user_subscription')
    op.drop_table('user_subscription')

    op.drop_index(op.f('ix_subscription_plan_name'), table_name='subscription_plan')
    op.drop_table('subscription_plan')
