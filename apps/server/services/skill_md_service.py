"""
Skill MD Service - Generates SKILL.md documentation for AI agents.

Uses route introspection to auto-generate endpoint tables from FastAPI routers,
eliminating manual sync drift between documentation and actual API surface.
"""

import os

from services.skill_md_routes import EndpointInfo, extract_agent_endpoints
from utils.logger import get_logger

logger = get_logger(__name__)

# NOTE: Keep in sync with require_rate_limit() params in agent_api.py and vector_search.py
RATE_LIMITS = {
    "read": "2000/hour",
    "write": "1000/hour",
    "search": "500/hour",
    "context": "500/hour",
}

_TABLE_HEADERS = {
    "zh": "| 端点 | 方法 | 描述 | 所需权限 |\n|------|------|------|----------|",
    "en": "| Endpoint | Method | Description | Required Scope |\n|----------|--------|-------------|----------------|",
}


def _get_agent_routers():
    """Lazy-import agent API routers to avoid circular imports."""
    from api.agent_api import router as agent_router
    from api.vector_search import router as search_router
    return [agent_router, search_router]


_cached_endpoints: list[EndpointInfo] | None = None


def _get_cached_endpoints() -> list[EndpointInfo]:
    """Get endpoints with caching to avoid repeated imports."""
    global _cached_endpoints
    if _cached_endpoints is None:
        _cached_endpoints = []
        for router in _get_agent_routers():
            _cached_endpoints.extend(extract_agent_endpoints(router))
    return _cached_endpoints


def _build_endpoint_table(endpoints: list[EndpointInfo], lang: str = "zh") -> str:
    header = _TABLE_HEADERS.get(lang, _TABLE_HEADERS["zh"])
    rows = [f"| `{ep.path}` | {ep.method} | {ep.summary} | {ep.scope} |" for ep in endpoints]
    return header + "\n" + "\n".join(rows)


