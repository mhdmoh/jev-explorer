import { useState } from "react"
import { formatJson } from "../lib/decisions.ts"

type Props = {
  request: unknown | null
  response: unknown | null
}

export function JsonPanel({ request, response }: Props) {
  const [copied, setCopied] = useState<"request" | "response" | null>(null)

  async function copy(kind: "request" | "response", value: unknown) {
    try {
      await navigator.clipboard.writeText(formatJson(value))
      setCopied(kind)
    } catch {
      setCopied(null)
    }
  }

  return (
    <div className="json-grid">
      <JsonBlock
        title="Request JSON"
        empty="The request body appears here after you run a decision."
        value={request}
        copied={copied === "request"}
        onCopy={() => copy("request", request)}
      />
      <JsonBlock
        title="Response JSON"
        empty="The AgentGuard response appears here, including error JSON."
        value={response}
        copied={copied === "response"}
        onCopy={() => copy("response", response)}
      />
    </div>
  )
}

function JsonBlock({
  title,
  empty,
  value,
  copied,
  onCopy,
}: {
  title: string
  empty: string
  value: unknown | null
  copied: boolean
  onCopy: () => void
}) {
  return (
    <section className="json-block">
      <div className="json-head">
        <h3>{title}</h3>
        <button type="button" disabled={value === null} onClick={onCopy}>
          {copied ? "Copied" : "Copy"}
        </button>
      </div>
      {value === null ? (
        <p className="hint">{empty}</p>
      ) : (
        <pre tabIndex={0}>
          <code>{formatJson(value)}</code>
        </pre>
      )}
    </section>
  )
}
