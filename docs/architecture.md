# Architecture

AgentGuard sits between a browser and the hosted Jev API. The browser never sees Jev credentials. Jev returns typed decision signals. Application branching stays in AgentGuard.

```text
Browser
   |
React + TypeScript + Vite
   | HTTP / JSON
AgentGuard Backend API
   | authenticated server-side request
Jev Hosted API
```

## Frontend

The frontend is the only user-facing application. It will own:

- Interaction for constructing Jev requests
- JSON presentation of requests and responses
- Typed response presentation
- Visualizations of `choice`, `score`, and `noul`
- Illustrative examples of how an application might branch on those signals

Illustrative branching is application behavior. It must stay visually distinct from the actual Jev response.

This phase only checks that the backend is reachable (`GET /health`). The decision explorer is not implemented yet.

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

The existing gateway still evaluates a proposed tool call with one batched Jev `POST /api/v1/decide` (choice, score, and noul together), then applies AgentGuard policy. That path is Python library code. It is not exposed as an HTTP route in this phase.

These routes are planned and **not implemented**:

```text
POST /api/v1/jev/choice
POST /api/v1/jev/score
POST /api/v1/jev/noul
```

Do not assume the hosted Jev API uses those paths. Jev's current integration target in this repository is `JEV_BASE_URL` (default `https://jevtypesafeai.com/api/v1/decide`). Confirm official request and response formats before adding the three routes.

## Jev

Jev returns typed decisions for the primitives it supports: `choice`, `score`, and `noul`. A Jev response is a signal. It is not the application's final behavior. AgentGuard (or a later UI example) decides what to do with the signal.

## Local development CORS

`CORS_ALLOW_ORIGINS` is a comma-separated list of browser origins. The default allows only:

- `http://localhost:5173`
- `http://127.0.0.1:5173`

Wildcard origins are rejected. Production should list the real frontend origin and nothing else.
