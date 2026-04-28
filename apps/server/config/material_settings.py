"""
Material Library Settings
素材库功能配置（从 DeepNovel config 迁移）
"""
from pydantic_settings import BaseSettings, SettingsConfigDict


class MaterialSettings(BaseSettings):
    """素材库功能配置（从 DeepNovel config 迁移）"""

    # ============ LLM 配置 ============
    # LLM 提供商: "anthropic" 或 "openai"
    LLM_PROVIDER: str = "openai"

    # Anthropic 配置 (备用)
    ANTHROPIC_API_KEY: str = ""
    ANTHROPIC_BASE_URL: str = "https://open.bigmodel.cn/api/anthropic"
    ANTHROPIC_MODEL: str = "glm-4.7"

    # OpenAI 兼容配置 (主力 — DeepSeek)
    OPENAI_API_KEY: str = ""
    OPENAI_BASE_URL: str = "https://api.deepseek.com"
    OPENAI_MODEL: str = "deepseek-v4-flash"

    # 通用 LLM 参数
    LLM_TEMPERATURE: float = 0.7
    LLM_MAX_TOKENS: int = 64000

    # ============ 并发控制 ============
    MAX_CONCURRENT_WORKFLOWS: int = 3
    MAX_CONCURRENT_CHAPTERS: int = 3

    # ============ 小说处理配置 ============
    NOVEL_MAX_CHARACTERS: int = 50000  # 单章最大字符数
    MIN_PLOTS_PER_CHAPTER: int = 10
    MAX_PLOTS_PER_CHAPTER: int = 15
    MIN_PLOTS_PER_STORY: int = 3
    MAX_PLOTS_PER_STORY: int = 10

    # ============ 摘要配置 ============
    CHAPTER_SUMMARY_MAX_LENGTH: int = 500
    NOVEL_SYNOPSIS_MAX_LENGTH: int = 2000

    # ============ 人物关系配置 ============
    RELATIONSHIP_BATCH_SIZE: int = 5  # 每N章提取一次

    # ============ Feature Flags ============
    # 阶段1: 按章节提取
    ENABLE_CHAPTER_SUMMARIES: bool = True
    ENABLE_PLOT_EXTRACTION: bool = True
    ENABLE_ENTITY_EXTRACTION: bool = True

    # 阶段2A: 剧情相关
    ENABLE_NOVEL_SYNOPSIS: bool = True
    ENABLE_STORY_AGGREGATION: bool = True
    ENABLE_STORYLINE_GENERATION: bool = True

    # 阶段2B: 人物关系（默认关闭以降低拆解成本，可通过环境变量显式开启）
    ENABLE_RELATIONSHIP_EXTRACTION: bool = False
    ENABLE_NEO4J_STORAGE: bool = False  # 禁用 Neo4j

    # ============ 上传配置 ============
    UPLOAD_FOLDER: str = "uploads"
    MAX_CONTENT_LENGTH: int = 100 * 1024 * 1024  # 100MB

    # ============ Redis 配置（用于进度推送）============
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_PASSWORD: str | None = None
    REDIS_DB: int = 0
    REDIS_ENABLED: bool = False  # 无 Redis 时优雅降级

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="MATERIAL_",  # 环境变量前缀
        extra="ignore",  # 忽略额外的环境变量
    )


material_settings = MaterialSettings()
