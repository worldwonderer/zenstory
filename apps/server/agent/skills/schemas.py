"""
Skill data models for the skills system.

Defines the Skill schema used for both builtin and user-defined skills.
"""

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class SkillSource(StrEnum):
    """Source type of a skill."""
    BUILTIN = "builtin"
    PROJECT = "project"  # Project-level skills (.zenstory/skills/)
    USER = "user"        # User-level skills (~/.zenstory/skills/)


class Skill(BaseModel):
    """
    Represents a skill that can be loaded into the AI assistant.

    Skills contain instructions that are injected into the system prompt
    when triggered by matching keywords in user messages.
    """

    id: str = Field(..., description="Unique identifier for the skill")
    name: str = Field(..., description="Display name of the skill")
    description: str = Field(..., description="Brief description of what the skill does")
    triggers: list[str] = Field(
        default_factory=list,
        description="Keywords that trigger this skill"
    )
    instructions: str = Field(..., description="Instructions to inject into system prompt")
    source: SkillSource = Field(
        default=SkillSource.BUILTIN,
        description="Whether this is a builtin or user-defined skill"
    )
    user_id: str | None = Field(
        default=None,
        description="User ID if this is a user-defined skill"
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional metadata for the skill"
    )

    # OpenViking compatibility fields
    allowed_tools: list[str] | None = Field(
        default=None,
        description="Restrict which tools this skill can use"
    )
    tags: list[str] = Field(
        default_factory=list,
        description="Tags for categorization"
    )

    # Path to skill file (for reloading)
    file_path: str | None = Field(
        default=None,
        description="Path to the skill file for reloading"
    )

    model_config = ConfigDict(use_enum_values=True)


class SkillMatch(BaseModel):
    """Result of matching a skill against user input."""

    skill: Skill = Field(..., description="The matched skill")
    matched_trigger: str = Field(..., description="The trigger keyword that matched")
    confidence: float = Field(
        default=1.0,
        description="Confidence score of the match (0.0 to 1.0)"
    )


class SkillFrontmatter(BaseModel):
    """
    Pydantic model for validating SKILL.md YAML frontmatter.

    Used to parse and validate the YAML block in OpenViking-style skill files.
    """

    name: str = Field(..., description="Display name of the skill")
    description: str = Field(..., description="Brief description of what the skill does")
    triggers: list[str] = Field(
        default_factory=list,
        description="Keywords that trigger this skill"
    )
    allowed_tools: list[str] | None = Field(
        default=None,
        alias="allowed-tools",
        description="Restrict which tools this skill can use"
    )
    tags: list[str] = Field(
        default_factory=list,
        description="Tags for categorization"
    )

    model_config = ConfigDict(populate_by_name=True)  # Allow both alias and field name
