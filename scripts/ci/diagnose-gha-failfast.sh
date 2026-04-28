#!/usr/bin/env bash

set -euo pipefail

if ! command -v gh >/dev/null 2>&1; then
  echo "❌ gh CLI is required (https://cli.github.com/)" >&2
  exit 1
fi

usage() {
  cat <<'EOF'
Usage:
  ./scripts/ci/diagnose-gha-failfast.sh <run-id>
  ./scripts/ci/diagnose-gha-failfast.sh --sha <commit-sha>

Examples:
  ./scripts/ci/diagnose-gha-failfast.sh 22803763630
  ./scripts/ci/diagnose-gha-failfast.sh --sha 4c3ece4974a7a9209186029bc769456b9182d8d6
EOF
}

repo_from_origin() {
  local remote
  remote="$(git remote get-url origin 2>/dev/null || true)"
  remote="${remote%.git}"
  if [[ "$remote" =~ github\.com[:/]([^/]+/[^/]+)$ ]]; then
    printf '%s\n' "${BASH_REMATCH[1]}"
    return 0
  fi
  return 1
}

REPO="${GITHUB_REPOSITORY:-$(repo_from_origin || true)}"
if [[ -z "${REPO:-}" ]]; then
  echo "❌ Unable to resolve GitHub repository. Set GITHUB_REPOSITORY=owner/repo." >&2
  exit 1
fi

RUN_ID=""
if [[ "${1:-}" == "--sha" ]]; then
  SHA="${2:-}"
  if [[ -z "$SHA" ]]; then
    usage
    exit 1
  fi
  RUN_ID="$(gh api "repos/$REPO/actions/runs?head_sha=$SHA&per_page=1" --jq '.workflow_runs[0].id // empty')"
  if [[ -z "$RUN_ID" ]]; then
    echo "❌ No workflow run found for sha: $SHA" >&2
    exit 1
  fi
elif [[ -n "${1:-}" ]]; then
  RUN_ID="$1"
else
  usage
  exit 1
fi

echo "Repo: $REPO"
echo "Run:  $RUN_ID"
echo

JOBS_JSON="$(gh api "repos/$REPO/actions/runs/$RUN_ID/jobs?per_page=100")"
echo "$JOBS_JSON" | jq -r '.jobs[] | select(.conclusion=="failure") | [.id, .name] | @tsv' | while IFS=$'\t' read -r job_id job_name; do
  [[ -z "$job_id" ]] && continue
  echo "=== $job_name (job_id=$job_id) ==="
  annotation_msg="$(gh api "repos/$REPO/check-runs/$job_id/annotations?per_page=1" --jq '.[0].message // empty' 2>/dev/null || true)"
  if [[ -n "$annotation_msg" ]]; then
    echo "annotation: $annotation_msg"
  else
    echo "annotation: <none>"
  fi
  echo
done
