"""Add unique constraint on user_added_skill (user_id, public_skill_id).

Revision ID: 20260219_000000_add_unique_constraint_user_added_skill
Revises: 20260217_000000_add_missing_usage_quota_columns
Create Date: 2026-02-19 00:00:00.000000

"""
from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260219_000000_add_unique_constraint_user_added_skill"
down_revision: str | None = "20260217_000000_add_missing_usage_quota_columns"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add uniqueness guarantee for one user adding one public skill once."""
    # Deduplicate historical data before adding unique constraint.
    op.execute(
        """
        DELETE FROM user_added_skill
        WHERE id IN (
            SELECT id FROM (
                SELECT
                    id,
                    ROW_NUMBER() OVER (
                        PARTITION BY user_id, public_skill_id
                        ORDER BY added_at ASC, id ASC
                    ) AS rn
                FROM user_added_skill
            ) ranked
            WHERE ranked.rn > 1
        )
        """
    )

    op.create_unique_constraint(
        "uq_user_added_skill_user_public",
        "user_added_skill",
        ["user_id", "public_skill_id"],
    )


def downgrade() -> None:
    """Drop uniqueness guarantee."""
    op.drop_constraint(
        "uq_user_added_skill_user_public",
        "user_added_skill",
        type_="unique",
    )
