#!/usr/bin/env bash
set -euo pipefail

BACKEND_URL="${ZENSTORY_BACKEND_URL:-}"
FRONTEND_URL="${ZENSTORY_FRONTEND_URL:-}"
SMOKE_USERNAME="${ZENSTORY_SMOKE_USERNAME:-}"
SMOKE_PASSWORD="${ZENSTORY_SMOKE_PASSWORD:-}"
TIMEOUT_SECONDS="${ZENSTORY_SMOKE_TIMEOUT_SECONDS:-480}"
SLEEP_SECONDS=10
MAX_RETRIES=$(( TIMEOUT_SECONDS / SLEEP_SECONDS ))
if (( MAX_RETRIES < 1 )); then
  MAX_RETRIES=1
fi

if [[ -z "$BACKEND_URL" || -z "$FRONTEND_URL" ]]; then
  echo "[zenstory-smoke] ZENSTORY_BACKEND_URL and ZENSTORY_FRONTEND_URL must both be provided."
  exit 1
fi

BACKEND_URL="${BACKEND_URL%/}"
FRONTEND_URL="${FRONTEND_URL%/}"

log() {
  echo "[zenstory-smoke] $1"
}

wait_for_backend_health() {
  local health_url="${BACKEND_URL}/health"
  local i=1

  log "Waiting for backend health at ${health_url}"
  while (( i <= MAX_RETRIES )); do
    if curl -fsS --max-time 10 "$health_url" >/tmp/zenstory_health.json 2>/tmp/zenstory_health.err; then
      log "Backend health endpoint is reachable."
      return 0
    fi
    log "Backend not ready yet (${i}/${MAX_RETRIES})."
    sleep "$SLEEP_SECONDS"
    (( i++ ))
  done

  log "Backend health check timed out."
  if [[ -s /tmp/zenstory_health.err ]]; then
    cat /tmp/zenstory_health.err
  fi
  return 1
}

assert_frontend_available() {
  local status_code
  status_code="$(curl -sS -o /tmp/zenstory_frontend.html -w "%{http_code}" --max-time 15 "${FRONTEND_URL}/")"
  if [[ "$status_code" != "200" ]]; then
    log "Frontend check failed with status ${status_code}."
    return 1
  fi
  log "Frontend is reachable."
}

assert_unauth_projects_endpoint() {
  local status_code
  status_code="$(curl -sS -o /tmp/zenstory_projects_unauth.json -w "%{http_code}" --max-time 15 "${BACKEND_URL}/api/v1/projects")"
  if [[ "$status_code" != "401" ]]; then
    log "Expected unauthorized status 401 for /api/v1/projects, got ${status_code}."
    return 1
  fi
  log "Unauthenticated API guard works (401)."
}

run_authenticated_flow() {
  if [[ -z "$SMOKE_USERNAME" || -z "$SMOKE_PASSWORD" ]]; then
    log "ZENSTORY_SMOKE_USERNAME or ZENSTORY_SMOKE_PASSWORD not set, skipping authenticated flow."
    return 0
  fi

  local login_response
  local login_status
  local login_body
  local token
  local project_name
  local create_response
  local create_status
  local create_body
  local project_id

  login_response="$(curl -sS --max-time 20 -w $'\n%{http_code}' \
    -X POST "${BACKEND_URL}/api/auth/login" \
    -H "Content-Type: application/x-www-form-urlencoded" \
    --data-urlencode "username=${SMOKE_USERNAME}" \
    --data-urlencode "password=${SMOKE_PASSWORD}")"

  login_status="$(echo "$login_response" | tail -n1)"
  login_body="$(echo "$login_response" | sed '$d')"
  if [[ "$login_status" != "200" ]]; then
    log "Login failed with status ${login_status}."
    echo "$login_body"
    return 1
  fi

  token="$(echo "$login_body" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("access_token",""))')"
  if [[ -z "$token" ]]; then
    log "Login succeeded but access token is missing."
    return 1
  fi

  local me_status
  me_status="$(curl -sS -o /tmp/zenstory_me.json -w "%{http_code}" --max-time 15 \
    -H "Authorization: Bearer ${token}" \
    "${BACKEND_URL}/api/auth/me")"
  if [[ "$me_status" != "200" ]]; then
    log "Token validation failed via /api/auth/me with status ${me_status}."
    return 1
  fi

  project_name="online-smoke-$(date +%s)"
  create_response="$(curl -sS --max-time 20 -w $'\n%{http_code}' \
    -X POST "${BACKEND_URL}/api/v1/projects" \
    -H "Authorization: Bearer ${token}" \
    -H "Content-Type: application/json" \
    -d "{\"name\":\"${project_name}\",\"description\":\"Online smoke\",\"project_type\":\"novel\"}")"

  create_status="$(echo "$create_response" | tail -n1)"
  create_body="$(echo "$create_response" | sed '$d')"
  if [[ "$create_status" != "200" ]]; then
    log "Project creation failed with status ${create_status}."
    echo "$create_body"
    return 1
  fi

  project_id="$(echo "$create_body" | python3 -c 'import json,sys; print(json.load(sys.stdin)["id"])')"
  log "Project created successfully: id=${project_id}"

  local list_status
  list_status="$(curl -sS -o /tmp/zenstory_projects_list.json -w "%{http_code}" --max-time 15 \
    -H "Authorization: Bearer ${token}" \
    "${BACKEND_URL}/api/v1/projects")"
  if [[ "$list_status" != "200" ]]; then
    log "Project list fetch failed with status ${list_status}."
    return 1
  fi

  local delete_status
  delete_status="$(curl -sS -o /tmp/zenstory_project_delete.json -w "%{http_code}" --max-time 20 \
    -X DELETE \
    -H "Authorization: Bearer ${token}" \
    "${BACKEND_URL}/api/v1/projects/${project_id}")"
  if [[ "$delete_status" != "200" ]]; then
    log "Project delete failed with status ${delete_status}."
    return 1
  fi

  log "Authenticated API flow passed."
}

main() {
  wait_for_backend_health
  assert_frontend_available
  assert_unauth_projects_endpoint
  run_authenticated_flow
  log "zenstory online smoke passed."
}

main "$@"
