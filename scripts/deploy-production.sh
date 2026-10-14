#!/usr/bin/env bash
# Deploy Jev Explorer to DigitalOcean via local Docker build + SSH image transfer.
# One image serves the Vite build and the FastAPI API on container port 8000.
# Architecture: Laptop → docker build/save → ssh load → container on 127.0.0.1:HOST_PORT ← Nginx ← HTTPS
#
# Usage:
#   cp scripts/deploy.config.example scripts/deploy.config   # edit DOMAIN / HOST_PORT
#   ./scripts/deploy-production.sh
#
# Does NOT overwrite remote /opt/apps/<project>/production/.env
# Does NOT copy or delete /opt/apps/agentguard
# Does NOT run Certbot or change DNS or Nginx.
#
# First cutover: create /opt/apps/jev-explorer/production/.env on the server
# by copying the existing AgentGuard env file. This script only checks that
# the destination exists and that the JEV_API_KEY name is present.

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
LEGACY_CONTAINER_NAME="${LEGACY_CONTAINER_NAME:-agentguard-production}"
LEGACY_ENV_FILE="${LEGACY_ENV_FILE:-/opt/apps/agentguard/production/.env}"
LEGACY_WORKSPACE="${LEGACY_WORKSPACE:-/opt/apps/agentguard/production/workspace}"

LEGACY_PRESENT=0
LEGACY_STOPPED=0
LEGACY_IMAGE=""
LEGACY_CONTAINER_PORT=""
PREVIOUS_IMAGE=""
CUTOVER_STARTED=0

log()  { printf '==> %s\n' "$*"; }
warn() { printf '!!  %s\n' "$*" >&2; }
die()  { printf 'ERROR: %s\n' "$*" >&2; exit 1; }

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || die "Missing required command: $1"
}

remote() {
  ssh -o BatchMode=yes -o ConnectTimeout=15 "${SSH_HOST}" "$@"
}

rollback() {
  warn "Deployment failed — attempting rollback…"
  remote "docker rm -f '${CANDIDATE_NAME}' >/dev/null 2>&1 || true"
  # Only the container this run tried to put on HOST_PORT is removed.
  # A candidate failure leaves the current production container alone.
  if [[ "${CUTOVER_STARTED}" == "1" ]]; then
    remote "docker rm -f '${CONTAINER_NAME}' >/dev/null 2>&1 || true"
  fi
  if [[ "${LEGACY_STOPPED}" == "1" ]]; then
    # docker start keeps the legacy container's original port publish,
    # env file, and workspace mount. Do not docker run that image on
    # container port 8000.
    remote "docker start '${LEGACY_CONTAINER_NAME}'" \
      && log "Rollback: started ${LEGACY_CONTAINER_NAME} with its original port mapping" \
      || warn "Rollback could not start ${LEGACY_CONTAINER_NAME} — intervene manually"
    return
  fi
  if [[ "${CUTOVER_STARTED}" == "1" && -n "${PREVIOUS_IMAGE}" ]]; then
    remote "docker run -d \
      --name '${CONTAINER_NAME}' \
      --restart unless-stopped \
      --env-file '${REMOTE_ENV_FILE}' \
      -e DEMO_WORKSPACE=/app/demo/workspace \
      -v '${REMOTE_WORKSPACE}:/app/demo/workspace' \
      -p '127.0.0.1:${HOST_PORT}:${CONTAINER_PORT}' \
      '${PREVIOUS_IMAGE}'" \
      && log "Rollback: restored ${PREVIOUS_IMAGE} on 127.0.0.1:${HOST_PORT} → ${CONTAINER_PORT}" \
      || warn "Rollback could not restart previous container — intervene manually"
  elif [[ "${CUTOVER_STARTED}" == "1" ]]; then
    warn "No previous Jev Explorer image recorded — intervene manually"
  else
    log "Candidate failed before cutover. The current production container was left in place."
  fi
}

GIT_SHA="$(git rev-parse --short=12 HEAD)"
IMAGE_TAG="${PROJECT_NAME}:production-${GIT_SHA}"
IMAGE_LATEST="${PROJECT_NAME}:production"

[[ -n "${DOMAIN}" ]] || die "DOMAIN is required (set in scripts/deploy.config or environment)"
[[ "${CONTAINER_PORT}" == "8000" ]] || die "CONTAINER_PORT must be 8000. The image listens on 8000; the previous AgentGuard image may listen on 8501 and is not restarted with this mapping."
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
log "Host port     : 127.0.0.1:${HOST_PORT} → container :${CONTAINER_PORT}"
log "Remote env    : ${REMOTE_ENV_FILE}"
log "Container     : ${CONTAINER_NAME}"

# ── Preflight ──────────────────────────────────────────
if [[ -n "$(git status --porcelain)" ]]; then
  warn "Working tree is dirty. Docker build copies the working tree, so uncommitted files WOULD be in the image. The tag would still be ${GIT_SHA} from HEAD."
  read -r -p "Continue with a mismatched tag? [y/N] " reply
  [[ "${reply}" =~ ^[Yy]$ ]] || die "Aborted"
