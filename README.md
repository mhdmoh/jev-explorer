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
Dockerfile               Frontend build plus API runtime
backend/                 FastAPI app, Jev client, policy, tests
  app/
  tests/
  demo/workspace/        Sandbox filesystem
frontend/                React + TypeScript + Vite
docs/architecture.md
deploy/                  Nginx site template
scripts/                 Production deploy script
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
npm run dev
```

The dev server is http://localhost:5173. It proxies `/health` and `/api` to http://127.0.0.1:8000. The page calls those paths on the same origin. See `frontend/README.md` for the fields and error messages.

## Environment variables

Backend and frontend configuration are separate. Real `.env` files are gitignored. Examples are committed.

| Variable | Where | Purpose |
| --- | --- | --- |
| `JEV_API_KEY` | backend | Optional. Enables live Jev. Never expose this to the browser. |
| `JEV_MODEL` | backend | Default `jev-1.13.0` |
| `JEV_BASE_URL` | backend | Default `https://jevtypesafeai.com/api/v1/decide` |
| `JEV_TIMEOUT_SECONDS` | backend | HTTP timeout for Jev, in seconds. Default `30`. |
| `APP_ENV` | backend | Default `development`. Values `development`, `dev`, `local`, and `test` leave the anonymous cookie non-`Secure` unless a trusted proxy sends `X-Forwarded-Proto: https`. Any other value sets `Secure`. |
| `LOG_LEVEL` | backend | `DEBUG`, `INFO`, `WARNING`, `ERROR`, or `CRITICAL`. Default `INFO`. |
| `POLICY_VERSION` | backend | Policy version label. Default `1.0`. |
| `DEMO_WORKSPACE` | backend | Sandbox root. Default `demo/workspace` under the backend directory. |
| `AUTO_EXECUTE_MAX_RISK` | backend | Default `2.0` |
| `AUTO_EXECUTE_MIN_SAFE` | backend | Default `0.90` |
| `CONFIRM_MAX_RISK` | backend | Default `3.0` |
| `CONFIRM_MIN_SAFE` | backend | Default `0.50` |
| `BLOCK_MIN_RISK` | backend | Default `4.0` |
| `RATE_LIMIT_ENABLED` | backend | When `true` (the default), live Jev calls use the limits below. `false` does not reject requests for rate. |
| `ANONYMOUS_RATE_LIMIT_REQUESTS` | backend | Max live decide calls per anonymous id. Default `3`. |
| `ANONYMOUS_RATE_LIMIT_WINDOW_SECONDS` | backend | Anonymous window in seconds. Default `18000` (5 hours). |
| `IP_RATE_LIMIT_REQUESTS` | backend | Max live decide calls per client IP. Default `20`. |
| `IP_RATE_LIMIT_WINDOW_SECONDS` | backend | IP window in seconds. Default `3600`. |
| `ANONYMOUS_ID_COOKIE_MAX_AGE_SECONDS` | backend | `jev_anon_id` lifetime in seconds. Default `31536000` (one year). The server raises a shorter value up to the anonymous window. |
| `TRUSTED_PROXY_CIDRS` | backend | Comma-separated CIDRs whose TCP peers may supply `X-Real-IP` and `X-Forwarded-For`. Default `127.0.0.0/8,::1/128,172.16.0.0/12`. |
| `CORS_ALLOW_ORIGINS` | backend | Comma-separated browser origins. Do not use `*`. Default `http://localhost:5173,http://127.0.0.1:5173`. The production UI is same-origin and does not need its public URL in this list. |

`JEV_API_KEY` stays in the server environment. Do not put it in the frontend, a `VITE_` variable, or a committed file. `backend/.env` and `scripts/deploy.config` are gitignored. The committed examples use empty or placeholder values.

Without `JEV_API_KEY`, gateway evaluations use deterministic demo signals. Those signals are not live Jev results. The health check does not need a key and does not call Jev. The three decision routes return `503` with `jev_not_configured` and do not consume a rate-limit permit.

The decision routes share one in-memory limiter in the Uvicorn process. The production image starts a single process and no extra workers, so that one copy covers the container. A restart clears the counters. Another worker or container would keep its own copy. A browser that drops `jev_anon_id` receives a new anonymous id; the IP bucket still applies. The cookie is `HttpOnly`, `SameSite=Lax`, and `Path=/api/v1/jev`. Nginx in front of the app must overwrite `X-Real-IP` and `X-Forwarded-For` with `$remote_addr`. A peer outside `TRUSTED_PROXY_CIDRS` cannot choose its IP bucket by sending those headers.

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
| 429 | `jev_rate_limited` | The anonymous-id or client-IP budget is exhausted. Jev is not called. |
| 502 | `jev_upstream_error` | Jev responded with an HTTP error. |
| 502 | `jev_network_error` | The connection to Jev failed. |
| 502 | `jev_invalid_response` | The body was not the documented decision shape. |
| 503 | `jev_not_configured` | `JEV_API_KEY` is missing. The process still starts, `/health` still works, and the rate-limit counters are not incremented. |
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

