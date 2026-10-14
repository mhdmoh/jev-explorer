import { useEffect, useRef, useState, type FormEvent, type KeyboardEvent } from "react"
import { backendStatusLabel, useBackendStatus } from "../hooks/useBackendStatus.ts"
import { ApiError, postJson } from "../lib/api.ts"
import {
  buildChoiceBody,
  buildNoulBody,
  buildScoreBody,
  endpointFor,
  explainError,
  formatJson,
  parseState,
  sharedFieldErrors,
  validateChoiceDrafts,
  validateScoreDrafts,
} from "../lib/decisions.ts"
import type { ChoiceDraft, FieldErrors, ScoreDraft } from "../lib/decisions.ts"
import type { Primitive, StateMode } from "../types/decisions.ts"
import { ChoiceFields } from "./ChoiceFields.tsx"
import { Icon } from "./Icon.tsx"
import { JsonPanel } from "./JsonPanel.tsx"
import { ResultPanel } from "./ResultPanel.tsx"
import { ScoreFields } from "./ScoreFields.tsx"

const PRIMITIVES: { id: Primitive; title: string; summary: string }[] = [
  { id: "choice", title: "Choice", summary: "Select one option from a defined set." },
  {
    id: "score",
    title: "Score",
    summary: "Place the state on an ordered scale. The score may be fractional.",
  },
  { id: "noul", title: "Noul", summary: "Return a 0–1 probability that the answer is yes." },
]

const DEFAULT_INSTRUCTIONS: Record<Primitive, string> = {
  choice: "Where should this go?",
  score: "How urgent is this?",
  noul: "Escalate to a human immediately?",
}

const INSTRUCTION_PLACEHOLDER: Record<Primitive, string> = {
  choice: "Where should this go?",
  score: "What should Jev measure?",
  noul: "Ask a yes or no question",
}

type Run =
  | { phase: "idle"; request: null; response: null; message: null; detail: null }
  | { phase: "loading"; request: unknown; response: null; message: null; detail: null }
  | { phase: "success"; request: unknown; response: unknown; message: null; detail: null }
  | {
      phase: "error"
      request: unknown
      response: unknown | null
      message: string
      detail: string | null
    }

const IDLE: Run = { phase: "idle", request: null, response: null, message: null, detail: null }

function newChoiceRows(): ChoiceDraft[] {
  return [
    { id: crypto.randomUUID(), key: "billing", description: "payments, refunds, invoices" },
    { id: crypto.randomUUID(), key: "bug", description: "the product is broken" },
    { id: crypto.randomUUID(), key: "account", description: "login or access" },
  ]
}

function newScoreRows(): ScoreDraft[] {
  return ["routine, no rush", "today", "urgent", "critical, about to churn"].map((label) => ({
    id: crypto.randomUUID(),
    label,
  }))
}

function emptyRuns(): Record<Primitive, Run> {
  return { choice: IDLE, score: IDLE, noul: IDLE }
}

function preferredTheme(): "light" | "dark" {
  try {
    const stored = localStorage.getItem("jev-explorer-theme")
    if (stored === "light" || stored === "dark") {
      return stored
    }
  } catch {
    // Ignore storage failures and fall through to the document or system theme.
  }
  const attr = document.documentElement.getAttribute("data-theme")
  if (attr === "light" || attr === "dark") {
    return attr
  }
  if (typeof window.matchMedia === "function" && window.matchMedia("(prefers-color-scheme: dark)").matches) {
    return "dark"
  }
  return "light"
}

