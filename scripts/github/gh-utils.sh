#!/bin/bash
# GitHub CLI utilities - unified entry point for GitHub operations
set -e

# Usage: ./scripts/github/gh-utils.sh [logs|watch|pr] [args]

COMMAND="${1:-help}"
shift || true

case "$COMMAND" in
  logs)
    # Fetch logs for a specific CI run
    if [ -z "$1" ]; then
      echo "Usage: $0 logs <run-id>"
      echo "Get run ID from: gh run list --branch \$(git branch --show-current)"
      exit 1
    fi

    RUN_ID="$1"
    echo "📋 Fetching logs for run: $RUN_ID"
    gh run view "$RUN_ID" --log
    ;;

  watch)
    # Watch CI status for current branch
    BRANCH=$(git branch --show-current)
    echo "👀 Watching CI for branch: $BRANCH"

    gh run list --branch "$BRANCH" --limit 1
    gh run watch
    ;;

  pr)
    # Create PR and watch CI
    if [ -z "$1" ]; then
      echo "Usage: $0 pr \"PR title\""
      exit 1
    fi

    TITLE="$1"
    BRANCH=$(git branch --show-current)

    echo "🚀 Creating PR: $TITLE"
    gh pr create --title "$TITLE" --body "Automated PR creation"

    echo "👀 Watching CI..."
    exec "$0" watch
    ;;

  help|*)
    echo "GitHub CLI Utilities"
    echo ""
    echo "Usage: $0 [logs|watch|pr] [args]"
    echo ""
    echo "Commands:"
    echo "  logs <run-id>  - Fetch CI logs for a specific run"
    echo "  watch          - Watch CI status for current branch"
    echo "  pr <title>     - Create PR and watch CI"
    echo ""
    echo "Examples:"
    echo "  $0 logs 1234567890"
    echo "  $0 watch"
    echo "  $0 pr \"Fix authentication bug\""
    exit 1
    ;;
esac
