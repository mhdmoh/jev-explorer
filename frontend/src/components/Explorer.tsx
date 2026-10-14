import { useRef, useState, type FormEvent } from "react"
import { backendStatusLabel, useBackendStatus } from "../hooks/useBackendStatus.ts"
import { ApiError, postJson } from "../lib/api.ts"
import {
  buildChoiceBody,
  buildNoulBody,
  buildScoreBody,
  endpointFor,
  explainError,
  parseState,
  sharedFieldErrors,
  validateChoiceDrafts,
  validateScoreDrafts,
} from "../lib/decisions.ts"
import type { ChoiceDraft, FieldErrors, ScoreDraft } from "../lib/decisions.ts"
import type { Primitive, StateMode } from "../types/decisions.ts"
import { ChoiceFields } from "./ChoiceFields.tsx"
import { JsonPanel } from "./JsonPanel.tsx"
import { ResultPanel } from "./ResultPanel.tsx"
import { ScoreFields } from "./ScoreFields.tsx"

const PRIMITIVES: { id: Primitive; title: string; summary: string }[] = [
  { id: "choice", title: "Choice", summary: "Select one option from a defined set." },
  { id: "score", title: "Score", summary: "Place the state on an ordered scale. The score may be fractional." },
  { id: "noul", title: "Noul", summary: "Return a 0–1 probability that the answer is yes." },
]

const DEFAULT_INSTRUCTIONS: Record<Primitive, string> = {
  choice: "Where should this go?",
  score: "How urgent is this?",
  noul: "Escalate to a human immediately?",
}

type Run =
  | { phase: "idle"; request: null; response: null; message: null; detail: null }
  | { phase: "loading"; request: unknown; response: null; message: null; detail: null }
  | { phase: "success"; request: unknown; response: unknown; message: null; detail: null }
  | { phase: "error"; request: unknown; response: unknown | null; message: string; detail: string | null }

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

