"""
File CRUD operations for agent tools.

This module provides Create, Read, Update, Delete operations on the File model:
- create_file: Create any type of file
- update_file: Update existing file
- delete_file: Delete a file (with optional recursive deletion)
- query_files: Query and search files (unified)
- hybrid_search: Lexical + vector hybrid retrieval (RAG)

Extracted from the monolithic file_executor.py for better maintainability.
"""

import contextlib
import json
from typing import Any

from services.file_version import FileVersionService
from sqlalchemy import func
from sqlmodel import Session, col, select

from agent.tools.permissions import (
    check_project_ownership,
)
from config.datetime_utils import utcnow
from models import File
from models.file_version import (
    CHANGE_SOURCE_AI,
    CHANGE_TYPE_AI_EDIT,
)
from utils.logger import get_logger, log_with_context
from utils.title_sequence import (
    extract_title_first_sequence_number,
    resolve_persisted_sequence_order,
)

from .serialization import (
    QUERY_FILES_DEFAULT_CONTENT_PREVIEW_CHARS,
    QUERY_FILES_DEFAULT_RESPONSE_MODE,
    serialize_file,
    serialize_query_file,
)

logger = get_logger(__name__)


class FileCRUD:
    """
    CRUD operations for File model.

    This class provides simple, unified CRUD operations on the File model
    with permission checking and version history support.
    """

    def __init__(self, session: Session, user_id: str | None = None):
        """
        Initialize file CRUD operations.

        Args:
            session: Database session
            user_id: Current user ID (UUID string, for permission checks)
        """
        self.session = session
        self.user_id = user_id

    def create_file(
        self,
        project_id: str,
        title: str,
        file_type: str = "document",
        content: str = "",
        parent_id: str | None = None,
        order: int | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Create a new file.

        Args:
            project_id: Project ID
            title: File title/name
            file_type: File type (outline, character, lore, etc.)
            content: File content
            parent_id: Parent file ID (for folders)
            order: Sort order
            metadata: Type-specific metadata (JSON)

        Returns:
            Created file data

        Raises:
            PermissionError: If user doesn't have permission
        """
        log_with_context(
            logger,
            20,  # INFO
            "create_file started",
            project_id=project_id,
            user_id=self.user_id,
            file_type=file_type,
            title=title,
            content_length=len(content),
            parent_id=parent_id,
        )

        # Check project permission
        project = check_project_ownership(self.session, project_id, self.user_id)

        # Root folder repair (best-effort): some projects may have their root folders
        # soft-deleted or missing due to historical bugs/admin actions. Since agents
        # rely on predictable root folder ids (e.g. "{project_id}-draft-folder"),
        # we auto-restore/recreate expected root folders when referenced.
        expected_root_folders: dict[str, dict[str, Any]] = {}
        try:
            from config.project_templates import get_folders_for_type

            for cfg in get_folders_for_type(project.project_type, "zh"):
                cfg_id = (cfg or {}).get("id")
                if isinstance(cfg_id, str) and cfg_id:
                    expected_root_folders[f"{project_id}-{cfg_id}"] = cfg
        except Exception:
            expected_root_folders = {}

        def _repair_root_folder(folder_id: str) -> File | None:
            cfg = expected_root_folders.get(folder_id)
            if not cfg:
                return None

            existing = self.session.get(File, folder_id)
            if existing:
                if existing.project_id != project_id:
                    return None
                if existing.file_type != "folder":
                    return None

                changed = False
                if existing.is_deleted:
                    existing.is_deleted = False
                    existing.deleted_at = None
                    changed = True

                if existing.parent_id is not None:
                    existing.parent_id = None
                    changed = True

                if changed:
                    existing.updated_at = utcnow()
                    self.session.add(existing)
                    self.session.commit()
                    self.session.refresh(existing)

                    log_with_context(
                        logger,
                        30,  # WARNING
                        "Repaired missing/deleted root folder",
                        project_id=project_id,
                        user_id=self.user_id,
                        folder_id=folder_id,
                        folder_title=existing.title,
                        project_type=project.project_type,
                    )

                return existing

            folder = File(
                id=folder_id,
                project_id=project_id,
                title=str(cfg.get("title") or "folder"),
                file_type="folder",
                order=int(cfg.get("order") or 0),
                parent_id=None,
            )
            self.session.add(folder)
            self.session.commit()
            self.session.refresh(folder)

            log_with_context(
                logger,
                30,  # WARNING
                "Created missing root folder on-demand",
                project_id=project_id,
                user_id=self.user_id,
                folder_id=folder_id,
                folder_title=folder.title,
                project_type=project.project_type,
            )

            return folder

        # Validate parent_id exists and belongs to project
        if parent_id is not None:
            parent = self.session.get(File, parent_id)
            if not parent or parent.is_deleted or parent.project_id != project_id:
                # Best-effort repair for missing/deleted root folders (novel/short/screenplay)
                repaired_parent = _repair_root_folder(parent_id)
                if repaired_parent is not None:
                    parent = repaired_parent
                else:
                    # Recovery: screenplay projects do not have a "draft-folder".
                    # Some LLM calls may still pass "{project_id}-draft-folder" as the parent_id,
                    # which would otherwise hard-fail this tool call and interrupt the user flow.
                    should_fallback = (
                        project.project_type == "screenplay"
                        and parent_id == f"{project_id}-draft-folder"
                        and file_type in ("draft", "script", "document")
                    )
                    if should_fallback:
                        fallback_parent_id = f"{project_id}-script-folder"
                        fallback_parent = self.session.get(File, fallback_parent_id)
                        if not fallback_parent or fallback_parent.is_deleted:
                            fallback_parent = _repair_root_folder(fallback_parent_id)
                        if (
                            fallback_parent
                            and not fallback_parent.is_deleted
                            and fallback_parent.project_id == project_id
                        ):
                            log_with_context(
                                logger,
                                30,  # WARNING
                                "Parent file validation failed; falling back to screenplay script folder",
                                project_id=project_id,
                                user_id=self.user_id,
                                parent_id=parent_id,
                                fallback_parent_id=fallback_parent_id,
                                file_type=file_type,
                            )
                            parent_id = fallback_parent_id
                        else:
                            log_with_context(
                                logger,
                                40,  # ERROR
                                "Parent file validation failed (fallback target missing)",
                                project_id=project_id,
                                user_id=self.user_id,
                                parent_id=parent_id,
                                fallback_parent_id=fallback_parent_id,
                            )
                            raise ValueError(
                                f"Parent file {parent_id} not found in project {project_id}"
                            )
                    else:
                        log_with_context(
                            logger,
                            40,  # ERROR
                            "Parent file validation failed",
                            project_id=project_id,
                            user_id=self.user_id,
                            parent_id=parent_id,
                            file_type=file_type,
                        )
                        raise ValueError(
                            f"Parent file {parent_id} not found in project {project_id}"
                        )

        normalized_title = (title or "").strip()
        if normalized_title and normalized_title != title:
            title = normalized_title

        # Pre-compute sequence number for ordering + screenplay episode safeguards.
        seq_num = extract_title_first_sequence_number(title, metadata)

        is_screenplay_project = project.project_type == "screenplay"
        screenplay_script_folder_id = f"{project_id}-script-folder"
        is_screenplay_script_folder = parent_id == screenplay_script_folder_id

        looks_like_episode = (
            is_screenplay_project
            and is_screenplay_script_folder
            and seq_num is not None
            and ("集" in title or "episode" in title.lower())
        )

        # Guardrail: if the agent is writing an episode under the screenplay script folder,
        # normalize accidental draft/document file types to "script" to keep query/search stable.
        if looks_like_episode and file_type in {"draft", "document"}:
            log_with_context(
                logger,
                30,  # WARNING
                "Normalizing screenplay episode file_type to script",
                project_id=project_id,
                user_id=self.user_id,
                parent_id=parent_id,
                title=title,
                original_file_type=file_type,
            )
            file_type = "script"

        resolved_order: int
        if order is not None:
            requested_order = int(order)
            resolved_order = resolve_persisted_sequence_order(
                requested_order,
                title=title,
                metadata=metadata,
                file_type=file_type,
            )
            if resolved_order != requested_order:
                log_with_context(
                    logger,
                    30,  # WARNING
                    "Resolved chapter-like file order from parsed sequence",
                    project_id=project_id,
                    user_id=self.user_id,
                    parent_id=parent_id,
                    title=title,
                    requested_order=requested_order,
                    normalized_order=resolved_order,
                    sequence_number=seq_num,
                )
        else:
            if seq_num is not None:
                resolved_order = int(seq_num)
            else:
                # Append to the end of siblings (stable insertion).
                max_order = self.session.exec(
                    select(func.max(File.order)).where(
                        File.project_id == project_id,
                        File.parent_id == parent_id,
                        File.is_deleted.is_(False),
                    )
                ).one()
                resolved_order = int(max_order or 0)
                if max_order is not None:
                    resolved_order += 1

        # Idempotency for screenplay episode streaming:
        # If an agent tries to create the same episode twice (often due to earlier
        # mismatched file_type/order), reuse the existing file to prevent duplicates.
        #
        # IMPORTANT: The streaming pipeline expects create_file to return an empty
        # `content` field, so StreamAdapter can enter "<file>...</file>" capture mode.
        # Therefore, when we reuse an existing file, we return `content=""` even if the
        # file currently has content, and rely on update_file + FileVersion for history.
        if looks_like_episode and file_type == "script" and not content:
            existing_stmt = (
                select(File)
                .where(
                    File.project_id == project_id,
                    File.parent_id == parent_id,
                    File.title == title,
                    File.is_deleted.is_(False),
                )
                .order_by(
                    col(File.updated_at).desc(),  # type: ignore[attr-defined]
                    col(File.created_at).desc(),  # type: ignore[attr-defined]
                    col(File.id).desc(),  # type: ignore[attr-defined]
                )
            )
            existing_files = list(self.session.exec(existing_stmt).all())

            if existing_files:
                # Reuse the newest matching file; promote legacy draft/document into script.
                candidate = next(
                    (f for f in existing_files if f.file_type in {"script", "draft", "document"}),
                    None,
                )
                if candidate is not None:
                    changed = False
                    promoted = False

                    if candidate.file_type != "script":
                        candidate.file_type = "script"
                        promoted = True
                        changed = True

                    # Keep episode ordering stable: only fill order when it's unset (0).
                    if (candidate.order or 0) == 0 and resolved_order > 0:
                        candidate.order = resolved_order
                        changed = True

                    if changed:
                        candidate.updated_at = utcnow()
                        self.session.add(candidate)
                        self.session.commit()
                        self.session.refresh(candidate)
                        self._schedule_index_upsert(candidate)

                    log_with_context(
                        logger,
                        20,  # INFO
                        "Reusing existing screenplay episode file to prevent duplicates",
                        project_id=project_id,
                        user_id=self.user_id,
                        file_id=candidate.id,
                        title=title,
                        file_type=candidate.file_type,
                        promoted=promoted,
                        total_matches=len(existing_files),
                    )

                    reused = serialize_file(candidate)
                    reused["content"] = ""
                    return reused

        # Create file
        file = File(
            project_id=project_id,
            title=title,
            content=content,
            file_type=file_type,
            parent_id=parent_id,
            order=resolved_order,
            file_metadata=self._serialize_metadata(metadata),
        )

        self.session.add(file)
        self.session.commit()
        self.session.refresh(file)

        # Fire-and-forget vector index upsert (do not block)
        self._schedule_index_upsert(file, metadata)

        log_with_context(
            logger,
            20,  # INFO
            "create_file completed",
            project_id=project_id,
            user_id=self.user_id,
            file_id=file.id,
            file_type=file.file_type,
            title=file.title,
            content_length=len(file.content or ""),
        )

        return serialize_file(file)

    def update_file(
        self,
        id: str,
        title: str | None = None,
        content: str | None = None,
        parent_id: str | None = None,
        order: int | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Update an existing file.

        Args:
            id: File ID to update
            title: New title
            content: New content
            parent_id: New parent ID
            order: New order
            metadata: New metadata (overwrites existing)

        Returns:
            Updated file data

        Raises:
            PermissionError: If user doesn't have permission
            ValueError: If file not found
        """
        log_with_context(
            logger,
            20,  # INFO
            "update_file started",
            file_id=id,
            user_id=self.user_id,
            has_title=title is not None,
            has_content=content is not None,
            content_length=len(content) if content else 0,
        )

        # Get file
        file = self.session.get(File, id)

        if not file:
            # Do not leak internal IDs to end users
            log_with_context(
                logger,
                40,  # ERROR
                "File not found",
                file_id=id,
                user_id=self.user_id,
            )
            raise ValueError("文件不存在或已删除")

        # Check permission
        check_project_ownership(self.session, file.project_id, self.user_id)

        # Store old content for version history
        old_content = file.content

        # Update fields
        if title is not None:
            file.title = title

        if content is not None:
            file.content = content

        if parent_id is not None:
            # Empty string or "null" means move to root (no parent)
            if parent_id == "" or parent_id == "null":
                file.parent_id = None
            else:
                # Validate parent exists
                parent = self.session.get(File, parent_id)
                if not parent or parent.is_deleted or parent.project_id != file.project_id:
                    raise ValueError(f"Parent file {parent_id} not found in same project")
                file.parent_id = parent_id

        if metadata is not None:
            file.file_metadata = self._serialize_metadata(metadata)

        if order is not None or title is not None or metadata is not None:
            file.order = resolve_persisted_sequence_order(
                order if order is not None else file.order,
                title=file.title,
                metadata=file.get_metadata(),
                file_type=file.file_type,
            )

        # Update timestamp
        file.updated_at = utcnow()

        # Check if content changed
        content_changed = content is not None and content != old_content

        self.session.commit()
        self.session.refresh(file)

        # Create version history for content changes (AI edit)
        if content_changed:
            self._create_version(id, content)

        # Fire-and-forget vector index upsert (do not block)
        self._schedule_index_upsert(file)

        log_with_context(
            logger,
            20,  # INFO
            "update_file completed",
            file_id=id,
            user_id=self.user_id,
            project_id=file.project_id,
            content_changed=content_changed,
        )

        return serialize_file(file)

    def delete_file(
        self,
        id: str,
        recursive: bool = False,
    ) -> bool:
        """
        Delete a file.

        Args:
            id: File ID to delete
            recursive: If True, also delete all children

        Returns:
            True if deleted successfully

        Raises:
            PermissionError: If user doesn't have permission
            ValueError: If file not found
        """
        log_with_context(
            logger,
            20,  # INFO
            "delete_file started",
            file_id=id,
            user_id=self.user_id,
            recursive=recursive,
        )

        # Get file
        file = self.session.get(File, id)

        if not file or file.is_deleted:
            # Do not leak internal IDs to end users
            log_with_context(
                logger,
                40,  # ERROR
                "File not found",
                file_id=id,
                user_id=self.user_id,
            )
            raise ValueError("文件不存在或已删除")

        # Check permission
        check_project_ownership(self.session, file.project_id, self.user_id)

        deleted: list[File] = []

        # Delete recursively if requested
        if recursive:
            deleted = self._delete_recursive(file)
        else:
            # Soft delete: mark as deleted instead of removing from database
            file.is_deleted = True
            file.deleted_at = utcnow()
            deleted = [file]
            self.session.add(file)

        self.session.commit()

        # Fire-and-forget vector index delete (do not block)
        self._schedule_index_delete(deleted)

        log_with_context(
            logger,
            20,  # INFO
            "delete_file completed",
            file_id=id,
            user_id=self.user_id,
            project_id=file.project_id,
            deleted_count=len(deleted),
            recursive=recursive,
        )

        return True

    def query_files(
        self,
        project_id: str,
        id: str | None = None,
        query: str | None = None,
        file_type: str | None = None,
        file_types: list[str] | None = None,
        parent_id: str | None = None,
        metadata_filter: dict[str, Any] | None = None,
        limit: int = 50,
        offset: int = 0,
        response_mode: str = QUERY_FILES_DEFAULT_RESPONSE_MODE,
        content_preview_chars: int = QUERY_FILES_DEFAULT_CONTENT_PREVIEW_CHARS,
        include_content: bool | None = None,
    ) -> list[dict[str, Any]]:
        """
        Query and search files (unified method).

        Supports keyword search, type filtering, parent filtering, and metadata filtering.

        Args:
            project_id: Project ID
            id: Exact file ID lookup (optional, overrides keyword search)
            query: Search keyword for title/content (optional)
            file_type: Single file type filter (optional)
            file_types: Multiple file types filter (optional, use this OR file_type)
            parent_id: Parent file ID filter (optional)
            metadata_filter: Metadata field filters (optional)
            limit: Maximum results
            offset: Offset for pagination
            response_mode: Response format mode ("summary" or "full")
            content_preview_chars: Preview length in summary mode
            include_content: Backward-compatible override; True forces full content

        Returns:
            List of file data

        Raises:
            PermissionError: If user doesn't have permission
        """
        # Check project permission
        check_project_ownership(self.session, project_id, self.user_id)

        # Fast path: exact ID lookup (avoids same-title ambiguity and extra tool calls).
        normalized_id = (id or "").strip()
        if normalized_id:
            stmt = select(File).where(
                File.id == normalized_id,
                File.project_id == project_id,
                File.is_deleted.is_(False),
            )
            if file_types:
                stmt = stmt.where(File.file_type.in_(file_types))  # type: ignore[attr-defined]
            if file_type:
                stmt = stmt.where(File.file_type == file_type)
            if parent_id is not None:
                stmt = stmt.where(File.parent_id == parent_id)
            results = list(self.session.exec(stmt).all())
            if metadata_filter:
                results = self._filter_by_metadata(results, metadata_filter)
            return [
                serialize_query_file(
                    r,
                    response_mode=response_mode,
                    content_preview_chars=content_preview_chars,
                    include_content=include_content,
                )
                for r in results
            ]

        # Determine which file types to query
        target_types = None
        if file_types:
            target_types = file_types
        elif file_type:
            target_types = [file_type]

        # If querying specific types, search each type separately
        if target_types:
            results = []
            for ft in target_types:
                type_results = self._query_single_type(
                    project_id=project_id,
                    file_type=ft,
                    query=query,
                    parent_id=parent_id,
                    limit=limit,
                    offset=offset,
                )
                results.extend(type_results)
        else:
            # Query all types at once
            results = self._query_single_type(
                project_id=project_id,
                file_type=None,
                query=query,
                parent_id=parent_id,
                limit=limit,
                offset=offset,
            )

        # Apply metadata filter in Python (SQLite JSON support is limited)
        if metadata_filter:
            results = self._filter_by_metadata(results, metadata_filter)

        return [
            serialize_query_file(
                r,
                response_mode=response_mode,
                content_preview_chars=content_preview_chars,
                include_content=include_content,
            )
            for r in results
        ]

    def hybrid_search(
        self,
        project_id: str,
        query: str,
        top_k: int = 10,
        entity_types: list[str] | None = None,
        min_score: float = 0.0,
    ) -> dict[str, Any]:
        """
        Hybrid retrieval (lexical + vector fusion).

        Args:
            project_id: Project ID
            query: Search query
            top_k: Maximum results to return
            entity_types: Filter by entity types
            min_score: Minimum fused score threshold

        Returns:
            Search results with hybrid fused scores
        """
        check_project_ownership(self.session, project_id, self.user_id)

        top_k = max(1, min(int(top_k or 10), 20))
        min_score = float(min_score or 0.0)

        from services.llama_index import get_llama_index_service

        svc = get_llama_index_service()
        results = svc.hybrid_search(
            project_id=project_id,
            query=query,
            top_k=top_k,
            entity_types=entity_types,
        )

        filtered = [
            r for r in results
            if (r.fused_score if r.fused_score is not None else (r.score or 0.0)) >= min_score
        ]

        return {
            "query": query,
            "top_k": top_k,
            "min_score": min_score,
            "search_mode": "hybrid",
            "results": [r.to_dict() for r in filtered],
            "result_count": len(filtered),
        }

    # ========== Helper Methods ==========

    def _query_single_type(
        self,
        project_id: str,
        file_type: str | None,
        query: str | None,
        parent_id: str | None,
        limit: int,
        offset: int,
    ) -> list[File]:
        """
        Query files of a single type (or all types).

        Args:
            project_id: Project ID
            file_type: File type filter (None for all types)
            query: Search keyword (optional)
            parent_id: Parent ID filter (optional)
            limit: Max results
            offset: Offset for pagination

        Returns:
            List of File objects
        """
        # Build base query
        stmt = select(File).where(
            File.project_id == project_id,
            File.is_deleted.is_(False)
        )

        # Apply file type filter
        if file_type:
            stmt = stmt.where(File.file_type == file_type)

        # Apply keyword search
        if query:
            stmt = stmt.where(
                (File.title.contains(query)) | (File.content.contains(query))  # type: ignore[attr-defined]
            )

        # Apply parent filter
        if parent_id is not None:
            stmt = stmt.where(File.parent_id == parent_id)

        # Order and paginate
        stmt = stmt.order_by(File.order.asc(), col(File.created_at).desc())  # type: ignore[attr-defined]
        stmt = stmt.offset(offset).limit(limit)

        return list(self.session.exec(stmt).all())

    def _filter_by_metadata(
        self,
        files: list[File],
        metadata_filter: dict[str, Any],
    ) -> list[File]:
        """
        Filter files by metadata fields.

        Since SQLite's JSON support is limited, we filter in Python.

        Args:
            files: List of File objects
            metadata_filter: Dict of field -> value to match

        Returns:
            Filtered list of files
        """
        filtered = []
        for file in files:
            # Parse file metadata
            if not file.file_metadata:
                continue

            try:
                file_meta = json.loads(file.file_metadata)
            except (json.JSONDecodeError, TypeError):
                continue

            # Check all filter conditions (AND logic)
            match = True
            for key, expected_value in metadata_filter.items():
                actual_value = file_meta.get(key)

                # Handle different comparison types
                if actual_value is None:
                    match = False
                    break
                elif isinstance(expected_value, list):
                    # For array fields like tags, check if any match
                    if isinstance(actual_value, list):
                        if not any(v in actual_value for v in expected_value):
                            match = False
                            break
                    else:
                        if actual_value not in expected_value:
                            match = False
                            break
                else:
                    # Direct equality comparison (case-insensitive for strings)
                    if isinstance(actual_value, str) and isinstance(expected_value, str):
                        if actual_value.lower() != expected_value.lower():
                            match = False
                            break
                    elif actual_value != expected_value:
                        match = False
                        break

            if match:
                filtered.append(file)

        return filtered

    def _delete_recursive(self, file: File) -> list[File]:
        """
        Delete a file and all its children recursively.

        Returns a list of File objects that were deleted (including the root file).
        Uses soft delete: marks files as deleted instead of removing from database.
        """
        deleted: list[File] = []

        # Get children that are not already deleted
        children = list(
            self.session.exec(
                select(File).where(
                    File.parent_id == file.id,
                    File.is_deleted.is_(False)
                )
            ).all()
        )
        for child in children:
            deleted.extend(self._delete_recursive(child))

        deleted.append(file)
        # Soft delete: mark as deleted instead of removing from database
        file.is_deleted = True
        file.deleted_at = utcnow()

        return deleted

    def _serialize_metadata(self, metadata: dict[str, Any] | None) -> str | None:
        """Serialize metadata dict to JSON string."""
        if metadata is None:
            return None
        return json.dumps(metadata)

    def _create_version(self, file_id: str, content: str) -> None:
        """Create version history for AI edit using an independent session.

        Uses a separate database session to avoid SQLAlchemy state-machine
        conflicts when ``parallel_execute`` runs multiple tasks concurrently
        on the same shared session.
        """
        try:
            from database import create_session

            version_session = create_session()
            try:
                version_service = FileVersionService()
                version_service.create_version(
                    session=version_session,
                    file_id=file_id,
                    new_content=content,
                    change_type=CHANGE_TYPE_AI_EDIT,
                    change_source=CHANGE_SOURCE_AI,
                    change_summary="AI 更新文件内容",
                )
            finally:
                version_session.close()
        except Exception as e:
            # Don't fail the update if version creation fails
            logger.warning(f"Failed to create version for update_file: {e}")

    def _schedule_index_upsert(
        self,
        file: File,
        extra_metadata: dict[str, Any] | None = None,
    ) -> None:
        """Fire-and-forget vector index upsert (do not block)."""
        try:
            from services.llama_index import schedule_index_upsert

            from agent.tools.mcp_tools import ToolContext

            metadata = extra_metadata or {}
            if file.file_metadata:
                with contextlib.suppress(Exception):
                    metadata = {**metadata, **json.loads(file.file_metadata)}
            if file.parent_id:
                metadata = {**metadata, "parent_id": file.parent_id}

            user_id = ToolContext._get_context().get("user_id")

            schedule_index_upsert(
                project_id=file.project_id,
                entity_type=file.file_type,
                entity_id=file.id,
                title=file.title,
                content=file.content or "",
                extra_metadata=metadata,
                user_id=user_id,
            )
        except Exception:
            pass

    def _schedule_index_delete(self, files: list[File]) -> None:
        """Fire-and-forget vector index delete (do not block)."""
        try:
            from services.llama_index import schedule_index_delete

            from agent.tools.mcp_tools import ToolContext

            user_id = ToolContext._get_context().get("user_id")

            for f in files:
                schedule_index_delete(
                    project_id=f.project_id,
                    entity_type=f.file_type,
                    entity_id=f.id,
                    user_id=user_id,
                )
        except Exception:
            pass


__all__ = [
    "FileCRUD",
]