fi

log "Checking SSH connectivity…"
remote 'echo ok' >/dev/null || die "Cannot SSH to ${SSH_HOST}. Fix SSH config / keys first."

log "Checking remote env file exists before any container is stopped…"
log "This script does not create, print, or overwrite ${REMOTE_ENV_FILE}."
remote "test -s '${REMOTE_ENV_FILE}'" \
  || die "Missing ${REMOTE_ENV_FILE} on server. Copy ${LEGACY_ENV_FILE} to that path first. ${LEGACY_CONTAINER_NAME} is still untouched."
remote "grep -qE '^(export[[:space:]]+)?JEV_API_KEY=' '${REMOTE_ENV_FILE}'" \
  || die "Remote env file has no JEV_API_KEY entry. The value may be empty. The value was not printed. ${LEGACY_CONTAINER_NAME} is still untouched."

# ── Local validation ───────────────────────────────────
if [[ "${SKIP_TESTS}" != "1" ]]; then
  require_cmd uv
  require_cmd npm
  log "Running backend tests + lint…"
  (cd backend && uv run pytest -q && uv run ruff check app tests)
  log "Running frontend tests, lint, and build…"
  (cd frontend && npm test && npm run lint && npm run build)
else
  warn "SKIP_TESTS=1 — skipping local validation"
fi

# ── Build ──────────────────────────────────────────────
log "Building Docker image ${IMAGE_TAG}…"
docker build \
  --platform linux/amd64 \
  -f Dockerfile \
  -t "${IMAGE_TAG}" \
  -t "${IMAGE_LATEST}" \
  "${REPO_ROOT}"

# ── Transfer ───────────────────────────────────────────
log "Transferring image to ${SSH_HOST}…"
docker save "${IMAGE_TAG}" | gzip | remote 'gunzip | docker load'

log "Verifying remote image tag…"
remote "docker image inspect '${IMAGE_TAG}'" >/dev/null \
  || die "Image ${IMAGE_TAG} not found on server after load"

PREVIOUS_IMAGE="$(remote "docker inspect -f '{{.Config.Image}}' '${CONTAINER_NAME}' 2>/dev/null || true")"
log "Previous image: ${PREVIOUS_IMAGE:-<none>}"

if remote "docker container inspect '${LEGACY_CONTAINER_NAME}' >/dev/null 2>&1"; then
  LEGACY_PRESENT=1
  LEGACY_IMAGE="$(remote "docker inspect -f '{{.Config.Image}}' '${LEGACY_CONTAINER_NAME}'")"
  LEGACY_BINDINGS="$(remote "docker inspect -f '{{json .HostConfig.PortBindings}}' '${LEGACY_CONTAINER_NAME}'")"
  LEGACY_CONTAINER_PORT="$(
    printf '%s' "${LEGACY_BINDINGS}" | HOST_PORT="${HOST_PORT}" python3 -c '
import json, os, sys
raw = json.loads(sys.stdin.read() or "{}")
bindings = raw if isinstance(raw, dict) else {}
host_port = os.environ["HOST_PORT"]
found = ""
for key, conf in bindings.items():
    container_port = key.split("/", 1)[0]
    for item in conf or []:
        if str(item.get("HostPort")) == host_port:
            found = container_port
print(found)
'
  )"
  log "Legacy container: ${LEGACY_CONTAINER_NAME} image ${LEGACY_IMAGE} host-port mapping ${LEGACY_CONTAINER_PORT:-<not on ${HOST_PORT}>}"
fi

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

smoke_check() {
  local name="$1"
  local port="$2"
  log "Smoke checks for ${name} on 127.0.0.1:${port}…"
  remote "PORT='${port}' bash -s" <<'EOF'
set -euo pipefail
fail() { printf 'SMOKE FAIL: %s\n' "$*" >&2; exit 1; }
health=$(curl -fsS "http://127.0.0.1:${PORT}/health")
printf '%s' "$health" | grep -q '"status"' || fail "health body"
printf '%s' "$health" | grep -q '<html' && fail "health returned html"
html=$(curl -fsS "http://127.0.0.1:${PORT}/")
printf '%s' "$html" | grep -q 'id="root"' || fail "index missing root"
assets=$(printf '%s' "$html" | grep -oE '/assets/[^"[:space:]]+' | sort -u)
[ -n "$assets" ] || fail "index has no assets"
while IFS= read -r path; do
  [ -n "$path" ] || continue
  headers=$(curl -fsS -o /dev/null -D - "http://127.0.0.1:${PORT}${path}")
  printf '%s' "$headers" | grep -qi '^content-type:.*text/html' && fail "asset ${path} is html"
done <<END
${assets}
END
if printf '%s' "$html" | grep -q '/favicon.svg'; then
  curl -fsS -o /dev/null "http://127.0.0.1:${PORT}/favicon.svg"
fi
code=$(curl -sS -o /tmp/jev-explorer-unknown.json -w '%{http_code}' "http://127.0.0.1:${PORT}/api/v1/jev/not-a-route")
[ "$code" = "404" ] || fail "unknown route status ${code}"
grep -q 'id="root"' /tmp/jev-explorer-unknown.json && fail "unknown route returned the frontend"
grep -qE '"error"|"detail"' /tmp/jev-explorer-unknown.json || fail "unknown route was not a JSON error"
choice=$(curl -sS -o /tmp/jev-explorer-choice.json -w '%{http_code}' -H 'Content-Type: application/json' -d '{}' "http://127.0.0.1:${PORT}/api/v1/jev/choice")
[ "$choice" = "422" ] || fail "choice validation status ${choice}"
grep -q 'validation_error' /tmp/jev-explorer-choice.json || fail "choice was not validation_error"
grep -q 'id="root"' /tmp/jev-explorer-choice.json && fail "choice returned the frontend"
rm -f /tmp/jev-explorer-unknown.json /tmp/jev-explorer-choice.json
EOF
}