export function Explorer() {
  const status = useBackendStatus()
  const [primitive, setPrimitive] = useState<Primitive>("choice")
  const [stateMode, setStateMode] = useState<StateMode>("text")
  const [stateText, setStateText] = useState(
    "Customer: I was charged twice and nobody has replied for 3 days.",
  )
  const [instructions, setInstructions] = useState(DEFAULT_INSTRUCTIONS)
  const [choiceRows, setChoiceRows] = useState(newChoiceRows)
  const [scoreRows, setScoreRows] = useState(newScoreRows)
  const [errors, setErrors] = useState<FieldErrors>({})
  const [run, setRun] = useState<Run>(IDLE)
  const abortRef = useRef<AbortController | null>(null)
  const generation = useRef(0)

  function selectPrimitive(next: Primitive) {
    if (next === primitive) {
      return
    }
    abortRef.current?.abort()
    generation.current += 1
    setPrimitive(next)
    setErrors({})
    setRun(IDLE)
  }

  async function onSubmit(event: FormEvent) {
    event.preventDefault()
    if (run.phase === "loading") {
      return
    }
    const parsed = parseState(stateMode, stateText)
    const nextErrors: FieldErrors = {
      ...sharedFieldErrors(instructions[primitive]),
      ...(parsed.ok ? {} : { state: parsed.message }),
    }
    if (primitive === "choice") {
      Object.assign(nextErrors, validateChoiceDrafts(choiceRows))
    }
    if (primitive === "score") {
      Object.assign(nextErrors, validateScoreDrafts(scoreRows))
    }
    if (!parsed.ok || nextErrors.instructions || nextErrors.criteria || nextErrors.rows || nextErrors.state) {
      setErrors(nextErrors)
      return
    }
    setErrors({})
    const body =
      primitive === "choice"
        ? buildChoiceBody(parsed.state, instructions.choice, choiceRows)
        : primitive === "score"
          ? buildScoreBody(parsed.state, instructions.score, scoreRows)
          : buildNoulBody(parsed.state, instructions.noul)
    const ticket = generation.current + 1
    generation.current = ticket
    abortRef.current?.abort()
    const controller = new AbortController()
    abortRef.current = controller
    setRun({ phase: "loading", request: body, response: null, message: null, detail: null })
    try {
      const response = await postJson(endpointFor(primitive), body, controller.signal)
      if (generation.current !== ticket) {
        return
      }
      setRun({ phase: "success", request: body, response, message: null, detail: null })
    } catch (error) {
      if (generation.current !== ticket || controller.signal.aborted) {
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
      setRun({
        phase: "error",
        request: body,
        response: apiError?.body ?? null,
        message: clientTimeout
          ? "The decision request timed out. You can try again."
          : explainError(code, apiError?.status),
        detail: [serverMessage, ...(detailLines ?? [])].filter(Boolean).join(" ") || null,
      })
    }
  }

  const loading = run.phase === "loading"
  const stateErrorId = "state-error"
  const instructionErrorId = "instructions-error"

  return (
    <div className="app">
      <header className="topbar">
        <div>
          <p className="wordmark">AgentGuard</p>
          <h1>Jev Decision Explorer</h1>
          <p className="lede">
            Requests go to the AgentGuard backend. The browser never calls Jev and never sees
            the API key.
          </p>
        </div>
        <p className={`status status-${status}`} role="status">
          {backendStatusLabel(status)}
        </p>
      </header>

      <fieldset className="primitives">
        <legend className="sr-only">Decision primitive</legend>
        {PRIMITIVES.map((item) => (
          <label key={item.id} className={item.id === primitive ? "primitive active" : "primitive"}>
            <input
              type="radio"
              name="primitive"
              value={item.id}
              checked={item.id === primitive}
              onChange={() => selectPrimitive(item.id)}
            />
            <span>{item.title}</span>
            <small>{item.summary}</small>
          </label>
        ))}
      </fieldset>

      <div className="workspace">
        <form className="form" onSubmit={onSubmit} aria-busy={loading} noValidate>
          <fieldset className="state-mode">
            <legend>State</legend>
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
          <label className="stack" htmlFor="state-input">
            {stateMode === "text" ? "State text" : "State JSON"}
            <textarea
              id="state-input"
              rows={stateMode === "json" ? 8 : 5}
              spellCheck={stateMode === "text"}
              aria-invalid={Boolean(errors.state)}
              aria-describedby={errors.state ? stateErrorId : undefined}
              value={stateText}
              onChange={(event) => setStateText(event.target.value)}
            />
          </label>
          {errors.state ? (
            <p id={stateErrorId} className="field-error">
              {errors.state}
            </p>
          ) : (
            <p className="hint">
              {stateMode === "text"
                ? "Sent as a JSON string."
                : "Parsed before sending. A string, object, or array is accepted. Text is not turned into an object."}
            </p>
          )}

          <label className="stack" htmlFor="instructions-input">
            Instructions
            <textarea
              id="instructions-input"
              rows={3}
              aria-invalid={Boolean(errors.instructions)}
              aria-describedby={errors.instructions ? instructionErrorId : undefined}
              value={instructions[primitive]}
              onChange={(event) =>
                setInstructions((current) => ({ ...current, [primitive]: event.target.value }))
              }
            />
          </label>
          {errors.instructions ? (
            <p id={instructionErrorId} className="field-error">
              {errors.instructions}
            </p>
          ) : null}

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

          <button type="submit" className="primary" disabled={loading}>
            {loading ? `Evaluating ${primitive}…` : `Run ${primitive}`}
          </button>
        </form>

        <ResultPanel
          primitive={primitive}
          phase={run.phase}
          response={run.response}
          errorMessage={run.message}
          errorDetail={run.detail}
          choiceKeys={choiceRows.map((row) => row.key.trim()).filter(Boolean)}
          scoreLabels={scoreRows.map((row) => row.label.trim())}
        />
      </div>

      <JsonPanel request={run.request} response={run.response} />
    </div>
  )
}
