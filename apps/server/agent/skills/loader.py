"""
Skill loader for parsing SKILL.md files.

Supports two formats:
1. zenstory native format (## Triggers / ## Instructions sections)
2. OpenViking format (YAML frontmatter + markdown body)
"""

import asyncio
import re
import time
from collections import OrderedDict
from pathlib import Path
from typing import Any

import yaml

from utils.logger import get_logger, log_with_context

from .schemas import Skill, SkillFrontmatter, SkillSource

logger = get_logger(__name__)

# OpenViking-style frontmatter pattern
FRONTMATTER_PATTERN = re.compile(r"^---\s*\n(.*?)\n---\s*\n(.*)$", re.DOTALL)

# Directory containing builtin skills
BUILTIN_SKILLS_DIR = Path(__file__).parent / "builtin"

# Project skills directory (relative to project root)
PROJECT_SKILLS_DIR = ".zenstory/skills"

# User skills directory (in user home)
USER_SKILLS_DIR = Path.home() / ".zenstory" / "skills"


def parse_skill_md(content: str, file_path: str) -> Skill | None:
    """
    Parse a SKILL.md file content into a Skill object.

    Supports two formats:

    Format 1 (OpenViking-style with YAML frontmatter):
    ```markdown
    ---
    name: Chapter Writer
    description: Writes chapters following an outline
    allowed-tools:
      - create_file
      - edit_file
    tags:
      - writing
      - chapters
    ---
    # Instructions
    Write chapters by following the outline structure...
    ```

    Format 2 (zenstory native):
    ```markdown
    # Skill Name
    Description here.

    ## Triggers
    - keyword1
    - keyword2

    ## Instructions
    Instructions content...
    ```
    """
    # Try OpenViking format first
    skill = parse_openviking_format(content, file_path)
    if skill:
        log_with_context(
            logger, 20, "Parsed OpenViking format skill",
            file_path=file_path,
            skill_name=skill.name
        )
        return skill

    # Fall back to zenstory native format
    skill = parse_zenstory_format(content, file_path)
    if skill:
        log_with_context(
            logger, 20, "Parsed zenstory native format skill",
            file_path=file_path,
            skill_name=skill.name
        )
    return skill


def parse_openviking_format(content: str, file_path: str) -> Skill | None:
    """Parse OpenViking-style SKILL.md with YAML frontmatter using Pydantic validation."""
    match = FRONTMATTER_PATTERN.match(content)
    if not match:
        return None

    frontmatter_text, body = match.groups()

    try:
        raw_meta = yaml.safe_load(frontmatter_text)
        if not isinstance(raw_meta, dict):
            return None

        # Validate using Pydantic model
        try:
            meta = SkillFrontmatter.model_validate(raw_meta)
        except Exception as e:
            log_with_context(
                logger, 30, "Failed to validate YAML frontmatter",
                file_path=file_path,
                error=str(e)
            )
            return None

        # Generate ID from filename
        skill_id = Path(file_path).stem.lower().replace(" ", "-")

        return Skill(
            id=skill_id,
            name=meta.name,
            description=meta.description,
            triggers=meta.triggers,
            instructions=body.strip(),
            allowed_tools=meta.allowed_tools,
            tags=meta.tags,
            source=SkillSource.BUILTIN,
        )

    except yaml.YAMLError as e:
        log_with_context(
            logger, 30, "Failed to parse YAML frontmatter",
            file_path=file_path,
            error=str(e)
        )
        return None


def parse_zenstory_format(content: str, file_path: str) -> Skill | None:
    """Parse zenstory native SKILL.md format."""
    try:
        lines = content.strip().split("\n")

        # Parse name from first heading
        name = ""
        description_lines: list[str] = []
        triggers: list[str] = []
        instructions_lines: list[str] = []

        current_section = "description"

        for line in lines:
            line_stripped = line.strip()

            # Check for main title
            if line_stripped.startswith("# ") and not name:
                name = line_stripped[2:].strip()
                continue

            # Check for section headers
            if line_stripped.startswith("## "):
                section_name = line_stripped[3:].strip().lower()
                if section_name == "triggers":
                    current_section = "triggers"
                elif section_name == "instructions":
                    current_section = "instructions"
                continue

            # Add content to appropriate section
            if current_section == "description" and line_stripped:
                description_lines.append(line_stripped)
            elif current_section == "triggers":
                if line_stripped.startswith("- "):
                    triggers.append(line_stripped[2:].strip())
            elif current_section == "instructions":
                instructions_lines.append(line)

        if not name:
            log_with_context(
                logger, 30, "Skill file missing name",
                file_path=file_path
            )
            return None

        # Generate ID from filename
        skill_id = Path(file_path).stem.lower().replace(" ", "-")

        return Skill(
            id=skill_id,
            name=name,
            description=" ".join(description_lines),
            triggers=triggers,
            instructions="\n".join(instructions_lines).strip(),
            source=SkillSource.BUILTIN,
        )

    except Exception as e:
        log_with_context(
            logger, 40, "Failed to parse skill file",
            file_path=file_path,
            error=str(e)
        )
        return None


