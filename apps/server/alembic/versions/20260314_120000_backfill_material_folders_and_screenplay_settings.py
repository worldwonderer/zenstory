"""Backfill materials folder for short/screenplay projects and rename screenplay settings folder.

Revision ID: 20260314_120000_backfill_material_folders_and_screenplay_settings
Revises: 20260312_120000_add_feedback_debug_fields
Create Date: 2026-03-14 12:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260314_120000_backfill_material_folders_and_screenplay_settings"
down_revision: str | Sequence[str] | None = "20260312_120000_add_feedback_debug_fields"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


EN_ROOT_FOLDER_MARKERS: tuple[str, ...] = (
    # short (en)
    "Characters",
    "Concept",
    "Drafts",
    # screenplay (en)
    "Scripts",
    "Scenes",
    "Episode Outlines",
    "World Building",
)


def _fetch_english_project_ids(conn) -> set[str]:
    """Detect whether a project uses English root folder titles (heuristic)."""
    marker_sql = ", ".join(f"'{title}'" for title in EN_ROOT_FOLDER_MARKERS)
    result = conn.execute(
        sa.text(
            f"""
            SELECT DISTINCT f.project_id
            FROM file f
            JOIN project p ON p.id = f.project_id
            WHERE p.is_deleted = FALSE
              AND p.project_type IN ('short', 'screenplay')
              AND f.is_deleted = FALSE
              AND f.parent_id IS NULL
              AND f.file_type = 'folder'
              AND f.title IN ({marker_sql})
            """
        )
    )
    return {row[0] for row in result.fetchall()}


def _upsert_root_folder(
    conn,
    *,
    folder_id: str,
    project_id: str,
    title: str,
    order: int,
) -> None:
    """Create or restore a predictable root folder (idempotent)."""
    conn.execute(
        sa.text(
            """
            INSERT INTO file (
                id,
                project_id,
                title,
                content,
                file_type,
                parent_id,
                "order",
                file_metadata,
                created_at,
                updated_at,
                is_deleted,
                deleted_at
            ) VALUES (
                :id,
                :project_id,
                :title,
                '',
                'folder',
                NULL,
                :order,
                NULL,
                CURRENT_TIMESTAMP,
                CURRENT_TIMESTAMP,
                FALSE,
                NULL
            )
            ON CONFLICT (id) DO UPDATE
            SET title = EXCLUDED.title,
                content = '',
                file_type = 'folder',
                parent_id = NULL,
                "order" = EXCLUDED."order",
                is_deleted = FALSE,
                deleted_at = NULL,
                updated_at = CURRENT_TIMESTAMP
            WHERE "file".project_id = EXCLUDED.project_id
            """
        ),
        {
            "id": folder_id,
            "project_id": project_id,
            "title": title,
            "order": order,
        },
    )


def _update_root_folder_order(conn, *, folder_id: str, project_id: str, order: int) -> int:
    result = conn.execute(
        sa.text(
            """
            UPDATE file
            SET "order" = :order,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = :id
              AND project_id = :project_id
              AND file_type = 'folder'
              AND parent_id IS NULL
            """
        ),
        {"id": folder_id, "project_id": project_id, "order": order},
    )
    return int(result.rowcount or 0)


def _update_root_folder_order_with_fallback(
    conn,
    *,
    folder_id: str,
    project_id: str,
    order: int,
    title_candidates: tuple[str, ...],
) -> None:
    """Update root folder order by predictable id first; fall back to matching titles for legacy data."""
    updated = _update_root_folder_order(
        conn, folder_id=folder_id, project_id=project_id, order=order
    )
    if updated:
        return

    if not title_candidates:
        return

    title_sql = ", ".join(f"'{title}'" for title in title_candidates)
    conn.execute(
        sa.text(
            f"""
            UPDATE file
            SET "order" = :order,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = (
                SELECT id
                FROM file
                WHERE project_id = :project_id
                  AND file_type = 'folder'
                  AND parent_id IS NULL
                  AND title IN ({title_sql})
                ORDER BY created_at ASC, id ASC
                LIMIT 1
            )
            """
        ),
        {"project_id": project_id, "order": order},
    )


def _rename_screenplay_lore_folder(conn, *, project_id: str, title: str) -> None:
    """Rename screenplay lore-folder from legacy '场景/Scenes' to the new title."""
    lore_folder_id = f"{project_id}-lore-folder"
    result = conn.execute(
        sa.text(
            """
            UPDATE file
            SET title = CASE
                    WHEN title IN ('场景', 'Scenes') THEN :title
                    ELSE title
                END,
                is_deleted = FALSE,
                deleted_at = NULL,
                parent_id = NULL,
                file_type = 'folder',
                updated_at = CURRENT_TIMESTAMP
            WHERE id = :id
              AND project_id = :project_id
              AND file_type = 'folder'
              AND parent_id IS NULL
            """
        ),
        {"id": lore_folder_id, "project_id": project_id, "title": title},
    )

    if int(result.rowcount or 0) > 0:
        return

    # Legacy projects may have non-predictable root folder ids; rename the earliest matching root folder.
    conn.execute(
        sa.text(
            """
            UPDATE file
            SET title = :title,
                is_deleted = FALSE,
                deleted_at = NULL,
                parent_id = NULL,
                file_type = 'folder',
                updated_at = CURRENT_TIMESTAMP
            WHERE id = (
                SELECT id
                FROM file
                WHERE project_id = :project_id
                  AND file_type = 'folder'
                  AND parent_id IS NULL
                  AND title IN ('场景', 'Scenes')
                ORDER BY created_at ASC, id ASC
                LIMIT 1
            )
            """
        ),
        {"project_id": project_id, "title": title},
    )


def upgrade() -> None:
    conn = op.get_bind()

    english_project_ids = _fetch_english_project_ids(conn)

    projects = conn.execute(
        sa.text(
            """
            SELECT id, project_type
            FROM project
            WHERE is_deleted = FALSE
              AND project_type IN ('short', 'screenplay')
            ORDER BY created_at ASC
            """
        )
    ).fetchall()

    for project_id, project_type in projects:
        is_english = project_id in english_project_ids

        material_title = "Materials" if is_english else "素材"
        material_folder_id = f"{project_id}-material-folder"

        if project_type == "short":
            # Root folder order: 人物/Characters, 构思/Concept, 素材/Materials, 正文/Drafts
            _upsert_root_folder(
                conn,
                folder_id=material_folder_id,
                project_id=project_id,
                title=material_title,
                order=2,
            )

            _update_root_folder_order_with_fallback(
                conn,
                folder_id=f"{project_id}-character-folder",
                project_id=project_id,
                order=0,
                title_candidates=("Characters",) if is_english else ("人物",),
            )
            _update_root_folder_order_with_fallback(
                conn,
                folder_id=f"{project_id}-outline-folder",
                project_id=project_id,
                order=1,
                title_candidates=("Concept",) if is_english else ("构思",),
            )
            _update_root_folder_order_with_fallback(
                conn,
                folder_id=material_folder_id,
                project_id=project_id,
                order=2,
                title_candidates=(material_title,),
            )
            _update_root_folder_order_with_fallback(
                conn,
                folder_id=f"{project_id}-draft-folder",
                project_id=project_id,
                order=3,
                title_candidates=("Drafts",) if is_english else ("正文",),
            )

        if project_type == "screenplay":
            lore_title = "World Building" if is_english else "设定"

            # Root folder order: 角色/Characters, 设定/World Building, 素材/Materials,
            # 分集大纲/Episode Outlines, 剧本/Scripts
            _upsert_root_folder(
                conn,
                folder_id=material_folder_id,
                project_id=project_id,
                title=material_title,
                order=2,
            )
            _rename_screenplay_lore_folder(conn, project_id=project_id, title=lore_title)

            _update_root_folder_order_with_fallback(
                conn,
                folder_id=f"{project_id}-character-folder",
                project_id=project_id,
                order=0,
                title_candidates=("Characters",) if is_english else ("角色",),
            )
            _update_root_folder_order_with_fallback(
                conn,
                folder_id=f"{project_id}-lore-folder",
                project_id=project_id,
                order=1,
                title_candidates=(
                    ("World Building", "Scenes") if is_english else ("设定", "场景")
                ),
            )
            _update_root_folder_order_with_fallback(
                conn,
                folder_id=material_folder_id,
                project_id=project_id,
                order=2,
                title_candidates=(material_title,),
            )
            _update_root_folder_order_with_fallback(
                conn,
                folder_id=f"{project_id}-outline-folder",
                project_id=project_id,
                order=3,
                title_candidates=("Episode Outlines",) if is_english else ("分集大纲",),
            )
            _update_root_folder_order_with_fallback(
                conn,
                folder_id=f"{project_id}-script-folder",
                project_id=project_id,
                order=4,
                title_candidates=("Scripts",) if is_english else ("剧本",),
            )


def downgrade() -> None:
    """Downgrade is intentionally a no-op (data migration is not safely reversible)."""
    pass
