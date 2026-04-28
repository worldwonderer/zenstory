"""
Unified File model - Everything is a file.

This replaces separate models (Outline, Character, Lore, Draft, Snippet)
with a single File model that can represent any file type.

File types:
- outline: 章节大纲
- draft: 草稿内容
- character: 角色档案
- lore: 世界设定
- snippet: 文本素材
- script: 剧本内容（短剧专用）
- folder: 文件夹（用于组织）
"""

from datetime import datetime
from typing import Any, Optional

from sqlmodel import Field, Relationship, SQLModel

from .utils import generate_uuid


class File(SQLModel, table=True):
    """
    Unified file model for all entity types.

    All project content (outlines, characters, lores, etc.) is stored as Files.
    The file_type field distinguishes the semantic meaning, and metadata
    stores type-specific attributes.
    """

    id: str = Field(default_factory=generate_uuid, primary_key=True)
    project_id: str = Field(foreign_key="project.id", index=True)

    # Basic file attributes
    title: str = Field(index=True, description="文件名/标题")
    content: str = Field(default="", description="文件内容")
    file_type: str = Field(
        default="document",
        index=True,
        description="文件类型：outline/draft/character/lore/snippet/script/folder",
    )

    # Hierarchy and ordering
    parent_id: str | None = Field(
        default=None,
        foreign_key="file.id",
        index=True,
        description="父文件ID（用于文件夹结构）",
    )
    order: int = Field(default=0, index=True, description="排序")

    # Metadata for type-specific attributes
    file_metadata: str | None = Field(
        default=None, description="JSON元数据：存储类型特定的扩展字段"
    )

    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    # Soft delete
    is_deleted: bool = Field(default=False, index=True, description="软删除标记")
    deleted_at: datetime | None = Field(default=None, description="删除时间")

    # Relationships - self-referential for folder hierarchy
    parent: Optional["File"] = Relationship(
        back_populates="children",
        sa_relationship_kwargs={
            "remote_side": "File.id",
            "foreign_keys": "[File.parent_id]",
        },
    )
    children: list["File"] = Relationship(
        back_populates="parent",
        sa_relationship_kwargs={"foreign_keys": "[File.parent_id]"},
    )

    # Metadata convenience helpers
    def get_metadata(self) -> dict[str, Any]:
        """Parse file_metadata JSON to dict."""
        import json

        if self.file_metadata:
            try:
                result: Any = json.loads(self.file_metadata)
                if isinstance(result, dict):
                    return result
                return {}
            except (json.JSONDecodeError, TypeError):
                return {}
        return {}

    def set_metadata(self, data: dict[str, Any]) -> None:
        """Set file_metadata from dict."""
        import json

        self.file_metadata = json.dumps(data)

    def get_metadata_field(self, key: str, default: Any = None) -> Any:
        """Get a specific metadata field."""
        return self.get_metadata().get(key, default)

    def set_metadata_field(self, key: str, value: Any) -> None:
        """Set a specific metadata field."""
        metadata = self.get_metadata()
        metadata[key] = value
        self.set_metadata(metadata)


# File type constants (for convenience)
FILE_TYPE_OUTLINE = "outline"
FILE_TYPE_DRAFT = "draft"
FILE_TYPE_CHARACTER = "character"
FILE_TYPE_LORE = "lore"
FILE_TYPE_SNIPPET = "snippet"
FILE_TYPE_SCRIPT = "script"  # Script content (for screenplay)
FILE_TYPE_FOLDER = "folder"


# Standard file type metadata schemas
# These help AI understand what metadata fields are expected for each type

FILE_TYPE_METADATA_SCHEMA = {
    FILE_TYPE_OUTLINE: {
        "description": "章节大纲",
        "optional_fields": ["chapter_number", "status", "word_count_target"],
    },
    FILE_TYPE_DRAFT: {
        "description": "草稿内容",
        "optional_fields": ["version", "is_current", "word_count"],
    },
    FILE_TYPE_CHARACTER: {
        "description": "角色档案",
        "optional_fields": ["age", "gender", "role", "personality", "appearance"],
    },
    FILE_TYPE_LORE: {
        "description": "世界设定",
        "optional_fields": ["category", "importance", "tags"],
    },
    FILE_TYPE_SNIPPET: {
        "description": "文本素材",
        "optional_fields": ["source", "tags", "importance"],
    },
    FILE_TYPE_SCRIPT: {
        "description": "剧本内容（短剧专用）",
        "optional_fields": ["episode_number", "scene_count", "duration"],
    },
    FILE_TYPE_FOLDER: {
        "description": "文件夹（用于组织）",
        "optional_fields": [],
    },
}
