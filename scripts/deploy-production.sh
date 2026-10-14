#!/usr/bin/env bash
# Deploy Jev Explorer to DigitalOcean via local Docker build + SSH image transfer.
# Architecture: Laptop → docker build/save → ssh load → container on 127.0.0.1:HOST_PORT ← Nginx ← HTTPS
#
# Usage:
#   cp scripts/deploy.config.example scripts/deploy.config   # edit DOMAIN / HOST_PORT
#   ./scripts/deploy-production.sh
#
# Does NOT overwrite remote /opt/apps/<project>/production/.env
# Does NOT run Certbot or change DNS automatically.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${REPO_ROOT}"

# Optional local overrides (not committed)
if [[ -f "${SCRIPT_DIR}/deploy.config" ]]; then
  # shellcheck disable=SC1091
  source "${SCRIPT_DIR}/deploy.config"
fi

PROJECT_NAME="${PROJECT_NAME:-jev-explorer}"
SSH_HOST="${SSH_HOST:-mhdmoh-server}"
DOMAIN="${DOMAIN:-}"
HOST_PORT="${HOST_PORT:-8510}"
CONTAINER_PORT="${CONTAINER_PORT:-8000}"
SKIP_TESTS="${SKIP_TESTS:-0}"
REMOTE_APP_DIR="${REMOTE_APP_DIR:-/opt/apps/${PROJECT_NAME}/production}"
REMOTE_ENV_FILE="${REMOTE_ENV_FILE:-${REMOTE_APP_DIR}/.env}"
REMOTE_WORKSPACE="${REMOTE_WORKSPACE:-${REMOTE_APP_DIR}/workspace}"
CONTAINER_NAME="${CONTAINER_NAME:-${PROJECT_NAME}-production}"
CANDIDATE_NAME="${CONTAINER_NAME}-candidate"
CANDIDATE_PORT="${CANDIDATE_PORT:-$((HOST_PORT + 1))}"

log()  { printf '==> %s\n' "$*"; }
warn() { printf '!!  %s\n' "$*" >&2; }
die()  { printf 'ERROR: %s\n' "$*" >&2; exit 1; }

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || die "Missing required command: $1"
}

remote() {
  ssh -o BatchMode=yes -o ConnectTimeout=15 "${SSH_HOST}" "$@"
}

GIT_SHA="$(git rev-parse --short=12 HEAD)"
IMAGE_TAG="${PROJECT_NAME}:production-${GIT_SHA}"
IMAGE_LATEST="${PROJECT_NAME}:production"

[[ -n "${DOMAIN}" ]] || die "DOMAIN is required (set in scripts/deploy.config or environment)"
require_cmd docker
require_cmd ssh
require_cmd git
require_cmd gzip
require_cmd curl

log "Project       : ${PROJECT_NAME}"
log "Git SHA       : ${GIT_SHA}"
log "Image         : ${IMAGE_TAG}"
log "SSH host      : ${SSH_HOST}"
log "Domain        : ${DOMAIN}"
log "Host port     : ${HOST_PORT} → container :${CONTAINER_PORT}"
log "Remote env    : ${REMOTE_ENV_FILE}"

# ── Preflight ──────────────────────────────────────────
if [[ -n "$(git status --porcelain)" ]]; then
  warn "Working tree is dirty — deploying commit ${GIT_SHA} only (uncommitted changes are NOT in the image)."
  read -r -p "Continue? [y/N] " reply
  [[ "${reply}" =~ ^[Yy]$ ]] || die "Aborted"
fi

log "Checking SSH connectivity…"
remote 'echo ok' >/dev/null || die "Cannot SSH to ${SSH_HOST}. Fix SSH config / keys first."

log "Checking remote env file exists (will not overwrite)…"
remote "test -f '${REMOTE_ENV_FILE}'" \
  || die "Missing ${REMOTE_ENV_FILE} on server. Create it from .env.example first."

# ── Local validation ───────────────────────────────────
if [[ "${SKIP_TESTS}" != "1" ]]; then
  log "Running tests + lint…"
  if command -v uv >/dev/null 2>&1; then
    (cd backend && uv run pytest -q && uv run ruff check app tests)
  else
    warn "uv not found — skipping local tests (set SKIP_TESTS=0 after installing uv)"
  fi
else
  warn "SKIP_TESTS=1 — skipping local validation"
fi

# ── Build ──────────────────────────────────────────────
log "Building Docker image ${IMAGE_TAG}…"
docker build \
  --platform linux/amd64 \
  -t "${IMAGE_TAG}" \
  -t "${IMAGE_LATEST}" \
  "${REPO_ROOT}/backend"

# ── Transfer ───────────────────────────────────────────
log "Transferring image to ${SSH_HOST}…"
docker save "${IMAGE_TAG}" | gzip | remote 'gunzip | docker load'

log "Verifying remote image tag…"
remote "docker image inspect '${IMAGE_TAG}'" >/dev/null \
  || die "Image ${IMAGE_TAG} not found on server after load"

# Record previous production image for rollback
PREVIOUS_IMAGE="$(remote "docker inspect -f '{{.Config.Image}}' '${CONTAINER_NAME}' 2>/dev/null || true")"
log "Previous image: ${PREVIOUS_IMAGE:-<none>}"

# Ensure remote dirs exist (do not touch .env)
remote "mkdir -p '${REMOTE_APP_DIR}' '${REMOTE_WORKSPACE}'"

