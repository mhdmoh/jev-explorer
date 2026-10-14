import { CHOICE_MAX } from "../lib/decisions.ts"
import type { ChoiceDraft } from "../lib/decisions.ts"
import { Icon } from "./Icon.tsx"

type Props = {
  rows: ChoiceDraft[]
  rowErrors: Record<string, string> | undefined
  criteriaError: string | undefined
  disabled: boolean
  onChange: (rows: ChoiceDraft[]) => void
}

export function ChoiceFields({ rows, rowErrors, criteriaError, disabled, onChange }: Props) {
  function update(id: string, patch: Partial<ChoiceDraft>) {
    onChange(rows.map((row) => (row.id === id ? { ...row, ...patch } : row)))
  }

  function move(index: number, direction: -1 | 1) {
    const next = index + direction
    if (next < 0 || next >= rows.length) {
      return
    }
    const copy = rows.slice()
    const current = copy[index]
    const target = copy[next]
    if (!current || !target) {
      return
    }
    copy[index] = target
    copy[next] = current
    onChange(copy)
  }

  return (
    <fieldset className="field" disabled={disabled}>
      <legend className="sr">Options</legend>
      <div className="lab">
        <span className="lab-t">Options</span>
        <span className="count">
          {rows.length} / {CHOICE_MAX}
        </span>
      </div>
      <p className="hint">
        Each key is a value Jev can select. The description tells Jev what that key means.
        {` Use 1–${CHOICE_MAX} options. Keys must be unique.`}
      </p>
      <div className="row-head">
        <span />
        <span>Key</span>
        <span>Description</span>
        <span />
      </div>
      <ol className="rows">
        {rows.map((row, index) => {
          const error = rowErrors?.[row.id]
          const errorId = `choice-error-${row.id}`
          const position = index + 1
          return (
            <li key={row.id} className="row pair">
              <span className="idx" style={{ ["--t" as string]: 12 }} aria-hidden="true">
                {position}
              </span>
              <input
                className="in key"
                aria-label="Key"
                aria-invalid={Boolean(error)}
                aria-describedby={error ? errorId : undefined}
                value={row.key}
                spellCheck={false}
                placeholder="key"
                onChange={(event) => update(row.id, { key: event.target.value })}
              />
              <input
                className="in in-desc"
                aria-label="Description"
                aria-invalid={Boolean(error)}
                aria-describedby={error ? errorId : undefined}
                value={row.description}
                placeholder="What this key means"
                onChange={(event) => update(row.id, { description: event.target.value })}
              />
              <div className="row-actions">
                <button
                  type="button"
                  className="ib"
                  aria-label={`Move option ${position} up`}
                  disabled={index === 0}
                  onClick={() => move(index, -1)}
                >
                  <Icon name="up" />
                </button>
                <button
                  type="button"
                  className="ib"
                  aria-label={`Move option ${position} down`}
                  disabled={index === rows.length - 1}
                  onClick={() => move(index, 1)}
                >
                  <Icon name="down" />
                </button>
                <button
                  type="button"
                  className="ib rm"
                  aria-label={`Remove option ${position}`}
                  disabled={rows.length === 1}
                  onClick={() => onChange(rows.filter((item) => item.id !== row.id))}
                >
                  <Icon name="x" />
                </button>
              </div>
              {error ? (
                <p id={errorId} className="field-error">
                  {error}
                </p>
              ) : null}
            </li>
          )
        })}
      </ol>
      <button
        type="button"
        className="add"
        disabled={rows.length >= CHOICE_MAX}
        onClick={() => onChange([...rows, { id: crypto.randomUUID(), key: "", description: "" }])}
      >
        <Icon name="plus" />
        <span>Add option</span>
      </button>
      {criteriaError ? <p className="field-error">{criteriaError}</p> : null}
    </fieldset>
  )
}
