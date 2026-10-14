import { readApiError } from "./decisions.ts"
import type { ApiErrorPayload } from "../types/decisions.ts"

const HEALTH_TIMEOUT_MS = 4000
const DECISION_TIMEOUT_MS = 35_000

export type HealthResponse = {
  status: string
}

export class ApiError extends Error {
  readonly status: number | undefined
  readonly body: unknown
  readonly payload: ApiErrorPayload | null

  constructor(message: string, status?: number, body?: unknown) {
    super(message)
    this.name = "ApiError"
    this.status = status
    this.body = body
    this.payload = readApiError(body)
  }
}

/** Same-origin path. The dev server proxies these to the API. */
export function apiBaseUrl(): string {
  return ""
}

export function apiUrl(path: string): string {
  const normalized = path.startsWith("/") ? path : `/${path}`
  return `${apiBaseUrl()}${normalized}`
}

function isHealthResponse(value: unknown): value is HealthResponse {
  if (typeof value !== "object" || value === null) {
    return false
  }
  return typeof (value as { status?: unknown }).status === "string"
}

export async function getHealth(signal?: AbortSignal): Promise<HealthResponse> {
  const timeout = AbortSignal.timeout(HEALTH_TIMEOUT_MS)
  const combined = signal ? AbortSignal.any([signal, timeout]) : timeout

  let response: Response
  try {
    response = await fetch(apiUrl("/health"), {
      method: "GET",
      headers: { Accept: "application/json" },
      signal: combined,
    })
  } catch (error) {
    if (error instanceof DOMException && error.name === "TimeoutError") {
      throw new ApiError("Backend health check timed out")
    }
    if (error instanceof DOMException && error.name === "AbortError") {
      throw new ApiError("Backend health check was cancelled")
    }
    throw new ApiError("Backend health check failed")
  }

  if (!response.ok) {
    throw new ApiError(`Backend health check failed (${response.status})`, response.status)
  }

  let body: unknown
  try {
    body = await response.json()
  } catch {
    throw new ApiError("Backend returned an unreadable health response", response.status)
  }

  if (!isHealthResponse(body)) {
    throw new ApiError("Backend returned an unexpected health response", response.status)
  }

  return body
}

export async function postJson(path: string, body: unknown, signal?: AbortSignal): Promise<unknown> {
  const timeout = AbortSignal.timeout(DECISION_TIMEOUT_MS)
  const combined = signal ? AbortSignal.any([signal, timeout]) : timeout
  let response: Response
  try {
    response = await fetch(apiUrl(path), {
      method: "POST",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
      },
      body: JSON.stringify(body),
      signal: combined,
    })
  } catch (error) {
    if (signal?.aborted) {
      throw new ApiError("The decision request was cancelled")
    }
    if (error instanceof DOMException && error.name === "TimeoutError") {
      throw new ApiError("The decision request timed out before Jev Explorer responded")
    }
    throw new ApiError("The backend could not be reached")
  }

  const parsed = await readBody(response)
  if (!response.ok) {
    const payload = readApiError(parsed)
    throw new ApiError(payload?.message ?? `Request failed (${response.status})`, response.status, parsed)
  }
  return parsed
}

async function readBody(response: Response): Promise<unknown> {
  const text = await response.text()
  if (!text) {
    return null
  }
  try {
    return JSON.parse(text) as unknown
  } catch {
    return { raw: text }
  }
}
