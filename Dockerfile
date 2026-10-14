# One image: Vite build, then the FastAPI runtime.
# Context is the repository root:
#   docker build --platform linux/amd64 -f Dockerfile -t jev-explorer:local .
#
# Vite 8.3 requires Node ^20.19.0 or >=22.12.0. 22.17.1 is the Node version
# verified with this frontend. The runtime stage does not include Node.

FROM node:22.17.1-bookworm-slim AS frontend

WORKDIR /src/frontend

COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

COPY frontend/ ./
RUN npm run build

# ── Python dependencies ────────────────────────────────
FROM python:3.13-slim-bookworm AS builder

COPY --from=ghcr.io/astral-sh/uv:0.9.22 /uv /uvx /bin/

WORKDIR /app

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never

COPY backend/pyproject.toml backend/uv.lock backend/README.md ./
COPY backend/app ./app

RUN uv sync --frozen --no-dev --no-editable

# ── Runtime ────────────────────────────────────────────
FROM python:3.13-slim-bookworm

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --uid 10001 --shell /usr/sbin/nologin appuser

WORKDIR /app

COPY --from=builder /app/.venv /app/.venv
COPY backend/app ./app
COPY backend/demo ./demo
COPY --from=frontend /src/frontend/dist ./static

# Ensure sandbox defaults exist even when local config.json is gitignored
RUN mkdir -p /app/demo/workspace/notes \
    && if [ ! -f /app/demo/workspace/config.json ]; then echo '{}' > /app/demo/workspace/config.json; fi \
    && test -f /app/static/index.html \
    && test -d /app/static/assets

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    DEMO_WORKSPACE=/app/demo/workspace

RUN chown -R appuser:appuser /app

USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD curl --fail http://127.0.0.1:8000/health || exit 1

# One process, no --workers. The Jev rate limiter keeps its counters in this
# process and clears them on restart. Do not add workers without a shared store.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
