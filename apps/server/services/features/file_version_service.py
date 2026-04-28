"""
File version service.

Handles file version creation, retrieval, diff computation, and rollback.
Uses incremental diff storage with periodic base versions for efficiency.
"""

import difflib
import json
import re
from datetime import timedelta
from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, func, select

from config.datetime_utils import utcnow
from models import File, FileVersion
from models.file_version import (
    CHANGE_SOURCE_AI,
    CHANGE_SOURCE_USER,
    CHANGE_TYPE_AUTO_SAVE,
    CHANGE_TYPE_CREATE,
    CHANGE_TYPE_EDIT,
    CHANGE_TYPE_RESTORE,
    VERSION_BASE_INTERVAL,
)
from services.quota_service import quota_service
from utils.logger import get_logger
from utils.text_metrics import count_words

logger = get_logger(__name__)
MAX_CREATE_VERSION_RETRIES = 3


class FileVersionService:
    """Service for managing file versions with diff-based storage."""

    def create_version(
        self,
        session: Session,
        file_id: str,
        new_content: str,
        change_type: str = CHANGE_TYPE_EDIT,
        change_source: str = CHANGE_SOURCE_USER,
        change_summary: str | None = None,
        force_base: bool = False,
        user_id: str | None = None,
    ) -> FileVersion:
        """
        Create a new version of a file.

        Args:
            session: Database session
            file_id: ID of the file
            new_content: New content of the file
            change_type: Type of change (create/edit/ai_edit/restore/auto_save)
            change_source: Source of change (user/ai/system)
            change_summary: Optional description of changes
            force_base: Force this to be a base version (full content)
            user_id: Optional user ID for quota checking

        Returns:
            Created FileVersion object
        """
        # Check version limit if user_id is provided
        if user_id:
            plan = quota_service.get_user_plan(session, user_id)
            if plan:
                max_versions = plan.features.get("file_versions_per_file", 10)
                if max_versions != -1:
                    existing_count = self.get_version_count(session, file_id)
                    if existing_count >= max_versions:
                        from core.error_codes import ErrorCode
                        from core.error_handler import APIException
                        raise APIException(
                            error_code=ErrorCode.QUOTA_FILE_VERSIONS_EXCEEDED,
                            status_code=402,
                            detail=f"Version limit reached ({existing_count}/{max_versions}). Please upgrade your plan.",
                        )

        # Get the file
        file = session.get(File, file_id)
        if not file or file.is_deleted:
            raise ValueError(f"File {file_id} not found")

        for attempt in range(1, MAX_CREATE_VERSION_RETRIES + 1):
            # Get latest version
            latest = self.get_latest_version(session, file_id)
            version_number = (latest.version_number + 1) if latest else 1

            # Determine if this should be a base version
            is_base = (
                force_base
                or version_number == 1
                or (version_number % VERSION_BASE_INTERVAL == 0)
                or change_type == CHANGE_TYPE_CREATE
            )

            # Get previous content for diff
            previous_content = ""
            if latest:
                previous_content = self.get_content_at_version(
                    session,
                    file_id,
                    latest.version_number,
                )

            # Calculate diff statistics
            lines_added, lines_removed = self._calculate_diff_stats(
                previous_content,
                new_content,
            )

            # Store content or diff
            content = (
                new_content
                if is_base
                else self._create_diff(previous_content, new_content)
            )

            # Calculate word/char counts
            word_count = count_words(new_content)
            char_count = len(new_content)

            # Create version
            version = FileVersion(
                file_id=file_id,
                project_id=file.project_id,
                version_number=version_number,
                content=content,
                is_base_version=is_base,
                word_count=word_count,
                char_count=char_count,
                change_type=change_type,
                change_source=change_source,
                change_summary=change_summary,
                lines_added=lines_added,
                lines_removed=lines_removed,
            )

            session.add(version)
            try:
                session.commit()
                session.refresh(version)
                return version
            except IntegrityError as err:
                session.rollback()
                if attempt >= MAX_CREATE_VERSION_RETRIES:
                    raise ValueError(
                        "Failed to create version due to concurrent updates. Please retry."
                    ) from err
                logger.warning(
                    "Version number conflict detected, retrying create_version",
                    extra={"file_id": file_id, "attempt": attempt},
                )

        raise ValueError("Failed to create file version")

    def get_versions(
        self,
        session: Session,
        file_id: str,
        limit: int = 50,
        offset: int = 0,
        include_auto_save: bool = False,
    ) -> list[FileVersion]:
        """
        Get version history for a file.

        Args:
            session: Database session
            file_id: ID of the file
            limit: Maximum number of versions to return
            offset: Number of versions to skip
            include_auto_save: Whether to include auto-save versions

        Returns:
            List of FileVersion objects (newest first)
        """
        query = select(FileVersion).where(FileVersion.file_id == file_id)

        if not include_auto_save:
            query = query.where(FileVersion.change_type != CHANGE_TYPE_AUTO_SAVE)

        query = (
            query.order_by(FileVersion.version_number.desc())  # type: ignore[attr-defined]
            .offset(offset)
            .limit(limit)
        )

        return list(session.exec(query).all())

    def get_version(
        self, session: Session, version_id: str
    ) -> FileVersion | None:
        """Get a specific version by ID."""
        return session.get(FileVersion, version_id)

    def get_latest_version(
        self, session: Session, file_id: str
    ) -> FileVersion | None:
        """Get the latest version for a file."""
        query = (
            select(FileVersion)
            .where(FileVersion.file_id == file_id)
            .order_by(FileVersion.version_number.desc())  # type: ignore[attr-defined]
            .limit(1)
        )
        return session.exec(query).first()

    def get_content_at_version(
        self, session: Session, file_id: str, version_number: int
    ) -> str:
        """
        Reconstruct content at a specific version.

        This may require applying diffs from the nearest base version.

        Args:
            session: Database session
            file_id: ID of the file
            version_number: Version number to retrieve

        Returns:
            Content at the specified version
        """
        # Get the target version
        target = session.exec(
            select(FileVersion).where(
                FileVersion.file_id == file_id,
                FileVersion.version_number == version_number,
            )
        ).first()

        if not target:
            raise ValueError(f"Version {version_number} not found for file {file_id}")

        # If it's a base version, return content directly
        if target.is_base_version:
            return target.content

        # Find the nearest base version before this
        base_version = session.exec(
            select(FileVersion)
            .where(
                FileVersion.file_id == file_id,
                FileVersion.version_number <= version_number,
                FileVersion.is_base_version,
            )
            .order_by(FileVersion.version_number.desc())  # type: ignore[attr-defined]
            .limit(1)
        ).first()

        if not base_version:
            # No base version found, start from empty
            content = ""
            start_version = 1
        else:
            content = base_version.content
            start_version = base_version.version_number + 1

        # Apply diffs sequentially (only delta versions, not base versions)
        versions = session.exec(
            select(FileVersion)
            .where(
                FileVersion.file_id == file_id,
                FileVersion.version_number >= start_version,
                FileVersion.version_number <= version_number,
                FileVersion.is_base_version == False,  # type: ignore[comparison-overlap]
            )
            .order_by(FileVersion.version_number.asc())  # type: ignore[attr-defined]
        ).all()

        for version in versions:
            content = self._apply_diff(content, version.content)

        return content

    def compare_versions(
        self,
        session: Session,
        file_id: str,
        version1: int,
        version2: int,
    ) -> dict[str, Any]:
        """
        Compare two versions of a file.

        Args:
            session: Database session
            file_id: ID of the file
            version1: First version number (older)
            version2: Second version number (newer)

        Returns:
            Dict with comparison data including unified diff
        """
        content1 = self.get_content_at_version(session, file_id, version1)
        content2 = self.get_content_at_version(session, file_id, version2)

        # Get version metadata
        v1 = session.exec(
            select(FileVersion).where(
                FileVersion.file_id == file_id,
                FileVersion.version_number == version1,
            )
        ).first()
        v2 = session.exec(
            select(FileVersion).where(
                FileVersion.file_id == file_id,
                FileVersion.version_number == version2,
            )
        ).first()

        # Generate unified diff
        diff_lines = list(
            difflib.unified_diff(
                content1.splitlines(keepends=True),
                content2.splitlines(keepends=True),
                fromfile=f"v{version1}",
                tofile=f"v{version2}",
                lineterm="",
            )
        )

        # Generate HTML diff for display
        html_diff = self._generate_html_diff(content1, content2)

        # Calculate statistics
        lines_added, lines_removed = self._calculate_diff_stats(content1, content2)

        return {
            "file_id": file_id,
            "version1": {
                "number": version1,
                "created_at": v1.created_at.isoformat() if v1 else None,
                "change_type": v1.change_type if v1 else None,
                "change_source": v1.change_source if v1 else None,
                "word_count": v1.word_count if v1 else 0,
            },
            "version2": {
                "number": version2,
                "created_at": v2.created_at.isoformat() if v2 else None,
                "change_type": v2.change_type if v2 else None,
                "change_source": v2.change_source if v2 else None,
                "word_count": v2.word_count if v2 else 0,
            },
            "unified_diff": "".join(diff_lines),
            "html_diff": html_diff,
            "stats": {
                "lines_added": lines_added,
                "lines_removed": lines_removed,
                "word_diff": (v2.word_count if v2 else 0) - (v1.word_count if v1 else 0),
            },
        }

    def rollback_to_version(
        self,
        session: Session,
        file_id: str,
        version_number: int,
        user_id: str,
    ) -> tuple[File, FileVersion]:
        """
        Rollback a file to a previous version.

        Creates a new version with the old content (doesn't delete history).

        Args:
            session: Database session
            file_id: ID of the file
            version_number: Version number to rollback to
            user_id: User ID for quota checking

        Returns:
            Tuple of (updated File, new FileVersion)
        """
        # Get content at target version
        content = self.get_content_at_version(session, file_id, version_number)

        # Get the file
        file = session.get(File, file_id)
        if not file or file.is_deleted:
            raise ValueError(f"File {file_id} not found")

        # Update file content
        file.content = content
        file.updated_at = utcnow()
        session.add(file)

        # Create a new version for the rollback
        new_version = self.create_version(
            session=session,
            file_id=file_id,
            new_content=content,
            change_type=CHANGE_TYPE_RESTORE,
            change_source=CHANGE_SOURCE_USER,
            change_summary=f"Restored to version {version_number}",
            force_base=True,  # Force base version for clarity
            user_id=user_id,
        )

        return file, new_version

    def get_version_count(
        self,
        session: Session,
        file_id: str,
        include_auto_save: bool = True,
    ) -> int:
        """Get total number of versions for a file."""
        query = select(func.count(FileVersion.id)).where(FileVersion.file_id == file_id)  # type: ignore[arg-type]

        if not include_auto_save:
            query = query.where(FileVersion.change_type != CHANGE_TYPE_AUTO_SAVE)

        result = session.exec(query).one()
        return int(result or 0)

    def cleanup_old_versions(
        self,
        session: Session,
        file_id: str,
        keep_recent: int = 50,
        keep_days: int = 30,
        keep_bases: bool = True,
        keep_ai_edits: bool = True,
    ) -> int:
        """
        Clean up old versions based on retention policy.

        Keeps:
        - Most recent N versions
        - All versions from the last N days
        - All base versions (if keep_bases=True)
        - All AI edit versions (if keep_ai_edits=True)

        Args:
            session: Database session
            file_id: ID of the file
            keep_recent: Number of recent versions to always keep
            keep_days: Number of days to keep all versions
            keep_bases: Whether to always keep base versions
            keep_ai_edits: Whether to always keep AI edit versions

        Returns:
            Number of versions deleted
        """
        cutoff_date = utcnow() - timedelta(days=keep_days)

        # Get versions to potentially delete
        query = select(FileVersion).where(
            FileVersion.file_id == file_id,
            FileVersion.created_at < cutoff_date,
            FileVersion.change_type == CHANGE_TYPE_AUTO_SAVE,  # Only auto-saves
        )

        if keep_bases:
            query = query.where(FileVersion.is_base_version == False)  # type: ignore[comparison-overlap]

        if keep_ai_edits:
            query = query.where(FileVersion.change_source != CHANGE_SOURCE_AI)

        # Skip the most recent ones
        query = query.order_by(FileVersion.version_number.desc()).offset(keep_recent)  # type: ignore[attr-defined]

        versions_to_delete = list(session.exec(query).all())

        count = 0
        for version in versions_to_delete:
            session.delete(version)
            count += 1

        if count > 0:
            session.commit()

        return count

    # Private helper methods

    def _create_diff(self, old_content: str, new_content: str) -> str:
        """Create a diff between two contents (stored as JSON)."""
        diff = list(
            difflib.unified_diff(
                old_content.splitlines(keepends=True),
                new_content.splitlines(keepends=True),
            )
        )
        return json.dumps(diff)

    def _apply_diff(self, content: str, diff_json: str) -> str:
        """Apply a diff to content to get new content."""
        try:
            diff_lines = json.loads(diff_json)
        except json.JSONDecodeError:
            # If diff is not valid JSON, assume it's raw content
            return diff_json

        if not diff_lines:
            return content

        # Parse unified diff and apply
        lines = content.splitlines(keepends=True)
        result_lines = []
        line_idx = 0

        i = 0
        while i < len(diff_lines):
            line = diff_lines[i]

            # Skip header lines
            if line.startswith("---") or line.startswith("+++"):
                i += 1
                continue

            # Parse hunk header
            if line.startswith("@@"):
                # Extract line numbers from @@ -start,count +start,count @@
                match = re.match(r"@@ -(\d+)(?:,\d+)? \+(\d+)(?:,\d+)? @@", line)
                if match:
                    old_start = int(match.group(1)) - 1  # 0-indexed

                    # Add unchanged lines before this hunk
                    while line_idx < old_start and line_idx < len(lines):
                        result_lines.append(lines[line_idx])
                        line_idx += 1

                i += 1
                continue

            # Process diff content
            if line.startswith("-"):
                # Line removed - skip it in original
                line_idx += 1
            elif line.startswith("+"):
                # Line added - add to result
                result_lines.append(line[1:])
            elif line.startswith(" "):
                # Context line - copy from original
                if line_idx < len(lines):
                    result_lines.append(lines[line_idx])
                    line_idx += 1
            else:
                # Unknown line type, add as-is
                if line_idx < len(lines):
                    result_lines.append(lines[line_idx])
                    line_idx += 1

            i += 1

        # Add remaining lines
        while line_idx < len(lines):
            result_lines.append(lines[line_idx])
            line_idx += 1

        return "".join(result_lines)

    def _calculate_diff_stats(
        self, old_content: str, new_content: str
    ) -> tuple[int, int]:
        """Calculate lines added and removed."""
        old_lines = old_content.splitlines()
        new_lines = new_content.splitlines()

        matcher = difflib.SequenceMatcher(None, old_lines, new_lines)
        added = 0
        removed = 0

        for op, i1, i2, j1, j2 in matcher.get_opcodes():
            if op == "replace":
                removed += i2 - i1
                added += j2 - j1
            elif op == "delete":
                removed += i2 - i1
            elif op == "insert":
                added += j2 - j1

        return added, removed

    def _generate_html_diff(self, old_content: str, new_content: str) -> list[dict]:
        """
        Generate structured diff data for HTML rendering.

        Returns a list of diff operations for the frontend to render.
        """
        old_lines = old_content.splitlines()
        new_lines = new_content.splitlines()

        matcher = difflib.SequenceMatcher(None, old_lines, new_lines)
        result = []

        for op, i1, i2, j1, j2 in matcher.get_opcodes():
            if op == "equal":
                for i in range(i1, i2):
                    result.append({
                        "type": "equal",
                        "old_line": i + 1,
                        "new_line": j1 + (i - i1) + 1,
                        "content": old_lines[i],
                    })
            elif op == "replace":
                # Show removed lines
                for i in range(i1, i2):
                    result.append({
                        "type": "removed",
                        "old_line": i + 1,
                        "new_line": None,
                        "content": old_lines[i],
                    })
                # Show added lines
                for j in range(j1, j2):
                    result.append({
                        "type": "added",
                        "old_line": None,
                        "new_line": j + 1,
                        "content": new_lines[j],
                    })
            elif op == "delete":
                for i in range(i1, i2):
                    result.append({
                        "type": "removed",
                        "old_line": i + 1,
                        "new_line": None,
                        "content": old_lines[i],
                    })
            elif op == "insert":
                for j in range(j1, j2):
                    result.append({
                        "type": "added",
                        "old_line": None,
                        "new_line": j + 1,
                        "content": new_lines[j],
                    })

        return result


# Singleton instance
_file_version_service: FileVersionService | None = None


def get_file_version_service() -> FileVersionService:
    """Get singleton file version service instance."""
    global _file_version_service
    if _file_version_service is None:
        _file_version_service = FileVersionService()
    return _file_version_service
