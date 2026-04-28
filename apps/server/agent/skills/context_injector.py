"""
Skill context injector for AI-driven skill selection.

Instead of trigger-word matching, this module builds a skill catalog
that is injected into the AI's system prompt, allowing the AI to
autonomously decide when to apply skills.
"""

from sqlmodel import Session, select

from models import PublicSkill, UserAddedSkill, UserSkill
from utils.logger import get_logger, log_with_context

logger = get_logger(__name__)


class SkillContextInjector:
    """
    Builds skill context for injection into AI system prompt.

    The AI receives a catalog of available skills and their descriptions,
    then autonomously decides when to apply them based on user requests.
    """

    def build_skill_catalog(
        self,
        session: Session,
        user_id: str | None,
    ) -> str | None:
        """
        Build a concise skill catalog for the system prompt.

        Returns a formatted string listing available skills with their
        names and brief descriptions. Returns None if no skills available.

        Args:
            session: Database session
            user_id: User ID to load skills for

        Returns:
            Formatted skill catalog string or None
        """
        if not user_id:
            return None

        skills = self._load_user_skills(session, user_id)

        if not skills:
            return None

        # Build catalog
        lines = [
            "## 可用写作技能",
            "",
            "你有以下专业技能可用。当用户请求与某技能用途匹配时，应用该技能的方法。",
            "",
        ]

        for skill in skills:
            name = skill["name"]
            desc = skill["description"] or "专业写作辅助"
            lines.append(f"- **{name}**: {desc}")

        lines.extend([
            "",
            "当识别到匹配的技能时，自然地将其方法融入你的回复中。",
            "",
            "**重要：技能使用标记**",
            "当你应用上述任何技能时，必须在回复的最开头添加标记：",
            "`[使用技能: 技能名称]`",
            "",
            "示例：如果你应用了「悬念大师」技能，回复开头应为：",
            "`[使用技能: 悬念大师]`",
            "",
            "注意：",
            "- 仅在实际应用技能方法时添加标记",
            "- 如果未应用任何技能，不要添加标记",
            "- 标记必须放在回复最开头，然后换行继续正文",
        ])

        log_with_context(
            logger, 20, "Built skill catalog",
            user_id=user_id,
            skill_count=len(skills),
        )

        return "\n".join(lines)

    def get_skill_instructions(
        self,
        session: Session,
        user_id: str | None,
    ) -> dict[str, str]:
        """
        Get full skill instructions as a lookup dictionary.

        Returns a dict mapping skill names to their full instructions.
        The AI can reference these when it decides to apply a skill.

        Args:
            session: Database session
            user_id: User ID to load skills for

        Returns:
            Dict mapping skill name to instructions
        """
        if not user_id:
            return {}

        skills = self._load_user_skills(session, user_id)
        return {s["name"]: s["instructions"] for s in skills}

    def build_skill_reference(
        self,
        session: Session,
        user_id: str | None,
        max_skills: int = 8,
        max_instruction_chars: int = 4000,
    ) -> str | None:
        """
        Build full skill reference with instructions.

        This is a more detailed version that includes full instructions
        for each skill. Use when context budget allows.

        Args:
            session: Database session
            user_id: User ID to load skills for

        Returns:
            Formatted skill reference string or None
        """
        if not user_id:
            return None

        skills = self._load_user_skills(session, user_id)

        if not skills:
            return None

        if len(skills) > max_skills:
            return None

        total_instruction_chars = sum(len(s["instructions"] or "") for s in skills)
        if total_instruction_chars > max_instruction_chars:
            return None

        lines = [
            "## 技能参考手册",
            "",
            "以下是你可用的专业写作技能及其详细指令：",
            "",
        ]

        for skill in skills:
            name = skill["name"]
            desc = skill["description"] or ""
            instructions = skill["instructions"]

            lines.extend([
                f"### {name}",
                "",
            ])

            if desc:
                lines.append(f"*{desc}*")
                lines.append("")

            lines.append(instructions)
            lines.extend(["", "---", ""])

        return "\n".join(lines)

    def _load_user_skills(
        self,
        session: Session,
        user_id: str,
    ) -> list[dict]:
        """
        Load all skills available to a user.

        Combines:
        1. User's custom skills (UserSkill)
        2. User's added public skills (UserAddedSkill -> PublicSkill)

        Args:
            session: Database session
            user_id: User ID

        Returns:
            List of skill dicts with name, description, instructions
        """
        skills = []

        # Load user's custom skills
        user_stmt = select(UserSkill).where(
            UserSkill.user_id == user_id,
            UserSkill.is_active,
        )
        user_skills = session.exec(user_stmt).all()

        for skill in user_skills:
            skills.append({
                "id": skill.id,
                "name": skill.name,
                "description": skill.description,
                "instructions": skill.instructions,
                "source": "user",
            })

        # Load user's added public skills
        added_stmt = select(UserAddedSkill, PublicSkill).join(
            PublicSkill, UserAddedSkill.public_skill_id == PublicSkill.id
        ).where(
            UserAddedSkill.user_id == user_id,
            UserAddedSkill.is_active,
            PublicSkill.status == "approved",
        )
        added_results = session.exec(added_stmt).all()

        for added, public in added_results:
            skills.append({
                "id": public.id,
                "name": added.custom_name or public.name,
                "description": public.description,
                "instructions": public.instructions,
                "source": "added",
            })

        return skills


# Singleton instance
_injector: SkillContextInjector | None = None


def get_skill_context_injector() -> SkillContextInjector:
    """Get singleton skill context injector."""
    global _injector
    if _injector is None:
        _injector = SkillContextInjector()
    return _injector
