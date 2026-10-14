import { SCORE_MAX, SCORE_MIN } from "../lib/decisions.ts"
import type { ScoreDraft } from "../lib/decisions.ts"
import { Icon } from "./Icon.tsx"

type Props = {
  rows: ScoreDraft[]
  rowErrors: Record<string, string> | undefined
  criteriaError: string | undefined
  disabled: boolean
  onChange: (rows: ScoreDraft[]) => void
}

export function ScoreFields({ rows, rowErrors, criteriaError, disabled, onChange }: Props) {
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
      <legend className="sr">Levels, low to high</legend>
      <div className="lab">
        <span className="lab-t">Levels, low to high</span>
        <span className="count">
          {rows.length} / {SCORE_MAX}
        </span>
      </div>
      <p className="hint">
        {`Index 0 is the lowest level. A score can fall between levels, such as 2.5. Use ${SCORE_MIN}–${SCORE_MAX} levels.`}
      </p>
      <ol className="rows">
        {rows.map((row, index) => {
          const error = rowErrors?.[row.id]
          const errorId = `score-error-${row.id}`
          const tint = Math.round(8 + (rows.length > 1 ? index / (rows.length - 1) : 0) * 32)
          return (
            <li key={row.id} className="row">
              <span className="idx" style={{ ["--t" as string]: tint }}>
                {index}
              </span>
              <input
                className="in"
                aria-label={`Level ${index}`}
                aria-invalid={Boolean(error)}
                aria-describedby={error ? errorId : undefined}
                value={row.label}
                placeholder={`Level ${index}`}
                onChange={(event) =>
                  onChange(
                    rows.map((item) =>
                      item.id === row.id ? { ...item, label: event.target.value } : item,
                    ),
                  )
                }
              />
              <div className="row-actions">
                <button
                  type="button"
                  className="ib"
                  aria-label={`Move level ${index} up`}
                  disabled={index === 0}
                  onClick={() => move(index, -1)}
                >
                  <Icon name="up" />
                </button>
                <button
                  type="button"
                  className="ib"
                  aria-label={`Move level ${index} down`}
                  disabled={index === rows.length - 1}
                  onClick={() => move(index, 1)}
                >
                  <Icon name="down" />
                </button>
                <button
                  type="button"
                  className="ib rm"
                  aria-label={`Remove level ${index}`}
                  disabled={rows.length <= SCORE_MIN}
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
        disabled={rows.length >= SCORE_MAX}
        onClick={() => onChange([...rows, { id: crypto.randomUUID(), label: "" }])}
      >
        <Icon name="plus" />
        <span>Add level</span>
      </button>
      {criteriaError ? <p className="field-error">{criteriaError}</p> : null}
    </fieldset>
  )
}
