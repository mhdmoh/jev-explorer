import { CHOICE_MAX } from "../lib/decisions.ts"
import type { ChoiceDraft } from "../lib/decisions.ts"

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

  return (
    <fieldset className="editor" disabled={disabled}>
      <legend>Options</legend>
      <p className="hint">
        Each key is a value Jev can select. The description tells Jev what that key means.
        {`Use 1–${CHOICE_MAX} options. Keys must be unique.`}
      </p>
      <ul className="rows">
        {rows.map((row, index) => {
          const error = rowErrors?.[row.id]
          const errorId = `choice-error-${row.id}`
          return (
            <li key={row.id} className="row">
              <label>
                Key
                <input
                  aria-invalid={Boolean(error)}
                  aria-describedby={error ? errorId : undefined}
                  value={row.key}
                  spellCheck={false}
                  onChange={(event) => update(row.id, { key: event.target.value })}
                />
              </label>
              <label>
                Description
                <input
                  aria-invalid={Boolean(error)}
                  aria-describedby={error ? errorId : undefined}
                  value={row.description}
                  onChange={(event) => update(row.id, { description: event.target.value })}
                />
              </label>
              <button
                type="button"
                className="text-button"
                disabled={rows.length === 1}
                onClick={() => onChange(rows.filter((item) => item.id !== row.id))}
              >
                Remove option {index + 1}
              </button>
              {error ? (
                <p id={errorId} className="field-error">
                  {error}
                </p>
              ) : null}
            </li>
          )
        })}
      </ul>
      <button
        type="button"
        disabled={rows.length >= CHOICE_MAX}
        onClick={() =>
          onChange([...rows, { id: crypto.randomUUID(), key: "", description: "" }])
        }
      >
        Add option
      </button>
      {criteriaError ? <p className="field-error">{criteriaError}</p> : null}
    </fieldset>
  )
}