run_container() {
  local name="$1"
  local host_port="$2"
  remote "docker rm -f '${name}' >/dev/null 2>&1 || true"
  remote "docker run -d \
    --name '${name}' \
    --restart unless-stopped \
    --env-file '${REMOTE_ENV_FILE}' \
    -e DEMO_WORKSPACE=/app/demo/workspace \
    -v '${REMOTE_WORKSPACE}:/app/demo/workspace' \
    -p '127.0.0.1:${host_port}:${CONTAINER_PORT}' \
    --label 'app=${PROJECT_NAME}' \
    --label 'env=production' \
    --label 'git.sha=${GIT_SHA}' \
    '${IMAGE_TAG}'"
}

# ── Candidate container (private port) ─────────────────
log "Starting candidate container on 127.0.0.1:${CANDIDATE_PORT}…"
run_container "${CANDIDATE_NAME}" "${CANDIDATE_PORT}"
wait_healthy "${CANDIDATE_NAME}" "${CANDIDATE_PORT}"
smoke_check "${CANDIDATE_NAME}" "${CANDIDATE_PORT}"

# ── Free the public host port, then cut over ───────────
if [[ "${LEGACY_PRESENT}" == "1" && -n "${LEGACY_CONTAINER_PORT}" ]]; then
  log "Stopping ${LEGACY_CONTAINER_NAME} to free 127.0.0.1:${HOST_PORT}. The container is not removed until the new one is healthy."
  remote "docker stop '${LEGACY_CONTAINER_NAME}'" >/dev/null
  LEGACY_STOPPED=1
fi

log "Cutting over to production container ${CONTAINER_NAME} on :${HOST_PORT}…"
CUTOVER_STARTED=1
remote "docker rm -f '${CANDIDATE_NAME}' >/dev/null 2>&1 || true"
run_container "${CONTAINER_NAME}" "${HOST_PORT}"
wait_healthy "${CONTAINER_NAME}" "${HOST_PORT}"
smoke_check "${CONTAINER_NAME}" "${HOST_PORT}"
trap - ERR

if [[ "${LEGACY_STOPPED}" == "1" ]]; then
  log "Leaving ${LEGACY_CONTAINER_NAME} stopped. It still has its original port mapping, env, and workspace."
  log "Do not start it while ${CONTAINER_NAME} is bound to 127.0.0.1:${HOST_PORT}."
fi

# ── Public check (best-effort) ─────────────────────────
log "Checking public HTTPS (best-effort)…"
if curl -fsSI --max-time 15 "https://${DOMAIN}/" >/dev/null 2>&1; then
  log "HTTPS reachable: https://${DOMAIN}/"
else
  warn "https://${DOMAIN}/ not reachable yet — Nginx must proxy this domain to 127.0.0.1:${HOST_PORT}. This script does not change Nginx or DNS."
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
  Workspace   : ${REMOTE_WORKSPACE}
  Previous    : ${PREVIOUS_IMAGE:-<none>}
  Legacy container : ${LEGACY_CONTAINER_NAME} ($([[ "${LEGACY_STOPPED}" == "1" ]] && printf 'stopped, not removed' || printf 'not stopped by this run'))
  Legacy image     : ${LEGACY_IMAGE:-<none>}

Useful commands:
  ssh ${SSH_HOST} 'docker ps --filter name=${CONTAINER_NAME}'
  ssh ${SSH_HOST} 'docker logs -f ${CONTAINER_NAME}'
  ssh ${SSH_HOST} 'curl -fsS http://127.0.0.1:${HOST_PORT}/health'
  curl -I https://${DOMAIN}/

The legacy container, image, env file, and workspace were not deleted.
If a later check shows the new site is wrong, free port ${HOST_PORT} and start the stopped container.
docker start restores its original publish, env, and workspace. Do not run the legacy image on container port ${CONTAINER_PORT}.
  ssh ${SSH_HOST} 'docker rm -f ${CONTAINER_NAME} && docker start ${LEGACY_CONTAINER_NAME}'
────────────────────────────────────────
EOF
