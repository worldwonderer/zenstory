# CI Scripts

Unified CI runner for local testing and development.

## ci.sh - Unified CI Entry Point

The main script that combines functionality from the legacy `ci-local.sh` and `local-ci.sh`.

### Usage

```bash
./scripts/ci/ci.sh <command> [--docker|--lite]
```

### Commands

| Command   | Description                                    |
|-----------|------------------------------------------------|
| `all`     | Run full CI pipeline (lint + test + e2e)       |
| `frontend`| Run frontend lint and tests only               |
| `backend` | Run backend lint and tests only                |
| `lint`    | Run lint checks only                           |
| `test`    | Run unit tests only (no e2e)                   |
| `e2e`     | Run E2E tests only (`--docker` or `--lite`)    |
| `start`   | Start Docker services (--docker mode only)     |
| `stop`    | Stop Docker services (--docker mode only)      |
| `help`    | Show help message                              |

### Modes

| Mode      | Description                                    |
|-----------|------------------------------------------------|
| `--docker`| Use Docker environment (PostgreSQL + Redis) - default |
| `--lite`  | Use SQLite lightweight mode (no Docker required) |

### Examples

```bash
# Full CI with Docker (default)
./scripts/ci/ci.sh all

# Full CI with SQLite (lightweight)
./scripts/ci/ci.sh all --lite

# Backend tests with SQLite
./scripts/ci/ci.sh backend --lite

# Frontend tests only
./scripts/ci/ci.sh frontend

# E2E tests (Docker)
./scripts/ci/ci.sh e2e

# E2E tests (SQLite lite mode)
./scripts/ci/ci.sh e2e --lite

# Start/stop Docker services
./scripts/ci/ci.sh start
./scripts/ci/ci.sh stop
```

### Environment Variables

The script sets these test environment variables automatically:

| Variable              | Docker Mode Value                    | Lite Mode Value          |
|-----------------------|-------------------------------------|--------------------------|
| `DATABASE_URL`        | `postgresql://...@localhost:5433`   | `sqlite:///./test.db`    |
| `REDIS_URL`           | `redis://localhost:6380/1`          | `redis://localhost:6379/1`|
| `OPENAI_API_KEY`      | `test-key-for-ci-testing`           | Same                     |
| `JWT_SECRET_KEY`      | `test-secret-key-...`               | Same                     |
| `ANTHROPIC_API_KEY`   | `test-key-for-ci-testing`           | Same                     |

### Browser lane selection

`ci.sh e2e` now supports explicit browser lanes via `E2E_SUITE`:

| E2E_SUITE | Purpose | Default CI role |
|---|---|---|
| `smoke` | Fast release-signal browser sanity | Local default |
| `default` | Default required web functional gate | PR required |
| `nightly` | Higher-value restored suites with dedicated fixtures | Nightly only |
| `release` | Expensive or baseline-driven browser checks | Release/manual |
| `full` | Everything currently automated via flags | Manual / branch-wide |

Examples:

```bash
# Required PR-style browser lane
E2E_SUITE=default ./scripts/ci/ci.sh e2e --lite

# Nightly lane
E2E_SUITE=nightly ./scripts/ci/ci.sh e2e --lite

# Release/manual lane
E2E_SUITE=release ./scripts/ci/ci.sh e2e --lite
```

## zenstory lane policy

维护者治理说明见：

- `docs/advanced/e2e-lane-governance-2026-04.md`

### Default required
- `auth.spec.ts`
- `session.spec.ts`
- `projects.spec.ts`
- `points.spec.ts`
- `onboarding-persona.spec.ts`
- `public-skills.spec.ts`
- `referral.spec.ts`
- `security.spec.ts`
- `subscription.spec.ts`
- `settings-regression.spec.ts`
- `settings.spec.ts`
- `smoke.spec.ts`

### Nightly
- `versions.spec.ts`
- `skills.spec.ts`
- `skills-flow.spec.ts`

### Permanent opt-in / release-manual
- `visual.spec.ts`
- `performance.spec.ts`
- `large-document.spec.ts`
- `concurrent.spec.ts`
- `voice.spec.ts` real interaction chain

## Promotion rules

### opt-in -> nightly
- 7 consecutive days green
- failure rate < 5%
- no manual step required
- seeded fixture / persona documented
- reproducible in clean env

### nightly -> default required
- 14 consecutive days green
- failure rate < 1%
- fits PR runtime budget
- no dependency on unstable external service
- failures are diagnosable and reproducible

### Docker Services

In Docker mode, the script uses `apps/server/docker-compose.test.yml`:

- **PostgreSQL**: Port 5433 (test database)
- **Redis**: Port 6380 (test cache)

### Cleanup

- **Docker mode**: Automatic cleanup on script exit (via trap)
- **Lite mode**: Automatic SQLite test database cleanup

### Related Files

- `apps/server/docker-compose.test.yml` - Docker test services configuration
- `scripts/wait-for-services.sh` - Service health check utility

## local-gha.sh - GitHub Workflow Local Mirror

Run a GitHub-style local gate before push (especially useful when Actions quota is tight).

### Usage

```bash
./scripts/ci/local-gha.sh [--with-e2e] [--skip-db-tests]
```

### Examples

```bash
# Default local gate (lint + unit tests)
./scripts/ci/local-gha.sh

# Include browser E2E
./scripts/ci/local-gha.sh --with-e2e

# Run zenstory nightly browser lane locally
ZENSTORY_E2E_SUITE=nightly ./scripts/ci/local-gha.sh --with-e2e

# Run without Docker (skip DB integration checks)
./scripts/ci/local-gha.sh --skip-db-tests
```

### Notes

- Script pins/activates pnpm `10.29.3` locally to match lockfile behavior.
- zenstory checks reuse existing `ci.sh` Docker flow.
- `--skip-db-tests` is available for environments where Docker is unavailable.

## changed-path-quick-gate.sh - Changed-path 快速门禁

用于 PR 快速反馈：按变更路径只执行对应子集检查（不替代 full gate）。

### Usage

```bash
CHANGED_SERVER_BACKEND=false \
CHANGED_WEB_FRONTEND=false \
CHANGED_CI=true \
bash scripts/ci/changed-path-quick-gate.sh
```

### 在 CI 中

- 由 `.github/workflows/quick-gate.yml` 通过 `dorny/paths-filter` 注入变更标记。
- 典型检查：
  - zenstory backend：ruff + 状态机契约测试子集
  - web frontend：关键 vitest 子集
  - CI 目录：shell 语法检查 + workflow YAML lint（若可用）

## diagnose-gha-failfast.sh - 快速定位 Actions“秒失败”原因

当 GitHub Actions 任务在 1-3 秒内全部失败时，可用该脚本快速读取 check-run annotation，定位是否为账号配额/计费问题。

### Usage

```bash
./scripts/ci/diagnose-gha-failfast.sh <run-id>
./scripts/ci/diagnose-gha-failfast.sh --sha <commit-sha>
```

### Examples

```bash
./scripts/ci/diagnose-gha-failfast.sh 22803763630
./scripts/ci/diagnose-gha-failfast.sh --sha 4c3ece4974a7a9209186029bc769456b9182d8d6
```