def load_skills_from_dir(dir_path: Path | str, source: SkillSource) -> list[Skill]:
    """Load all skills from a directory."""
    skills: list[Skill] = []
    dir_path = Path(dir_path)

    if not dir_path.exists():
        return skills

    for skill_file in dir_path.glob("*.md"):
        try:
            content = skill_file.read_text(encoding="utf-8")
            skill = parse_skill_md(content, str(skill_file))
            if skill:
                skill.source = source
                skill.file_path = str(skill_file)
                skills.append(skill)
                log_with_context(
                    logger, 20, "Loaded skill",
                    skill_id=skill.id,
                    skill_name=skill.name,
                    source=source,
                    triggers_count=len(skill.triggers)
                )
        except Exception as e:
            log_with_context(
                logger, 40, "Failed to load skill file",
                file_path=str(skill_file),
                error=str(e)
            )

    return skills


def load_builtin_skills() -> list[Skill]:
    """
    Load all builtin skills from the builtin directory.

    Returns:
        List of Skill objects parsed from SKILL.md files
    """
    skills = load_skills_from_dir(BUILTIN_SKILLS_DIR, SkillSource.BUILTIN)

    log_with_context(
        logger, 20, "Builtin skills loaded",
        total_count=len(skills)
    )
    return skills


def load_project_skills(project_path: str) -> list[Skill]:
    """
    Load skills from a project's .zenstory/skills directory.

    Project skills override builtin skills with the same ID.

    Args:
        project_path: Path to the project root directory

    Returns:
        List of project-level Skill objects
    """
    skills_dir = Path(project_path) / PROJECT_SKILLS_DIR
    skills = load_skills_from_dir(skills_dir, SkillSource.PROJECT)

    if skills:
        log_with_context(
            logger, 20, "Project skills loaded",
            project_path=project_path,
            total_count=len(skills)
        )
    return skills


def load_user_skills() -> list[Skill]:
    """
    Load skills from user's ~/.zenstory/skills directory.

    User skills override project skills with the same ID.

    Returns:
        List of user-level Skill objects
    """
    skills = load_skills_from_dir(USER_SKILLS_DIR, SkillSource.USER)

    if skills:
        log_with_context(
            logger, 20, "User skills loaded",
            total_count=len(skills)
        )
    return skills


def get_all_skills(project_path: str | None = None) -> list[Skill]:
    """
    Get all skills with proper override priority.

    Priority: user > project > builtin

    Args:
        project_path: Optional path to project root for loading project skills

    Returns:
        List of all skills with proper overrides applied
    """
    skills_by_id: dict[str, Skill] = {}

    # Load builtin first (lowest priority)
    for skill in get_builtin_skills():
        skills_by_id[skill.id] = skill

    # Load project skills (medium priority)
    if project_path:
        for skill in load_project_skills(project_path):
            skills_by_id[skill.id] = skill

    # Load user skills (highest priority)
    for skill in load_user_skills():
        skills_by_id[skill.id] = skill

    all_skills = list(skills_by_id.values())
    log_with_context(
        logger, 20, "All skills loaded with overrides",
        total_count=len(all_skills)
    )
    return all_skills


# ============================================================================
# Skill Cache with TTL and LRU eviction
# ============================================================================


