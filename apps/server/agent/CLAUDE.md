# Agent 模块架构文档

本文档描述 zenstory Agent 系统的架构、流程和关键组件。

## 目录结构

```
agent/
├── service.py              # 主服务入口
├── suggest_service.py      # 智能建议生成服务
├── stream_adapter.py       # LangGraph 事件适配器
├── context/                # 上下文组装模块
│   ├── assembler.py        # 上下文组装器
│   ├── budget.py           # Token 预算管理
│   ├── compaction.py       # 上下文压缩（长会话总结）
│   └── prioritizer.py      # 优先级管理
├── core/                   # 核心基础设施
│   ├── events.py           # SSE 事件定义
│   ├── llm_client.py       # OpenAI 兼容 LLM 客户端
│   ├── message_manager.py  # 消息和系统提示管理
│   ├── session_loader.py   # 会话加载器
│   └── stream_processor.py # 文件流处理器
├── graph/                  # LangGraph 工作流
│   ├── state.py            # 工作流状态定义
│   ├── writing_graph.py    # 图执行入口
│   ├── nodes.py            # 流式节点实现
│   └── router.py           # 意图路由
├── llm/                    # LLM 集成
│   └── anthropic_client.py # Anthropic Claude 客户端
├── prompts/                # 提示词模板
│   ├── base.py             # 基础提示
│   ├── novel.py            # 小说项目提示
│   ├── screenplay.py       # 剧本项目提示
│   ├── short_story.py      # 短篇故事提示
│   ├── subagents.py        # 子代理提示 (planner/writer/quality_reviewer)
│   └── suggestions.py      # 建议生成提示
├── schemas/                # 数据模型
│   ├── context.py          # 上下文数据模型
├── skills/                 # 技能系统
│   ├── context_injector.py # 技能上下文注入
│   ├── loader.py           # 技能加载
│   ├── matcher.py          # 技能匹配
│   ├── schemas.py          # 技能数据模型
│   └── user_skill_service.py # 用户技能服务
└── tools/                  # 工具实现
    ├── anthropic_tools.py  # Anthropic 工具定义
    ├── file_executor.py    # 文件操作执行器
    ├── mcp_tools.py        # MCP 格式工具函数
    └── permissions.py      # 权限检查
```

## 核心流程

### 1. 请求处理流程

```
用户消息
    │
    ▼
┌─────────────────────────────────────────────────────────┐
│  AgentService.process_stream() [service.py]             │
│  - 设置 ToolContext                                      │
│  - 组装上下文 (ContextAssembler)                         │
│  - 加载会话历史 (SessionLoader)                          │
│  - 构建系统提示 (MessageManager)                         │
│  - 调用工作流                                            │
└─────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────┐
│  run_writing_workflow_streaming() [writing_graph.py]    │
│  - 路由策略选择初始 agent（默认 llm，可配置 off）           │
│  - 循环执行 agent 直到完成或达到最大迭代次数              │
└─────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────┐
│  router (llm / off) [router.py]                         │
│  - llm: 调用 router_node()（额外一次 LLM 往返；使用轻量 client）│
│  - off: 固定从 writer 开始                               │
│  - 返回: initial_agent + workflow_plan + workflow_agents │
└─────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────┐
│  run_streaming_agent() [nodes.py]                       │
│  - 组合基础提示 + 专业 agent 提示                        │
│  - 调用 run_agent_loop_streaming()                      │
│  - 处理工具调用和 handoff                                │
└─────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────┐
│  StreamAdapter.adapt_langgraph_events() [stream_adapter]│
│  - 转换 LangGraph 事件为 SSE 事件                        │
│  - 处理文件流式写入 (<file>...</file>)                   │
│  - 发送事件到前端                                        │
└─────────────────────────────────────────────────────────┘
```

### 2. 多 Agent 协作流程

```
┌─────────────┐
│   Router    │ ─── 分析意图，确定工作流
└─────────────┘
       │
       ▼
   ┌───────────────────────────────────────┐
   │         工作流类型 (workflow_plan)      │
   ├───────────────────────────────────────┤
   │ quick       : writer（必要时再 review）  │
   │ standard    : planner → writer（必要时再 review）│
   │ full        : planner → hook_designer → writer（必要时再 review）│
   │ hook_focus  : hook_designer → writer（必要时再 review）│
   │ review_only : quality_reviewer          │
   └───────────────────────────────────────┘
       │
       ▼
┌─────────────┐     handoff      ┌─────────────┐     handoff      ┌─────────────┐
│   Planner   │ ───────────────► │   Writer    │ ───────────────► │ Quality Reviewer │
│  大纲规划师  │                  │  内容创作者  │                  │   质量审稿人     │
└─────────────┘                  └─────────────┘                  └─────────────┘
```

### 3. Agent 交接机制

Agent 可以通过两种方式交接：

1. **显式 handoff**: Agent 调用 `handoff_to_agent` 工具
2. **工作流自动交接**: 按照 router 规划的 workflow_agents 顺序执行

## 关键组件详解

### AgentService (service.py)

主服务类，处理用户消息的流式响应。

