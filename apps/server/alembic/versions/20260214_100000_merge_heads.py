"""merge_heads_20260214

Revision ID: merge_heads_20260214
Revises: 20260214_000000_add_referral_system_tables, 5bc06fe103e9, 827c8c6578d3
Create Date: 2026-02-14

"""

from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = 'merge_heads_20260214'
down_revision: str | Sequence[str] | None = (
    '20260214_000000_add_referral_system_tables',
    '5bc06fe103e9',
    '827c8c6578d3',
)
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema - merge heads."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
