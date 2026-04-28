"""Ensure unique check-in index on (user_id, check_in_date).

Revision ID: 20260219_010000_add_unique_index_for_checkin
Revises: 20260219_000000_add_unique_constraint_user_added_skill
Create Date: 2026-02-19 01:00:00.000000

"""
from collections.abc import Sequence

from alembic import op
from sqlalchemy import inspect

# revision identifiers, used by Alembic.
revision: str = "20260219_010000_add_unique_index_for_checkin"
down_revision: str | None = "20260219_000000_add_unique_constraint_user_added_skill"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

INDEX_NAME = "ix_check_in_record_user_date"


def _has_unique_user_date_index() -> bool:
    bind = op.get_bind()
    inspector = inspect(bind)
    try:
        indexes = inspector.get_indexes("check_in_record")
    except Exception:
        return False

    for idx in indexes:
        if idx.get("name") == INDEX_NAME and idx.get("unique"):
            return True
        columns = idx.get("column_names") or []
        if idx.get("unique") and set(columns) == {"user_id", "check_in_date"}:
            return True
    return False


def upgrade() -> None:
    """Add unique index for one check-in per user per day."""
    if not _has_unique_user_date_index():
        op.create_index(
            INDEX_NAME,
            "check_in_record",
            ["user_id", "check_in_date"],
            unique=True,
        )


def downgrade() -> None:
    """Drop unique index for one check-in per user per day."""
    bind = op.get_bind()
    inspector = inspect(bind)
    indexes = {idx.get("name") for idx in inspector.get_indexes("check_in_record")}
    if INDEX_NAME in indexes:
        op.drop_index(INDEX_NAME, table_name="check_in_record")
