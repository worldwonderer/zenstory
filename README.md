<div align="center">

# ZenStory

**AI-Powered Novel Writing Workbench**

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![GitHub Stars](https://img.shields.io/github/stars/worldwonderer/zenstory?style=social)](https://github.com/worldwonderer/zenstory)
[![Website](https://img.shields.io/website?url=https%3A%2F%2Fzenstory.ai&label=zenstory.ai)](https://zenstory.ai/)

Write novels with a conversational AI interface. Three-panel layout: File Tree + Editor + AI Chat.

**[zenstory.ai](https://zenstory.ai/)** · [Getting Started](#quick-start) · [Documentation](docs/) · [Contributing](CONTRIBUTING.md)

[English](#features) · [中文文档](README_CN.md)

</div>

---

## Features

- **AI Chat-Driven Writing** — Generate outlines, chapters, and character profiles through natural conversation
- **File Tree Management** — Organize outlines, drafts, characters, and world-building entries with drag-and-drop
- **Version History** — Automatic snapshots on every edit, one-click diff comparison and rollback
- **Multi-Model Support** — Works with DeepSeek, Anthropic Claude, and OpenAI-compatible providers
- **AI Diff Review** — Review AI-suggested changes with inline diff before accepting
- **Voice Input** — Speech-to-text for hands-free writing
- **Multi-Format Export** — Export to Word, Markdown, or plain text
- **Dark Mode** — Eye-friendly writing that follows your system preference
- **i18n** — English and Chinese interface support

## 功能特性

- **AI 对话驱动写作** — 与 AI 聊天即可生成大纲、章节、角色设定
- **文件树管理** — 大纲、草稿、角色、世界观统一组织，支持拖拽排序
- **版本历史** — 每次编辑自动快照，一键对比、回滚任意版本
- **多模型支持** — DeepSeek / Anthropic Claude，配置一个 Key 即可开始
- **AI Diff 审阅** — 查看AI建议的内联差异，确认后再应用
- **语音输入** — 语音转文字，解放双手
- **多格式导出** — 一键导出 Word / Markdown / 纯文本
- **深色模式** — 护眼写作，自动跟随系统
- **国际化** — 支持中英文界面

---

## Screenshots

<table>
  <tr>
    <td align="center"><b>Three-Panel Workspace</b></td>
    <td align="center"><b>AI Chat Writing</b></td>
  </tr>
  <tr>
    <td><img src="docs/screenshots/workspace.png" alt="Workspace" width="400"></td>
    <td><img src="docs/screenshots/ai-chat.png" alt="AI Chat" width="400"></td>
  </tr>
  <tr>
    <td align="center"><b>File Tree</b></td>
    <td align="center"><b>Version History</b></td>
  </tr>
  <tr>
    <td><img src="docs/screenshots/file-tree.png" alt="File Tree" width="400"></td>
    <td><img src="docs/screenshots/version-history.png" alt="Version History" width="400"></td>
  </tr>
</table>

---

## Quick Start

### Prerequisites

- Node.js >= 18
- Python >= 3.12
- pnpm

### Option 1: Docker Compose (Recommended)

One API key, one command:

```bash
export DEEPSEEK_API_KEY=your-key
docker compose up -d --build
```

Open:
- Frontend: http://localhost:5173
- API Docs: http://localhost:8000/docs

> Data persists in Docker volumes. Works with SQLite out of the box.

### Option 2: Local Development

```bash
# 1. Backend
cd apps/server
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # Edit .env to add your API key
python3 main.py

# 2. Frontend (new terminal)
cd apps/web
pnpm install
cp .env.example .env.local
pnpm dev
```

> For production deployment (PostgreSQL + Redis), see [docs/docker-compose.md](docs/docker-compose.md).

---

## Tech Stack

| Layer | Technologies |
|-------|-------------|
| **Frontend** | React 19 · TypeScript · Vite · Tailwind CSS 4 · TanStack Query · Zustand · Tiptap |
| **Backend** | FastAPI · SQLModel · Alembic · JWT · ChromaDB |
| **AI** | Anthropic Claude · DeepSeek (OpenAI-compatible) |
| **Infra** | Vercel (frontend) · Railway (backend) · Cloudflare CDN |

## Project Structure

```text
zenstory/
├── apps/
│   ├── web/          # React frontend (Vite + TypeScript)
│   └── server/       # FastAPI backend (SQLModel + Alembic)
├── docs/             # Documentation & screenshots
├── scripts/          # CI and quality check scripts
└── docker-compose.yml
```

---

## Contributing

Contributions are welcome! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

- [Report a Bug](https://github.com/worldwonderer/zenstory/issues/new?template=bug_report.md)
- [Request a Feature](https://github.com/worldwonderer/zenstory/issues/new?template=feature_request.md)

## License

[MIT License](LICENSE) © 2024-2026 ZenStory
