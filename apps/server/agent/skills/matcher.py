"""
Skill matcher for detecting and matching skills from user input.

Matches user messages against skill triggers to determine which
skills should be activated. Supports semantic matching with synonyms
and fuzzy matching for better user experience.

Supports multi-skill activation for complex requests (e.g., "create a character
and write their entrance scene" -> activates both "create-character" and "describe-scene").
"""

from utils.logger import get_logger, log_with_context

from .loader import get_builtin_skills
from .schemas import Skill, SkillMatch

logger = get_logger(__name__)

# Default confidence threshold for fuzzy matches
DEFAULT_CONFIDENCE_THRESHOLD = 0.6

# Maximum number of skills that can be activated simultaneously
MAX_ACTIVE_SKILLS = 3

# Synonym mappings for semantic matching
# Maps alternative terms to canonical terms used in triggers
SYNONYM_MAP: dict[str, list[str]] = {
    # 角色相关
    "角色": ["人物", "角色", "主角", "配角", "人设"],
    "人物": ["角色", "人物", "主角", "配角", "人设"],
    # 大纲相关
    "大纲": ["提纲", "框架", "纲要", "结构", "大纲"],
    "提纲": ["大纲", "框架", "纲要", "结构", "提纲"],
    "框架": ["大纲", "提纲", "纲要", "结构", "框架"],
    # 世界观相关
    "世界观": ["世界设定", "背景", "设定", "世界观"],
    "设定": ["世界观", "背景", "设定集", "设定"],
    # 动作词相关
    "创建": ["新建", "创建", "写", "设计", "添加", "做", "弄"],
    "新建": ["创建", "新建", "写", "设计", "添加", "做", "弄"],
    "写": ["创建", "新建", "写", "设计", "添加", "做", "弄"],
    "设计": ["创建", "新建", "写", "设计", "添加", "做", "弄"],
    "添加": ["创建", "新建", "写", "设计", "添加", "做", "弄"],
}

# Action words that can combine with nouns for fuzzy matching
ACTION_WORDS = ["创建", "新建", "写", "设计", "添加", "做", "弄", "帮我", "给我"]

# Noun mappings for fuzzy matching (noun -> skill trigger patterns)
NOUN_TO_TRIGGERS: dict[str, list[str]] = {
    "角色": ["创建角色", "新建角色", "设计角色", "角色设定"],
    "人物": ["创建角色", "新建角色", "设计角色", "角色设定"],
    "大纲": ["创建大纲", "写大纲", "故事大纲", "章节大纲"],
    "提纲": ["创建大纲", "写大纲", "故事大纲", "章节大纲"],
    "框架": ["创建大纲", "写大纲", "故事大纲"],
    "世界观": ["世界观", "世界设定", "背景设定"],
    "世界": ["世界观", "世界设定", "创建世界"],
    "背景": ["背景设定", "世界设定"],
}


def match_skills(
    user_message: str,
    user_skills: list[Skill] | None = None,
    confidence_threshold: float = DEFAULT_CONFIDENCE_THRESHOLD,
    max_skills: int = MAX_ACTIVE_SKILLS,
) -> list[SkillMatch]:
    """
    Match user message against available skills.

    User skills take priority over builtin skills when names match.
    Supports exact matching (confidence=1.0), synonym matching (0.9),
    and fuzzy matching (0.7-0.8).

    Supports multi-skill activation: when a user message contains multiple
    intents (e.g., "create a character and write their entrance scene"),
    multiple skills can be matched and returned.

    Args:
        user_message: The user's input message
        user_skills: Optional list of user-defined skills
        confidence_threshold: Minimum confidence for a match (default 0.6)
        max_skills: Maximum number of skills to return (default 3)

    Returns:
        List of matched skills, sorted by confidence (exact matches first),
        limited to max_skills entries
    """
    matches: list[SkillMatch] = []
    message_lower = user_message.lower()

    # Combine skills with user skills taking priority
    all_skills = _merge_skills(user_skills)

    for skill in all_skills:
        match = _match_skill(skill, message_lower)
        if match and match.confidence >= confidence_threshold:
            matches.append(match)

    # Sort by confidence (highest first), exact matches come first
    matches.sort(key=lambda m: m.confidence, reverse=True)

    # Limit to max_skills
    matches = matches[:max_skills]

    if matches:
        log_with_context(
            logger, 20, "Skills matched",
            matched_count=len(matches),
            skill_names=[m.skill.name for m in matches],
            top_confidence=matches[0].confidence if matches else None,
        )

    return matches


