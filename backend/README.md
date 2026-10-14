# Jev Explorer backend

Python API for Jev Explorer. It keeps the Jev client, policy engine, gateway, and sandboxed tools, and exposes them over HTTP. The browser UI lives in `../frontend`.

## Run

From this directory:

```bash
uv sync
uv run uvicorn app.main:app --reload
```

- API: http://localhost:8000
- Interactive docs: http://localhost:8000/docs
- Health: http://localhost:8000/health

Health does not call Jev and does not require `JEV_API_KEY`.

## Configuration

```bash
cp .env.example .env
```

`JEV_API_KEY` is optional at startup. `/health` never calls Jev. `POST /api/v1/jev/choice`, `/score`, and `/noul` return `503` with `jev_not_configured` until the key is set. The key stays on the server. Do not put it in a frontend `VITE_` variable.

Those three routes each send one question to `JEV_BASE_URL` and return Jev's typed answer. They do not apply policy and they do not execute tools. Request and response examples are in the repository README. `pytest` covers them without a live key.

`CORS_ALLOW_ORIGINS` lists allowed browser origins. The default is the Vite dev server. Do not use `*`.

## Rate limits

`POST /api/v1/jev/choice`, `/score`, and `/noul` share one in-memory limiter on the application. The defaults are 3 calls per anonymous browser per 18000 seconds, and 20 calls per client IP per 3600 seconds. `RATE_LIMIT_ENABLED=false` turns rejection off. A rejected call returns HTTP 429 with error code `jev_rate_limited` and does not call Jev. A missing `JEV_API_KEY` still returns 503 and does not consume a permit.

The browser identity is the `jev_anon_id` cookie (`HttpOnly`, `SameSite=Lax`, `Path=/api/v1/jev`). It is set when a valid cookie is missing. Its lifetime is `ANONYMOUS_ID_COOKIE_MAX_AGE_SECONDS` (one year by default), raised to the anonymous window when that value is shorter, so the cookie does not expire before the quota window. `Secure` is set when `APP_ENV` is not a local environment, and also when a trusted proxy sends `X-Forwarded-Proto: https`.

Client IP comes from the TCP peer. `X-Real-IP` and `X-Forwarded-For` are used only when that peer is inside `TRUSTED_PROXY_CIDRS` (loopback and the Docker bridge by default). Nginx must overwrite those headers with `$remote_addr`.

The counters live in the Uvicorn process. The production image starts one worker and no extra replicas. A restart clears them. More than one worker would not share this limit.

## Tests

```bash
uv run pytest
uv run ruff check app tests
```

## Layout

```text
app/
  main.py            FastAPI app
  api/               HTTP routes (health, choice, score, noul)
  agent/             Scenario proposals
  guard/             Gateway, policy, models
  jev/               Jev client, evaluator, rate limits
  tools/             Sandboxed demo tools
  execution/         Executor and audit helpers
  config/            Settings
demo/workspace/      Sandbox filesystem
tests/
```

Interactive docs: http://localhost:8000/docs. The decision explorer UI is in `../frontend`.

The production image is built from the repository root `Dockerfile`. It listens on port 8000 and serves the compiled UI from `/app/static` together with this API. Build it from the repo root, not from `backend/`.
