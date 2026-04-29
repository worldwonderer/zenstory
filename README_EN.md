<div align="center">

# ZenStory

**Conversational AI Agent Meets File System — The Commercial-Grade Writing Workbench**

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![GitHub Stars](https://img.shields.io/github/stars/worldwonderer/zenstory?style=social)](https://github.com/worldwonderer/zenstory)
[![Website](https://img.shields.io/website?url=https%3A%2F%2Fzenstory.ai&label=zenstory.ai)](https://zenstory.ai/)

Not just another AI chatbox — ZenStory's Agent directly operates your file system. From material decomposition to inspiration generation, from outline planning to chapter-by-chapter writing, the entire creative workflow is AI-collaborative.

**[zenstory.ai](https://zenstory.ai/)** &middot; [Quick Start](#quick-start) &middot; [中文文档](README.md)

</div>

---

## Why ZenStory?

Traditional AI writing tools stop at "chat + copy-paste." ZenStory makes the AI Agent a true writing partner — it creates, edits, and organizes files directly in your file tree, understands character settings and world-building constraints, and can even decompose reference materials into reusable creative elements.

<table>
  <tr>
    <td><img src="docs/screenshots/workspace.png" alt="ZenStory Three-Panel Workspace" width="100%"></td>
  </tr>
  <tr>
    <td align="center"><b>Three-Panel Workspace — File Tree &middot; Editor &middot; AI Chat, everything at your fingertips</b></td>
  </tr>
</table>

---

## Core Highlights

### Multi-Agent Collaborative Writing Engine

Not one AI — a professional writing team. Five specialized agents, each with a clear role:

| Agent | Role |
|-------|------|
| **Router** | Intent classification, automatic workflow selection |
| **Planner** | Story structure and chapter pacing |
| **Hook Designer** | Plot twists, suspense, and climaxes |
| **Writer** | Content creation with adaptive style |
| **Quality Reviewer** | Consistency checking and quality assurance |

Four intelligent workflows — Quick Write, Standard, Full Collaboration, and Hook Focus — the Router automatically assesses task complexity and routes to the optimal path.

### Conversation x File System = A New Creative Paradigm

The AI doesn't stay in the chat box — it directly operates your creative files:

- **File operations in conversation** — "Create a villain character" and the Agent automatically creates a character card with filled-in details
- **Context-aware** — The AI understands your character relationships and world-building rules, no continuity errors
- **Diff review mode** — AI changes shown as inline diffs, apply only after your approval — you stay in control
- **Streaming generation** — Watch the AI write in real-time, intervene and adjust at any moment

<table>
  <tr>
    <td align="center"><b>AI Chat-Driven Creation</b></td>
    <td align="center"><b>Intelligent File Tree</b></td>
  </tr>
  <tr>
    <td><img src="docs/screenshots/ai-chat.png" alt="AI Chat-Driven Creation" width="100%"></td>
    <td><img src="docs/screenshots/file-tree.png" alt="File Tree Management" width="100%"></td>
  </tr>
</table>

### Material Library & Inspiration Engine

**Material Decomposition** — Upload reference works you admire (novel excerpts, writing guides, style examples) and the AI automatically decomposes them into reusable creative elements: character templates, plot structures, narrative techniques, dialogue styles...

**Inspiration Generator** — Based on your project context, the AI proactively generates creative inspiration cards to break through writer's block. The richer your materials, the more precise the inspiration.

**Hybrid Search (RAG)** — Dual-engine keyword + semantic vector search to precisely locate relevant fragments across massive material libraries.

### Skills System & Marketplace

13+ built-in professional writing skills, ready to use:

| Category | Skills |
|----------|--------|
| Writing | Continue Writing &middot; Scene Description &middot; Dialogue Generation &middot; Opening Creation |
| Plot | Conflict Design &middot; Suspense Design &middot; Reversal Design &middot; Rhythm Control |
| Style | Immersion Enhancement &middot; Text Polishing |
| Setup | Character Creation &middot; Outline Generation &middot; World Building |

Support custom skill creation with Markdown format, one-click sharing to the skill marketplace. Community-driven, growing stronger with use.

### Professional Writing Workbench

- **Six file types** — Outline, Draft, Script, Character, Lore, Snippet — each with a specialized editing interface
- **Smart sorting** — Auto-detects Chinese and Arabic chapter numbers ("第一章" / "Chapter 1"), orders accordingly
- **Version snapshots** — Auto-save on every edit, one-click diff comparison between any two versions, rollback support
- **Project-level snapshots** — A time machine for your entire project, return to any creative checkpoint
- **Multi-format export** — One-click export to Word / Markdown / Plain Text, chapters auto-merged in order
- **Voice input** — Speech-to-text, long-press recording, mobile-friendly
- **Dark mode** — Eye-friendly writing, follows system preference
- **Bilingual** — Full i18n support for English and Chinese interfaces

<table>
  <tr>
    <td align="center"><b>Version Comparison & Rollback</b></td>
    <td align="center"><b>AI Skills Marketplace</b></td>
  </tr>
  <tr>
    <td><img src="docs/screenshots/version-history.png" alt="Version History" width="100%"></td>
    <td><img src="apps/web/public/docs-images/user-guide/skills.png" alt="Skills Marketplace" width="100%"></td>
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

## Roadmap

- [x] Multi-Agent collaborative writing engine
- [x] Material library with AI decomposition
- [x] Inspiration engine
- [x] Skills system & marketplace
- [x] Version snapshots & diff comparison
- [x] Voice input
- [ ] Native mobile app

---

## Contributing

Contributions are welcome!

- [Report a Bug](https://github.com/worldwonderer/zenstory/issues/new?template=bug_report.md)
- [Request a Feature](https://github.com/worldwonderer/zenstory/issues/new?template=feature_request.md)
- Submit a Pull Request

Please read [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## License

[MIT License](LICENSE) &copy; 2024-2026 ZenStory
