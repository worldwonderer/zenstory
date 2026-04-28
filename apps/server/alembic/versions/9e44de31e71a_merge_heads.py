"""merge_heads

Revision ID: 9e44de31e71a
Revises: drop_material_embeddings, add_deleted_at_to_novels, db9a8418af28
Create Date: 2026-02-04 12:04:41.933406

"""
from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = '9e44de31e71a'
down_revision: str | Sequence[str] | None = ('drop_material_embeddings', 'add_deleted_at_to_novels', 'db9a8418af28')
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
