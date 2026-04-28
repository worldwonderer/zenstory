"""Add missing columns to usage_quota table

Revision ID: 20260217_000000_add_missing_usage_quota_columns
Revises: 20260216_000000_merge_heads
Create Date: 2026-02-17

"""

from collections.abc import Sequence
from sqlalchemy import inspect

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '20260217_000000_add_missing_usage_quota_columns'
down_revision: str | Sequence[str] | None = '20260216_000000_merge_heads'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _column_exists(table_name: str, column_name: str) -> bool:
    """Check if a column exists in the table."""
    conn = op.get_bind()
    inspector = inspect(conn)
    columns = [col['name'] for col in inspector.get_columns(table_name)]
    return column_name in columns


def upgrade() -> None:
    """Add missing monthly quota columns to usage_quota table (idempotent)."""
    # Add monthly feature usage tracking columns
    if not _column_exists('usage_quota', 'material_uploads_used'):
        op.add_column('usage_quota', sa.Column('material_uploads_used', sa.Integer(), nullable=False, server_default='0'))
    if not _column_exists('usage_quota', 'material_decompositions_used'):
        op.add_column('usage_quota', sa.Column('material_decompositions_used', sa.Integer(), nullable=False, server_default='0'))
    if not _column_exists('usage_quota', 'skill_creates_used'):
        op.add_column('usage_quota', sa.Column('skill_creates_used', sa.Integer(), nullable=False, server_default='0'))
    if not _column_exists('usage_quota', 'inspiration_copies_used'):
        op.add_column('usage_quota', sa.Column('inspiration_copies_used', sa.Integer(), nullable=False, server_default='0'))

    # Add monthly period tracking columns
    if not _column_exists('usage_quota', 'monthly_period_start'):
        op.add_column('usage_quota', sa.Column('monthly_period_start', sa.DateTime(), nullable=True))
    if not _column_exists('usage_quota', 'monthly_period_end'):
        op.add_column('usage_quota', sa.Column('monthly_period_end', sa.DateTime(), nullable=True))


def downgrade() -> None:
    """Remove monthly quota columns from usage_quota table (idempotent)."""
    # Drop monthly period tracking columns
    if _column_exists('usage_quota', 'monthly_period_end'):
        op.drop_column('usage_quota', 'monthly_period_end')
    if _column_exists('usage_quota', 'monthly_period_start'):
        op.drop_column('usage_quota', 'monthly_period_start')

    # Drop monthly feature usage tracking columns
    if _column_exists('usage_quota', 'inspiration_copies_used'):
        op.drop_column('usage_quota', 'inspiration_copies_used')
    if _column_exists('usage_quota', 'skill_creates_used'):
        op.drop_column('usage_quota', 'skill_creates_used')
    if _column_exists('usage_quota', 'material_decompositions_used'):
        op.drop_column('usage_quota', 'material_decompositions_used')
    if _column_exists('usage_quota', 'material_uploads_used'):
        op.drop_column('usage_quota', 'material_uploads_used')
