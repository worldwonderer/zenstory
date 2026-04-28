"""Update free tier display name to free trial wording.

Revision ID: 20260220_230000_update_free_plan_display_name
Revises: 20260220_020000_add_unique_index_for_file_versions
Create Date: 2026-02-20 23:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260220_230000_update_free_plan_display_name"
down_revision: str | Sequence[str] | None = "20260220_020000_add_unique_index_for_file_versions"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Apply free-tier display naming for commercialization copy."""
    op.execute(
        sa.text(
            """
            UPDATE subscription_plan
            SET display_name = '免费试用',
                display_name_en = 'Free Trial',
                updated_at = CURRENT_TIMESTAMP
            WHERE name = 'free'
            """
        )
    )


def downgrade() -> None:
    """Restore legacy free-tier display naming."""
    op.execute(
        sa.text(
            """
            UPDATE subscription_plan
            SET display_name = '免费版',
                display_name_en = 'Free',
                updated_at = CURRENT_TIMESTAMP
            WHERE name = 'free'
            """
        )
    )
