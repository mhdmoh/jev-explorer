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
