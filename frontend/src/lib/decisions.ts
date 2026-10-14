import type {
  ApiErrorPayload,
  ChoiceRequestBody,
  DecisionState,
  NoulRequestBody,
  Primitive,
  ScoreRequestBody,
  StateMode,
} from "../types/decisions.ts"

export const CHOICE_MIN = 1
export const CHOICE_MAX = 255
export const SCORE_MIN = 2
export const SCORE_MAX = 10

export type FieldErrors = {
  state?: string
  instructions?: string
  criteria?: string
  rows?: Record<string, string>
}

export type ChoiceDraft = { id: string; key: string; description: string }
export type ScoreDraft = { id: string; label: string }

export function formatJson(value: unknown): string {
  return JSON.stringify(value, null, 2) ?? ""
}

export function formatExact(value: number): string {
  return Object.is(value, -0) ? "-0" : String(value)
}

export function formatPercent(value: number): string {
  return `${new Intl.NumberFormat("en-US", { maximumFractionDigits: 2 }).format(value * 100)}%`
}

export function parseState(
  mode: StateMode,
  text: string,
): { ok: true; state: DecisionState } | { ok: false; message: string } {
  if (mode === "text") {
    return { ok: true, state: text }
  }
  let parsed: unknown
  try {
    parsed = JSON.parse(text)
  } catch {
    return { ok: false, message: "State JSON is not valid. Fix the syntax before running." }
  }
  if (typeof parsed === "string" || Array.isArray(parsed)) {
    return { ok: true, state: parsed }
  }
  if (isRecord(parsed)) {
    return { ok: true, state: parsed }
  }
  return {
    ok: false,
    message: "State JSON must be a string, object, or array.",
  }
}

export function validateChoiceDrafts(rows: ChoiceDraft[]): FieldErrors {
  const errors: FieldErrors = {}
  const rowErrors: Record<string, string> = {}
  const seen = new Map<string, string>()
  if (rows.length < CHOICE_MIN) {
    errors.criteria = "Add at least one option."
  } else if (rows.length > CHOICE_MAX) {
    errors.criteria = `Use at most ${CHOICE_MAX} options.`
  }
  for (const row of rows) {
    const key = row.key.trim()
    const description = row.description.trim()
    if (!key) {
      rowErrors[row.id] = "Option key is required."
      continue
    }
    if (!description) {
      rowErrors[row.id] = "Option description is required."
      continue
    }
    const previous = seen.get(key)
    if (previous) {
      rowErrors[row.id] = "Option keys must be unique."
      rowErrors[previous] = "Option keys must be unique."
    } else {
      seen.set(key, row.id)
    }
  }
  if (Object.keys(rowErrors).length > 0) {
    errors.rows = rowErrors
  }
  return errors
}

export function validateScoreDrafts(rows: ScoreDraft[]): FieldErrors {
  const errors: FieldErrors = {}
  const rowErrors: Record<string, string> = {}
  if (rows.length < SCORE_MIN || rows.length > SCORE_MAX) {
    errors.criteria = `Use ${SCORE_MIN}–${SCORE_MAX} levels, ordered from low to high.`
  }
  for (const row of rows) {
    if (!row.label.trim()) {
      rowErrors[row.id] = "Level label is required."
    }
  }
  if (Object.keys(rowErrors).length > 0) {
    errors.rows = rowErrors
  }
  return errors
}

export function sharedFieldErrors(instructions: string): FieldErrors {
  const errors: FieldErrors = {}
  if (!instructions.trim()) {
    errors.instructions = "Instructions are required."
  }
  return errors
}

export function buildChoiceBody(
  state: DecisionState,
  instructions: string,
  rows: ChoiceDraft[],
): ChoiceRequestBody {
  const criteria: Record<string, string> = {}
  for (const row of rows) {
    criteria[row.key.trim()] = row.description.trim()
  }
  return {
    state,
    instructions: instructions.trim(),
    criteria,
  }
}

