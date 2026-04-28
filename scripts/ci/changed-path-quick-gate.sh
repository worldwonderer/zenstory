#!/usr/bin/env bash
set -euo pipefail

CHANGED_SERVER_BACKEND="${CHANGED_SERVER_BACKEND:-false}"
CHANGED_WEB_FRONTEND="${CHANGED_WEB_FRONTEND:-false}"
CHANGED_CI="${CHANGED_CI:-false}"

run_any="false"

echo "[quick-gate] changed flags:"
echo "  server_backend=${CHANGED_SERVER_BACKEND}"
echo "  web_frontend=${CHANGED_WEB_FRONTEND}"
echo "  ci=${CHANGED_CI}"

if [[ "${CHANGED_SERVER_BACKEND}" == "true" ]]; then
  run_any="true"
  echo "[quick-gate] zenstory backend checks"
  (
    cd apps/server
    if [[ ! -x .venv/bin/python ]]; then
      python3 -m venv .venv
    fi
    if ! .venv/bin/python -m pip --version >/dev/null 2>&1; then
      .venv/bin/python -m ensurepip --upgrade >/dev/null
    fi
    .venv/bin/python -m pip install --upgrade pip >/dev/null
    .venv/bin/pip install -r requirements.txt >/dev/null
    .venv/bin/pip install ruff >/dev/null
    .venv/bin/ruff check \
      api/auth.py \
      api/projects.py \
      api/export.py \
      api/subscription.py \
      services/features/upgrade_funnel_event_service.py \
      tests/test_api/test_growth_regression_baseline.py
    .venv/bin/pytest tests/test_agent/test_project_operations.py -q
    .venv/bin/pytest tests/test_api/test_growth_regression_baseline.py -q
  )
fi

if [[ "${CHANGED_WEB_FRONTEND}" == "true" ]]; then
  run_any="true"
  echo "[quick-gate] web frontend checks"
  (
    cd apps/web
    pnpm install --frozen-lockfile
    pnpm run test:run -- src/lib/__tests__/onboardingPersona.test.ts src/config/__tests__/upgradeExperience.test.ts
  )
fi

if [[ "${CHANGED_CI}" == "true" ]]; then
  run_any="true"
  echo "[quick-gate] CI workflow/script checks"

  for script in scripts/ci/*.sh; do
    bash -n "${script}"
  done

  if command -v yamllint >/dev/null 2>&1; then
    yamllint .github/workflows/test.yml .github/workflows/quick-gate.yml
  else
    echo "[quick-gate] yamllint not found, skipping yaml lint"
  fi
fi

if [[ "${run_any}" != "true" ]]; then
  echo "[quick-gate] no relevant changed-path checks; pass"
fi
