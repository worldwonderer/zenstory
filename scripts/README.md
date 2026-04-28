# Scripts Directory

Unified entry point for development, CI, and GitHub CLI utilities.

## Directory Structure

```
scripts/
├── dev/              # Local developer helpers
│   ├── docker-up.sh  # Start zenstory main-site compose (build + detached)
│   └── docker-down.sh # Stop zenstory main-site compose and remove volumes
├── ci/               # CI and local testing
│   ├── ci.sh         # Unified CI runner (--docker/--lite modes)
│   └── README-LOCAL-CI.md
├── github/           # GitHub CLI utilities
│   └── gh-utils.sh   # Unified GitHub operations (logs, watch, pr)
├── quality/          # Code quality checks
│   ├── check-quality.sh      # Unified quality checker (backend/frontend/security/i18n)
│   └── check-hardcoded-text.sh  # i18n hardcoded text detection
└── wait-for-services.sh      # Utility: Wait for Docker services
```

## Quick Reference

### CI Testing

```bash
# Full CI with Docker (default)
./scripts/ci/ci.sh all

# Full CI with SQLite (lightweight, no Docker)
./scripts/ci/ci.sh all --lite

# Backend tests only
./scripts/ci/ci.sh backend --lite

# Frontend tests only
./scripts/ci/ci.sh frontend

# E2E tests (requires Docker)
./scripts/ci/ci.sh e2e

# Start/stop Docker services
./scripts/ci/ci.sh start
./scripts/ci/ci.sh stop
```

### Docker Compose（zenstory 主站）

```bash
# 从任意目录启动（脚本会自动切回仓库根目录）
./scripts/dev/docker-up.sh

# 停止并清理卷
./scripts/dev/docker-down.sh
```

也可直接使用：

```bash
docker compose up -d --build
docker compose down -v
```

### Quality Checks

```bash
# All checks (backend + frontend)
./scripts/quality/check-quality.sh all

# Backend only (Ruff, MyPy, Bandit, Safety)
./scripts/quality/check-quality.sh backend

# Frontend only (ESLint, TypeScript)
./scripts/quality/check-quality.sh frontend

# Security focused (Bandit + Safety)
./scripts/quality/check-quality.sh security

# i18n hardcoded text detection
./scripts/quality/check-quality.sh i18n
```

### GitHub Operations

```bash
# Watch CI for current branch
./scripts/github/gh-utils.sh watch

# Fetch logs for a specific run
./scripts/github/gh-utils.sh logs <run-id>

# Create PR and watch CI
./scripts/github/gh-utils.sh pr "Fix authentication bug"
```

## Detailed Documentation

- **CI Scripts**: See `ci/README-LOCAL-CI.md` for detailed CI usage
- **Quality Scripts**: Run with `--help` for usage information
- **GitHub Utilities**: Run `./scripts/github/gh-utils.sh help` for commands

## Prerequisites

### Backend
- Python 3.11+ with virtual environment at `apps/server/venv`
- Ruff, MyPy, Bandit, Safety installed in venv

### Frontend
- Node.js 18+ with pnpm
- Dependencies installed (`pnpm install`)

### Docker Mode (CI)
- Docker and docker-compose installed
- Docker daemon running

## Integration with IDE

Add these as run configurations or tasks in your IDE:

```json
{
  "name": "Quality Check",
  "command": "./scripts/quality/check-quality.sh all"
},
{
  "name": "CI Test (Lite)",
  "command": "./scripts/ci/ci.sh all --lite"
}
```