class SkillMdService:
    """Service for generating SKILL.md documentation."""

    def __init__(self):
        self.app_name = os.getenv("APP_NAME", "zenstory API")
        self.app_version = os.getenv("APP_VERSION", "1.0.0")
        self.api_base = os.getenv("API_BASE_URL", "https://api.zenstory.ai/api/v1")

    def generate_skill_md(self, lang: str = "zh") -> str:
        """
        Generate SKILL.md documentation.

        Args:
            lang: Language for documentation ("zh" for Chinese, "en" for English)

        Returns:
            Complete SKILL.md content as string
        """
        if lang == "en":
            return self._generate_english()
        return self._generate_chinese()

    def _get_endpoints(self) -> list[EndpointInfo]:
        """Extract endpoints from all agent API routers (cached)."""
        endpoints = _get_cached_endpoints()

        if len(endpoints) < 8:
            logger.warning(
                "SKILL.md: only %d endpoints found, expected at least 8",
                len(endpoints),
            )
        return endpoints

    def _generate_chinese(self) -> str:
        endpoints = self._get_endpoints()
        endpoint_table = _build_endpoint_table(endpoints, "zh")

        return f'''---
name: zenstory 小说写作平台
version: "{self.app_version}"
description: AI 辅助的小说写作工作台，支持大纲、草稿、人物设定、世界观管理
api_base: {self.api_base}
auth_method: api_key
auth_header: X-Agent-API-Key
auth_prefix: eg_
rate_limit:
  read: {RATE_LIMITS["read"]}
  write: {RATE_LIMITS["write"]}
  search: {RATE_LIMITS["search"]}
  context: {RATE_LIMITS["context"]}
triggers:
  - "写小说"
  - "小说创作"
  - "角色创建"
  - "大纲规划"
  - "世界观设定"
  - "write a novel"
  - "create characters"
  - "story outline"
  - "world building"
  - "draft chapters"
capabilities:
  - project_management
  - file_crud
  - hybrid_search
  - writing_context
file_types:
  - outline
  - draft
  - character
  - lore
  - material
---

# zenstory 小说写作平台

AI 辅助的小说写作工作台，提供智能对话、文件管理、语义搜索等功能。

## 认证说明

所有 API 请求需要在请求头中携带有效的 API Key：

```
X-Agent-API-Key: eg_your_api_key_here
```

API Key 格式为 `eg_` 前缀加上 64 位十六进制字符。在平台设置中生成和管理 API Key。

**权限范围 (Scopes)**：
- `read` - 读取项目和文件
- `write` - 创建和更新内容

## API 端点列表

{endpoint_table}

## 文件类型说明

| 类型 | 用途 | 关键字段 |
|------|------|----------|
| outline | 大纲，支持层级嵌套 | title, content, parent_id, metadata |
| draft | 正文草稿 | title, content, parent_id, metadata |
| character | 人物设定 | title, content, metadata(traits, relationships) |
| lore | 世界观设定 | title, content, metadata(category) |
| material | 写作素材 | title, content, metadata(source, tags) |

## 使用示例

### 1. 获取项目列表

```bash
curl -H "X-Agent-API-Key: eg_your_key" \\
  "{self.api_base}/agent/projects"
```

### 2. 创建新项目

```bash
curl -X POST "{self.api_base}/agent/projects" \\
  -H "X-Agent-API-Key: eg_your_key" \\
  -H "Content-Type: application/json" \\
  -d '{{
    "name": "我的科幻小说",
    "description": "一部关于星际旅行的科幻作品",
    "project_type": "novel"
  }}'
```

### 3. 创建章节草稿

```bash
curl -X POST "{self.api_base}/agent/projects/{{project_id}}/files" \\
  -H "X-Agent-API-Key: eg_your_key" \\
  -H "Content-Type: application/json" \\
  -d '{{
    "title": "第一章：启程",
    "file_type": "draft",
    "content": "晨光透过窗帘的缝隙洒进房间..."
  }}'
```

### 4. 获取写作上下文

```bash
curl -H "X-Agent-API-Key: eg_your_key" \\
  "{self.api_base}/agent/projects/{{project_id}}/writing-context?file_id={{file_id}}"
```

### 5. 语义搜索

```bash
curl -X POST "{self.api_base}/agent/projects/{{project_id}}/search" \\
  -H "X-Agent-API-Key: eg_your_key" \\
  -H "Content-Type: application/json" \\
  -d '{{
    "query": "主角的冒险经历",
    "top_k": 5
  }}'
```

## 适用范围

**适用于：** 小说创作、短篇故事、剧本写作、人物设定、世界观构建、大纲规划
**不适用于：** 通用问答、代码生成、图像创作、非虚构写作、数据分析

## 完整工作流示例

### 工作流 1：创建新小说项目

```
1. POST /agent/projects                          → 创建新项目
2. POST /agent/projects/{{id}}/files             → 创建大纲文件 (file_type=outline)
3. POST /agent/projects/{{id}}/files             → 创建人物设定 (file_type=character)
4. POST /agent/projects/{{id}}/files             → 创建世界观设定 (file_type=lore)
5. GET  /agent/projects/{{id}}/writing-context   → 获取写作上下文
6. POST /agent/projects/{{id}}/files             → 创建草稿文件 (file_type=draft)
```

### 工作流 2：续写已有章节

```
1. GET  /agent/projects/{{id}}/files?file_type=draft&fields=id,title  → 列出草稿
2. GET  /agent/files/{{file_id}}                                        → 读取当前内容
3. GET  /agent/projects/{{id}}/writing-context?file_id={{file_id}}     → 获取相关上下文
4. POST /agent/projects/{{id}}/search  query="角色关系"                 → 搜索人物关系
5. PUT  /agent/files/{{file_id}}                                        → 更新草稿内容
```

## 错误处理

API 返回标准化的错误响应格式：

```json
{{
  "detail": "错误描述信息",
  "error_code": "ERROR_CODE",
  "request_id": "req_xxx"
}}
```

常见错误码：

| 错误码 | HTTP 状态码 | 描述 |
|--------|-------------|------|
| `AUTH_UNAUTHORIZED` | 401 | 缺少认证信息 |
| `AUTH_TOKEN_INVALID` | 401 | API Key 无效 |
| `AUTH_TOKEN_EXPIRED` | 401 | API Key 已过期 |
| `NOT_AUTHORIZED` | 403 | 权限不足 |
| `NOT_FOUND` | 404 | 资源不存在 |
| `VALIDATION_ERROR` | 422 | 请求参数验证失败 |
| `RATE_LIMIT_EXCEEDED` | 429 | 请求频率超限 |

## 速率限制

按端点类型分级限速：

| 类型 | 限制 |
|------|------|
| 读取 (read) | {RATE_LIMITS["read"]} |
| 写入 (write) | {RATE_LIMITS["write"]} |
| 搜索 (search) | {RATE_LIMITS["search"]} |
| 上下文 (context) | {RATE_LIMITS["context"]} |

---

如有问题或建议，请联系技术支持或访问 API 文档：{self.api_base.rsplit("/api/v1", 1)[0]}/docs
'''

    def _generate_english(self) -> str:
        endpoints = self._get_endpoints()
        endpoint_table = _build_endpoint_table(endpoints, "en")

        return f'''---
name: zenstory Novel Writing Platform
version: "{self.app_version}"
description: AI-assisted novel writing workbench with file management, semantic search, and writing context
api_base: {self.api_base}
auth_method: api_key
auth_header: X-Agent-API-Key
auth_prefix: eg_
rate_limit:
  read: {RATE_LIMITS["read"]}
  write: {RATE_LIMITS["write"]}
  search: {RATE_LIMITS["search"]}
  context: {RATE_LIMITS["context"]}
triggers:
  - "write a novel"
  - "novel writing"
  - "create characters"
  - "story outline"
  - "world building"
  - "draft chapters"
  - "写小说"
  - "小说创作"
  - "角色创建"
  - "大纲规划"
capabilities:
  - project_management
  - file_crud
  - hybrid_search
  - writing_context
file_types:
  - outline
  - draft
  - character
  - lore
  - material
---

# zenstory Novel Writing Platform

AI-assisted novel writing workbench with file management, semantic search, and writing context.

## Authentication

All API requests require a valid API Key in the request header:

```
X-Agent-API-Key: eg_your_api_key_here
```

The API Key format is `eg_` prefix followed by 64 hexadecimal characters. Generate and manage API Keys in platform settings.

**Available Scopes**:
- `read` - Read projects and files
- `write` - Create and update content

## API Endpoints

{endpoint_table}

## File Types

| Type | Purpose | Key Fields |
|------|---------|------------|
| outline | Story structure with hierarchy | title, content, parent_id, metadata |
| draft | Main content editing | title, content, parent_id, metadata |
| character | Character profiles | title, content, metadata(traits, relationships) |
| lore | World-building entries | title, content, metadata(category) |
| material | Writing materials | title, content, metadata(source, tags) |

## Usage Examples

### 1. List Projects

```bash
curl -H "X-Agent-API-Key: eg_your_key" \\
  "{self.api_base}/agent/projects"
```

### 2. Create New Project

```bash
curl -X POST "{self.api_base}/agent/projects" \\
  -H "X-Agent-API-Key: eg_your_key" \\
  -H "Content-Type: application/json" \\
  -d '{{
    "name": "My Sci-Fi Novel",
    "description": "A story about interstellar travel",
    "project_type": "novel"
  }}'
```

### 3. Create Chapter Draft

```bash
curl -X POST "{self.api_base}/agent/projects/{{project_id}}/files" \\
  -H "X-Agent-API-Key: eg_your_key" \\
  -H "Content-Type: application/json" \\
  -d '{{
    "title": "Chapter 1: The Journey Begins",
    "file_type": "draft",
    "content": "Morning light streamed through the curtains..."
  }}'
```

### 4. Get Writing Context

```bash
curl -H "X-Agent-API-Key: eg_your_key" \\
  "{self.api_base}/agent/projects/{{project_id}}/writing-context?file_id={{file_id}}"
```

### 5. Semantic Search

```bash
curl -X POST "{self.api_base}/agent/projects/{{project_id}}/search" \\
  -H "X-Agent-API-Key: eg_your_key" \\
  -H "Content-Type: application/json" \\
  -d '{{
    "query": "protagonist adventure",
    "top_k": 5
  }}'
```

## Scope

**Suitable for:** Novel writing, short stories, screenwriting, character design, world building, outline planning
**Not suitable for:** General Q&A, code generation, image creation, non-fiction writing, data analysis

## Complete Workflow Examples

### Workflow 1: Create a New Novel Project

```
1. POST /agent/projects                          → Create new project
2. POST /agent/projects/{{id}}/files             → Create outline file (file_type=outline)
3. POST /agent/projects/{{id}}/files             → Create character profiles (file_type=character)
4. POST /agent/projects/{{id}}/files             → Create lore entries (file_type=lore)
5. GET  /agent/projects/{{id}}/writing-context   → Get writing context
6. POST /agent/projects/{{id}}/files             → Create draft file (file_type=draft)
```

### Workflow 2: Continue an Existing Chapter

```
1. GET  /agent/projects/{{id}}/files?file_type=draft&fields=id,title  → List drafts
2. GET  /agent/files/{{file_id}}                                        → Read current content
3. GET  /agent/projects/{{id}}/writing-context?file_id={{file_id}}     → Get relevant context
4. POST /agent/projects/{{id}}/search  query="character relationships"  → Search character relations
5. PUT  /agent/files/{{file_id}}                                        → Update draft content
```

## Error Handling

API returns standardized error responses:

```json
{{
  "detail": "Error description",
  "error_code": "ERROR_CODE",
  "request_id": "req_xxx"
}}
```

Common error codes:

| Error Code | HTTP Status | Description |
|------------|-------------|-------------|
| `AUTH_UNAUTHORIZED` | 401 | Missing authentication |
| `AUTH_TOKEN_INVALID` | 401 | Invalid API Key |
| `AUTH_TOKEN_EXPIRED` | 401 | API Key expired |
| `NOT_AUTHORIZED` | 403 | Insufficient permissions |
| `NOT_FOUND` | 404 | Resource not found |
| `VALIDATION_ERROR` | 422 | Request validation failed |
| `RATE_LIMIT_EXCEEDED` | 429 | Rate limit exceeded |

## Rate Limiting

Tiered rate limits by endpoint type:

| Type | Limit |
|------|-------|
| Read (read) | {RATE_LIMITS["read"]} |
| Write (write) | {RATE_LIMITS["write"]} |
| Search (search) | {RATE_LIMITS["search"]} |
| Context (context) | {RATE_LIMITS["context"]} |

---

For questions or suggestions, contact support or visit API docs: {self.api_base.rsplit("/api/v1", 1)[0]}/docs
'''


# Singleton instance
skill_md_service = SkillMdService()
