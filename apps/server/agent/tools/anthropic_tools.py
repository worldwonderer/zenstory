"""
Anthropic tool definitions for workflow integration.

Defines tools in Anthropic format with proper input_schema.
"""

from typing import Any

from agent.tools.parallel_executor import PARALLEL_EXECUTE_TOOL
from config.project_status import PROJECT_STATUS_MAX_LENGTHS

# Tool: create_file
CREATE_FILE_TOOL: dict[str, Any] = {
    "name": "create_file",
    "description": "创建新文件。用于在项目中创建大纲、角色、设定、草稿等各类文件。注意：此工具只创建空文件，文件内容需要在工具调用后使用 <file>内容</file> 标记流式输出。",
    "input_schema": {
        "type": "object",
        "properties": {
            "title": {
                "type": "string",
                "description": "文件标题/名称"
            },
            "file_type": {
                "type": "string",
                "description": "文件类型：outline(大纲)、character(角色)、lore(设定)、draft(草稿)、script(剧本)、snippet(素材)等",
                "enum": ["outline", "character", "lore", "draft", "script", "snippet", "document", "folder"]
            },
            "parent_id": {
                "type": "string",
                "description": "父文件ID（用于创建子文件/文件夹结构）"
            },
            "order": {
                "type": "integer",
                "description": "可选排序顺序。仅在你明确要自定义排序时传；对带章节/分集标题的 draft/outline/script 文件，系统会强制按标题序号排序。"
            },
            "metadata": {
                "type": "object",
                "description": "文件元数据（JSON对象）"
            }
        },
        "required": ["title", "file_type"]
    }
}

# Tool: edit_file
EDIT_FILE_TOOL: dict[str, Any] = {
    "name": "edit_file",
    "description": "精确编辑文件内容（diff风格）。支持replace/insert_after/insert_before/append/prepend/delete操作。适合对文件进行局部修改而非全量替换。",
    "input_schema": {
        "type": "object",
        "properties": {
            "id": {
                "type": "string",
                "description": "要编辑的文件ID"
            },
            "edits": {
                "type": "array",
                "description": "编辑操作列表",
                "items": {
                    "type": "object",
                    "properties": {
                        "op": {
                            "type": "string",
                            "description": "操作类型",
                            "enum": ["replace", "insert_after", "insert_before", "append", "prepend", "delete"]
                        },
                        "old": {
                            "type": "string",
                            "description": "要替换/删除的原文（用于replace/delete操作）"
                        },
                        "new": {
                            "type": "string",
                            "description": "替换后的新文本（用于replace操作）"
                        },
                        "anchor": {
                            "type": "string",
                            "description": "锚点文本（用于insert_after/insert_before操作）"
                        },
                        "text": {
                            "type": "string",
                            "description": "要插入的文本（用于insert_*/append/prepend操作）"
                        },
                        "replace_all": {
                            "type": "boolean",
                            "description": "是否替换所有匹配项（用于replace操作）",
                            "default": False
                        }
                    },
                    "required": ["op"]
                }
            },
            "continue_on_error": {
                "type": "boolean",
                "description": "是否在单个编辑失败后继续执行后续编辑（默认 false）",
                "default": False,
            }
        },
        "required": ["id", "edits"]
    }
}

# Tool: delete_file
DELETE_FILE_TOOL: dict[str, Any] = {
    "name": "delete_file",
    "description": "删除文件。支持递归删除子文件。",
    "input_schema": {
        "type": "object",
        "properties": {
            "id": {
                "type": "string",
                "description": "要删除的文件ID"
            },
            "recursive": {
                "type": "boolean",
                "description": "是否递归删除所有子文件",
                "default": False
            }
        },
        "required": ["id"]
    }
}

# Tool: query_files
QUERY_FILES_TOOL: dict[str, Any] = {
    "name": "query_files",
    "description": "查询和搜索项目中的文件。默认返回 summary（不含全文 content），可按需切换 full。",
    "input_schema": {
        "type": "object",
        "properties": {
            "id": {
                "type": "string",
                "description": "按文件ID精确查询（用于读取「当前文件」全文，避免同名文件误匹配）"
            },
            "query": {
                "type": "string",
                "description": "搜索关键词（在标题和内容中搜索）"
            },
            "file_type": {
                "type": "string",
                "description": "文件类型过滤（单个类型）",
                "enum": ["outline", "character", "lore", "draft", "script", "snippet", "document", "folder"]
            },
            "file_types": {
                "type": "array",
                "description": "文件类型过滤（多个类型）",
                "items": {
                    "type": "string",
                    "enum": ["outline", "character", "lore", "draft", "script", "snippet", "document", "folder"]
                }
            },
            "parent_id": {
                "type": "string",
                "description": "父文件ID过滤"
            },
            "metadata_filter": {
                "type": "object",
                "description": "元数据字段过滤"
            },
            "limit": {
                "type": "integer",
                "description": "最大返回数量",
                "default": 50
            },
            "offset": {
                "type": "integer",
                "description": "分页偏移量",
                "default": 0
            },
            "response_mode": {
                "type": "string",
                "description": "返回模式：summary（默认，仅返回 content_preview）或 full（返回完整 content）",
                "enum": ["summary", "full"],
                "default": "summary"
            },
            "content_preview_chars": {
                "type": "integer",
                "description": "summary 模式下 content_preview 的最大字符数",
                "default": 200,
                "minimum": 0
            },
            "include_content": {
                "type": "boolean",
                "description": "兼容参数：true 等同于 response_mode=full",
                "default": False
            }
        },
        "required": []
    }
}

