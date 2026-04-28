"""Drop material_embeddings table

Revision ID: drop_material_embeddings
Revises:
Create Date: 2026-02-03

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'drop_material_embeddings'
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Drop material_embeddings table - vector search no longer needed."""
    op.drop_table('material_embeddings')


def downgrade() -> None:
    """Recreate material_embeddings table."""
    op.create_table(
        'material_embeddings',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('material_type', sa.String(length=20), nullable=False),
        sa.Column('material_id', sa.Integer(), nullable=False),
        sa.Column('novel_id', sa.Integer(), nullable=True),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('embedding_model', sa.String(length=100), nullable=True),
        sa.Column('content_checksum', sa.String(length=64), nullable=True),
        sa.Column('status', sa.String(length=16), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
