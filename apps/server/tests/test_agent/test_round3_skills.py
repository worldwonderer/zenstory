"""
第三轮深度 review 回归测试：技能系统（G12）。

覆盖两条确认缺陷：
- #25 SKILL.md 解析器把正文（尤其是代码围栏内）的 `## ` 行当成节标题静默丢弃，
  导致内置技能的「输出格式」模板被吃掉。
- #26 技能目录宣告全部技能、技能手册只注入前若干个，
  「宣告的能力」与「实际注入的指令」脱节；且技能查询没有 order_by，生效子集会漂移。
"""

from datetime import datetime

import pytest
from sqlmodel import Session

from agent.skills.context_injector import SkillContextInjector
from agent.skills.loader import (
    load_builtin_skills,
    parse_zenstory_format,
    reload_builtin_skills,
)
from models import PublicSkill, User, UserAddedSkill, UserSkill


@pytest.fixture
def skill_user(db_session: Session) -> User:
    user = User(
        email="round3_skills@example.com",
        username="round3skills",
        hashed_password="hashed_password",
        email_verified=True,
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


# ============================================================================
# #25 SKILL.md 解析器
# ============================================================================


@pytest.mark.unit
class TestBug25SkillMarkdownParsing:
    """解析器必须区分「结构性节标题」与「正文里的 markdown 内容」。"""

    @pytest.mark.parametrize(
        ("skill_id", "expected_headings"),
        [
            (
                "create-character",
                ["## 基本信息", "## 外貌特征", "## 性格特点", "## 背景故事",
                 "## 人物关系", "## 角色弧光"],
            ),
            (
                "create-outline",
                ["## 故事概念", "## 三幕结构", "## 章节规划", "## 伏笔与呼应"],
            ),
            (
                "worldbuilding",
                ["## 世界概述", "## 核心规则", "## 社会结构", "## 主要地点",
                 "## 历史大事记"],
            ),
        ],
    )
    def test_builtin_skill_output_templates_survive_parsing(
        self, skill_id: str, expected_headings: list[str]
    ):
        """三个内置技能的输出格式模板（代码围栏内的二级标题）必须完整保留。"""
        reload_builtin_skills()
        skills = {s.id: s for s in load_builtin_skills()}
        skill = skills.get(skill_id)
        assert skill is not None, f"内置技能 {skill_id} 未能加载"

        for heading in expected_headings:
            assert heading in skill.instructions, (
                f"{skill_id} 的输出模板丢失了小节标题 {heading!r}"
            )

    def test_headings_inside_code_fence_are_preserved(self):
        """代码围栏内的 `## ` 行是正文模板，不能被当作节标题吞掉。"""
        content = """# 模板技能

一句话描述。

## Triggers
- 模板

## Instructions
按以下格式输出：

```
# [标题]

## 小节甲
（说明甲）

## 小节乙
（说明乙）
```

结束。"""
        skill = parse_zenstory_format(content, "template.md")

        assert skill is not None
        assert "## 小节甲" in skill.instructions
        assert "## 小节乙" in skill.instructions
        assert "# [标题]" in skill.instructions
        # 围栏内的内容顺序也必须保持
        assert skill.instructions.index("## 小节甲") < skill.instructions.index("（说明甲）")

    def test_unknown_heading_in_instructions_body_is_preserved(self):
        """instructions 正文里未识别的二级标题（围栏外）同样属于正文，必须保留。"""
        content = """# 普通技能

描述。

## Instructions
开头段落。

## 注意事项
不要跑题。"""
        skill = parse_zenstory_format(content, "plain.md")

        assert skill is not None
        assert "## 注意事项" in skill.instructions
        assert "不要跑题。" in skill.instructions

    def test_known_section_headers_still_switch_sections(self):
        """白名单节标题（Triggers / Instructions）仍然是结构性的，不能被当成正文。"""
        content = """# 结构技能

一句话描述。

## Triggers
- 触发词甲
- 触发词乙

## Instructions
真正的指令。"""
        skill = parse_zenstory_format(content, "structured.md")

        assert skill is not None
        assert skill.name == "结构技能"
        assert skill.description == "一句话描述。"
        assert skill.triggers == ["触发词甲", "触发词乙"]
        assert skill.instructions == "真正的指令。"
        assert "## Triggers" not in skill.instructions
        assert "## Instructions" not in skill.instructions

    def test_tilde_fence_is_tracked(self):
        """`~~~` 围栏同样要被识别。"""
        content = """# 波浪线围栏

描述。

## Instructions
示例：

~~~
## 围栏内标题
内容
~~~
"""
        skill = parse_zenstory_format(content, "tilde.md")

        assert skill is not None
        assert "## 围栏内标题" in skill.instructions

    def test_unclosed_fence_does_not_swallow_section_headers(self):
        """未闭合的围栏（笔误）不能把后面的 `## Instructions` 节标题一起吞掉。"""
        content = """# 笔误技能

描述里有个没闭合的围栏：

```

## Triggers
- 触发词

## Instructions
真正的指令。"""
        skill = parse_zenstory_format(content, "unclosed.md")

        assert skill is not None
        assert skill.triggers == ["触发词"]
        assert skill.instructions == "真正的指令。"


# ============================================================================
# #26 技能目录 / 技能手册一致性
# ============================================================================


def _add_user_skills(
    session: Session,
    user_id: str,
    count: int,
    instruction_chars: int = 1500,
) -> list[UserSkill]:
    """批量创建自建技能，指令开头带唯一标记便于断言。"""
    created: list[UserSkill] = []
    for index in range(count):
        marker = f"MARKER{index:02d}"
        skill = UserSkill(
            user_id=user_id,
            name=f"技能{index:02d}",
            description=f"描述{index:02d}",
            instructions=marker + ("填充" * instruction_chars),
            created_at=datetime(2026, 1, 1, 0, index),
        )
        session.add(skill)
        created.append(skill)
    session.commit()
    return created


def _catalog_section_names(catalog: str, heading: str) -> list[str]:
    """从技能目录里取出指定小节下的技能名（`- **名字**: 描述` 行）。"""
    names: list[str] = []
    in_section = False
    for line in catalog.split("\n"):
        stripped = line.strip()
        if stripped.startswith("### "):
            in_section = stripped[4:].strip() == heading
            continue
        if in_section and stripped.startswith("- **"):
            names.append(stripped[4:].split("**", 1)[0])
    return names


@pytest.mark.unit
class TestBug26CatalogReferenceConsistency:
    """技能目录宣告的「可直接应用」必须与技能手册实际注入的内容同源。"""

    def test_catalog_only_declares_skills_whose_instructions_were_injected(
        self, db_session: Session, skill_user: User
    ):
        _add_user_skills(db_session, skill_user.id, count=13)

        injector = SkillContextInjector()
        catalog = injector.build_skill_catalog(db_session, skill_user.id)
        reference = injector.build_skill_reference(db_session, skill_user.id)

        assert catalog is not None
        assert reference is not None

        applicable = _catalog_section_names(catalog, "可直接应用")
        deferred = _catalog_section_names(catalog, "需显式调用")

        # 目录仍然覆盖全部技能，只是分成两类
        assert len(applicable) + len(deferred) == 13
        assert applicable, "至少应有技能真正注入了指令"
        assert deferred, "预算不足时其余技能必须被明确标注为「需显式调用」"

        # 宣告为「可直接应用」的每一个技能，其指令都必须真的出现在手册里
        for name in applicable:
            index = int(name.replace("技能", ""))
            assert f"MARKER{index:02d}" in reference, (
                f"{name} 被宣告可直接应用，但其指令从未进入技能手册"
            )

        # 没注入的技能不得出现在手册里
        for name in deferred:
            index = int(name.replace("技能", ""))
            assert f"MARKER{index:02d}" not in reference

    def test_deferred_section_tells_model_how_to_load_them(
        self, db_session: Session, skill_user: User
    ):
        _add_user_skills(db_session, skill_user.id, count=13)

        injector = SkillContextInjector()
        catalog = injector.build_skill_catalog(db_session, skill_user.id)

        assert catalog is not None
        assert "需显式调用" in catalog
        # 必须给出可执行的加载方式（消息开头写技能名 -> explicit_resolver）
        assert "消息开头" in catalog

    def test_all_skills_directly_applicable_when_budget_allows(
        self, db_session: Session, skill_user: User
    ):
        """预算足够时不应出现「需显式调用」小节，避免无谓的提示噪音。"""
        _add_user_skills(db_session, skill_user.id, count=3, instruction_chars=50)

        injector = SkillContextInjector()
        catalog = injector.build_skill_catalog(db_session, skill_user.id)
        reference = injector.build_skill_reference(db_session, skill_user.id)

        assert catalog is not None
        assert reference is not None
        assert _catalog_section_names(catalog, "可直接应用") == ["技能00", "技能01", "技能02"]
        assert "需显式调用" not in catalog
        for index in range(3):
            assert f"MARKER{index:02d}" in reference

    def test_user_skills_are_loaded_in_deterministic_order(
        self, db_session: Session, skill_user: User
    ):
        """自建技能按 created_at 排序，避免数据库返回顺序漂移导致生效子集变化。"""
        later = UserSkill(
            user_id=skill_user.id,
            name="后创建",
            description="后",
            instructions="后创建的指令",
            created_at=datetime(2026, 5, 1),
        )
        earlier = UserSkill(
            user_id=skill_user.id,
            name="先创建",
            description="先",
            instructions="先创建的指令",
            created_at=datetime(2026, 1, 1),
        )
        # 故意按「后创建」在前的顺序插入，模拟数据库堆顺序与业务顺序不一致
        db_session.add(later)
        db_session.commit()
        db_session.add(earlier)
        db_session.commit()

        injector = SkillContextInjector()
        skills = injector._load_user_skills(db_session, skill_user.id)

        assert [s["name"] for s in skills] == ["先创建", "后创建"]

    def test_added_public_skills_are_loaded_in_deterministic_order(
        self, db_session: Session, skill_user: User
    ):
        """已添加的公共技能按 added_at 排序。"""
        for name in ("公共甲", "公共乙"):
            db_session.add(
                PublicSkill(
                    id=f"public-{name}",
                    name=name,
                    description=name,
                    instructions=f"{name}的指令",
                    status="approved",
                )
            )
        db_session.commit()

        db_session.add(
            UserAddedSkill(
                user_id=skill_user.id,
                public_skill_id="public-公共乙",
                added_at=datetime(2026, 5, 1),
            )
        )
        db_session.commit()
        db_session.add(
            UserAddedSkill(
                user_id=skill_user.id,
                public_skill_id="public-公共甲",
                added_at=datetime(2026, 1, 1),
            )
        )
        db_session.commit()

        injector = SkillContextInjector()
        skills = injector._load_user_skills(db_session, skill_user.id)

        assert [s["name"] for s in skills] == ["公共甲", "公共乙"]

    def test_skill_without_instructions_is_never_declared_applicable(
        self, db_session: Session, skill_user: User
    ):
        """指令为空的技能没有任何可注入内容，不能被宣告为「可直接应用」。"""
        db_session.add(
            UserSkill(
                user_id=skill_user.id,
                name="空技能",
                description="没有指令",
                instructions="   ",
                created_at=datetime(2026, 1, 1),
            )
        )
        db_session.add(
            UserSkill(
                user_id=skill_user.id,
                name="正常技能",
                description="有指令",
                instructions="MARKER-OK 正常的指令内容",
                created_at=datetime(2026, 1, 2),
            )
        )
        db_session.commit()

        injector = SkillContextInjector()
        catalog = injector.build_skill_catalog(db_session, skill_user.id)
        reference = injector.build_skill_reference(db_session, skill_user.id)

        assert catalog is not None
        assert reference is not None
        assert _catalog_section_names(catalog, "可直接应用") == ["正常技能"]
        assert "空技能" in _catalog_section_names(catalog, "需显式调用")
        assert "MARKER-OK" in reference
