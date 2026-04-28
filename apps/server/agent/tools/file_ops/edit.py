"""
File edit operations for agent tools.

This module provides precise file editing operations:
- edit_file: Apply multiple edit operations (replace/insert/append/prepend/delete)

Supports fuzzy and approximate text matching for robust editing even when
the LLM provides slightly different text.

Extracted from the monolithic file_executor.py for better maintainability.
"""

from typing import Any

from services.file_version import FileVersionService
from sqlmodel import Session

from agent.tools.permissions import check_project_ownership
from config.datetime_utils import utcnow
from models import File
from models.file_version import (
    CHANGE_SOURCE_AI,
    CHANGE_TYPE_AI_EDIT,
)
from utils.logger import get_logger, log_with_context

from .text_matching import (
    build_span_previews,
    find_approximate_match,
    find_fuzzy_spans,
    find_unique_line_span,
    suggest_similar_lines,
)

logger = get_logger(__name__)


class FileEditor:
    """
    Editor for file content with robust text matching.

    This class provides precise editing operations on file content with:
    - Exact, fuzzy, and approximate text matching
    - Support for replace, insert, append, prepend, and delete operations
    - Version history tracking
    - Permission checking
    """

    def __init__(self, session: Session, user_id: str | None = None):
        """
        Initialize file editor.

        Args:
            session: Database session
            user_id: Current user ID (UUID string, for permission checks)
        """
        self.session = session
        self.user_id = user_id

    def edit_file(
        self,
        id: str,
        edits: list[dict[str, Any]],
        continue_on_error: bool = False,
    ) -> dict[str, Any]:
        """
        Apply precise edits to a file's content.

        Supports the following edit operations:
        - replace: Find and replace text (old -> new)
        - insert_after: Insert text after an anchor
        - insert_before: Insert text before an anchor
        - append: Add text at the end
        - prepend: Add text at the beginning
        - delete: Remove specified text

        Args:
            id: File ID to edit
            edits: List of edit operations, each containing:
                - op: Operation type
                - old: Original text (for replace/delete)
                - new: New text (for replace)
                - anchor: Anchor text (for insert_after/insert_before)
                - text: Text to insert (for insert_*/append/prepend)
                - replace_all: Whether to replace all occurrences (for replace)
            continue_on_error: Whether to continue applying remaining edits when one edit fails

        Returns:
            Dict with edit results:
                - id: File ID
                - title: File title
                - edits_applied: Number of successful edits
                - new_length: New content length
                - details: List of applied edit details
                - failed_edits: List of failed edit details (when continue_on_error=True)

        Raises:
            ValueError: If file not found or edit operation fails
            PermissionError: If user doesn't have permission
        """
        # Get file
        file = self.session.get(File, id)

        if not file or file.is_deleted:
            # Do not leak internal IDs to end users
            log_with_context(
                logger,
                40,  # ERROR
                "File not found for edit_file",
                file_id=id,
                user_id=self.user_id,
            )
            raise ValueError("文件不存在或已删除")

        # Check permission
        check_project_ownership(self.session, file.project_id, self.user_id)

        old_content = file.content or ""
        content = old_content
        applied_edits = []
        failed_edits: list[dict[str, Any]] = []
        warnings: list[str] = []

        for i, edit in enumerate(edits):
            try:
                if not isinstance(edit, dict):
                    raise ValueError(f"Edit {i}: invalid edit object, must be JSON object")

                # Normalize op field (common LLM mistakes: op is null / uses alias keys)
                op_raw = edit.get("op")
                if op_raw is None:
                    op_raw = edit.get("operation") or edit.get("action") or edit.get("type")

                op = op_raw.strip().lower() if isinstance(op_raw, str) else ""
                op = op.replace("-", "_")

                alias_map = {
                    "insertafter": "insert_after",
                    "after": "insert_after",
                    "insertbefore": "insert_before",
                    "before": "insert_before",
                    "insert": "insert_after",
                    "add_after": "insert_after",
                    "add_before": "insert_before",
                }
                op = alias_map.get(op, op)
                if op in ("none", "null", "nil"):
                    op = ""

                # If op is still missing, try safe inference from fields.
                if not op:
                    has_old = isinstance(edit.get("old"), str) and bool(edit.get("old"))
                    has_new = isinstance(edit.get("new"), str)
                    has_anchor = isinstance(edit.get("anchor"), str) and bool(edit.get("anchor"))
                    has_text = isinstance(edit.get("text"), str) and bool(edit.get("text"))
                    pos_hint = str(edit.get("position") or edit.get("where") or "").lower()

                    inferred = None
                    if has_old and has_new:
                        inferred = "replace"
                    elif has_old and (not has_new) and (not has_anchor) and (not has_text):
                        inferred = "delete"
                    elif has_anchor and has_text:
                        if ("before" in pos_hint) or ("前" in pos_hint):
                            inferred = "insert_before"
                        elif ("after" in pos_hint) or ("后" in pos_hint):
                            inferred = "insert_after"
                        else:
                            # Default to insert_after; if multiple matches, later logic will stop safely.
                            inferred = "insert_after"
                    elif has_text and (not has_old) and (not has_anchor):
                        if ("before" in pos_hint) or ("pre" in pos_hint) or ("head" in pos_hint) or ("前" in pos_hint):
                            inferred = "prepend"
                        elif ("after" in pos_hint) or ("tail" in pos_hint) or ("后" in pos_hint):
                            inferred = "append"
                        else:
                            # Default to append for novel writing.
                            inferred = "append"

                    if inferred:
                        warnings.append(f"Edit {i}: op inferred as {inferred}")
                        op = inferred
                    else:
                        # Ignore completely empty edits (common trailing null/empty item)
                        if not any(v for v in edit.values() if v not in (None, "", [], {})):
                            warnings.append(f"Edit {i}: empty edit ignored")
                            continue
                        raise ValueError(
                            f"Edit {i}: missing op. Each edit must include op=replace/insert_after/insert_before/append/prepend/delete"
                        )

                # Normalize common field aliases
                if "old" not in edit and isinstance(edit.get("from"), str):
                    edit["old"] = edit.get("from")
                if "new" not in edit and isinstance(edit.get("to"), str):
                    edit["new"] = edit.get("to")
                if "text" not in edit and isinstance(edit.get("content"), str):
                    edit["text"] = edit.get("content")

                # Persist normalized op for subsequent logic
                edit["op"] = op

                if op == "replace":
                    content = self._apply_replace(
                        content, edit, i, applied_edits, warnings
                    )
                elif op == "insert_after":
                    content = self._apply_insert_after(
                        content, edit, i, applied_edits, warnings
                    )
                elif op == "insert_before":
                    content = self._apply_insert_before(
                        content, edit, i, applied_edits, warnings
                    )
                elif op == "append":
                    text = edit.get("text", "")
                    content = content + text
                    applied_edits.append({
                        "op": op,
                        "text_len": len(text),
                        "text_preview": text[:200] + ("..." if len(text) > 200 else ""),
                    })
                elif op == "prepend":
                    text = edit.get("text", "")
                    content = text + content
                    applied_edits.append({
                        "op": op,
                        "text_len": len(text),
                        "text_preview": text[:200] + ("..." if len(text) > 200 else ""),
                    })
                elif op == "delete":
                    content = self._apply_delete(
                        content, edit, i, applied_edits, warnings
                    )
                else:
                    raise ValueError(f"Edit {i}: unknown operation '{op}'. Valid ops: replace, insert_after, insert_before, append, prepend, delete")
            except Exception as e:
                if not continue_on_error:
                    raise
                failed_op = str(edit.get("op", "")).strip() if isinstance(edit, dict) else ""
                failed_edits.append({
                    "index": i,
                    "error": str(e),
                    "op": failed_op,
                })
                warnings.append(f"Edit {i}: failed and skipped ({e})")

        # Update file only when content changed.
        if content != old_content:
            file.content = content
            file.updated_at = utcnow()
            self.session.commit()
            self.session.refresh(file)

        # Create version history for AI edit
        if content != old_content:
            self._create_edit_version(id, content, applied_edits)

        return {
            "id": file.id,
            "title": file.title,
            "file_type": file.file_type,
            "edits_applied": len(applied_edits),
            "new_length": len(content),
            "details": applied_edits,
            "failed_edits": failed_edits,
            "partial_success": bool(applied_edits and failed_edits),
            "all_failed": bool(failed_edits and not applied_edits),
            "warnings": warnings,
        }

    def _apply_replace(
        self,
        content: str,
        edit: dict[str, Any],
        edit_index: int,
        applied_edits: list[dict[str, Any]],
        warnings: list[str],
    ) -> str:
        """Apply a replace edit operation."""
        old_text = edit.get("old", "")
        new_text = edit.get("new", "")
        replace_all = edit.get("replace_all", False)

        match_mode = str(edit.get("match_mode") or "auto").strip().lower()
        ignore_punct_whitespace = bool(edit.get("ignore_punct_whitespace", True))

        if not old_text:
            warnings.append(f"Edit {edit_index}: missing old for replace; skipped")
            return content

        if not isinstance(new_text, str):
            warnings.append(f"Edit {edit_index}: invalid new for replace; skipped")
            return content

        # 1) Exact match first
        if old_text in content:
            if replace_all:
                count = content.count(old_text)
                content = content.replace(old_text, new_text)
                applied_edits.append({
                    "op": "replace",
                    "match_mode": "exact",
                    "old_preview": old_text[:200] + ("..." if len(old_text) > 200 else ""),
                    "new_preview": new_text[:200] + ("..." if len(new_text) > 200 else ""),
                    "count": count,
                })
            else:
                content = content.replace(old_text, new_text, 1)
                applied_edits.append({
                    "op": "replace",
                    "match_mode": "exact",
                    "old_preview": old_text[:200] + ("..." if len(old_text) > 200 else ""),
                    "new_preview": new_text[:200] + ("..." if len(new_text) > 200 else ""),
                })
        else:
            if match_mode == "exact":
                raise ValueError(
                    f"Edit {edit_index}: old text not found in content (exact match)"
                )

            # 2) Fuzzy match (ignore punctuation/whitespace)
            spans = find_fuzzy_spans(
                content,
                old_text,
                ignore_punct_whitespace=ignore_punct_whitespace,
            )

            # 3) If fuzzy match fails, try approximate match (handles word errors)
            approx_match = None
            if not spans:
                approx_match = find_approximate_match(
                    content,
                    old_text,
                    max_error_rate=0.25,  # Allow up to 25% character difference
                    min_pattern_len=8,
                )
                if approx_match:
                    start, end, similarity, matched_text = approx_match
                    # Single approximate match - use it
                    content = content[:start] + new_text + content[end:]
                    applied_edits.append({
                        "op": "replace",
                        "match_mode": "approximate",
                        "similarity": round(similarity, 3),
                        "matched_original": matched_text[:200] + ("..." if len(matched_text) > 200 else ""),
                        "old_preview": old_text[:200] + ("..." if len(old_text) > 200 else ""),
                        "new_preview": new_text[:200] + ("..." if len(new_text) > 200 else ""),
                    })
                    return content

            if not spans and not approx_match:
                suggestions = suggest_similar_lines(
                    content,
                    old_text,
                    ignore_punct_whitespace=ignore_punct_whitespace,
                )
                raise ValueError(
                    f"Edit {edit_index}: 找不到要替换的原文片段。请从当前文件原文中复制更长且唯一的原文。候选片段: {suggestions}"
                )

            if replace_all:
                # Replace from tail to head to keep indices stable
                for start, end in reversed(spans):
                    content = content[:start] + new_text + content[end:]
                applied_edits.append({
                    "op": "replace",
                    "match_mode": "fuzzy",
                    "ignore_punct_whitespace": ignore_punct_whitespace,
                    "old_preview": old_text[:200] + ("..." if len(old_text) > 200 else ""),
                    "new_preview": new_text[:200] + ("..." if len(new_text) > 200 else ""),
                    "count": len(spans),
                })
            else:
                if len(spans) != 1:
                    previews = build_span_previews(content, spans)
                    raise ValueError(
                        f"Edit {edit_index}: 原文片段匹配到多个位置（{len(spans)}处），为避免误改已中止。请提供更长且更唯一的原文/锚点。候选片段: {previews}"
                    )

                start, end = spans[0]
                content = content[:start] + new_text + content[end:]
                applied_edits.append({
                    "op": "replace",
                    "match_mode": "fuzzy",
                    "ignore_punct_whitespace": ignore_punct_whitespace,
                    "old_preview": old_text[:200] + ("..." if len(old_text) > 200 else ""),
                    "new_preview": new_text[:200] + ("..." if len(new_text) > 200 else ""),
                    "match_count": len(spans),
                })

        return content

    def _apply_insert_after(
        self,
        content: str,
        edit: dict[str, Any],
        edit_index: int,
        applied_edits: list[dict[str, Any]],
        _warnings: list[str],
    ) -> str:
        """Apply an insert_after edit operation."""
        anchor = edit.get("anchor", "")
        text = edit.get("text", "")

        match_mode = str(edit.get("match_mode") or "auto").strip().lower()
        ignore_punct_whitespace = bool(edit.get("ignore_punct_whitespace", True))
        occurrence = edit.get("occurrence")

        if not anchor:
            raise ValueError(f"Edit {edit_index}: 'anchor' field is required for insert_after operation")

        if anchor in content:
            match_count = content.count(anchor)
            pos = content.find(anchor) + len(anchor)
            content = content[:pos] + text + content[pos:]
            applied_edits.append({
                "op": "insert_after",
                "match_mode": "exact",
                "match_count": match_count,
                "anchor_preview": anchor[:200] + ("..." if len(anchor) > 200 else ""),
                "text_len": len(text),
                "text_preview": text[:200] + ("..." if len(text) > 200 else ""),
            })
        else:
            if match_mode == "exact":
                raise ValueError(
                    f"Edit {edit_index}: anchor text not found in content (exact match)"
                )

            spans = find_fuzzy_spans(
                content,
                anchor,
                ignore_punct_whitespace=ignore_punct_whitespace,
            )
            if not spans:
                # Secondary fallback: approximate match (handles word errors)
                approx_match = find_approximate_match(
                    content,
                    anchor,
                    max_error_rate=0.25,
                    min_pattern_len=8,
                )
                if approx_match:
                    start, end, similarity, matched_text = approx_match
                    pos = end  # Insert after the matched text
                    content = content[:pos] + text + content[pos:]
                    applied_edits.append({
                        "op": "insert_after",
                        "match_mode": "approximate",
                        "similarity": round(similarity, 3),
                        "matched_original": matched_text[:200] + ("..." if len(matched_text) > 200 else ""),
                        "anchor_preview": anchor[:200] + ("..." if len(anchor) > 200 else ""),
                        "text_len": len(text),
                        "text_preview": text[:200] + ("..." if len(text) > 200 else ""),
                    })
                    return content

                # Tertiary fallback: locate a unique best paragraph
                block_span = find_unique_line_span(
                    content,
                    anchor,
                    ignore_punct_whitespace=ignore_punct_whitespace,
                )
                if block_span:
                    start, end = block_span
                    pos = end
                    content = content[:pos] + text + content[pos:]
                    applied_edits.append({
                        "op": "insert_after",
                        "match_mode": "fuzzy_paragraph",
                        "ignore_punct_whitespace": ignore_punct_whitespace,
                        "match_count": 1,
                        "anchor_preview": anchor[:200] + ("..." if len(anchor) > 200 else ""),
                        "text_len": len(text),
                        "text_preview": text[:200] + ("..." if len(text) > 200 else ""),
                    })
                    return content

                suggestions = suggest_similar_lines(
                    content,
                    anchor,
                    ignore_punct_whitespace=ignore_punct_whitespace,
                )
                raise ValueError(
                    f"Edit {edit_index}: 找不到插入锚点。请从当前文件原文中复制更长且唯一的锚点。候选片段: {suggestions}"
                )

            if len(spans) != 1 and occurrence is None:
                previews = build_span_previews(content, spans)
                raise ValueError(
                    f"Edit {edit_index}: 锚点匹配到多个位置（{len(spans)}处），为避免插入到错误位置已中止。请提供更长且更唯一的锚点，或指定 occurrence。候选片段: {previews}"
                )

            idx = 0
            if occurrence is not None:
                try:
                    occ = int(occurrence)
                except Exception as e:
                    raise ValueError(
                        f"Edit {edit_index}: occurrence must be an integer when provided"
                    ) from e
                if occ <= 0 or occ > len(spans):
                    raise ValueError(
                        f"Edit {edit_index}: occurrence out of range (1..{len(spans)})"
                    )
                idx = occ - 1

            start, end = spans[idx]
            pos = end
            content = content[:pos] + text + content[pos:]
            applied_edits.append({
                "op": "insert_after",
                "match_mode": "fuzzy",
                "ignore_punct_whitespace": ignore_punct_whitespace,
                "match_count": len(spans),
                "anchor_preview": anchor[:200] + ("..." if len(anchor) > 200 else ""),
                "text_len": len(text),
                "text_preview": text[:200] + ("..." if len(text) > 200 else ""),
            })

        return content

    def _apply_insert_before(
        self,
        content: str,
        edit: dict[str, Any],
        edit_index: int,
        applied_edits: list[dict[str, Any]],
        _warnings: list[str],
    ) -> str:
        """Apply an insert_before edit operation."""
        anchor = edit.get("anchor", "")
        text = edit.get("text", "")

        match_mode = str(edit.get("match_mode") or "auto").strip().lower()
        ignore_punct_whitespace = bool(edit.get("ignore_punct_whitespace", True))
        occurrence = edit.get("occurrence")

        if not anchor:
            raise ValueError(f"Edit {edit_index}: 'anchor' field is required for insert_before operation")

        if anchor in content:
            match_count = content.count(anchor)
            pos = content.find(anchor)
            content = content[:pos] + text + content[pos:]
            applied_edits.append({
                "op": "insert_before",
                "match_mode": "exact",
                "match_count": match_count,
                "anchor_preview": anchor[:200] + ("..." if len(anchor) > 200 else ""),
                "text_len": len(text),
                "text_preview": text[:200] + ("..." if len(text) > 200 else ""),
            })
        else:
            if match_mode == "exact":
                raise ValueError(
                    f"Edit {edit_index}: anchor text not found in content (exact match)"
                )

            spans = find_fuzzy_spans(
                content,
                anchor,
                ignore_punct_whitespace=ignore_punct_whitespace,
            )
            if not spans:
                # Secondary fallback: approximate match (handles word errors)
                approx_match = find_approximate_match(
                    content,
                    anchor,
                    max_error_rate=0.25,
                    min_pattern_len=8,
                )
                if approx_match:
                    start, end, similarity, matched_text = approx_match
                    pos = start  # Insert before the matched text
                    content = content[:pos] + text + content[pos:]
                    applied_edits.append({
                        "op": "insert_before",
                        "match_mode": "approximate",
                        "similarity": round(similarity, 3),
                        "matched_original": matched_text[:200] + ("..." if len(matched_text) > 200 else ""),
                        "anchor_preview": anchor[:200] + ("..." if len(anchor) > 200 else ""),
                        "text_len": len(text),
                        "text_preview": text[:200] + ("..." if len(text) > 200 else ""),
                    })
                    return content

                # Tertiary fallback: locate a unique best paragraph
                block_span = find_unique_line_span(
                    content,
                    anchor,
                    ignore_punct_whitespace=ignore_punct_whitespace,
                )
                if block_span:
                    start, end = block_span
                    pos = start
                    content = content[:pos] + text + content[pos:]
                    applied_edits.append({
                        "op": "insert_before",
                        "match_mode": "fuzzy_paragraph",
                        "ignore_punct_whitespace": ignore_punct_whitespace,
                        "match_count": 1,
                        "anchor_preview": anchor[:200] + ("..." if len(anchor) > 200 else ""),
                        "text_len": len(text),
                        "text_preview": text[:200] + ("..." if len(text) > 200 else ""),
                    })
                    return content

                suggestions = suggest_similar_lines(
                    content,
                    anchor,
                    ignore_punct_whitespace=ignore_punct_whitespace,
                )
                raise ValueError(
                    f"Edit {edit_index}: 找不到插入锚点。请从当前文件原文中复制更长且唯一的锚点。候选片段: {suggestions}"
                )

            if len(spans) != 1 and occurrence is None:
                previews = build_span_previews(content, spans)
                raise ValueError(
                    f"Edit {edit_index}: 锚点匹配到多个位置（{len(spans)}处），为避免插入到错误位置已中止。请提供更长且更唯一的锚点，或指定 occurrence。候选片段: {previews}"
                )

            idx = 0
            if occurrence is not None:
                try:
                    occ = int(occurrence)
                except Exception as e:
                    raise ValueError(
                        f"Edit {edit_index}: occurrence must be an integer when provided"
                    ) from e
                if occ <= 0 or occ > len(spans):
                    raise ValueError(
                        f"Edit {edit_index}: occurrence out of range (1..{len(spans)})"
                    )
                idx = occ - 1

            start, end = spans[idx]
            pos = start
            content = content[:pos] + text + content[pos:]
            applied_edits.append({
                "op": "insert_before",
                "match_mode": "fuzzy",
                "ignore_punct_whitespace": ignore_punct_whitespace,
                "match_count": len(spans),
                "anchor_preview": anchor[:200] + ("..." if len(anchor) > 200 else ""),
                "text_len": len(text),
                "text_preview": text[:200] + ("..." if len(text) > 200 else ""),
            })

        return content

    def _apply_delete(
        self,
        content: str,
        edit: dict[str, Any],
        edit_index: int,
        applied_edits: list[dict[str, Any]],
        warnings: list[str],
    ) -> str:
        """Apply a delete edit operation."""
        old_text = edit.get("old", "")

        match_mode = str(edit.get("match_mode") or "auto").strip().lower()
        ignore_punct_whitespace = bool(edit.get("ignore_punct_whitespace", True))

        if not old_text:
            warnings.append(f"Edit {edit_index}: missing old for delete; skipped")
            return content

        if old_text in content:
            content = content.replace(old_text, "", 1)
            applied_edits.append({
                "op": "delete",
                "match_mode": "exact",
                "deleted_preview": old_text[:200] + ("..." if len(old_text) > 200 else ""),
            })
        else:
            if match_mode == "exact":
                raise ValueError(
                    f"Edit {edit_index}: text to delete not found in content (exact match)"
                )

            spans = find_fuzzy_spans(
                content,
                old_text,
                ignore_punct_whitespace=ignore_punct_whitespace,
            )
            if not spans:
                suggestions = suggest_similar_lines(
                    content,
                    old_text,
                    ignore_punct_whitespace=ignore_punct_whitespace,
                )
                raise ValueError(
                    f"Edit {edit_index}: 找不到要删除的原文片段。请从当前文件原文中复制更长且唯一的原文。候选片段: {suggestions}"
                )

            if len(spans) != 1:
                previews = build_span_previews(content, spans)
                raise ValueError(
                    f"Edit {edit_index}: 删除片段匹配到多个位置（{len(spans)}处），为避免误删已中止。请提供更长且更唯一的原文/锚点。候选片段: {previews}"
                )

            start, end = spans[0]
            content = content[:start] + content[end:]
            applied_edits.append({
                "op": "delete",
                "match_mode": "fuzzy",
                "ignore_punct_whitespace": ignore_punct_whitespace,
                "deleted_preview": old_text[:200] + ("..." if len(old_text) > 200 else ""),
                "match_count": len(spans),
            })

        return content

    def _create_edit_version(
        self,
        file_id: str,
        content: str,
        applied_edits: list[dict[str, Any]],
    ) -> None:
        """Create version history for AI edit using an independent session.

        Uses a separate database session to avoid SQLAlchemy state-machine
        conflicts when ``parallel_execute`` runs multiple edit_file tasks
        concurrently on the same shared session.
        """
        try:
            # Build change summary from edit operations
            op_summaries = []
            for detail in applied_edits:
                op = detail.get("op", "unknown")
                if op == "replace":
                    op_summaries.append("替换")
                elif op == "append":
                    op_summaries.append("追加")
                elif op == "prepend":
                    op_summaries.append("前置")
                elif op in ("insert_after", "insert_before"):
                    op_summaries.append("插入")
                elif op == "delete":
                    op_summaries.append("删除")

            change_summary = f"AI 编辑: {', '.join(op_summaries[:3])}" if op_summaries else "AI 编辑"
            if len(op_summaries) > 3:
                change_summary += f" 等 {len(op_summaries)} 处修改"

            # Use an independent session to avoid concurrent-commit conflicts
            # when multiple parallel edit_file tasks share the same ToolContext session.
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
                    change_summary=change_summary,
                )
            finally:
                version_session.close()
        except Exception as e:
            # Don't fail the edit if version creation fails
            logger.warning(f"Failed to create version for edit_file: {e}")


__all__ = [
    "FileEditor",
]
