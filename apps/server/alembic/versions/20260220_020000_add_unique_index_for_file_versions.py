"""Ensure unique file version number per file.

Revision ID: 20260220_020000_add_unique_index_for_file_versions
Revises: 20260219_010000_add_unique_index_for_checkin
Create Date: 2026-02-20 02:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

# revision identifiers, used by Alembic.
revision: str = "20260220_020000_add_unique_index_for_file_versions"
down_revision: str | Sequence[str] | None = "20260219_010000_add_unique_index_for_checkin"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLE_NAME = "file_version"
INDEX_NAME = "uq_file_version_file_id_version_number"


def _has_unique_file_version_key() -> bool:
    bind = op.get_bind()
    inspector = inspect(bind)

    for index in inspector.get_indexes(TABLE_NAME):
        if index.get("name") == INDEX_NAME and index.get("unique"):
            return True
        if index.get("unique") and set(index.get("column_names") or []) == {
            "file_id",
            "version_number",
        }:
            return True

    for constraint in inspector.get_unique_constraints(TABLE_NAME):
        if constraint.get("name") == INDEX_NAME:
            return True
        if set(constraint.get("column_names") or []) == {"file_id", "version_number"}:
            return True

    return False


def _normalize_duplicate_versions() -> None:
    bind = op.get_bind()
    metadata = sa.MetaData()
    file_version = sa.Table(TABLE_NAME, metadata, autoload_with=bind)

    duplicate_groups = bind.execute(
        sa.select(
            file_version.c.file_id,
            file_version.c.version_number,
            sa.func.count().label("row_count"),
        )
        .group_by(file_version.c.file_id, file_version.c.version_number)
        .having(sa.func.count() > 1)
    ).fetchall()

    for file_id, version_number, _row_count in duplicate_groups:
        duplicate_rows = bind.execute(
            sa.select(
                file_version.c.id,
                file_version.c.created_at,
            )
            .where(
                file_version.c.file_id == file_id,
                file_version.c.version_number == version_number,
            )
            .order_by(file_version.c.created_at.asc(), file_version.c.id.asc())
        ).fetchall()

        if len(duplicate_rows) <= 1:
            continue

        max_version_number = bind.execute(
            sa.select(sa.func.max(file_version.c.version_number)).where(
                file_version.c.file_id == file_id
            )
        ).scalar()

        next_version_number = int(max_version_number or 0) + 1
        for row in duplicate_rows[1:]:
            bind.execute(
                file_version.update()
                .where(file_version.c.id == row.id)
                .values(version_number=next_version_number)
            )
            next_version_number += 1


def upgrade() -> None:
    """Normalize duplicates and add unique key on (file_id, version_number)."""
    _normalize_duplicate_versions()
    if not _has_unique_file_version_key():
        op.create_index(
            INDEX_NAME,
            TABLE_NAME,
            ["file_id", "version_number"],
            unique=True,
        )


def downgrade() -> None:
    """Drop unique index if it was created by this migration."""
    bind = op.get_bind()
    inspector = inspect(bind)
    indexes = {idx.get("name") for idx in inspector.get_indexes(TABLE_NAME)}
    if INDEX_NAME in indexes:
        op.drop_index(INDEX_NAME, table_name=TABLE_NAME)
