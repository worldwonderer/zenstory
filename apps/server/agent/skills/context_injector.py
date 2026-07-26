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

# 技能手册（reference）的注入预算默认值。
# 目录（catalog）与手册必须共用同一份预算参数，否则会出现
# 「目录宣告全部技能可用，手册只注入了前几个」的谎报。
DEFAULT_MAX_SKILLS = 8
DEFAULT_MAX_INSTRUCTION_CHARS = 4000

# 单个技能进入手册所需的最小剩余预算。
# 只剩几十上百字符时塞进去的是残片，对模型没有指导价值，
# 却会让目录把该技能宣告成「可直接应用」，属于更糟的谎报。
MIN_USEFUL_INSTRUCTION_CHARS = 300

# 目录中两类技能的小节标题（回归测试按此解析，改动需同步测试）
CATALOG_SECTION_APPLICABLE = "可直接应用"
CATALOG_SECTION_DEFERRED = "需显式调用"


def select_injected_skills(
    skills: list[dict],
    max_skills: int = DEFAULT_MAX_SKILLS,
    max_instruction_chars: int = DEFAULT_MAX_INSTRUCTION_CHARS,
) -> tuple[list[dict], list[dict]]:
    """
    在预算内挑出「真正会把完整指令注入 prompt」的技能。

    这是技能目录与技能参考手册唯一的筛选入口：两个注入面必须消费同一份结果，
    否则会出现「目录宣告 13 个技能可用、手册只注入了 3 个」的谎报——
    模型据此声明使用了某技能，实际却从未见过该技能的任何指令。

    Args:
        skills: _load_user_skills 返回的技能列表（顺序必须是确定的）
        max_skills: 最多注入几个技能
        max_instruction_chars: 指令总字符预算

    Returns:
        (injected, deferred) 两个列表。
        injected 元素为 {"skill": 原始 dict, "instructions": 实际注入文本, "truncated": bool}；
        deferred 元素为 {"skill": 原始 dict, "reason": 未注入原因}。
    """
    injected: list[dict] = []
    deferred: list[dict] = []

    remaining = max_instruction_chars

    for skill in skills:
        instructions = (skill.get("instructions") or "").strip()

        # 没有指令的技能本身就没有任何可注入内容，不能宣称「可直接应用」
        if not instructions:
            deferred.append({"skill": skill, "reason": "empty_instructions"})
            continue

        if len(injected) >= max_skills:
            deferred.append({"skill": skill, "reason": "max_skills"})
            continue

        # 剩余预算不足以承载一段有意义的指令时，宁可整条不注入，
        # 也不要塞一个几十字的残片再对模型宣称该技能可用。
        if remaining < min(MIN_USEFUL_INSTRUCTION_CHARS, len(instructions)):
            deferred.append({"skill": skill, "reason": "budget_exhausted"})
            continue

        truncated = len(instructions) > remaining
        if truncated:
            instructions = instructions[:remaining].rstrip() + "…"
        remaining -= len(instructions)

        injected.append({
            "skill": skill,
            "instructions": instructions,
            "truncated": truncated,
        })

    return injected, deferred


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
        max_skills: int = DEFAULT_MAX_SKILLS,
        max_instruction_chars: int = DEFAULT_MAX_INSTRUCTION_CHARS,
    ) -> str | None:
        """
        Build a concise skill catalog for the system prompt.

        目录必须与《技能参考手册》同源：用同一份筛选结果，把技能分成
        「本轮已注入完整指令、可直接应用」与「本轮未注入、需显式调用」两类，
        避免模型以为某技能可用、实际却一个字的指令都没拿到。

        Args:
            session: Database session
            user_id: User ID to load skills for
            max_skills: 手册最多注入几个技能（必须与 build_skill_reference 一致）
            max_instruction_chars: 手册指令总字符预算（必须与 build_skill_reference 一致）

        Returns:
            Formatted skill catalog string or None
        """
        if not user_id:
            return None

        skills = self._load_user_skills(session, user_id)

        if not skills:
            return None

        injected, deferred = select_injected_skills(
            skills,
            max_skills=max_skills,
            max_instruction_chars=max_instruction_chars,
        )

        # Build catalog
        lines = [
            "## 可用写作技能",
            "",
            "你有以下专业技能可用。当用户请求与某技能用途匹配时，应用该技能的方法。",
            "",
        ]

        if injected:
            lines.extend([
                f"### {CATALOG_SECTION_APPLICABLE}",
                "",
                "以下技能的完整指令已随本次对话注入（见《技能参考手册》），可直接按其方法执行：",
                "",
            ])
            for item in injected:
                skill = item["skill"]
                name = skill["name"]
                desc = skill["description"] or "专业写作辅助"
                suffix = "（指令较长，手册中已截断）" if item["truncated"] else ""
                lines.append(f"- **{name}**: {desc}{suffix}")
            lines.append("")

        if deferred:
            lines.extend([
                f"### {CATALOG_SECTION_DEFERRED}",
                "",
                "以下技能本轮受上下文预算限制未注入详细指令，你只知道它们的用途、不知道其具体方法。"
                "不要凭空臆造其做法；如果需要使用，请提示用户在消息开头写出该技能名称"
                "（例如「悬念大师 帮我写……」），系统会为那条消息加载它的完整指令。",
                "",
            ])
            for item in deferred:
                skill = item["skill"]
                name = skill["name"]
                desc = skill["description"] or "专业写作辅助"
                lines.append(f"- **{name}**: {desc}")
            lines.append("")

        lines.extend([
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
            injected_count=len(injected),
            deferred_count=len(deferred),
            deferred_skills=[item["skill"]["name"] for item in deferred],
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

        Note:
            这是一个查表接口，返回用户全部技能，不参与 system prompt 的预算裁剪。
            真正注入 prompt 的两个面（目录 / 手册）请走 select_injected_skills。
        """
        if not user_id:
            return {}

        skills = self._load_user_skills(session, user_id)
        return {s["name"]: s["instructions"] for s in skills}

    def build_skill_reference(
        self,
        session: Session,
        user_id: str | None,
        max_skills: int = DEFAULT_MAX_SKILLS,
        max_instruction_chars: int = DEFAULT_MAX_INSTRUCTION_CHARS,
    ) -> str | None:
        """
        Build full skill reference with instructions.

        This is a more detailed version that includes full instructions
        for each skill. Use when context budget allows.

        与 build_skill_catalog 共用 select_injected_skills 的筛选结果：
        目录里被列为「可直接应用」的技能，必然且仅有它们出现在这里。

        Args:
            session: Database session
            user_id: User ID to load skills for
            max_skills: 最多注入几个技能（必须与 build_skill_catalog 一致）
            max_instruction_chars: 指令总字符预算（必须与 build_skill_catalog 一致）

        Returns:
            Formatted skill reference string or None
        """
        if not user_id:
            return None

        skills = self._load_user_skills(session, user_id)

        if not skills:
            return None

        injected, _deferred = select_injected_skills(
            skills,
            max_skills=max_skills,
            max_instruction_chars=max_instruction_chars,
        )

        if not injected:
            return None

        lines = [
            "## 技能参考手册",
            "",
            "以下是你可用的专业写作技能及其详细指令：",
            "",
        ]

        for item in injected:
            skill = item["skill"]
            name = skill["name"]
            desc = skill["description"] or ""

            lines.extend([
                f"### {name}",
                "",
            ])

            if desc:
                lines.append(f"*{desc}*")
                lines.append("")

            lines.append(item["instructions"])
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
        # order_by 不可省：没有它时返回顺序由数据库堆序决定，
        # PostgreSQL 上任何一次 UPDATE 都会把元组重写到堆尾，
        # 导致「哪些技能进预算」在用户编辑技能后无声漂移。
        user_stmt = select(UserSkill).where(
            UserSkill.user_id == user_id,
            UserSkill.is_active,
        ).order_by(UserSkill.created_at, UserSkill.id)
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
        ).order_by(UserAddedSkill.added_at, UserAddedSkill.id)
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
