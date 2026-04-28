"""
Message manager for chat history and system prompt construction.

Handles:
- Saving user and assistant messages to chat history
- Building system prompts with project context
- Managing chat sessions
"""

import asyncio
import json as json_module
from typing import Any

from sqlalchemy import desc
from sqlmodel import Session, and_, select

from config.datetime_utils import utcnow
from database import create_session
from utils.logger import get_logger, log_with_context

from ..prompts import get_prompt_for_project_type
from ..utils.world_model_visibility import (
    extract_item_metadata,
    resolve_world_model_channels,
)

logger = get_logger(__name__)

_CONTEXT_MAX_CONSTRAINTS = 12
_CONTEXT_MAX_WORLD_KNOWLEDGE = 24
_CONTEXT_MAX_WORKING_SET = 18
_CONTEXT_ITEM_TEXT_CHAR_LIMIT = 220
_CONTEXT_RAW_CHAR_LIMIT = 14000


class MessageManager:
    """
    Manages chat messages and system prompt construction.

    Responsibilities:
    - Save messages to chat history
    - Build system prompts with context
    - Load chat history
    """

    def __init__(self, project_id: str, user_id: str | None = None):
        """
        Initialize message manager.

        Args:
            project_id: Project ID
            user_id: User ID (optional, for chat history)
        """
        self.project_id = project_id
        self.user_id = user_id

    async def save_messages(
        self,
        session: Session,
        session_id: str | None,
        user_message: str,
        assistant_message: str,
        tool_calls: list | None = None,
        reasoning_content: str | None = None,
        assistant_stop_reason: str | None = None,
        assistant_usage: dict[str, Any] | None = None,
        assistant_status_cards: list[dict[str, Any]] | None = None,
    ) -> str | None:
        """
        Save messages to chat history.

        Args:
            session: Database session
            session_id: Exact chat session to persist into when available
            user_message: User's message content
            assistant_message: Assistant's response content
            tool_calls: List of tool calls made during the response
            reasoning_content: Thinking/reasoning content from the model
            assistant_stop_reason: Model stop reason from MESSAGE_END
            assistant_usage: Model usage payload from MESSAGE_END

        Returns:
            Persisted assistant message ID when history save succeeds
        """
        if self._should_offload_session_work(session):
            return await asyncio.to_thread(
                self._save_messages_sync,
                session_id,
                user_message,
                assistant_message,
                tool_calls,
                reasoning_content,
                assistant_stop_reason,
                assistant_usage,
                assistant_status_cards,
            )
        return self._save_messages_with_session(
            session,
            session_id,
            user_message,
            assistant_message,
            tool_calls,
            reasoning_content,
            assistant_stop_reason,
            assistant_usage,
            assistant_status_cards,
        )

    def _should_offload_session_work(self, session: Session) -> bool:
        """Only offload when running against PostgreSQL production-style sessions."""
        bind = session.get_bind() if hasattr(session, "get_bind") else None
        dialect_name = getattr(getattr(bind, "dialect", None), "name", "")
        return dialect_name == "postgresql"

    def _save_messages_sync(
        self,
        session_id: str | None,
        user_message: str,
        assistant_message: str,
        tool_calls: list | None = None,
        reasoning_content: str | None = None,
        assistant_stop_reason: str | None = None,
        assistant_usage: dict[str, Any] | None = None,
        assistant_status_cards: list[dict[str, Any]] | None = None,
    ) -> str | None:
        """Persist chat history with a fresh sync DB session."""
        with create_session() as session:
            return self._save_messages_with_session(
                session,
                session_id,
                user_message,
                assistant_message,
                tool_calls,
                reasoning_content,
                assistant_stop_reason,
                assistant_usage,
                assistant_status_cards,
            )

    def _save_messages_with_session(
        self,
        session: Session,
        session_id: str | None,
        user_message: str,
        assistant_message: str,
        tool_calls: list | None = None,
        reasoning_content: str | None = None,
        assistant_stop_reason: str | None = None,
        assistant_usage: dict[str, Any] | None = None,
        assistant_status_cards: list[dict[str, Any]] | None = None,
    ) -> str | None:
        """Core chat-history persistence logic using the provided session."""
        from models import ChatMessage, ChatSession

        if not self.user_id:
            return None

        try:
            # Check if project is not deleted
            from models import Project

            project = session.get(Project, self.project_id)
            if not project or project.is_deleted:
                log_with_context(
                    logger,
                    30,  # WARNING
                    "Project not found or deleted, skipping save",
                    project_id=self.project_id,
                    user_id=self.user_id,
                )
                return None

            chat_session: ChatSession | None = None
            if session_id:
                chat_session = session.get(ChatSession, session_id)
                if chat_session is None:
                    raise ValueError(f"Chat session not found: {session_id}")
                if (
                    chat_session.project_id != self.project_id
                    or chat_session.user_id != self.user_id
                ):
                    raise ValueError(
                        f"Chat session does not belong to project/user: {session_id}"
                    )
            else:
                stmt = (
                    select(ChatSession)
                    .where(
                        and_(
                            ChatSession.project_id == self.project_id,
                            ChatSession.user_id == self.user_id,
                            ChatSession.is_active,
                        )
                    )
                    .order_by(
                        desc(ChatSession.updated_at),
                        desc(ChatSession.created_at),
                        desc(ChatSession.id),
                    )
                )
                active_sessions = session.exec(stmt).all()
                chat_session = active_sessions[0] if active_sessions else None

                if len(active_sessions) > 1 and chat_session is not None:
                    stale_count = 0
                    for stale in active_sessions[1:]:
                        if stale.is_active:
                            stale.is_active = False
                            session.add(stale)
                            stale_count += 1
                    if stale_count > 0:
                        log_with_context(
                            logger,
                            30,  # WARNING
                            "Multiple active chat sessions detected; stale sessions deactivated",
                            project_id=self.project_id,
                            user_id=self.user_id,
                            kept_session_id=chat_session.id,
                            stale_count=stale_count,
                        )

                if not chat_session:
                    log_with_context(
                        logger,
                        20,  # INFO
                        "Creating new chat session",
                        project_id=self.project_id,
                        user_id=self.user_id,
                    )
                    chat_session = ChatSession(
                        user_id=self.user_id,
                        project_id=self.project_id,
                        title="AI 助手对话",
                        is_active=True,
                        message_count=0,
                    )
                    session.add(chat_session)
                    session.commit()
                    session.refresh(chat_session)

            # Save user message
            user_chat_message = ChatMessage(
                session_id=chat_session.id,
                role="user",
                content=user_message,
            )
            session.add(user_chat_message)

            # Save assistant message
            tool_calls_json = self._serialize_tool_calls(tool_calls)
            assistant_metadata_json = self._serialize_message_metadata(
                stop_reason=assistant_stop_reason,
                usage=assistant_usage,
                status_cards=assistant_status_cards,
            )

            assistant_chat_message = ChatMessage(
                session_id=chat_session.id,
                role="assistant",
                content=assistant_message,
                tool_calls=tool_calls_json,
                reasoning_content=reasoning_content,
                message_metadata=assistant_metadata_json,
            )
            session.add(assistant_chat_message)

            chat_session.message_count += 2
            chat_session.updated_at = utcnow()
            session.commit()

            log_with_context(
                logger,
                20,  # INFO
                "Messages saved to chat history",
                project_id=self.project_id,
                user_id=self.user_id,
                session_id=chat_session.id,
                message_count=chat_session.message_count,
                tool_calls_count=len(tool_calls) if tool_calls else 0,
                has_usage=assistant_usage is not None,
                stop_reason=assistant_stop_reason,
            )
            return assistant_chat_message.id

        except Exception as e:
            session.rollback()
            log_with_context(
                logger,
                40,  # ERROR
                "Failed to save messages to chat history",
                project_id=self.project_id,
                user_id=self.user_id,
                error=str(e),
                error_type=type(e).__name__,
            )
            raise

    def _serialize_tool_calls(self, tool_calls: list | None) -> str | None:
        """
        Serialize tool calls to JSON string.

        Args:
            tool_calls: List of tool call objects

        Returns:
            JSON string or None
        """
        if not tool_calls:
            return None

        serialized_calls = []
        for tc in tool_calls:
            if isinstance(tc, dict):
                # New format with result info
                if "name" in tc:
                    serialized_calls.append({
                        "id": tc.get("id", ""),
                        "name": tc.get("name", ""),
                        "arguments": tc.get("arguments", ""),
                        "status": tc.get("status", "success"),
                        "result": tc.get("result"),
                        "error": tc.get("error"),
                    })
                elif "function" in tc:
                    # Old format with function key
                    serialized_calls.append({
                        "id": tc.get("id", ""),
                        "name": tc.get("function", {}).get("name", ""),
                        "arguments": tc.get("function", {}).get("arguments", ""),
                        "status": "success",
                        "result": None,
                        "error": None,
                    })
            else:
                # Legacy OpenAI object format (for backwards compatibility)
                serialized_calls.append({
                    "id": tc.id,
                    "name": tc.function.name,
                    "arguments": tc.function.arguments,
                    "status": "success",
                    "result": None,
                    "error": None,
                })

        return json_module.dumps(serialized_calls)

    def _serialize_message_metadata(
        self,
        stop_reason: str | None = None,
        usage: dict[str, Any] | None = None,
        status_cards: list[dict[str, Any]] | None = None,
    ) -> str | None:
        """Serialize assistant metadata payload to JSON."""
        payload: dict[str, Any] = {}
        if stop_reason:
            payload["stop_reason"] = stop_reason
        if usage and isinstance(usage, dict):
            payload["usage"] = usage
        if status_cards and isinstance(status_cards, list):
            payload["status_cards"] = status_cards

        if not payload:
            return None

        return json_module.dumps(payload)

    def build_system_prompt(
        self,
        session: Session,
        session_id: str | None = None,
        metadata: dict[str, Any] | None = None,
        assembled_context: str | None = None,
        context_items: list[dict[str, Any]] | None = None,
        language: str | None = None,
        skill_catalog: str | None = None,
        skill_reference: str | None = None,
        selected_skill: dict[str, Any] | None = None,
    ) -> str:
        """
        Build system prompt for the AI assistant.

        Args:
            session: Database session for querying project info
            session_id: Chat session ID for loading task board
            metadata: Optional metadata (current_file_id, etc.)
            assembled_context: Pre-assembled context from ContextAssembler
            context_items: Structured context items from ContextAssembler
            language: Language preference (zh/en)
            skill_catalog: Concise skill catalog for AI-driven selection
            skill_reference: Full skill instructions reference
            selected_skill: Explicit per-message selected skill to prioritize

        Returns:
            Complete system prompt string
        """
        from models import Project, User

        lang = (language or "").strip().lower() or "zh"
        force_en = lang.startswith("en")

        # Get project to determine type
        project = session.get(Project, self.project_id)
        if not project:
            raise ValueError(f"Project not found: {self.project_id}")

        # Check if project is soft-deleted
        if project.is_deleted:
            raise ValueError(f"Project not found: {self.project_id}")

        # Defense-in-depth: verify project ownership here as well.
        #
        # Most API entrypoints already validate access before calling the agent service,
        # but this extra check prevents accidental cross-project prompt assembly if a
        # future caller forgets to enforce access control.
        if self.user_id:
            user = session.get(User, self.user_id)
            if not user:
                raise ValueError(f"User not found: {self.user_id}")
            if not user.is_superuser and project.owner_id != user.id:
                # Do not leak project existence.
                raise ValueError(f"Project not found: {self.project_id}")

        project_type = getattr(project, "project_type", None) or "novel"

        # Build folder IDs for system prompt placeholders.
        #
        # NOTE:
        # - New projects use predictable root folder IDs (project_id-xxx-folder).
        # - Older/legacy projects may use random UUID root folders or slightly different
        #   titles (e.g. screenplay "场景" used as settings folder).
        #
        # We must resolve actual root folder IDs from DB to avoid AI creating duplicate
        # root folders and "losing" files in the UI.
        folder_ids = self._get_folder_ids(
            session=session,
            project_type=project_type,
        )

        # Get prompt from template
        prompt = get_prompt_for_project_type(project_type, self.project_id, folder_ids)

        # === STATIC PREFIX (stable across turns for context caching) ===
        parts = [prompt]

        # Force output language mode
        if force_en:
            parts.extend(self._build_language_section())

        constraints, world_truth, world_surface = self._extract_structured_context(
            context_items=context_items,
            force_en=force_en,
        )
        narrative_constraints = self._build_narrative_constraints_section(
            constraints=constraints,
            force_en=force_en,
        )
        if narrative_constraints:
            parts.extend(narrative_constraints)

        # Add skill catalog for AI-driven selection
        if skill_catalog:
            parts.extend(self._build_skill_catalog_section(skill_catalog, force_en))

        # Add skill reference (full instructions)
        if skill_reference:
            parts.extend(self._build_skill_reference_section(skill_reference, force_en))

        # === SEMI-STATIC (changes per session but stable within turns) ===
        if selected_skill:
            parts.extend(self._build_selected_skill_section(selected_skill, force_en))

        # Add assembled context / world model visibility contract
        if assembled_context or world_truth or world_surface:
            parts.extend(
                self._build_context_section(
                    assembled_context=assembled_context or "",
                    context_items=context_items,
                    force_en=force_en,
                    world_truth=world_truth,
                    world_surface=world_surface,
                )
            )

        # === DYNAMIC SUFFIX (changes every request) ===
        # Add current file metadata
        if metadata:
            parts.extend(self._build_metadata_section(metadata, force_en))

        # Add task board state
        parts.extend(self._build_task_board_section(session_id, force_en))

        return "\n".join(parts)

    def _build_language_section(self) -> list[str]:
        """Build language enforcement section for English mode."""
        return [
            "",
            "## CRITICAL: Output Language",
            "You MUST respond ENTIRELY in English for this session.",
            "- Reply in English even if the user writes in Chinese.",
            "- Do not mix Chinese and English.",
            "- UI labels/tool names can remain as-is if needed.",
        ]

    def _build_task_board_section(
        self, session_id: str | None, force_en: bool
    ) -> list[str]:
        """Build task board section for system prompt."""
        parts: list[str] = []

        if session_id:
            from services.infra.task_board_service import task_board_service

            tasks = (
                task_board_service.get_tasks(
                    session_id,
                    user_id=self.user_id,
                    project_id=self.project_id,
                )
                if self.user_id
                else None
            )
            if tasks:
                # Format tasks with emoji status icons
                task_lines = []
                for t in tasks:
                    status = t.get("status", "pending")
                    task_desc = t.get("task", "")
                    if status == "in_progress":
                        icon = "🔄"
                    elif status == "done":
                        icon = "✅"
                    else:  # pending
                        icon = "⏳"
                    task_lines.append(f"{icon} {task_desc}")

                parts.extend([
                    "",
                    "## Current Task Board" if force_en else "## 当前任务计划板",
                    "",
                    "\n".join(task_lines),
                    "",
                    "**Important Rule:** After completing each task, you MUST call update_project(tasks=[...]) to mark it as done"
                    if force_en
                    else "**重要规则:** 完成当前任务后必须调用 update_project(tasks=[...]) 标记为 done",
                ])
            else:
                parts.extend([
                    "",
                    "## Current Task Board" if force_en else "## 当前任务计划板",
                    "",
                    "No active tasks" if force_en else "当前无活跃任务",
                ])

        return parts

    def _build_metadata_section(
        self, metadata: dict[str, Any], force_en: bool
    ) -> list[str]:
        """Build current file metadata section."""
        parts: list[str] = []
        file_info = []

        if "current_file_id" in metadata:
            file_info.append(f"- 文件 ID: {metadata['current_file_id']}")
        if "current_file_type" in metadata:
            file_info.append(f"- 类型: {metadata['current_file_type']}")
        if "current_file_title" in metadata:
            file_info.append(f"- 标题: {metadata['current_file_title']}")

        if file_info:
            parts.extend(
                ["", "## Current File" if force_en else "## 当前文件"] + file_info
            )

        return parts

    def _build_context_section(
        self,
        assembled_context: str,
        context_items: list[dict[str, Any]] | None,
        force_en: bool,
        world_truth: list[str] | None = None,
        world_surface: list[str] | None = None,
    ) -> list[str]:
        """Build world-model truth/surface context section (no legacy aliases)."""
        if world_truth is None or world_surface is None:
            _, world_truth, world_surface = self._extract_structured_context(
                context_items=context_items,
                force_en=force_en,
            )

        truth_items = world_truth or []
        surface_items = world_surface or []
        raw_context = self._truncate_text(assembled_context, _CONTEXT_RAW_CHAR_LIMIT)

        parts: list[str] = [
            "",
            "## World Model Visibility Contract"
            if force_en
            else "## 世界模型可见性合同",
            "",
            "Use world_model_truth as canonical facts; treat world_model_surface as scene-level cues."
            if force_en
            else "将 world_model_truth 视为权威事实；world_model_surface 仅作为场景线索。",
            "",
        ]

        if truth_items:
            parts.append("<world_model_truth>")
            parts.extend([f"- {entry}" for entry in truth_items])
            parts.append("</world_model_truth>")
            parts.append("")

        if surface_items:
            parts.append("<world_model_surface>")
            parts.extend([f"- {entry}" for entry in surface_items])
            parts.append("</world_model_surface>")
            parts.append("")

        if raw_context:
            parts.append("<project_context_raw>")
            parts.append(raw_context)
            parts.append("</project_context_raw>")
        return parts

    def _build_narrative_constraints_section(
        self,
        *,
        constraints: list[str],
        force_en: bool,
    ) -> list[str]:
        """Inject narrative constraints as an independent prompt block."""
        if not constraints:
            return []

        return [
            "",
            "## Narrative Constraints" if force_en else "## 叙事约束",
            "",
            "<narrative_constraints>",
            *[f"{idx}. {rule}" for idx, rule in enumerate(constraints, start=1)],
            "</narrative_constraints>",
        ]

    def _extract_structured_context(
        self,
        *,
        context_items: list[dict[str, Any]] | None,
        force_en: bool,
    ) -> tuple[list[str], list[str], list[str]]:
        constraints: list[str] = []
        world_truth: list[str] = []
        world_surface: list[str] = []
        seen_constraints: set[str] = set()
        seen_truth: set[str] = set()
        seen_surface: set[str] = set()

        for raw_item in context_items or []:
            if not isinstance(raw_item, dict):
                continue
            item_type = str(raw_item.get("type") or "").strip().lower()
            priority = str(raw_item.get("priority") or "").strip().lower()
            metadata = extract_item_metadata(raw_item)
            inject_truth, inject_surface = resolve_world_model_channels(
                item_type=item_type,
                metadata=metadata,
            )
            if not inject_truth and not inject_surface:
                continue

            title = self._normalize_text(str(raw_item.get("title") or ""))
            content = self._normalize_text(str(raw_item.get("content") or ""))
            snippet = self._truncate_text(content, _CONTEXT_ITEM_TEXT_CHAR_LIMIT)
            item_entry = self._build_item_entry(
                title=title,
                snippet=snippet,
                force_en=force_en,
            )

            if item_entry and inject_truth and item_entry not in seen_truth:
                seen_truth.add(item_entry)
                world_truth.append(item_entry)
            if item_entry and inject_surface and item_entry not in seen_surface:
                seen_surface.add(item_entry)
                world_surface.append(item_entry)

            if item_type in {"character", "lore"} and inject_truth:
                if priority in {"critical", "constraint"}:
                    rule = self._build_consistency_rule(
                        item_type=item_type,
                        title=title,
                        force_en=force_en,
                    )
                    if rule and rule not in seen_constraints:
                        seen_constraints.add(rule)
                        constraints.append(rule)
                continue

            if item_type == "quote" and inject_truth:
                quote_rule = (
                    "Do not contradict the user-quoted text."
                    if force_en
                    else "不得与用户引用文本冲突。"
                )
                if quote_rule not in seen_constraints:
                    seen_constraints.add(quote_rule)
                    constraints.append(quote_rule)
                continue

        return (
            constraints[:_CONTEXT_MAX_CONSTRAINTS],
            world_truth[:_CONTEXT_MAX_WORLD_KNOWLEDGE],
            world_surface[:_CONTEXT_MAX_WORKING_SET],
        )

    def _build_consistency_rule(self, *, item_type: str, title: str, force_en: bool) -> str:
        safe_title = title or ("this profile" if force_en else "该档案")
        if item_type == "character":
            return (
                f"Character consistency: keep behavior and voice aligned with {safe_title}."
                if force_en
                else f"角色一致性：{safe_title} 的行为、语气、动机需前后一致。"
            )
        return (
            f"World consistency: keep rules in {safe_title} unchanged unless user requests."
            if force_en
            else f"设定一致性：遵守 {safe_title} 中的世界规则，除非用户明确要求修改。"
        )

    def _build_item_entry(self, *, title: str, snippet: str, force_en: bool) -> str:
        if title and snippet:
            return f"{title}: {snippet}" if force_en else f"{title}：{snippet}"
        return title or snippet

    def _normalize_text(self, text: str) -> str:
        return " ".join((text or "").split()).strip()

    def _truncate_text(self, text: str, max_chars: int) -> str:
        normalized = self._normalize_text(text)
        if max_chars <= 0 or len(normalized) <= max_chars:
            return normalized

        clipped = normalized[:max_chars]
        for sep in ("。", ".", "！", "!", "？", "?", "\n", "；", ";", "，", ",", " "):
            idx = clipped.rfind(sep)
            if idx > max_chars * 0.6:
                clipped = clipped[: idx + 1]
                break
        return clipped.rstrip() + "..."

    def _build_skill_catalog_section(
        self, skill_catalog: str, _force_en: bool
    ) -> list[str]:
        """Build skill catalog section for AI-driven selection."""
        return [
            "",
            skill_catalog,
        ]

    def _build_selected_skill_section(
        self,
        selected_skill: dict[str, Any],
        force_en: bool,
    ) -> list[str]:
        """Build the high-priority explicit skill section for this message."""
        skill_name = str(selected_skill.get("name") or "").strip()
        instructions = str(selected_skill.get("instructions") or "").strip()
        matched_text = str(selected_skill.get("matched_text") or "").strip()

        if not skill_name or not instructions:
            return []

        if force_en:
            lines = [
                "",
                "## User-Selected Skill For This Message",
                "",
                "The user explicitly selected the following skill at the start of the current message.",
                "Treat it as the user's direct choice for this turn and prioritize it over autonomous skill selection.",
            ]
            if matched_text:
                lines.append(f"Matched prefix: `{matched_text}`")
            lines.extend([
                "",
                f"### {skill_name}",
                "",
                instructions,
                "",
                "Requirements:",
                f"- Prioritize `{skill_name}` for this message unless a higher-priority safety/system rule conflicts.",
                f"- If you actually apply this skill, begin your reply with `[使用技能: {skill_name}]`.",
                "- Do not replace it with another skill just because another skill also seems relevant.",
            ])
            return lines

        lines = [
            "",
            "## 用户本条消息指定技能",
            "",
            "用户在本条消息开头显式指定了以下技能。",
            "将其视为用户对本轮请求的明确选择，并优先按该技能执行，而不是自行改选其他技能。",
        ]
        if matched_text:
            lines.append(f"匹配前缀：`{matched_text}`")
        lines.extend([
            "",
            f"### {skill_name}",
            "",
            instructions,
            "",
            "必须遵守：",
            f"- 本条消息优先使用「{skill_name}」技能；仅在更高优先级的系统/安全规则冲突时才可偏离。",
            f"- 如果你实际应用了该技能，必须在回复最开头输出 `[使用技能: {skill_name}]`。",
            "- 不要因为其他技能也相关，就忽略这次显式指定。",
        ])
        return lines

    def _build_skill_reference_section(
        self, skill_reference: str, _force_en: bool
    ) -> list[str]:
        """Build skill reference section with full instructions."""
        return [
            "",
            skill_reference,
        ]

    def _get_folder_ids(
        self,
        *,
        session: Session,
        project_type: str,
    ) -> dict[str, str]:
        """
        Resolve project root folder IDs for prompt placeholders.

        Args:
            session: Database session
            project_type: Type of project (novel, short, screenplay)

        Returns:
            Dict mapping folder types to their IDs
        """
        from sqlalchemy import func, or_

        from models import File

        def _norm(text: str | None) -> str:
            return "".join((text or "").split()).strip().lower()

        # Folder specs: (placeholder_key, deterministic_suffix, title_aliases)
        # - Deterministic ids come from current project template: {project_id}-{suffix}
        # - title_aliases handle legacy folder titles / language variants
        folder_specs_by_type: dict[str, list[tuple[str, str, list[str]]]] = {
            "novel": [
                ("lore", "lore-folder", ["设定", "世界观", "world building", "settings"]),
                ("character", "character-folder", ["角色", "人物", "characters"]),
                ("material", "material-folder", ["素材", "materials"]),
                ("outline", "outline-folder", ["大纲", "outlines"]),
                ("draft", "draft-folder", ["正文", "草稿", "drafts"]),
            ],
            "short": [
                ("character", "character-folder", ["人物", "角色", "characters"]),
                ("outline", "outline-folder", ["构思", "大纲", "concept", "outlines"]),
                ("material", "material-folder", ["素材", "materials"]),
                ("draft", "draft-folder", ["正文", "草稿", "drafts"]),
            ],
            "screenplay": [
                ("character", "character-folder", ["角色", "人物", "characters"]),
                # Legacy projects sometimes used "场景" as the settings folder.
                ("lore", "lore-folder", ["设定", "场景", "世界观", "world building", "settings", "scene", "scenes"]),
                ("material", "material-folder", ["素材", "materials"]),
                ("outline", "outline-folder", ["分集大纲", "大纲", "episodeoutlines", "outlines"]),
                ("script", "script-folder", ["剧本", "scripts"]),
            ],
        }

        folder_specs = folder_specs_by_type.get(project_type) or folder_specs_by_type["novel"]

        # Fetch existing root folders.
        #
        # NOTE: Some legacy imports/migrations stored root folders with parent_id=""
        # instead of NULL, so we treat both as "root" here.
        root_folders = session.exec(
            select(File).where(
                File.project_id == self.project_id,
                File.file_type == "folder",
                File.is_deleted.is_(False),
                or_(File.parent_id.is_(None), File.parent_id == ""),
            )
        ).all()

        root_ids = [f.id for f in root_folders if getattr(f, "id", None)]
        child_counts: dict[str, int] = {}
        child_type_counts: dict[str, dict[str, int]] = {}
        if root_ids:
            typed_rows = session.exec(
                select(File.parent_id, File.file_type, func.count(File.id))
                .where(
                    File.project_id == self.project_id,
                    File.is_deleted.is_(False),
                    File.parent_id.in_(root_ids),
                )
                .group_by(File.parent_id, File.file_type)
            ).all()
            for parent_id, file_type, count in typed_rows:
                if not parent_id:
                    continue
                parent_key = str(parent_id)
                child_counts[parent_key] = child_counts.get(parent_key, 0) + int(count or 0)
                if not file_type:
                    continue
                bucket = child_type_counts.setdefault(parent_key, {})
                bucket[str(file_type)] = int(count or 0)

        def _pick_folder_id(key: str, suffix: str, aliases: list[str]) -> str:
            deterministic_id = f"{self.project_id}-{suffix}"
            alias_norms = [_norm(a) for a in aliases if a]

            expected_child_type_by_key = {
                "character": "character",
                "lore": "lore",
                "outline": "outline",
                "draft": "draft",
                "script": "script",
                "material": "snippet",
            }
            expected_child_type = expected_child_type_by_key.get(key, "")

            # 1) Prefer the root folder that already contains the most children
            #    of the expected file_type. This is the most robust signal for
            #    legacy projects where folder titles / ids were inconsistent.
            if expected_child_type and child_type_counts:
                best_typed: File | None = None
                best_score: tuple[int, int, int, str] | None = None
                for folder in root_folders:
                    folder_id = str(folder.id)
                    typed_count = child_type_counts.get(folder_id, {}).get(expected_child_type, 0)
                    if typed_count <= 0:
                        continue
                    total_children = child_counts.get(folder_id, 0)
                    deterministic_bonus = 1 if folder_id == deterministic_id else 0
                    score = (typed_count, total_children, deterministic_bonus, folder_id)
                    if best_score is None or score > best_score:
                        best_score = score
                        best_typed = folder

                if best_typed is not None:
                    return str(best_typed.id)

            # 2) Otherwise fall back to title heuristics + deterministic id.
            candidates: list[File] = []
            for folder in root_folders:
                folder_id = str(folder.id)
                if folder_id == deterministic_id:
                    candidates.append(folder)
                    continue

                title_norm = _norm(getattr(folder, "title", ""))
                if not title_norm:
                    continue
                if any(alias and alias in title_norm for alias in alias_norms):
                    candidates.append(folder)

            if not candidates:
                return deterministic_id

            def _score(folder: File) -> tuple[int, int, str]:
                folder_id = str(folder.id)
                return (
                    child_counts.get(folder_id, 0),
                    1 if folder_id == deterministic_id else 0,
                    folder_id,
                )

            best = max(candidates, key=_score)

            resolved_id = str(best.id)
            if resolved_id != deterministic_id:
                log_with_context(
                    logger,
                    20,  # INFO
                    "Resolved legacy root folder id for prompt placeholder",
                    project_id=self.project_id,
                    user_id=self.user_id,
                    project_type=project_type,
                    folder_key=key,
                    resolved_folder_id=resolved_id,
                    deterministic_folder_id=deterministic_id,
                    resolved_title=getattr(best, "title", ""),
                    resolved_child_count=child_counts.get(resolved_id, 0),
                )

            return resolved_id

        folder_ids: dict[str, str] = {}
        for key, suffix, aliases in folder_specs:
            folder_ids[key] = _pick_folder_id(key, suffix, aliases)

        return folder_ids
