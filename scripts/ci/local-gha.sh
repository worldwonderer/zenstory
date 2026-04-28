#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
ZENSTORY_CI_SCRIPT="$ROOT_DIR/scripts/ci/ci.sh"

RUN_E2E=false
SKIP_DB_TESTS=false
ZENSTORY_E2E_SUITE="${ZENSTORY_E2E_SUITE:-default}"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

usage() {
  cat <<USAGE
Usage: $(basename "$0") [--with-e2e] [--skip-db-tests]

Run GitHub-style CI checks locally before push.

Options:
  --with-e2e        run browser E2E suites (slow)
  --skip-db-tests   skip Docker-dependent DB integration tests
  -h, --help        show this help

Examples:
  $(basename "$0")
  $(basename "$0") --with-e2e
  ZENSTORY_E2E_SUITE=nightly $(basename "$0") --with-e2e
  $(basename "$0") --skip-db-tests
USAGE
}

log_info() {
  echo -e "${GREEN}[INFO]${NC} $1"
}

log_step() {
  echo -e "${BLUE}[STEP]${NC} $1"
}

log_warn() {
  echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
  echo -e "${RED}[ERROR]${NC} $1"
}

require_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    log_error "Missing required command: $1"
    exit 1
  fi
}

setup_pnpm() {
  require_cmd pnpm
  if command -v corepack >/dev/null 2>&1; then
    corepack enable >/dev/null 2>&1 || true
    corepack prepare pnpm@10.29.3 --activate >/dev/null 2>&1 || true
  fi
  log_info "Using pnpm $(pnpm --version)"
}

run_zenstory_checks() {
  setup_pnpm

  if [[ ! -x "$ZENSTORY_CI_SCRIPT" ]]; then
    log_error "Cannot find executable script: $ZENSTORY_CI_SCRIPT"
    exit 1
  fi

  local mode="--docker"
  if [[ "$SKIP_DB_TESTS" == "true" ]]; then
    mode="--lite"
    log_warn "Using zenstory lite mode (--skip-db-tests)"
  fi

  log_step "zenstory: lint"
  "$ZENSTORY_CI_SCRIPT" lint "$mode"

  log_step "zenstory: unit tests"
  "$ZENSTORY_CI_SCRIPT" test "$mode"

  if [[ "$RUN_E2E" == "true" ]]; then
    log_step "zenstory: E2E"
    E2E_SUITE="$ZENSTORY_E2E_SUITE" "$ZENSTORY_CI_SCRIPT" e2e --docker
  else
    log_warn "Skip zenstory E2E (use --with-e2e to enable)"
  fi
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --with-e2e)
      RUN_E2E=true
      shift
      ;;
    --skip-db-tests)
      SKIP_DB_TESTS=true
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      log_error "Unknown argument: $1"
      usage
      exit 1
      ;;
  esac
done

log_info "Local CI start (e2e=$RUN_E2E, zenstory_e2e_suite=$ZENSTORY_E2E_SUITE, skip_db_tests=$SKIP_DB_TESTS)"

run_zenstory_checks

log_info "Local CI completed successfully"