Policy defaults are in `backend/.env.example`. Live Jev calls use two rate-limit layers: per anonymous id, and per client IP. Demo mode does not consume that budget. The counters are in memory for the one Uvicorn process and reset when that process restarts.

A longer write-up of the original experiment is in [docs/case-study.md](docs/case-study.md).

## Production

The project was previously called AgentGuard. The running production container is `jev-explorer-production`. This repository does not keep a way to start the retired deployment.

One image, built from the repository root, serves the compiled UI and the API:

```text
Browser → Nginx (https://jev-explorer.mhdmoh.com)
       → 127.0.0.1:8510
       → container port 8000
```

`GET /` is the explorer. `GET /health` is the liveness check and does not call Jev. Decision routes stay `POST /api/v1/jev/choice`, `/score`, and `/noul`.

Build from the repository root. The runtime stage does not include Node. `JEV_API_KEY` is not a build argument.

```bash
docker build --platform linux/amd64 -f Dockerfile -t jev-explorer:local .
```

The image listens on port 8000. Its Docker `HEALTHCHECK` requests `http://127.0.0.1:8000/health` inside the container.

`scripts/deploy-production.sh` is the deploy path. Copy the example config, set the SSH host and domain, and keep `CONTAINER_PORT=8000`:

```bash
cp scripts/deploy.config.example scripts/deploy.config
# scripts/deploy.config is gitignored. Set SSH_HOST to your own SSH alias.
./scripts/deploy-production.sh
```

With `PROJECT_NAME=jev-explorer` the script uses:

- App directory: `/opt/apps/jev-explorer/production`
- Env file: `/opt/apps/jev-explorer/production/.env`
- Workspace: `/opt/apps/jev-explorer/production/workspace`
- Container: `jev-explorer-production`
- Image tag: `jev-explorer:production-<12-character git sha>`

The env file must already be on the server. The script checks that the file is non-empty and contains a `JEV_API_KEY=` line before it stops any container. It does not create, print, or overwrite that file. Create the directory if needed, then place the env file there yourself:

```bash
ssh <your-ssh-alias> 'sudo mkdir -p /opt/apps/jev-explorer/production'
```

Unless `SKIP_TESTS=1`, the script runs the backend tests and Ruff check, then the frontend tests, lint, and build. It builds the image for `linux/amd64`, saves that sha tag, and loads it on the server over SSH. It creates the remote app and workspace directories if they are missing. If `project-notes.txt` is absent, it copies the image's demo workspace into the server workspace once. An existing workspace file is left in place.

It then starts `jev-explorer-production-candidate` on `127.0.0.1:8511` (host port plus one) and maps that to container port 8000. The candidate must pass `/health`, then a smoke check: the health body is JSON, `GET /` contains `id="root"`, referenced `/assets/` files are not HTML, an unknown `/api/v1/jev/` path returns JSON 404, and `POST /api/v1/jev/choice` with `{}` returns `422` and `validation_error`. Only after that does it remove the candidate and start `jev-explorer-production` on `127.0.0.1:8510`.

The script does not install Nginx, change DNS, or run Certbot. `deploy/nginx/jev-explorer.conf.template` is a template in this repository, not the live server config. Confirm the live block for `jev-explorer.mhdmoh.com` proxies to `127.0.0.1:8510`, and that it sets `X-Real-IP`, `X-Forwarded-For`, and `X-Forwarded-Proto` from the immediate connection:

```bash
ssh <your-ssh-alias> 'sudo nginx -T' | awk '
  /server_name[[:space:]]+jev-explorer\.mhdmoh\.com/ {show=1}
  show {print}
  show && /^[[:space:]]*}/ {show=0}
'
ssh <your-ssh-alias> 'curl -fsS http://127.0.0.1:8510/health'
```

This repository cannot show the live Nginx config.

If the candidate fails, the script removes the candidate and leaves the current production container running. If failure happens after cutover has started, it removes the new production container. When the container that was running before this deploy recorded an image, the script starts that image again on `127.0.0.1:8510`. A public HTTPS check runs after a successful cutover and does not roll back. Once the script exits successfully, a later failure is not rolled back automatically. After success it deletes older `jev-explorer:production-*` tags and keeps the tag just deployed plus the previous image reference.

The script still has a branch that stops a container named `agentguard-production` when that container is present and published on the host port, then tries `docker start` on it if cutover fails. That container and its image are no longer on the server, so that branch does not restore service. Do not treat it as a rollback.

## Limitations

- Sandboxed / simulated tools only
- Not a production security boundary
- Jev signals are not correctness guarantees
- The explorer demonstrates the three decision APIs. It does not run policy or tools.
- Rate-limit counters are per process, in memory, and reset when the container restarts