def _merge_skills(user_skills: list[Skill] | None) -> list[Skill]:
    """
    Merge user skills with builtin skills.

    User skills override builtin skills with the same ID.
    """
    builtin = get_builtin_skills()

    if not user_skills:
        return builtin

    # Create a dict of user skills by ID for quick lookup
    user_skill_ids = {s.id for s in user_skills}

    # Filter out builtin skills that are overridden by user skills
    merged = [s for s in builtin if s.id not in user_skill_ids]

    # Add user skills (they take priority)
    merged.extend(user_skills)

    return merged


def _match_skill(skill: Skill, message_lower: str) -> SkillMatch | None:
    """
    Check if a skill matches the user message.

    Matching priority:
    1. Exact match (confidence=1.0) - trigger found exactly in message
    2. Synonym match (confidence=0.9) - synonym of trigger found
    3. Fuzzy match (confidence=0.7-0.8) - action+noun pattern detected

    Returns a SkillMatch if any match is found, None otherwise.
    """
    # 1. Try exact match first (highest priority)
    exact_match = _try_exact_match(skill, message_lower)
    if exact_match:
        return exact_match

    # 2. Try synonym match
    synonym_match = _try_synonym_match(skill, message_lower)
    if synonym_match:
        return synonym_match

    # 3. Try fuzzy match (action + noun pattern)
    fuzzy_match = _try_fuzzy_match(skill, message_lower)
    if fuzzy_match:
        return fuzzy_match

    return None


def _try_exact_match(skill: Skill, message_lower: str) -> SkillMatch | None:
    """Try exact trigger matching."""
    for trigger in skill.triggers:
        trigger_lower = trigger.lower()
        if trigger_lower in message_lower:
            return SkillMatch(
                skill=skill,
                matched_trigger=trigger,
                confidence=1.0,
            )
    return None


def _try_synonym_match(skill: Skill, message_lower: str) -> SkillMatch | None:
    """Try matching using synonym mappings."""
    for trigger in skill.triggers:
        trigger_lower = trigger.lower()
        # Check each word in the trigger for synonyms
        for word in _extract_words(trigger_lower):
            if word in SYNONYM_MAP:
                for synonym in SYNONYM_MAP[word]:
                    # Build alternative trigger with synonym
                    alt_trigger = trigger_lower.replace(word, synonym)
                    if alt_trigger != trigger_lower and alt_trigger in message_lower:
                        return SkillMatch(
                            skill=skill,
                            matched_trigger=f"{trigger} (via {synonym})",
                            confidence=0.9,
                        )
    return None


def _try_fuzzy_match(skill: Skill, message_lower: str) -> SkillMatch | None:
    """Try fuzzy matching using action+noun patterns."""
    # Check if message contains action words
    has_action = any(action in message_lower for action in ACTION_WORDS)

    if not has_action:
        return None

    # Check if any noun maps to this skill's triggers
    for noun, related_triggers in NOUN_TO_TRIGGERS.items():
        if noun in message_lower:
            # Check if any of the related triggers match this skill
            for trigger in skill.triggers:
                if trigger in related_triggers:
                    return SkillMatch(
                        skill=skill,
                        matched_trigger=f"{trigger} (fuzzy: {noun})",
                        confidence=0.8,
                    )
    return None


def _extract_words(text: str) -> list[str]:
    """Extract meaningful words from text for synonym matching."""
    # For Chinese text, we do simple character-based extraction
    # This handles common 2-character words
    words = []
    i = 0
    while i < len(text):
        # Try 2-character words first (common in Chinese)
        if i + 2 <= len(text):
            two_char = text[i:i+2]
            if two_char in SYNONYM_MAP:
                words.append(two_char)
                i += 2
                continue
        # Single character
        if text[i] in SYNONYM_MAP:
            words.append(text[i])
        i += 1
    return words
