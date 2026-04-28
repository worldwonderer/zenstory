"""merge_heads_points_system

Revision ID: 6cd528c0e58c
Revises: 20260214_000000_add_referral_system_tables, 5bc06fe103e9, 827c8c6578d3
Create Date: 2026-02-14 15:57:46.118617

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '6cd528c0e58c'
down_revision: Union[str, Sequence[str], None] = ('20260214_000000_add_referral_system_tables', '5bc06fe103e9', '827c8c6578d3')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
