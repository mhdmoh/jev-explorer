import { useEffect, useState } from "react"
import { getHealth } from "../lib/api.ts"

export type BackendStatus = "checking" | "connected" | "unavailable"

const STATUS_LABEL: Record<BackendStatus, string> = {
  checking: "Checking connection...",
  connected: "Backend connected",
  unavailable: "Backend unavailable",
}

export function backendStatusLabel(status: BackendStatus): string {
  return STATUS_LABEL[status]
}

export function useBackendStatus(): BackendStatus {
  const [status, setStatus] = useState<BackendStatus>("checking")

  useEffect(() => {
    const controller = new AbortController()

    getHealth(controller.signal)
      .then(() => {
        if (!controller.signal.aborted) {
          setStatus("connected")
        }
      })
      .catch(() => {
        if (!controller.signal.aborted) {
          setStatus("unavailable")
        }
      })

    return () => controller.abort()
  }, [])

  return status
}
