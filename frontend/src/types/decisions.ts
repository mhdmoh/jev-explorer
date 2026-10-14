export type Primitive = "choice" | "score" | "noul"

export type StateMode = "text" | "json"

export type DecisionState = string | Record<string, unknown> | unknown[]

export type ChoiceRequestBody = {
  state: DecisionState
  instructions: string
  criteria: Record<string, string>
  model?: string
}

export type ScoreRequestBody = {
  state: DecisionState
  instructions: string
  criteria: string[]
  model?: string
}

export type NoulRequestBody = {
  state: DecisionState
  instructions: string
  model?: string
}

export type DecisionRequestBody = ChoiceRequestBody | ScoreRequestBody | NoulRequestBody

export type Usage = {
  input_tokens?: number | null
  output_tokens?: number | null
  cost_usd?: number | null
  credits_remaining_usd?: number | null
} & Record<string, unknown>

export type ChoiceResult = {
  model?: string
  type: "choice"
  choice: string
  confidence: number | null
  probabilities: Record<string, number> | null
  usage: Usage | null
}

export type ScoreResult = {
  model?: string
  type: "score"
  score: number
  confidence: number | null
  probabilities: Record<string, number> | null
  legend: Record<string, string> | null
  usage: Usage | null
}

export type NoulResult = {
  model?: string
  type: "noul"
  noul: number
  usage: Usage | null
}

export type ApiErrorDetail = {
  loc: string[]
  msg: string
  type: string
}

export type ApiErrorPayload = {
  code: string
  message: string
  details?: ApiErrorDetail[]
}
