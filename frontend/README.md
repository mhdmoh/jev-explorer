# Jev Explorer frontend

React + TypeScript + Vite app for the Jev Decision Explorer. It calls the Jev Explorer backend. It does not call Jev and it does not hold a Jev API key.

## Install and run

```bash
npm install
cp .env.example .env
npm run dev
```

Open http://localhost:5173.

Start the backend in another terminal:

```bash
cd ../backend
uv sync
uv run uvicorn app.main:app --reload
```

The header status comes from `GET /health`. It can read "Backend connected" when `JEV_API_KEY` is unset. Decision requests then return `jev_not_configured` until that key is set on the backend.

## API URL

`VITE_API_BASE_URL` is the Jev Explorer origin. It defaults to `http://localhost:8000`. Copy `.env.example` to `.env` to override it. Do not put `JEV_API_KEY` or any other secret in a `VITE_` variable.

## Using the explorer

Pick Choice, Score, or Noul. Each form shares:

- **State.** Text mode sends a JSON string. JSON mode sends a parsed string, object, or array. Malformed JSON is rejected in the browser and is not posted.
- **Instructions.** Required. Whitespace is trimmed.

The explorer does not send `model`. The backend uses its configured `JEV_MODEL`.

Choice also needs 1–255 options. Each key must be unique and non-empty, and each description must be non-empty. The selected result is that key.

Score needs 2–10 labels, ordered from low to high. The returned score is a 0-based index on that list and may be fractional. The explorer does not round it, clamp it, or treat 1 as the first level.

Noul needs only state and instructions. The result is a probability from 0 to 1. A percentage is shown for display. The decimal in the result and in the response JSON is the value Jev returned. The explorer does not turn it into yes/no or apply a cutoff.

Submit sends `POST /api/v1/jev/choice`, `/score`, or `/noul`. The button stays disabled until that request finishes.

After a response, the result panel shows the returned decision. Choice can switch between probability bars and a bar chart. Score shows the ordered scale and, when Jev returns them, the level probabilities beside it. Request JSON and Response JSON sit in two panes under the workspace. Each pane has its own copy button. The request pane shows the body the form would send, including before the first run.

## JSON inspector

Request JSON is the body the current form would post. After a run, it matches what was sent until an input changes. Response JSON is the body the backend returned, including the error envelope when a request fails. Copy puts that pane’s JSON on the clipboard. Neither panel includes headers or secrets.

## Errors

The result panel maps the backend `error.code`:

| Code | What the explorer says |
| --- | --- |
| `validation_error` | Some request fields are invalid |
| `jev_not_configured` | Set `JEV_API_KEY` on the backend |
| `jev_rate_limited` | Too many requests; wait and retry |
| `jev_timeout` | The decision request timed out |
| `jev_upstream_error` | Jev returned an error to Jev Explorer |
| `jev_network_error` | Jev Explorer could not reach Jev |
| `jev_invalid_response` | Jev Explorer could not accept Jev's response |
| `internal_error` | Unexpected Jev Explorer error |

A failed health check is "Backend unavailable". That is separate from a Jev upstream failure, which still means the backend answered.

## Checks

```bash
npm run lint
npm test
npm run build
```

`npm run lint` uses oxlint. `npm test` runs Vitest with mocked HTTP. `npm run build` runs `tsc -b` and the production bundle.
