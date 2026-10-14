# Jev Explorer

Jev Explorer is an engineering experiment that evaluates AI-generated tool calls before they execute.

It uses [Jev](https://jevtypesafeai.com) for typed decision signals (`choice`, `score`, `noul`), then applies a deterministic application policy. Jev does not choose the final action. Jev Explorer does.

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

The dev server is http://localhost:5173. The Jev Decision Explorer checks `GET /health`, then lets you run choice, score, and noul against the Jev Explorer API. See `frontend/README.md` for the fields and error messages.

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
npm test
npm run build
```

## API documentation

With the backend running, FastAPI serves interactive docs at http://localhost:8000/docs and the OpenAPI schema at http://localhost:8000/openapi.json.

`GET /health` does not call Jev. These routes do:

| Method | Path | What it returns |
| --- | --- | --- |
| `POST` | `/api/v1/jev/choice` | The selected criteria key, confidence, and per-option probabilities |
| `POST` | `/api/v1/jev/score` | A score index on your scale, probabilities, and legend when Jev sends one |
| `POST` | `/api/v1/jev/noul` | A calibrated probability from 0 to 1 that the answer is yes |

Each route sends one question to Jev `POST /api/v1/decide` (the URL in `JEV_BASE_URL`). The response is Jev's typed signal plus `model` and `usage` when Jev includes them. Jev Explorer does not turn that signal into execute, confirm, or block. Policy stays in `backend/app/guard/`.

### Choice

`criteria` is a map of up to 255 options. The key is the value Jev may select. `state` is a string, object, or array. `model` is optional on the API; the explorer never sends it, so the server uses `JEV_MODEL`.

```json
{
  "state": "Customer: I was charged twice and nobody has replied for 3 days.",
  "instructions": "Where should this go?",
  "criteria": {"billing": "money", "bug": "broken", "account": "login"}
}
```

```json
{
  "model": "jev-1.13.0",
  "type": "choice",
  "choice": "billing",
  "confidence": 0.99,
  "probabilities": {"billing": 0.99, "bug": 0.0, "account": 0.01},
  "usage": {"input_tokens": 62, "cost_usd": 0.000026, "credits_remaining_usd": 4.999974}
}
```

`choice` is one of the criteria keys. An unknown selection is an error, not a fallback.

### Score

`criteria` is an ordered list of 2–10 level descriptions, low to high. Jev's `score` is a position on that index. `0` is the first level. The value may be fractional, such as `2.97`. This API does not clamp it and does not shift it onto a 1–5 scale. The gateway's older parser still remaps a score for policy; these HTTP routes do not.

```json
{
  "state": "Nobody has replied for 3 days.",
  "instructions": "How urgent is this?",
  "criteria": ["routine", "today", "urgent", "critical"]
}
```

```json
{
  "model": "jev-1.13.0",
  "type": "score",
  "score": 2.97,
  "confidence": 1.0,
  "probabilities": {"0": 0.0, "3": 1.0},
  "legend": {"0": "routine", "3": "critical, about to churn"},
  "usage": {"input_tokens": 434, "output_tokens": 75}
}
```

`confidence` and `legend` are omitted by some documented Jev examples, so they are null when absent. `legend` maps an index string to the level text Jev echoes. `usage` may include `input_tokens`, `output_tokens`, `cost_usd`, and `credits_remaining_usd`; other usage keys are preserved.

### Noul

No criteria. `noul` is the probability the answer is yes. It is not a boolean, and this route does not apply a cutoff.

```json
{
  "state": "Delete the production database.",
  "instructions": "Escalate to a human immediately?"
}
```

```json
{"model": "jev-1.13.0", "type": "noul", "noul": 0.94, "usage": null}
```

### Errors

Failed requests use `{"error": {"code": "...", "message": "..."}}`. Validation errors also include `details`.

| HTTP | `code` | When |
| --- | --- | --- |
| 422 | `validation_error` | The JSON does not match the route's schema. Jev is not called. |
| 429 | `jev_rate_limited` | The existing anonymous-id or client-IP budget is exhausted. |
| 502 | `jev_upstream_error` | Jev responded with an HTTP error. |
| 502 | `jev_network_error` | The connection to Jev failed. |
| 502 | `jev_invalid_response` | The body was not the documented decision shape. |
| 503 | `jev_not_configured` | `JEV_API_KEY` is missing. The process still starts, and `/health` still works. |
| 504 | `jev_timeout` | Jev did not answer within `JEV_TIMEOUT_SECONDS`. |
| 500 | `internal_error` | Unexpected server failure. The body has no traceback. |

Responses never include the API key.

### Tests without a live key

```bash
cd backend
uv run pytest
uv run ruff check app tests
```

The decision tests inject a fake Jev transport. They do not read a real key and they do not call the hosted API.

## How the gateway works

```text
User request → Agent → Proposed tool call → Jev Explorer
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
| `backend/app/jev/` | Decide client. HTTP routes send one question; the gateway can still batch three |
| `backend/app/guard/policy.py` | Deterministic thresholds → policy outcome |
| `backend/app/guard/gateway.py` | Orchestration + audit events |
| `backend/app/tools/` | Sandboxed demo tools only |
| `backend/app/execution/` | Run tools only after policy (and optional approval) |
| `frontend/` | User interface |

Policy defaults are in `backend/.env.example`. Live Jev calls use two rate-limit layers: per anonymous id, and per public IP. Demo mode does not consume that budget.

A longer write-up of the original experiment is in [docs/case-study.md](docs/case-study.md).

## Existing production deploy

`scripts/deploy-production.sh` builds the API image from `backend/` and expects the process to listen on container port `8000`. Health checks call `GET /health`. Nginx site config is in `deploy/nginx/jev-explorer.conf.template`. This phase does not add new deployment tooling. If a local `scripts/deploy.config` still sets `CONTAINER_PORT=8501`, change it to `8000` before the next deploy.

## Limitations

- Sandboxed / simulated tools only
- Not a production security boundary
- Jev signals are not correctness guarantees
- The explorer demonstrates the three decision APIs. It does not run policy or tools.
