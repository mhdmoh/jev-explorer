# AgentGuard

AgentGuard is an engineering experiment that evaluates AI-generated tool calls before they execute.

It uses [Jev](https://jevtypesafeai.com) for typed decision signals (`choice`, `score`, `noul`), then applies a deterministic application policy. Jev does not choose the final action. AgentGuard does.

The repository is a monorepo:

- `backend/` is a Python API. It holds Jev credentials and calls Jev from the server.
- `frontend/` is a React + TypeScript app. It talks to the backend over HTTP and never calls Jev directly.

Splitting them keeps the API key off the browser and lets the UI and API change independently. See [docs/architecture.md](docs/architecture.md).

> Portfolio experiment — not a production security product. Tools stay sandboxed.

## Prerequisites

- Python 3.12+ and [uv](https://docs.astral.sh/uv/)
- Node.js 22+ and npm

## Repository structure

```text
backend/                 FastAPI app, Jev client, policy, tests
  app/
  tests/
  demo/workspace/        Sandbox filesystem
frontend/                React + TypeScript + Vite
docs/architecture.md
deploy/                  Existing Nginx site template
scripts/                 Existing production deploy script
```

## Backend

```bash
cd backend
uv sync
cp .env.example .env   # optional: set JEV_API_KEY for live Jev
uv run uvicorn app.main:app --reload
```

- API: http://localhost:8000
- OpenAPI docs: http://localhost:8000/docs
- Health: `GET /health` → `{"status":"ok"}`

## Frontend

In a second terminal:

```bash
cd frontend
npm install
cp .env.example .env
npm run dev
```

The dev server is http://localhost:5173. The home screen checks `GET /health` and shows whether the backend is connected.

`VITE_API_BASE_URL` defaults to `http://localhost:8000` when `.env` is absent. The backend allows that Vite origin through `CORS_ALLOW_ORIGINS`.

## Environment variables

Backend and frontend configuration are separate. Real `.env` files are gitignored. Examples are committed.

| Variable | Where | Purpose |
| --- | --- | --- |
| `JEV_API_KEY` | backend | Optional. Enables live Jev. Never expose this to the browser. |
| `JEV_MODEL` | backend | Default `jev-1.13.0` |
| `JEV_BASE_URL` | backend | Default `https://jevtypesafeai.com/api/v1/decide` |
| `JEV_TIMEOUT_SECONDS` | backend | HTTP timeout for Jev |
| `APP_ENV` | backend | `development` uses non-secure cookie settings |
| `LOG_LEVEL` | backend | `DEBUG`, `INFO`, `WARNING`, `ERROR`, or `CRITICAL` |
| `POLICY_VERSION` | backend | Policy version label |
| `DEMO_WORKSPACE` | backend | Sandbox root, default `demo/workspace` |
| `AUTO_EXECUTE_*`, `CONFIRM_*`, `BLOCK_MIN_RISK` | backend | Policy thresholds |
| `RATE_LIMIT_ENABLED` | backend | Limit live Jev calls (default `true`) |
| `ANONYMOUS_RATE_LIMIT_REQUESTS` | backend | Max live decide calls per anonymous id (default `3`) |
| `ANONYMOUS_RATE_LIMIT_WINDOW_SECONDS` | backend | Anonymous window (default `18000` = 5 hours) |
| `IP_RATE_LIMIT_REQUESTS` | backend | Max live decide calls per public IP (default `20`) |
| `IP_RATE_LIMIT_WINDOW_SECONDS` | backend | IP window (default `3600`) |
| `TRUSTED_PROXY_CIDRS` | backend | Peers allowed to set `X-Real-IP` / `X-Forwarded-For` |
| `CORS_ALLOW_ORIGINS` | backend | Comma-separated browser origins. Do not use `*`. |
| `VITE_API_BASE_URL` | frontend | Backend origin, default `http://localhost:8000` |

Without `JEV_API_KEY`, gateway evaluations use deterministic demo signals. Those signals are not live Jev results. The health check does not need a key and does not call Jev.

## Checks

Backend:

```bash
cd backend
uv run pytest
uv run ruff check app tests
```

Frontend (the Vite template lints with oxlint; `npm run build` also runs the TypeScript project build):

```bash
cd frontend
npm run lint
npm run build
```

## API documentation

With the backend running, FastAPI serves interactive docs at http://localhost:8000/docs and the OpenAPI schema at http://localhost:8000/openapi.json.

The only HTTP route in this phase is `GET /health`. Jev primitive routes (`/api/v1/jev/choice`, `/score`, `/noul`) are not implemented. The Jev client, evaluator, policy engine, and gateway remain available as Python modules for the next phase.

## How the gateway works

```text
User request → Agent → Proposed tool call → AgentGuard
                                              ↓
                                      Jev (choice · score · noul)
                                              ↓
                                   Deterministic policy engine
                                              ↓
                         EXECUTE | REQUIRE CONFIRMATION | BLOCK
                                              ↓
                         Sandboxed tool  /  rejection + audit trace
```

| Layer | Responsibility |
| --- | --- |
| `backend/app/agent/` | Propose structured tool calls (never executes) |
| `backend/app/jev/` | One batched decide call → typed signals |
| `backend/app/guard/policy.py` | Deterministic thresholds → policy outcome |
| `backend/app/guard/gateway.py` | Orchestration + audit events |
| `backend/app/tools/` | Sandboxed demo tools only |
| `backend/app/execution/` | Run tools only after policy (and optional approval) |
| `frontend/` | User interface |

Policy defaults are in `backend/.env.example`. Live Jev calls use two rate-limit layers: per anonymous id, and per public IP. Demo mode does not consume that budget.

A longer write-up of the original experiment is in [docs/case-study.md](docs/case-study.md).

## Existing production deploy

`scripts/deploy-production.sh` builds the API image from `backend/` and expects the process to listen on container port `8000`. Health checks call `GET /health`. Nginx site config is in `deploy/nginx/agentguard.conf.template`. This phase does not add new deployment tooling. If a local `scripts/deploy.config` still sets `CONTAINER_PORT=8501`, change it to `8000` before the next deploy.

## Limitations

- Sandboxed / simulated tools only
- Not a production security boundary
- Jev signals are not correctness guarantees
- The decision explorer UI is a connectivity scaffold, not the finished product
