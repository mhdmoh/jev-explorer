const DEFAULT_API_BASE_URL = "http://localhost:8000"
const HEALTH_TIMEOUT_MS = 4000

export type HealthResponse = {
  status: string
}

export class ApiError extends Error {
  readonly status: number | undefined

  constructor(message: string, status?: number) {
    super(message)
    this.name = "ApiError"
    this.status = status
  }
}

export function apiBaseUrl(): string {
  const configured = import.meta.env.VITE_API_BASE_URL?.trim()
  return (configured || DEFAULT_API_BASE_URL).replace(/\/$/, "")
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
