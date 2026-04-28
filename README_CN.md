<div align="center">

# ZenStory

**AI 辅助长篇小说写作工作台**

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![GitHub Stars](https://img.shields.io/github/stars/worldwonderer/zenstory?style=social)](https://github.com/worldwonderer/zenstory)
[![Website](https://img.shields.io/website?url=https%3A%2F%2Fzenstory.ai&label=zenstory.ai)](https://zenstory.ai/)

对话式 AI 写作平台。三栏布局：文件树 + 编辑器 + AI 对话，让创作像聊天一样自然。

**[zenstory.ai](https://zenstory.ai/)** · [快速开始](#快速开始) · [参与贡献](CONTRIBUTING.md)

[English](README.md) · [中文](#功能特性)

</div>

---

## 功能特性

- **AI 对话驱动写作** — 与 AI 聊天即可生成大纲、章节、角色设定
- **文件树管理** — 大纲、草稿、角色、世界观统一组织，支持拖拽排序
- **版本历史** — 每次编辑自动快照，一键对比、回滚任意版本
- **多模型支持** — DeepSeek / Anthropic Claude，配置一个 Key 即可开始
- **AI Diff 审阅** — 查看 AI 建议的内联差异，确认后再应用
- **语音输入** — 语音转文字，解放双手
- **多格式导出** — 一键导出 Word / Markdown / 纯文本
- **深色模式** — 护眼写作，自动跟随系统
- **国际化** — 支持中英文界面

---

## 页面预览

<table>
  <tr>
    <td align="center"><b>三栏工作台</b></td>
    <td align="center"><b>AI 对话写作</b></td>
  </tr>
  <tr>
    <td><img src="docs/screenshots/workspace.png" alt="三栏工作台" width="400"></td>
    <td><img src="docs/screenshots/ai-chat.png" alt="AI 对话写作" width="400"></td>
  </tr>
  <tr>
    <td align="center"><b>文件树管理</b></td>
    <td align="center"><b>版本历史</b></td>
  </tr>
  <tr>
    <td><img src="docs/screenshots/file-tree.png" alt="文件树管理" width="400"></td>
    <td><img src="docs/screenshots/version-history.png" alt="版本历史" width="400"></td>
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

> 数据持久化在 Docker volume 中，开箱即用。

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

## 技术栈

| 层 | 技术 |
|---|---|
| **前端** | React 19 · TypeScript · Vite · Tailwind CSS 4 · TanStack Query · Zustand · Tiptap |
| **后端** | FastAPI · SQLModel · Alembic · JWT · ChromaDB |
| **AI** | Anthropic Claude · DeepSeek（OpenAI 兼容接口） |
| **部署** | Vercel (前端) · Railway (后端) · Cloudflare CDN |

## 项目结构

```text
zenstory/
├── apps/
│   ├── web/          # React 前端 (Vite + TypeScript)
│   └── server/       # FastAPI 后端 (SQLModel + Alembic)
├── docs/             # 文档与截图
├── scripts/          # CI 与质量检查脚本
└── docker-compose.yml
```

---

## 参与贡献

欢迎通过以下方式参与：

- [提交 Bug](https://github.com/worldwonderer/zenstory/issues/new?template=bug_report.md)
- [功能建议](https://github.com/worldwonderer/zenstory/issues/new?template=feature_request.md)
- 提交 Pull Request

请阅读 [CONTRIBUTING.md](CONTRIBUTING.md) 了解贡献流程。

## 许可证

[MIT License](LICENSE) © 2024-2026 ZenStory
