"""add source_id to inspiration

Revision ID: a1f2c3d4e5b6
Revises: 9e44de31e71a
Create Date: 2026-04-25 18:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'a1f2c3d4e5b6'
down_revision: str | Sequence[str] | None = '20260314_120000_backfill_material_folders_and_screenplay_settings'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        'inspiration',
        sa.Column('source_id', sa.String(100), nullable=True),
    )
    op.create_index(
        'ix_inspiration_source_id',
        'inspiration',
        ['source_id'],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index('ix_inspiration_source_id', table_name='inspiration')
    op.drop_column('inspiration', 'source_id')
