#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

SERVER_ENV="${PROJECT_ROOT}/apps/server/.env.docker"
WEB_ENV="${PROJECT_ROOT}/apps/web/.env.docker"

if [[ ! -f "${SERVER_ENV}" || ! -f "${WEB_ENV}" ]]; then
  echo "[ERROR] 缺少 Docker 环境文件。请先执行："
  echo "  cp apps/server/.env.docker.example apps/server/.env.docker"
  echo "  cp apps/web/.env.docker.example apps/web/.env.docker"
  exit 1
fi

cd "${PROJECT_ROOT}"
docker compose up -d --build