export function Explorer() {
  const status = useBackendStatus()
  const [theme, setTheme] = useState<"light" | "dark">(preferredTheme)
  const [primitive, setPrimitive] = useState<Primitive>("choice")
  const [stateMode, setStateMode] = useState<StateMode>("text")
  const [stateText, setStateText] = useState(
    "Customer: I was charged twice and nobody has replied for 3 days.",
  )
  const [instructions, setInstructions] = useState(DEFAULT_INSTRUCTIONS)
  const [choiceRows, setChoiceRows] = useState(newChoiceRows)
  const [scoreRows, setScoreRows] = useState(newScoreRows)
  const [runs, setRuns] = useState(emptyRuns)
  const aborts = useRef<Partial<Record<Primitive, AbortController>>>({})

  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme)
  }, [theme])

  const parsed = parseState(stateMode, stateText)
  const errors: FieldErrors = {
    ...sharedFieldErrors(instructions[primitive]),
    ...(parsed.ok ? {} : { state: parsed.message }),
    ...(primitive === "choice" ? validateChoiceDrafts(choiceRows) : {}),
    ...(primitive === "score" ? validateScoreDrafts(scoreRows) : {}),
  }
  const blocked = Boolean(errors.state || errors.instructions || errors.criteria || errors.rows)
  const preview =
    parsed.ok && !blocked
      ? primitive === "choice"
        ? buildChoiceBody(parsed.state, instructions.choice, choiceRows)
        : primitive === "score"
          ? buildScoreBody(parsed.state, instructions.score, scoreRows)
          : buildNoulBody(parsed.state, instructions.noul)
      : null
  const run = runs[primitive]
  const loading = run.phase === "loading"
  const stale =
    run.phase !== "idle" && JSON.stringify(preview) !== JSON.stringify(run.request)
  const active = PRIMITIVES.find((item) => item.id === primitive) ?? PRIMITIVES[0]
  const shortcut =
    typeof navigator !== "undefined" && /Mac|iPhone|iPad/.test(navigator.platform) ? "⌘" : "Ctrl"

  function selectTheme(next: "light" | "dark") {
    document.documentElement.setAttribute("data-theme", next)
    try {
      localStorage.setItem("jev-explorer-theme", next)
    } catch {
      // Theme still applies for this page view when storage is blocked.
    }
    setTheme(next)
  }

  function selectPrimitive(next: Primitive) {
    if (next !== primitive) {
      setPrimitive(next)
    }
  }

  async function submit() {
    if (loading || blocked || !parsed.ok || preview === null) {
      return
    }
    const mode = primitive
    const body = preview
    aborts.current[mode]?.abort()
    const controller = new AbortController()
    aborts.current[mode] = controller
    setRuns((current) => ({
      ...current,
      [mode]: { phase: "loading", request: body, response: null, message: null, detail: null },
    }))
    try {
      const response = await postJson(endpointFor(mode), body, controller.signal)
      if (controller.signal.aborted) {
        return
      }
      setRuns((current) => ({
        ...current,
        [mode]: { phase: "success", request: body, response, message: null, detail: null },
      }))
    } catch (error) {
      if (controller.signal.aborted) {
        return
      }
      const apiError = error instanceof ApiError ? error : null
      const code = apiError?.payload?.code
      const serverMessage = apiError?.payload?.message
      const detailLines = apiError?.payload?.details?.map((item) => {
        const loc = item.loc.filter((part) => part !== "body").join(".")
        return loc ? `${loc}: ${item.msg}` : item.msg
      })
      const clientTimeout =
        apiError !== null &&
        apiError.status === undefined &&
        apiError.message.toLowerCase().includes("timed out")
      setRuns((current) => ({
        ...current,
        [mode]: {
          phase: "error",
          request: body,
          response: apiError?.body ?? null,
          message: clientTimeout
            ? "The decision request timed out. You can try again."
            : explainError(code, apiError?.status),
          detail: [serverMessage, ...(detailLines ?? [])].filter(Boolean).join(" ") || null,
        },
      }))
    }
  }

  function onSubmit(event: FormEvent) {
    event.preventDefault()
    void submit()
  }

  function onFormKeyDown(event: KeyboardEvent<HTMLFormElement>) {
    if ((event.metaKey || event.ctrlKey) && event.key === "Enter") {
      event.preventDefault()
      void submit()
    }
  }

  function formatStateJson() {
    const next = parseState("json", stateText)
    if (!next.ok) {
      return
    }
    setStateText(formatJson(next.state))
  }

  const stateErrorId = "state-error"
  const instructionErrorId = "instructions-error"

  return (
    <div className="page">
      <header className="top">
        <div className="brand">
          <p className="eyebrow">AgentGuard</p>
          <h1>Jev Decision Explorer</h1>
          <p className="lede">
            Try choice, score, and noul through the AgentGuard backend. The browser never calls
            Jev and never sees the API key.
          </p>
        </div>
        <div className="top-actions">
          <p className={`status status-${status}`} role="status">
            <i className="status-dot" aria-hidden="true" />
            {backendStatusLabel(status)}
          </p>
          <button
            type="button"
            className="ib"
            aria-label="Switch color theme"
            title={theme === "dark" ? "Switch to light" : "Switch to dark"}
            onClick={() => selectTheme(theme === "dark" ? "light" : "dark")}
          >
            <Icon name={theme === "dark" ? "sun" : "moon"} />
          </button>
        </div>
      </header>

      <div className="modes">
        <fieldset className="seg seg-lg">
          <legend className="sr">Decision type</legend>
          {PRIMITIVES.map((item) => (
            <label key={item.id}>
              <input
                type="radio"
                name="primitive"
                value={item.id}
                checked={item.id === primitive}
                onChange={() => selectPrimitive(item.id)}
              />
              {item.title}
            </label>
          ))}
        </fieldset>
        <p className="mode-desc">{active?.summary}</p>
      </div>

      <main className="work">
        <section className="panel" aria-labelledby="reqTitle">
          <div className="p-head">
            <h2 id="reqTitle">Request</h2>
          </div>
          <form className="form" onSubmit={onSubmit} onKeyDown={onFormKeyDown} autoComplete="off" noValidate>
            <div className="field">
              <div className="lab">
                <label htmlFor="state-input">{stateMode === "json" ? "State JSON" : "State"}</label>
                <fieldset className="seg">
                  <legend className="sr">State format</legend>
                  <label>
                    <input
                      type="radio"
                      name="state-mode"
                      checked={stateMode === "text"}
                      onChange={() => setStateMode("text")}
                    />
                    Text
                  </label>
                  <label>
                    <input
                      type="radio"
                      name="state-mode"
                      checked={stateMode === "json"}
                      onChange={() => setStateMode("json")}
                    />
                    JSON
                  </label>
                </fieldset>
              </div>
              <textarea
                id="state-input"
                className={stateMode === "json" ? "is-json" : undefined}
                rows={stateMode === "json" ? 8 : 4}
                spellCheck={stateMode === "text"}
                placeholder={
                  stateMode === "text" ? "Describe the situation to evaluate" : '{ "key": "value" }'
                }
                aria-invalid={Boolean(errors.state)}
                aria-describedby={errors.state ? stateErrorId : "state-note"}
                value={stateText}
                onChange={(event) => setStateText(event.target.value)}
              />
              <div className="foot">
                {errors.state ? (
                  <span id={stateErrorId} className="err">
                    {errors.state}
                  </span>
                ) : (
                  <span id="state-note" className={stateMode === "json" ? "ok" : undefined}>
                    {stateMode === "text"
                      ? "Sent as a JSON string."
                      : "Valid JSON. Sent as a JSON value."}
                  </span>
                )}
                <span className="foot-actions">
                  {stateMode === "json" ? (
                    <button type="button" className="text-btn" onClick={formatStateJson}>
                      Format
                    </button>
                  ) : null}
                  <span className="count">{stateText.length} characters</span>
                </span>
              </div>
            </div>

            <div className="field">
              <label className="lab-t" htmlFor="instructions-input">
                Instructions
              </label>
              <textarea
                id="instructions-input"
                rows={2}
                placeholder={INSTRUCTION_PLACEHOLDER[primitive]}
                aria-invalid={Boolean(errors.instructions)}
                aria-describedby={errors.instructions ? instructionErrorId : undefined}
                value={instructions[primitive]}
                onChange={(event) =>
                  setInstructions((current) => ({ ...current, [primitive]: event.target.value }))
                }
              />
              {errors.instructions ? (
                <p id={instructionErrorId} className="field-error">
                  {errors.instructions}
                </p>
              ) : null}
            </div>

            {primitive === "choice" ? (
              <ChoiceFields
                rows={choiceRows}
                rowErrors={errors.rows}
                criteriaError={errors.criteria}
                disabled={loading}
                onChange={setChoiceRows}
              />
            ) : null}
            {primitive === "score" ? (
              <ScoreFields
                rows={scoreRows}
                rowErrors={errors.rows}
                criteriaError={errors.criteria}
                disabled={loading}
                onChange={setScoreRows}
              />
            ) : null}

            <div className="runbar">
              <button className="btn" type="submit" disabled={loading || blocked}>
                {loading ? <span className="spin" aria-hidden="true" /> : null}
                <span>{loading ? `Evaluating ${primitive}…` : `Run ${primitive}`}</span>
              </button>
              {blocked ? (
                <span className="run-hint err">Fix the highlighted fields.</span>
              ) : (
                <span className="run-hint">
                  or press <kbd>{shortcut}</kbd> <kbd>Enter</kbd>
                </span>
              )}
            </div>
          </form>
        </section>

        <ResultPanel
          primitive={primitive}
          phase={run.phase}
          response={run.response}
          errorMessage={run.message}
          errorDetail={run.detail}
          stale={stale}
          choiceOptions={choiceRows
            .map((row) => ({ key: row.key.trim(), description: row.description.trim() }))
            .filter((row) => row.key)}
          scoreLabels={scoreRows.map((row) => row.label.trim())}
        />
      </main>

      <JsonPanel request={preview} response={run.response} />
    </div>
  )
}
