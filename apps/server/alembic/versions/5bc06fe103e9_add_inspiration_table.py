"""add_inspiration_table

Revision ID: 5bc06fe103e9
Revises: 9e44de31e71a
Create Date: 2026-02-14 12:26:24.292913

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel.sql.sqltypes as sqltypes


# revision identifiers, used by Alembic.
revision: str = '5bc06fe103e9'
down_revision: Union[str, Sequence[str], None] = '9e44de31e71a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema - add inspiration table only."""
    # Create only the inspiration table
    op.create_table('inspiration',
        sa.Column('id', sqltypes.AutoString(), nullable=False),
        sa.Column('name', sqltypes.AutoString(length=200), nullable=False),
        sa.Column('description', sqltypes.AutoString(length=1000), nullable=True),
        sa.Column('cover_image', sqltypes.AutoString(length=500), nullable=True),
        sa.Column('project_type', sqltypes.AutoString(length=20), nullable=False),
        sa.Column('tags', sa.Text(), nullable=True),
        sa.Column('snapshot_data', sa.Text(), nullable=True),
        sa.Column('source', sqltypes.AutoString(length=20), nullable=False),
        sa.Column('author_id', sqltypes.AutoString(), nullable=True),
        sa.Column('original_project_id', sqltypes.AutoString(), nullable=True),
        sa.Column('status', sqltypes.AutoString(length=20), nullable=False),
        sa.Column('reviewed_by', sqltypes.AutoString(), nullable=True),
        sa.Column('reviewed_at', sa.DateTime(), nullable=True),
        sa.Column('rejection_reason', sqltypes.AutoString(length=500), nullable=True),
        sa.Column('copy_count', sa.Integer(), nullable=False),
        sa.Column('sort_order', sa.Integer(), nullable=False),
        sa.Column('is_featured', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['author_id'], ['user.id'], ),
        sa.ForeignKeyConstraint(['original_project_id'], ['project.id'], ),
        sa.ForeignKeyConstraint(['reviewed_by'], ['user.id'], ),
        sa.PrimaryKeyConstraint('id')
    )

    # Add indexes for frequently queried columns
    op.create_index('ix_inspiration_status', 'inspiration', ['status'])
    op.create_index('ix_inspiration_featured_status', 'inspiration', ['is_featured', 'status'])
    op.create_index('ix_inspiration_project_type_status', 'inspiration', ['project_type', 'status'])
    op.create_index('ix_inspiration_copy_count', 'inspiration', ['copy_count'])
    op.create_index('ix_inspiration_created_at', 'inspiration', ['created_at'])


def downgrade() -> None:
    """Downgrade schema - drop inspiration table."""
    # Drop indexes first
    op.drop_index('ix_inspiration_created_at', table_name='inspiration')
    op.drop_index('ix_inspiration_copy_count', table_name='inspiration')
    op.drop_index('ix_inspiration_project_type_status', table_name='inspiration')
    op.drop_index('ix_inspiration_featured_status', table_name='inspiration')
    op.drop_index('ix_inspiration_status', table_name='inspiration')
    # Drop table
    op.drop_table('inspiration')
