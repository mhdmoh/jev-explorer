# AgentGuard frontend

React + TypeScript + Vite scaffold. It checks that the AgentGuard API is reachable. Decision exploration is not implemented yet.

## Run

```bash
npm install
cp .env.example .env
npm run dev
```

Open http://localhost:5173. Start the backend first if you want the connected state (`cd ../backend && uv run uvicorn app.main:app --reload`).

`VITE_API_BASE_URL` points at the API. It defaults to `http://localhost:8000` when unset. Do not put a Jev API key in any `VITE_` variable.

## Checks

```bash
npm run lint
npm run build
```

`npm run lint` uses oxlint, which ships with this Vite template. `npm run build` runs `tsc -b` and then the production bundle.