class SkillCache:
    """
    Thread-safe cache for skills with TTL and LRU eviction.

    Features:
    - TTL (Time-To-Live): Entries expire after a configurable time
    - LRU (Least Recently Used): Evicts least recently used entries when full
    - Thread-safe: Uses asyncio.Lock for concurrent access
    """

    def __init__(
        self,
        max_size: int = 100,
        ttl_seconds: float = 300,  # 5 minutes default
    ):
        """
        Initialize the skill cache.

        Args:
            max_size: Maximum number of entries to cache
            ttl_seconds: Time-to-live in seconds for cache entries
        """
        self._max_size = max_size
        self._ttl_seconds = ttl_seconds
        self._cache: OrderedDict[str, tuple[list[Skill], float]] = OrderedDict()
        self._lock = asyncio.Lock()

        # Stats
        self._hits = 0
        self._misses = 0

    async def get(self, key: str) -> list[Skill] | None:
        """
        Get skills from cache if not expired.

        Args:
            key: Cache key (e.g., "builtin", "project:/path")

        Returns:
            Cached skills or None if not found/expired
        """
        async with self._lock:
            if key not in self._cache:
                self._misses += 1
                return None

            skills, timestamp = self._cache[key]

            # Check TTL
            if time.time() - timestamp > self._ttl_seconds:
                del self._cache[key]
                self._misses += 1
                log_with_context(
                    logger, 20, "Cache entry expired",
                    key=key,
                    ttl_seconds=self._ttl_seconds
                )
                return None

            # Move to end (most recently used)
            self._cache.move_to_end(key)
            self._hits += 1
            return skills

    async def set(self, key: str, skills: list[Skill]) -> None:
        """
        Add skills to cache with current timestamp.

        Args:
            key: Cache key
            skills: Skills to cache
        """
        async with self._lock:
            # Evict LRU if at capacity
            while len(self._cache) >= self._max_size:
                oldest_key = next(iter(self._cache))
                del self._cache[oldest_key]
                log_with_context(
                    logger, 20, "Cache LRU eviction",
                    evicted_key=oldest_key,
                    cache_size=len(self._cache)
                )

            self._cache[key] = (skills, time.time())
            self._cache.move_to_end(key)

    async def invalidate(self, key: str | None = None) -> None:
        """
        Invalidate cache entries.

        Args:
            key: Specific key to invalidate, or None to clear all
        """
        async with self._lock:
            if key is None:
                self._cache.clear()
                log_with_context(logger, 20, "Cache cleared")
            elif key in self._cache:
                del self._cache[key]
                log_with_context(logger, 20, "Cache entry invalidated", key=key)

    def get_stats(self) -> dict[str, Any]:
        """
        Get cache statistics.

        Returns:
            Dict with hits, misses, size, hit_rate
        """
        total = self._hits + self._misses
        hit_rate = self._hits / total if total > 0 else 0.0

        return {
            "hits": self._hits,
            "misses": self._misses,
            "size": len(self._cache),
            "max_size": self._max_size,
            "hit_rate": hit_rate,
            "ttl_seconds": self._ttl_seconds,
        }


# Global skill cache instance
_skill_cache = SkillCache(max_size=100, ttl_seconds=300)


def get_cache_stats() -> dict[str, Any]:
    """
    Get cache statistics.

    Returns:
        Dict with cache stats (hits, misses, size, hit_rate)
    """
    return _skill_cache.get_stats()


# In-memory cache for builtin skills (simple, always-loaded cache)
_builtin_skills_cache: list[Skill] | None = None


async def get_builtin_skills_async() -> list[Skill]:
    """
    Get all builtin skills (cached with TTL).

    Returns:
        List of builtin Skill objects
    """
    global _builtin_skills_cache

    # Try cache first
    cached = await _skill_cache.get("builtin")
    if cached is not None:
        return cached

    # Load and cache
    skills = load_builtin_skills()
    await _skill_cache.set("builtin", skills)

    # Also update simple cache for sync access
    _builtin_skills_cache = skills

    return skills


def get_builtin_skills() -> list[Skill]:
    """
    Get all builtin skills (simple cached, for backwards compatibility).

    Returns:
        List of builtin Skill objects
    """
    global _builtin_skills_cache
    if _builtin_skills_cache is None:
        _builtin_skills_cache = load_builtin_skills()
    return _builtin_skills_cache


def reload_builtin_skills() -> list[Skill]:
    """
    Reload builtin skills from disk, clearing the cache.

    Returns:
        List of freshly loaded Skill objects
    """
    global _builtin_skills_cache
    _builtin_skills_cache = None
    return get_builtin_skills()


def to_skill_md(skill: Skill) -> str:
    """
    Convert a Skill to SKILL.md format (OpenViking style).

    Useful for exporting skills or creating templates.

    Args:
        skill: The Skill object to convert

    Returns:
        SKILL.md formatted string
    """
    frontmatter: dict[str, Any] = {
        "name": skill.name,
        "description": skill.description,
    }

    if skill.triggers:
        frontmatter["triggers"] = skill.triggers
    if skill.allowed_tools:
        frontmatter["allowed-tools"] = skill.allowed_tools
    if skill.tags:
        frontmatter["tags"] = skill.tags

    yaml_str = yaml.dump(frontmatter, allow_unicode=True, sort_keys=False)

    return f"---\n{yaml_str}---\n\n{skill.instructions}"
