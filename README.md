<div align="center">

# ZenStory

**对话即创作 — AI Agent 驱动的商业级写作工作台**

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![GitHub Stars](https://img.shields.io/github/stars/worldwonderer/zenstory?style=social)](https://github.com/worldwonderer/zenstory)
[![Website](https://img.shields.io/website?url=https%3A%2F%2Fzenstory.ai&label=zenstory.ai)](https://zenstory.ai/)

不只是 AI 对话框——Agent 直接操作你的文件系统，从素材拆解到灵感激发，从大纲规划到逐章写作，全流程 AI 协作。

**[zenstory.ai](https://zenstory.ai/)** &middot; [快速开始](#快速开始) &middot; [English](README_EN.md)

</div>

---

## 为什么选择 ZenStory？

传统的 AI 写作工具停留在"聊天 + 复制粘贴"。ZenStory 让 AI Agent 成为真正的写作伙伴——它直接在文件树上创建、编辑和组织你的创作文件，理解角色设定和世界观约束，甚至能自动拆解参考素材为可复用的创作元素。

<table>
  <tr>
    <td><img src="docs/screenshots/workspace.png" alt="ZenStory 三栏工作台" width="100%"></td>
  </tr>
  <tr>
    <td align="center"><b>三栏工作台 — 文件树 · 编辑器 · AI 对话，一切触手可及</b></td>
  </tr>
</table>

---

## 核心亮点

### 多 Agent 协作写作引擎

不是一个 AI，而是一支专业写作团队。五个专职 Agent 各司其职：

| Agent | 职责 |
|-------|------|
| **Router** | 意图识别，自动选择最佳工作流 |
| **Planner** | 规划故事结构，拆解章节节奏 |
| **Hook Designer** | 设计情节转折、悬念与高潮 |
| **Writer** | 专注内容创作，风格自适应 |
| **Quality Reviewer** | 一致性检查、质量把关 |

四种智能工作流——快速直写、标准流程、完整协作、转折专攻——Router 自动判断任务复杂度，匹配最优路径。

### 对话 x 文件系统 = 全新创作范式

AI 不只停留在对话框里，它直接操作你的创作文件：

- **对话中完成文件操作** — "帮我创建一个反派角色"，Agent 自动新建角色卡并填充设定
- **上下文感知** — AI 理解你的角色关系、世界观规则，不会写出"穿帮"的内容
- **Diff 审阅模式** — AI 修改先展示差异对比，确认后再应用，掌控权始终在你手里
- **流式生成** — 实时看到 AI 逐字创作的过程，随时介入调整

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

### 素材库 & 灵感引擎

**素材拆解** — 上传你欣赏的参考作品（小说片段、写作教程、风格范例），AI 自动拆解为可复用的创作元素：角色模板、情节结构、叙事技巧、对话风格……

**灵感激发** — 基于项目上下文，AI 主动生成创意灵感卡片，打破创作瓶颈。你的素材越丰富，灵感越精准。

**混合检索（RAG）** — 关键词 + 向量语义搜索双引擎，精准定位海量素材中的相关片段。

### 技能系统 & 市场

13+ 内置专业写作技能，开箱即用：

| 分类 | 技能 |
|------|------|
| 写作 | 继续写作 · 场景描写 · 对话生成 · 开头创作 |
| 情节 | 冲突设计 · 悬念设计 · 反转设计 · 节奏控制 |
| 风格 | 沉浸增强 · 文本润色 |
| 设定 | 角色创建 · 大纲生成 · 世界观构建 |

支持自定义技能创建，Markdown 格式定义，一键分享到技能市场。社区共建，越用越强。

### 专业写作工作台

- **六种文件类型** — 大纲、草稿、剧本、角色、世界观、片段，各类型独立编辑界面
- **智能排序** — 自动识别中英文章节编号（"第一章" / "Chapter 1"），按顺序排列
- **版本快照** — 每次编辑自动保存，一键对比任意两个版本的差异，支持回滚
- **项目级快照** — 整个项目的时光机，随时回到任意创作节点
- **多格式导出** — 一键导出 Word / Markdown / 纯文本，章节自动按序合并
- **语音输入** — 语音转文字，长Press 录音，移动端友好
- **深色模式** — 护眼写作，自动跟随系统偏好
- **中英双语** — 界面全面国际化支持

<table>
  <tr>
    <td align="center"><b>版本对比与回滚</b></td>
    <td align="center"><b>AI 技能市场</b></td>
  </tr>
  <tr>
    <td><img src="docs/screenshots/version-history.png" alt="版本历史" width="100%"></td>
    <td><img src="apps/web/public/docs-images/user-guide/skills.png" alt="技能市场" width="100%"></td>
  </tr>
</table>

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

> 生产部署（PostgreSQL + Redis）请参考 [docs/docker-compose.md](docs/docker-compose.md)。

---

## 路线图

- [x] 多 Agent 协作写作引擎
- [x] 素材库 AI 拆解
- [x] 灵感引擎
- [x] 技能系统 & 市场
- [x] 版本快照 & Diff 对比
- [x] 语音输入
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
