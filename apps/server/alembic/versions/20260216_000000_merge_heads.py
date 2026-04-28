"""merge_heads

Revision ID: 20260216_000000_merge_heads
Revises: 20260214_100000_add_points_checkin_system, 20260215_000000_add_writing_stats_tables
Create Date: 2026-02-16

"""

from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = '20260216_000000_merge_heads'
down_revision: str | Sequence[str] | None = (
    '20260214_100000_add_points_checkin_system',
    '20260215_000000_add_writing_stats_tables',
)
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Merge heads - points/checkin system and writing stats."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
