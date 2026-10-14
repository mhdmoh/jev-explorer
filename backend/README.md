# AgentGuard backend

Python API for AgentGuard. It keeps the Jev client, policy engine, gateway, and sandboxed tools, and exposes them over HTTP. The browser UI lives in `../frontend`.

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

`JEV_API_KEY` is optional. Without it, gateway evaluations stay in demo mode and do not call Jev. The key is read only on the server. Do not put it in a frontend `VITE_` variable.

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
  api/               HTTP routes (health only, for now)
  agent/             Scenario proposals
  guard/             Gateway, policy, models
  jev/               Jev client, evaluator, rate limits
  tools/             Sandboxed demo tools
  execution/         Executor and audit helpers
  config/            Settings
demo/workspace/      Sandbox filesystem
tests/
```

Planned Jev primitive routes are documented in `../docs/architecture.md`. They are not implemented yet.
