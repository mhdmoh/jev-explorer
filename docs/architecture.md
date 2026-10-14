# Architecture

Jev Explorer sits between a browser and the hosted Jev API. The browser never sees Jev credentials. Jev returns typed decision signals. Application branching stays in Jev Explorer.

```text
Browser
   |
https://jev-explorer.mhdmoh.com
   |
Nginx → 127.0.0.1:8510
   |
One container, port 8000
   FastAPI serves the built UI and /api/v1/jev/*
   | authenticated server-side request
Jev Hosted API
```

Local development still runs Vite on port 5173. That dev server proxies `/health` and `/api` to the API on port 8000. The browser calls relative paths in both environments.

## Frontend

The frontend is the Jev Decision Explorer. It checks `GET /health`, then posts choice, score, and noul requests to the Jev Explorer API. It shows the typed result, a visualization of the returned numbers, and the JSON body that was sent and received. It does not call Jev, store a key, run policy, or execute tools.

## Backend

The backend is a FastAPI application. It owns:

- HTTP endpoints and request validation
- Jev integration (`app/jev/`: client, evaluator, rate limits)
- Credentials and configuration (`JEV_API_KEY` and related settings stay server-side)
- Deterministic policy (`app/guard/policy.py`) and gateway orchestration (`app/guard/gateway.py`)
- Sandboxed demo tools and execution
- Error handling and logging
- Typed JSON responses

`GET /health` confirms the process is up. It does not call Jev and does not return configuration or secrets.

The gateway still evaluates a proposed tool call in Python: one batched Jev `POST /api/v1/decide`, then Jev Explorer policy, then a sandboxed tool. That path is not the HTTP API below.

The HTTP API exposes one primitive at a time. Each route validates the request, sends a single question to the same decide endpoint, and returns Jev's answer. It does not run policy and it does not execute a tool.

```text
POST /api/v1/jev/choice
POST /api/v1/jev/score
POST /api/v1/jev/noul
```

Jev itself does not publish those three paths. The hosted contract is `POST /api/v1/decide` with `state` plus a `questions` map. See the root README for the verified fields.

## Jev

Jev returns typed decisions for the primitives it supports: `choice`, `score`, and `noul`. A Jev response is a signal. It is not the application's final behavior. Jev Explorer (or a later UI example) decides what to do with the signal.

## Local development CORS

`CORS_ALLOW_ORIGINS` is a comma-separated list of browser origins. The default allows only:

- `http://localhost:5173`
- `http://127.0.0.1:5173`

Wildcard origins are rejected. Production serves the UI from the API origin, so the browser does not rely on CORS for the explorer. Keep this list limited to the local Vite origins unless another origin must call the API directly.