# Seed sandbox workspace from the image once (never overwrite existing files)
log "Seeding remote workspace if empty…"
remote "if [ ! -f '${REMOTE_WORKSPACE}/project-notes.txt' ]; then
  cid=\$(docker create '${IMAGE_TAG}')
  docker cp \"\$cid:/app/demo/workspace/.\" '${REMOTE_WORKSPACE}/'
  docker rm \"\$cid\" >/dev/null
  echo 'workspace seeded'
else
  echo 'workspace already present — leaving as-is'
fi"

rollback() {
  warn "Deployment failed — attempting rollback…"
  remote "docker rm -f '${CANDIDATE_NAME}' >/dev/null 2>&1 || true"
  if [[ -n "${PREVIOUS_IMAGE}" ]]; then
    remote "docker rm -f '${CONTAINER_NAME}' >/dev/null 2>&1 || true"
    remote "docker run -d \
      --name '${CONTAINER_NAME}' \
      --restart unless-stopped \
      --env-file '${REMOTE_ENV_FILE}' \
      -e DEMO_WORKSPACE=/app/demo/workspace \
      -v '${REMOTE_WORKSPACE}:/app/demo/workspace' \
      -p '127.0.0.1:${HOST_PORT}:${CONTAINER_PORT}' \
      '${PREVIOUS_IMAGE}'" \
      && log "Rollback: restored ${PREVIOUS_IMAGE} on port ${HOST_PORT}" \
      || warn "Rollback could not restart previous container — intervene manually"
  else
    warn "No previous image recorded — intervene manually"
  fi
}

trap 'rollback' ERR

wait_healthy() {
  local name="$1"
  local port="$2"
  local tries="${3:-30}"
  local i
  for ((i = 1; i <= tries; i++)); do
    if remote "curl -fsS 'http://127.0.0.1:${port}/health'" >/dev/null 2>&1; then
      log "Healthy: ${name} on :${port}"
      return 0
    fi
    sleep 2
  done
  die "Health check failed for ${name} on 127.0.0.1:${port}"
}

# ── Candidate container (private port) ─────────────────
log "Starting candidate container on 127.0.0.1:${CANDIDATE_PORT}…"
remote "docker rm -f '${CANDIDATE_NAME}' >/dev/null 2>&1 || true"
remote "docker run -d \
  --name '${CANDIDATE_NAME}' \
  --restart unless-stopped \
  --env-file '${REMOTE_ENV_FILE}' \
  -e DEMO_WORKSPACE=/app/demo/workspace \
  -v '${REMOTE_WORKSPACE}:/app/demo/workspace' \
  -p '127.0.0.1:${CANDIDATE_PORT}:${CONTAINER_PORT}' \
  '${IMAGE_TAG}'"

wait_healthy "${CANDIDATE_NAME}" "${CANDIDATE_PORT}"

# ── Cut over to production port ────────────────────────
log "Cutting over to production container ${CONTAINER_NAME} on :${HOST_PORT}…"
remote "docker rm -f '${CONTAINER_NAME}' >/dev/null 2>&1 || true"
remote "docker rm -f '${CANDIDATE_NAME}' >/dev/null 2>&1 || true"
remote "docker run -d \
  --name '${CONTAINER_NAME}' \
  --restart unless-stopped \
  --env-file '${REMOTE_ENV_FILE}' \
  -e DEMO_WORKSPACE=/app/demo/workspace \
  -v '${REMOTE_WORKSPACE}:/app/demo/workspace' \
  -p '127.0.0.1:${HOST_PORT}:${CONTAINER_PORT}' \
  --label 'app=${PROJECT_NAME}' \
  --label 'env=production' \
  --label 'git.sha=${GIT_SHA}' \
  '${IMAGE_TAG}'"

wait_healthy "${CONTAINER_NAME}" "${HOST_PORT}"
trap - ERR

# ── Public check (best-effort) ─────────────────────────
log "Checking public HTTPS (best-effort)…"
if curl -fsSI --max-time 15 "https://${DOMAIN}/" >/dev/null 2>&1; then
  log "HTTPS reachable: https://${DOMAIN}/"
else
  warn "https://${DOMAIN}/ not reachable yet — finish Nginx/DNS/Certbot if first deploy"
fi

# ── Project-specific cleanup (keep current + previous) ─
log "Cleaning older ${PROJECT_NAME}:production-* images (keeping current + previous)…"
remote "docker images '${PROJECT_NAME}' --format '{{.Repository}}:{{.Tag}}' \
  | grep '^${PROJECT_NAME}:production-' \
  | grep -v '${IMAGE_TAG}' \
  | grep -v '${PREVIOUS_IMAGE:-__none__}' \
  | while read -r img; do docker rmi \"\$img\" >/dev/null 2>&1 || true; done" || true

# ── Summary ────────────────────────────────────────────
cat <<EOF

────────────────────────────────────────
Deployment successful
────────────────────────────────────────
  Project     : ${PROJECT_NAME}
  Git SHA     : ${GIT_SHA}
  Image       : ${IMAGE_TAG}
  Container   : ${CONTAINER_NAME}
  Bind        : 127.0.0.1:${HOST_PORT} → ${CONTAINER_PORT}
  Domain      : https://${DOMAIN}
  Env file    : ${REMOTE_ENV_FILE}
  Previous    : ${PREVIOUS_IMAGE:-<none>}

Useful commands:
  ssh ${SSH_HOST} 'docker ps --filter name=${CONTAINER_NAME}'
  ssh ${SSH_HOST} 'docker logs -f ${CONTAINER_NAME}'
  ssh ${SSH_HOST} 'curl -fsS http://127.0.0.1:${HOST_PORT}/health'
  curl -I https://${DOMAIN}/
────────────────────────────────────────
EOF
