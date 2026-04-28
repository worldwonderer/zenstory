"""
Skills system for the AI writing assistant.

Provides skill loading, matching, and injection into system prompts.
"""

from .context_injector import SkillContextInjector, get_skill_context_injector
from .loader import get_builtin_skills, get_cache_stats, reload_builtin_skills
from .matcher import match_skills
from .schemas import Skill, SkillMatch, SkillSource
from .user_skill_service import get_user_skills

__all__ = [
    "Skill",
    "SkillMatch",
    "SkillSource",
    "get_builtin_skills",
    "reload_builtin_skills",
    "get_cache_stats",
    "match_skills",
    "get_user_skills",
    "SkillContextInjector",
    "get_skill_context_injector",
]
