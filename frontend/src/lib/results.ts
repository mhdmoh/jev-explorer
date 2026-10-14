import { isRecord, readNumber, readNumberMap, readStringMap } from "./decisions.ts"

export type ChoiceView = {
  choice: string | null
  confidence: number | null
  probabilities: Record<string, number> | null
  model: string | null
  warning: string | null
}

export type ScoreView = {
  score: number | null
  confidence: number | null
  probabilities: Record<string, number> | null
  legend: Record<string, string> | null
  model: string | null
  warning: string | null
}

export type NoulView = {
  noul: number | null
  model: string | null
  warning: string | null
}

export function readChoiceView(body: unknown): ChoiceView {
  const record = isRecord(body) ? body : null
  const choice = typeof record?.choice === "string" ? record.choice : null
  return {
    choice,
    confidence: readNumber(record?.confidence),
    probabilities: readNumberMap(record?.probabilities),
    model: typeof record?.model === "string" ? record.model : null,
    warning: choice ? null : "The response did not include a choice string.",
  }
}

export function readScoreView(body: unknown): ScoreView {
  const record = isRecord(body) ? body : null
  const score = readNumber(record?.score)
  return {
    score,
    confidence: readNumber(record?.confidence),
    probabilities: readNumberMap(record?.probabilities),
    legend: readStringMap(record?.legend),
    model: typeof record?.model === "string" ? record.model : null,
    warning: score === null ? "The response did not include a numeric score." : null,
  }
}

export function readNoulView(body: unknown): NoulView {
  const record = isRecord(body) ? body : null
  const noul = readNumber(record?.noul)
  let warning: string | null = null
  if (noul === null) {
    warning = "The response did not include a numeric noul value."
  } else if (noul < 0 || noul > 1) {
    warning = "This noul value is outside 0–1. The raw number is unchanged."
  }
  return {
    noul,
    model: typeof record?.model === "string" ? record.model : null,
    warning,
  }
}
