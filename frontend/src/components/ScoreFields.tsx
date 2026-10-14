import { SCORE_MAX, SCORE_MIN } from "../lib/decisions.ts"
import type { ScoreDraft } from "../lib/decisions.ts"

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
    <fieldset className="editor" disabled={disabled}>
      <legend>Levels, low to high</legend>
      <p className="hint">
        Order is the scale. Index 0 is the lowest level. Jev’s score is a position on these
        {`indexes and may be fractional, such as 2.5 between levels 2 and 3. Use ${SCORE_MIN}–${SCORE_MAX} levels.`}
      </p>
      <ol className="rows">
        {rows.map((row, index) => {
          const error = rowErrors?.[row.id]
          const errorId = `score-error-${row.id}`
          return (
            <li key={row.id} className="row">
              <span className="index">{index}</span>
              <label>
                Level {index}
                <input
                  aria-invalid={Boolean(error)}
                  aria-describedby={error ? errorId : undefined}
                  value={row.label}
                  onChange={(event) =>
                    onChange(
                      rows.map((item) =>
                        item.id === row.id ? { ...item, label: event.target.value } : item,
                      ),
                    )
                  }
                />
              </label>
              <div className="row-actions">
                <button type="button" disabled={index === 0} onClick={() => move(index, -1)}>
                  Move up
                </button>
                <button
                  type="button"
                  disabled={index === rows.length - 1}
                  onClick={() => move(index, 1)}
                >
                  Move down
                </button>
                <button
                  type="button"
                  className="text-button"
                  disabled={rows.length <= SCORE_MIN}
                  onClick={() => onChange(rows.filter((item) => item.id !== row.id))}
                >
                  Remove
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
        disabled={rows.length >= SCORE_MAX}
        onClick={() => onChange([...rows, { id: crypto.randomUUID(), label: "" }])}
      >
        Add level
      </button>
      {criteriaError ? <p className="field-error">{criteriaError}</p> : null}
    </fieldset>
  )
}