export function buildScoreBody(
  state: DecisionState,
  instructions: string,
  rows: ScoreDraft[],
): ScoreRequestBody {
  return {
    state,
    instructions: instructions.trim(),
    criteria: rows.map((row) => row.label.trim()),
  }
}

export function buildNoulBody(state: DecisionState, instructions: string): NoulRequestBody {
  return {
    state,
    instructions: instructions.trim(),
  }
}

export type ScorePlacement =
  | { kind: "aligned"; index: number }
  | { kind: "between"; lower: number; upper: number }
  | { kind: "below" }
  | { kind: "above"; lastIndex: number }

export function scorePlacement(score: number, levelCount: number): ScorePlacement {
  const lastIndex = Math.max(0, levelCount - 1)
  if (!Number.isFinite(score)) {
    return { kind: "above", lastIndex }
  }
  if (score < 0) {
    return { kind: "below" }
  }
  if (score > lastIndex) {
    return { kind: "above", lastIndex }
  }
  if (Number.isInteger(score)) {
    return { kind: "aligned", index: score }
  }
  return { kind: "between", lower: Math.floor(score), upper: Math.ceil(score) }
}

export function scoreTrackPercent(score: number, levelCount: number): number | null {
  if (levelCount < 2 || !Number.isFinite(score)) {
    return null
  }
  const lastIndex = levelCount - 1
  if (score < 0 || score > lastIndex) {
    return null
  }
  return (score / lastIndex) * 100
}

export function readApiError(body: unknown): ApiErrorPayload | null {
  if (!isRecord(body) || !isRecord(body.error)) {
    return null
  }
  const code = body.error.code
  const message = body.error.message
  if (typeof code !== "string" || typeof message !== "string") {
    return null
  }
  const details = Array.isArray(body.error.details)
    ? body.error.details.flatMap((item) => {
        if (!isRecord(item) || typeof item.msg !== "string") {
          return []
        }
        return [
          {
            loc: Array.isArray(item.loc) ? item.loc.map((part) => String(part)) : [],
            msg: item.msg,
            type: typeof item.type === "string" ? item.type : "",
          },
        ]
      })
    : undefined
  return details && details.length > 0 ? { code, message, details } : { code, message }
}

export function explainError(code: string | undefined, status: number | undefined): string {
  switch (code) {
    case "validation_error":
      return "Some request fields are invalid. Review the highlighted fields."
    case "jev_not_configured":
      return "Jev is not configured on the backend. Configure JEV_API_KEY to run decision requests."
    case "jev_rate_limited":
      return "The service is receiving too many requests. Wait briefly before trying again."
    case "jev_timeout":
      return "The decision request timed out. You can try again."
    case "jev_upstream_error":
      return "Jev returned an error to Jev Explorer."
    case "jev_network_error":
      return "Jev Explorer could not reach Jev. This is separate from the backend health check."
    case "jev_invalid_response":
      return "Jev returned a response Jev Explorer could not accept."
    case "internal_error":
      return "Jev Explorer hit an unexpected error."
    default:
      if (status === undefined) {
        return "The backend could not be reached. Health and decision calls both use the Jev Explorer API."
      }
      return "The decision request failed."
  }
}

export function endpointFor(primitive: Primitive): string {
  return `/api/v1/jev/${primitive}`
}

export function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value)
}

export function readNumber(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null
}

export function readStringMap(value: unknown): Record<string, string> | null {
  if (!isRecord(value)) {
    return null
  }
  const entries = Object.entries(value)
  if (entries.some(([, item]) => typeof item !== "string")) {
    return null
  }
  return Object.fromEntries(entries) as Record<string, string>
}

export function readNumberMap(value: unknown): Record<string, number> | null {
  if (!isRecord(value)) {
    return null
  }
  const result: Record<string, number> = {}
  for (const [key, item] of Object.entries(value)) {
    if (typeof item === "boolean" || typeof item !== "number" || !Number.isFinite(item)) {
      return null
    }
    result[key] = item
  }
  return result
}
