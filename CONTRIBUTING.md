# Contributing to ZenStory

Thank you for your interest in contributing! ZenStory is an AI-assisted novel writing workbench built as a monorepo with a React frontend and FastAPI backend.

## Development Setup

### Prerequisites

- Node.js >= 18
- Python >= 3.12
- pnpm (recommended) or npm

### Backend

```bash
cd apps/server
python3 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your API keys (ANTHROPIC_API_KEY, OPENAI_API_KEY, etc.)
```

### Frontend

```bash
cd apps/web
pnpm install
cp .env.example .env.local
```

### Running Both Services

Use two terminals:

```bash
# Terminal 1 — Backend (port 8000)
cd apps/server && source venv/bin/activate && python3 main.py

# Terminal 2 — Frontend (port 5173)
cd apps/web && pnpm dev
```

## Code Style

- **Backend**: Follow PEP 8. We use [ruff](https://docs.astral.sh/ruff/) for linting and formatting.
- **Frontend**: We use ESLint with TypeScript rules. Run `pnpm lint` to check.
- Keep route handlers thin — delegate business logic to the `services/` layer.

## Pull Request Process

1. Fork the repository and create a branch from `main`.
2. Make your changes with clear, focused commits.
3. Ensure CI passes (lint, type-check, build).
4. Open a pull request against `main` with a description of the change and motivation.

## Testing

- **Backend**: `make test` or `pytest` from `apps/server/`. See `apps/server/tests/README.md` for details.
- **Frontend unit tests**: `pnpm run test:run` from `apps/web/`.
- **Frontend E2E**: `pnpm run test:e2e` from `apps/web/`. See `apps/web/e2e/README.md` for setup.

## Commit Messages

Use [Conventional Commits](https://www.conventionalcommits.org/) style:

```
feat: add character relationship graph
fix: resolve draft auto-save race condition
docs: update API endpoint descriptions
chore: upgrade dependencies
```

## License

By contributing, you agree that your contributions will be licensed under the [MIT License](LICENSE).
