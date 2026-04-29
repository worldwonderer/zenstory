<div align="center">

<img src="apps/web/public/favicon.svg" alt="ZenStory Logo" width="64" height="64">

# ZenStory

**对话即创作 — AI Agent 驱动的商业级写作工作台**

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![GitHub Stars](https://img.shields.io/github/stars/worldwonderer/zenstory?style=social)](https://github.com/worldwonderer/zenstory)
[![Website](https://img.shields.io/website?url=https%3A%2F%2Fzenstory.ai&label=zenstory.ai)](https://zenstory.ai/)
![React](https://img.shields.io/badge/React_19-61DAFB?logo=react&logoColor=black)
![FastAPI](https://img.shields.io/badge/FastAPI-009688?logo=fastapi&logoColor=white)
![Python](https://img.shields.io/badge/Python_3.12+-3776AB?logo=python&logoColor=white)

**2000+ 创作者 · 1200 万字生成 · 4.9 分好评**

AI 不再只是聊天框。ZenStory 让 AI Agent 直接操作你的文件系统——创建角色卡、拆解参考素材、规划大纲、逐章写作——全部在对话中完成。

**[zenstory.ai](https://zenstory.ai/)** &middot; [快速开始](#快速开始) &middot; [English](README_EN.md)

</div>

---

<table>
  <tr>
    <td><img src="docs/screenshots/workspace.png" alt="ZenStory 三栏工作台" width="100%"></td>
  </tr>
  <tr>
    <td align="center"><b>三栏工作台 — 文件树 · 编辑器 · AI 对话，AI 直接读写你的创作文件</b></td>
  </tr>
</table>

---

## 为什么是 ZenStory？

| 传统 AI 写作工具 | ZenStory |
|:---|:---|
| 聊天框 + 复制粘贴 | Agent 直接创建、编辑、组织文件 |
| 无上下文记忆，每次从零开始 | 理解角色关系、世界观约束，不穿帮 |
| 单一 AI 模型 | 五个专职 Agent 协作（规划师→创作者→审稿人） |
| 灵感枯竭时无从下手 | AI 拆解参考作品 + 主动生成灵感卡片 |
| 无法对接外部工具 | Agent API 支持 Claude Code / OpenClaw 直连 |

---

## 核心亮点

### 1. 对话 x 文件系统 = 全新创作范式

AI 不只停留在对话框里，它通过工具直接操作你的创作文件：

<table>
  <tr>
    <td align="center"><b>AI 对话驱动创作</b></td>
    <td align="center"><b>智能文件树管理</b></td>
  </tr>
  <tr>
    <td><img src="docs/screenshots/ai-chat.png" alt="AI 对话驱动创作" width="100%"></td>
    <td><img src="docs/screenshots/file-tree.png" alt="文件树管理" width="100%"></td>
  </tr>
</table>

- **对话即操作** — "帮我创建一个反派角色，性格阴沉但有悲情过往"，Agent 自动新建角色卡并填充设定
- **上下文感知** — AI 理解角色关系、世界观规则、已有章节内容，写出连贯不穿帮的文字
- **Diff 审阅模式** — AI 修改先展示差异对比，确认后再应用，掌控权始终在你手里
- **流式生成** — 实时看到 AI 逐字创作的过程，随时介入调整方向
- **工具链完整** — 创建文件、编辑内容、搜索素材、更新项目状态，9 种工具覆盖全流程

### 2. 五 Agent 协作写作引擎

不是一个 AI，而是一支专业写作团队。五个专职 Agent 各司其职，智能协作：

```
┌─────────┐    ┌─────────┐    ┌──────────┐    ┌─────────┐    ┌──────────────────┐
│ Router  │───►│ Planner │───►│  Hook    │───►│ Writer  │───►│ Quality Reviewer │
│ 意图路由 │    │ 大纲规划 │    │ Designer │    │ 内容创作 │    │   质量审稿        │
└─────────┘    └─────────┘    │ 爽点设计 │    └─────────┘    └──────────────────┘
                              └──────────┘
```

| Agent | 职责 | 何时介入 |
|-------|------|---------|
| **Router** | 意图识别，选择最优工作流 | 每次请求 |
| **Planner** | 规划故事结构，拆解章节节奏 | 复杂创作任务 |
| **Hook Designer** | 设计情节转折、悬念与高潮 | 需要强化吸引力时 |
| **Writer** | 专注内容创作，风格自适应 | 所有创作任务 |
| **Quality Reviewer** | 一致性检查、质量把关 | 长内容自动触发 |

四种智能工作流——快速直写、标准流程、完整协作、转折专攻——Router 自动判断任务复杂度，匹配最优路径。Agent 之间支持智能交接（handoff），实现真正的多轮协作。

### 3. 素材库：AI 拆解参考作品

上传你欣赏的参考小说，AI 自动拆解为 **8 类结构化创作元素**：

| 拆解维度 | 说明 |
|---------|------|
| **章节摘要** | 每章核心事件与情节推进 |
| **角色档案** | 人物名称、别名、性格原型、能力体系 |
| **角色关系** | 人物间的复杂关系网络 |
| **情节点** | 每章 10-15 个关键事件（冲突/转折/揭示/对话） |
| **故事线** | 跨章聚合的完整剧情弧（起承转合） |
| **世界观** | 力量体系、世界结构、关键势力 |
| **金手指** | 特殊能力系统的名称、类型、进化历程 |
| **时间线** | 事件发生的时序排列 |

拆解后的素材可通过 **混合检索（RAG）** 精准定位——关键词 + 向量语义双引擎，在海量素材中秒级找到相关片段。AI 写作时自动引用相关素材，确保风格和设定的一致性。

### 4. 灵感库：打破创作瓶颈

<table>
  <tr>
    <td><img src="apps/web/public/docs-images/advanced/workflow-tips.png" alt="灵感库" width="100%"></td>
  </tr>
  <tr>
    <td align="center"><b>基于项目上下文的智能灵感卡片，一键复制到项目启动创作</b></td>
  </tr>
</table>

- **上下文感知** — 基于你的项目类型（长篇/短篇/短剧）和已有内容，生成精准灵感
- **精选推荐** — 编辑精选的高质量灵感模板，覆盖各类型创作场景
- **一键复用** — 看中灵感直接复制到项目，立即开始创作
- **素材联动** — 你的素材库越丰富，灵感推荐越精准

### 5. 技能系统 & 市场

13+ 内置专业写作技能，开箱即用：

| 分类 | 技能 |
|------|------|
| **写作** | 继续写作 · 场景描写 · 对话生成 · 开头创作 |
| **情节** | 冲突设计 · 悬念设计 · 反转设计 · 节奏控制 |
| **风格** | 沉浸增强 · 文本润色 |
| **设定** | 角色创建 · 大纲生成 · 世界观构建 |

<table>
  <tr>
    <td><img src="apps/web/public/docs-images/user-guide/skills.png" alt="技能市场" width="100%"></td>
  </tr>
  <tr>
    <td align="center"><b>技能市场 — Markdown 定义技能，一键分享，社区共建</b></td>
  </tr>
</table>

支持自定义技能创建，Markdown 格式定义，一键分享到技能市场。支持管理审核，社区共建，越用越强。

### 6. Agent API — 让你的 AI 工具直连创作空间

生成 API Key，粘贴到 Claude Code 或 OpenClaw，即可让外部 AI Agent 直接读写你的小说项目：

```bash
# 在 Claude Code 或 OpenClaw 中，Agent 可以：
# - 读取项目文件和角色设定
# - 创建新章节和角色
# - 搜索素材库
# - 编辑已有内容
```

这不再是"AI 辅助写作"，而是 **AI 生态互联互通**——你喜欢的任何 AI 工具都可以成为 ZenStory 的创作引擎。

### 7. 专业写作工作台

<table>
  <tr>
    <td align="center"><b>Tiptap 富文本编辑器</b></td>
    <td align="center"><b>版本对比与回滚</b></td>
  </tr>
  <tr>
    <td><img src="apps/web/public/docs-images/user-guide/editor.png" alt="编辑器" width="100%"></td>
    <td><img src="docs/screenshots/version-history.png" alt="版本历史" width="100%"></td>
  </tr>
</table>

- **六种文件类型** — 大纲、草稿、剧本、角色、世界观、片段，各类型独立编辑界面
- **智能排序** — 自动识别中英文章节编号（"第一章" / "Chapter 1"），按顺序排列
- **版本快照** — 每次编辑自动保存，一键对比任意两个版本的差异，支持回滚
- **项目级快照** — 整个项目的时光机，随时回到任意创作节点
- **多格式导出** — 一键导出 Word / Markdown / 纯文本，章节自动按序合并
- **语音输入** — 语音转文字，长按录音，移动端友好
- **全局搜索** — Cmd+K 快速搜索项目内所有文件
- **深色模式** — 护眼写作，自动跟随系统偏好
- **中英双语** — 界面全面国际化支持

### 8. 商业级功能

ZenStory 不只是技术演示，而是一个完整的商业产品：

- **订阅体系** — Free / Pro / Max 三档套餐，按创作任务选择方案
- **配额管理** — 写作字数、Agent 任务数、项目数、素材上传量精细控制
- **积分系统** — 每日签到、邀请奖励、兑换码
- **写作连续** — 追踪每日写作，连续打卡，冻断保护
- **数据统计** — 字数趋势、章节完成度、AI 协作分析、项目健康度
- **管理后台** — 用户管理、订阅管理、技能审核、Prompt 编辑、数据看板
- **项目类型** — 长篇小说、短篇小说、短剧剧本三种创作路径，各有专属引导

---

## 技术栈

<div align="center">

| 层级 | 技术 |
|:---:|:---|
| **前端** | React 19 · TypeScript · Vite · Tailwind CSS 4 · Zustand · TanStack Query · Tiptap |
| **后端** | FastAPI · Python 3.12+ · SQLModel · Alembic |
| **AI 引擎** | Anthropic Claude · DeepSeek · LangGraph · LlamaIndex |
| **向量检索** | ChromaDB（混合 RAG：关键词 + 语义向量） |
| **数据库** | SQLite（开发） / PostgreSQL（生产） |
| **部署** | Vercel（前端） + Railway（后端） + Cloudflare（CDN） |

</div>

---

## 快速开始

### 环境要求

- Node.js >= 18
- Python >= 3.12
- pnpm

### 方式一：Docker Compose（推荐）

只需一个 API Key，一行命令启动：

```bash
export DEEPSEEK_API_KEY=your-key
docker compose up -d --build
```

访问：
- 前端：http://localhost:5173
- API 文档：http://localhost:8000/docs

> 数据持久化在 Docker volume 中，开箱即用 SQLite。

### 方式二：本地开发

```bash
# 1. 后端
cd apps/server
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # 编辑 .env 填入 API Key
python3 main.py

# 2. 前端（新终端）
cd apps/web
pnpm install
cp .env.example .env.local
pnpm dev
```

> 只需一个 LLM API Key 即可运行（支持 DeepSeek / Anthropic）。生产部署（PostgreSQL + Redis）请参考 [docs/docker-compose.md](docs/docker-compose.md)。

---

## 项目架构

```
zenstory/
├── apps/
│   ├── web/                    # React 前端
│   │   ├── src/components/     # 组件（Layout/FileTree/Editor/ChatPanel/Skills/...）
│   │   ├── src/hooks/          # Hooks（useAgentStream/useVoiceInput/useMaterialLibrary/...）
│   │   ├── src/contexts/       # Context（Auth/Project/Theme）
│   │   └── src/pages/          # 页面（Dashboard/Project/Billing/Materials/...）
│   └── server/                 # FastAPI 后端
│       ├── api/                # API 路由（auth/projects/files/agent/chat/export/voice）
│       ├── agent/              # AI Agent 系统 ★
│       │   ├── graph/          #   LangGraph 多 Agent 工作流
│       │   ├── tools/          #   9 种 Agent 工具（create_file/edit_file/hybrid_search/...）
│       │   ├── context/        #   上下文组装 + Token 预算管理
│       │   ├── prompts/        #   项目类型提示 + Agent 专用提示
│       │   └── skills/         #   技能加载/匹配/注入
│       ├── models/             # 数据模型（File/Material/Subscription/Skill/...）
│       ├── services/           # 业务逻辑层
│       │   ├── material/       #   素材拆解服务（16 个子模块）
│       │   └── features/       #   导出/快照/验证等服务
│       └── config/             # 配置（Logger/Settings/AgentRuntime）
└── docs/                       # 文档和截图
```

---

## 路线图

- [x] 多 Agent 协作写作引擎（Router/Planner/Writer/QualityReviewer/HookDesigner）
- [x] 素材库 AI 拆解（8 类结构化元素 + 混合 RAG 检索）
- [x] 灵感库（上下文感知 + 一键复用）
- [x] 技能系统 & 市场（13+ 内置 + 自定义 + 社区分享）
- [x] Agent API（Claude Code / OpenClaw 直连）
- [x] 版本快照 & Diff 对比
- [x] 语音输入
- [x] 商业化（订阅/配额/积分/管理后台）
- [ ] 移动端原生 App

---

## 参与贡献

欢迎通过以下方式参与：

- [提交 Bug](https://github.com/worldwonderer/zenstory/issues/new?template=bug_report.md)
- [功能建议](https://github.com/worldwonderer/zenstory/issues/new?template=feature_request.md)
- 提交 Pull Request

请阅读 [CONTRIBUTING.md](CONTRIBUTING.md) 了解贡献流程。

## 许可证

[MIT License](LICENSE) &copy; 2024-2026 ZenStory