# Tool: hybrid_search
HYBRID_SEARCH_TOOL: dict[str, Any] = {
    "name": "hybrid_search",
    "description": "混合检索（关键词 + 向量融合）。优先使用此工具进行 RAG 检索，返回 snippet/line_start/fused_score/sources。",
    "input_schema": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "搜索查询文本"
            },
            "top_k": {
                "type": "integer",
                "description": "返回最相关的结果数量",
                "default": 10
            },
            "entity_types": {
                "type": "array",
                "description": "限制搜索的实体类型",
                "items": {
                    "type": "string"
                }
            },
            "min_score": {
                "type": "number",
                "description": "最小融合分数阈值",
                "default": 0.0
            }
        },
        "required": ["query"]
    }
}

# Tool: update_project (合并 update_project_status + update_plan)
UPDATE_PROJECT_TOOL: dict[str, Any] = {
    "name": "update_project",
    "description": "更新项目信息和任务计划。可同时更新项目状态（摘要、阶段、风格）和任务列表。",
    "input_schema": {
        "type": "object",
        "properties": {
            "summary": {
                "type": "string",
                "description": "项目摘要/背景介绍",
                "maxLength": PROJECT_STATUS_MAX_LENGTHS["summary"],
            },
            "current_phase": {
                "type": "string",
                "description": "当前写作阶段描述",
                "maxLength": PROJECT_STATUS_MAX_LENGTHS["current_phase"],
            },
            "writing_style": {
                "type": "string",
                "description": "写作风格指南",
                "maxLength": PROJECT_STATUS_MAX_LENGTHS["writing_style"],
            },
            "notes": {
                "type": "string",
                "description": "给AI助手的额外备注",
                "maxLength": PROJECT_STATUS_MAX_LENGTHS["notes"],
            },
            "tasks": {
                "type": "array",
                "description": "任务列表",
                "items": {
                    "type": "object",
                    "properties": {
                        "task": {
                            "type": "string",
                            "description": "任务描述"
                        },
                        "status": {
                            "type": "string",
                            "description": "任务状态",
                            "enum": ["pending", "in_progress", "done"]
                        },
                        "phase_id": {
                            "type": "string",
                            "description": "阶段ID（可选，用于轻量 phase 状态机关联）"
                        },
                        "artifact": {
                            "type": "string",
                            "description": "任务产出物（可选，例如文件名或里程碑）"
                        },
                        "done_when": {
                            "type": "string",
                            "description": "任务完成判定标准（可选）"
                        }
                    },
                    "required": ["task", "status"]
                }
            }
        },
        "required": []
    }
}

# Tool: handoff_to_agent
HANDOFF_TO_AGENT_TOOL: dict[str, Any] = {
    "name": "handoff_to_agent",
    "description": "将任务交接给另一个专业Agent继续处理。当你完成当前工作后，如果需要其他Agent协助，使用此工具。",
    "input_schema": {
        "type": "object",
        "properties": {
            "target_agent": {
                "type": "string",
                "description": "目标Agent类型",
                "enum": ["planner", "hook_designer", "writer", "quality_reviewer"]
            },
            "reason": {
                "type": "string",
                "description": "交接原因，说明为什么需要该Agent继续处理"
            },
            "context": {
                "type": "string",
                "description": "传递给下一个Agent的上下文信息"
            },
            "completed": {
                "type": "array",
                "description": "已完成项摘要（可选，便于结构化交接）",
                "items": {"type": "string"}
            },
            "todo": {
                "type": "array",
                "description": "待完成项摘要（可选）",
                "items": {"type": "string"}
            },
            "evidence": {
                "type": "array",
                "description": "关键证据（文件路径、测试结果、结论等，可选）",
                "items": {"type": "string"}
            },
            "artifact_refs": {
                "type": "array",
                "description": "关联产出物引用（如 file_id、文档路径、工件标识），用于交接追溯",
                "items": {"type": "string"}
            }
        },
        "required": ["target_agent", "reason"]
    }
}

# Tool: request_clarification
REQUEST_CLARIFICATION_TOOL: dict[str, Any] = {
    "name": "request_clarification",
    "description": "当信息不足以继续执行任务时，请求用户补充关键信息，并暂停当前工作流。",
    "input_schema": {
        "type": "object",
        "properties": {
            "question": {
                "type": "string",
                "description": "需要用户回答的澄清问题",
            },
            "context": {
                "type": "string",
                "description": "当前进展与背景说明（可选）",
            },
            "details": {
                "type": "array",
                "description": "需要用户补充的具体信息点（可选）",
                "items": {"type": "string"},
            },
        },
        "required": ["question"],
    },
}


# Export all tool schemas by name (schema source-of-truth).
ANTHROPIC_TOOL_SCHEMAS: dict[str, dict[str, Any]] = {
    "create_file": CREATE_FILE_TOOL,
    "edit_file": EDIT_FILE_TOOL,
    "delete_file": DELETE_FILE_TOOL,
    "query_files": QUERY_FILES_TOOL,
    "hybrid_search": HYBRID_SEARCH_TOOL,
    "update_project": UPDATE_PROJECT_TOOL,
    "handoff_to_agent": HANDOFF_TO_AGENT_TOOL,
    "request_clarification": REQUEST_CLARIFICATION_TOOL,
    "parallel_execute": PARALLEL_EXECUTE_TOOL,
}

def get_tool_by_name(name: str) -> dict[str, Any] | None:
    """Get a tool definition by name."""
    return ANTHROPIC_TOOL_SCHEMAS.get(name)


def get_all_tool_names() -> list[str]:
    """Get all tool names."""
    return list(ANTHROPIC_TOOL_SCHEMAS.keys())
