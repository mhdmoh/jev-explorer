import { useState, type ReactNode } from "react"
import { formatJson } from "../lib/decisions.ts"
import { Icon } from "./Icon.tsx"

type Props = {
  request: unknown | null
  response: unknown | null
}

export function JsonPanel({ request, response }: Props) {
  const [copied, setCopied] = useState<"request" | "response" | null>(null)
  const [open, setOpen] = useState(true)

  async function copy(kind: "request" | "response", value: unknown | null) {
    if (value === null) {
      return
    }
    try {
      await navigator.clipboard.writeText(formatJson(value))
      setCopied(kind)
      window.setTimeout(() => setCopied((current) => (current === kind ? null : current)), 1600)
    } catch {
      setCopied(null)
    }
  }

  return (
    <section className="console-wrap" aria-label="Request and response JSON">
      <div className="console-bar">
        <button type="button" className="text-btn" aria-expanded={open} onClick={() => setOpen((current) => !current)}>
          {open ? "Collapse JSON" : "Expand JSON"}
        </button>
      </div>
      <div className={open ? "console is-open" : "console"}>
      <JsonPane
        title="Request JSON"
        codeId="request-json"
        value={request}
        empty="The request appears here when the form is valid."
        copied={copied === "request"}
        onCopy={() => void copy("request", request)}
      />
      <JsonPane
        title="Response JSON"
        codeId="response-json"
        value={response}
        empty="The AgentGuard response appears here, including error JSON."
        copied={copied === "response"}
        onCopy={() => void copy("response", response)}
      />
      </div>
    </section>
  )
}

function JsonPane({
  title,
  codeId,
  value,
  empty,
  copied,
  onCopy,
}: {
  title: string
  codeId: string
  value: unknown | null
  empty: string
  copied: boolean
  onCopy: () => void
}) {
  return (
    <div className="code-panel">
      <div className="code-head">
        <h3>{title}</h3>
        <button type="button" className="copy" aria-live="polite" disabled={value === null} onClick={onCopy}>
          <Icon name={copied ? "check" : "copy"} size={14} />
          <span>{copied ? "Copied" : "Copy"}</span>
        </button>
      </div>
      {value === null ? (
        <p className="code-empty">{empty}</p>
      ) : (
        <pre tabIndex={0}>
          <code id={codeId}>{highlightJson(formatJson(value))}</code>
        </pre>
      )}
    </div>
  )
}

function highlightJson(json: string): ReactNode[] {
  const nodes: ReactNode[] = []
  const pattern =
    /("(?:\\.|[^"\\])*")(\s*:)?|\b(true|false|null)\b|-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?/g
  let last = 0
  let index = 0
  for (const match of json.matchAll(pattern)) {
    const start = match.index
    if (start > last) {
      nodes.push(json.slice(last, start))
    }
    if (match[1]) {
      nodes.push(
        <span key={index} className={match[2] ? "k" : "s"}>
          {match[1]}
        </span>,
      )
      index += 1
      if (match[2]) {
        nodes.push(match[2])
      }
    } else if (match[3]) {
      nodes.push(
        <span key={index} className="n">
          {match[3]}
        </span>,
      )
      index += 1
    } else {
      nodes.push(
        <span key={index} className="n">
          {match[0]}
        </span>,
      )
      index += 1
    }
    last = start + match[0].length
  }
  if (last < json.length) {
    nodes.push(json.slice(last))
  }
  return nodes
}