```python
async def process_stream(
    session: Session,
    project_id: str,
    user_message: str,
    ...
) -> AsyncIterator[str]:
    # 1. 设置工具上下文
    ToolContext.set_context(session, user_id, project_id, session_id)

    # 2. 组装项目上下文
    context_data = session_loader.assemble_context(...)

    # 3. 构建系统提示
    system_prompt = message_manager.build_system_prompt(...)

    # 4. 执行工作流
    async for event in run_writing_workflow_streaming(state):
        yield stream_adapter.adapt_event(event)

    # 5. 保存消息历史
    await message_manager.save_messages(...)
```

### Router (router.py)

意图分类器，决定使用哪个 agent 和工作流。

**输入**: 用户消息 + 上下文
**输出**:
- `current_agent`: 初始 agent (planner/writer/quality_reviewer)
- `workflow_plan`: 工作流类型 (quick/standard/full/hook_focus/review_only)
- `workflow_agents`: 后续要执行的 agent 列表

### Streaming Agent Loop (nodes.py)

流式 agent 循环，处理工具调用。

```python
async def run_agent_loop_streaming(...):
    while iteration < MAX_TOOL_ITERATIONS:
        # 1. 流式调用 LLM
        async for event in client.stream_message(...):
            # 2. 处理文本/思考/工具调用事件
            if event.type == TOOL_USE and status == "stop":
                # 3. 执行工具
                result = await execute_tool(name, input)

                # 4. 检查 handoff
                if name == "handoff_to_agent":
                    yield handoff_event
                    return

            yield event

        # 5. 如果有工具调用，继续循环
        if stop_reason != "tool_use":
            break
```

### StreamAdapter (stream_adapter.py)

事件适配器，处理文件流式写入。

**核心功能**:
- 转换 LangGraph 事件为 SSE 格式
- 处理 `<file>...</file>` 标记的文件内容流
- 在文件写入完成后更新数据库

### ContextAssembler (context/assembler.py)

上下文组装器，收集项目相关内容。

**收集内容**:
- 焦点文件 (当前编辑的文件)
- 附加文件 (用户选择的参考文件)
- 用户引用文本
- 相关大纲、角色、设定

**优先级** (prioritizer.py):
1. CRITICAL - 焦点文件、用户引用
2. CONSTRAINT - 角色设定、世界观
3. RELEVANT - 相关大纲、草稿
4. INSPIRATION - 其他参考内容

## 工具系统

### 可用工具 (anthropic_tools.py)

| 工具名 | 描述 |
|--------|------|
| `create_file` | 创建新文件 (大纲/角色/设定/草稿) |
| `edit_file` | 精确编辑 (replace/insert/append/delete) |
| `delete_file` | 删除文件 |
| `query_files` | 查询和搜索文件 |
| `hybrid_search` | 关键词+向量混合检索（优先） |
| `update_project` | 更新项目状态 |
| `handoff_to_agent` | 交接给另一个 agent |
| `request_clarification` | 请求用户澄清并暂停工作流 |
| `parallel_execute` | 并行执行多个只读/工具任务 |

### 文件流式写入协议

创建文件时使用 `<file>...</file>` 标记流式输出内容：

```
1. Agent 调用 create_file (不传 content)
2. StreamAdapter 检测到 create_file 结果，进入等待模式
3. Agent 输出 <file> 标记
4. StreamAdapter 开始收集文件内容
5. Agent 输出 </file> 标记
6. StreamAdapter 将内容写入数据库
```

## SSE 事件类型 (core/events.py)

| 事件类型 | 描述 |
|----------|------|
| `thinking` | 模型思考过程 |
| `content` | 文本内容 |
| `tool_call` | 工具调用开始/进行中 |
| `tool_result` | 工具执行结果 |
| `file_created` | 文件创建完成 |
| `file_updated` | 文件更新完成 |
| `file_content` | 文件内容流 |
| `agent_selected` | Agent 被选中 |
| `handoff` | Agent 交接 |
| `error` | 错误信息 |
| `done` | 流结束 |

## 提示词系统 (prompts/)

### 项目类型提示
- `novel.py` - 长篇小说
- `short_story.py` - 短篇故事
- `screenplay.py` - 剧本

### Agent 专业提示 (subagents.py)
- `ROUTER_PROMPT` - 意图分类规则
- `PLANNER_PROMPT` - 大纲规划指南
- `WRITER_PROMPT` - 内容创作规范
- `QUALITY_REVIEWER_PROMPT` - 质量检查标准

## 开发指南

### 添加新工具

1. 在 `tools/anthropic_tools.py` 添加工具定义
2. 在 `tools/mcp_tools.py` 实现工具函数
3. 在 `tools/registry.py` 注册工具映射

### 添加新 Agent 类型

1. 在 `prompts/subagents.py` 添加专业提示
2. 在 `graph/router.py` 更新路由逻辑
3. 在 `graph/nodes.py` 的 `specialized_prompts` 注册

### 调试技巧

- 查看日志: `utils/logger.py` 的 `log_with_context`
- 检查工具执行: `tools/mcp_tools.py` 的返回值
- 跟踪事件流: `stream_adapter.py` 的事件转换
