import {
  formatExact,
  formatPercent,
  scorePlacement,
  scoreTrackPercent,
} from "../lib/decisions.ts"
import { readChoiceView, readNoulView, readScoreView } from "../lib/results.ts"
import type { Primitive } from "../types/decisions.ts"

type Props = {
  primitive: Primitive
  phase: "idle" | "loading" | "success" | "error"
  response: unknown | null
  errorMessage: string | null
  errorDetail: string | null
  choiceKeys: string[]
  scoreLabels: string[]
}

const INTRO: Record<Primitive, string> = {
  choice: "Run a choice to see the selected key and the probability of each option.",
  score:
    "Run a score to see the exact index Jev returns. 0 is your first, lowest level. Fractional values stay fractional.",
  noul: "Run a noul to see a probability from 0 to 1 that the answer to your instructions is yes.",
}

export function ResultPanel({
  primitive,
  phase,
  response,
  errorMessage,
  errorDetail,
  choiceKeys,
  scoreLabels,
}: Props) {
  return (
    <section className="result" aria-live="polite">
      <h2>Result</h2>
      {phase === "idle" ? <p className="hint">{INTRO[primitive]}</p> : null}
      {phase === "loading" ? <p className="loading">Evaluating {primitive}…</p> : null}
      {phase === "error" ? (
        <div className="notice" role="alert">
          <p>{errorMessage}</p>
          {errorDetail ? <p>{errorDetail}</p> : null}
        </div>
      ) : null}
      {phase === "success" && primitive === "choice" ? (
        <ChoiceResult body={response} optionKeys={choiceKeys} />
      ) : null}
      {phase === "success" && primitive === "score" ? (
        <ScoreResult body={response} labels={scoreLabels} />
      ) : null}
      {phase === "success" && primitive === "noul" ? <NoulResult body={response} /> : null}
    </section>
  )
}

function ChoiceResult({ body, optionKeys }: { body: unknown; optionKeys: string[] }) {
  const view = readChoiceView(body)
  const probabilities = view.probabilities
  const keys = uniqueKeys(optionKeys, probabilities ? Object.keys(probabilities) : [])
  const ranked = [...keys].sort((left, right) => {
    const a = probabilities?.[left]
    const b = probabilities?.[right]
    if (a === undefined && b === undefined) return 0
    if (a === undefined) return 1
    if (b === undefined) return -1
    return b - a
  })
  const known = new Set(optionKeys)

  return (
    <div>
      {view.warning ? <p className="notice">{view.warning}</p> : null}
      <p className="result-kicker">Selected option</p>
      <p className="result-value">{view.choice ?? "Unavailable"}</p>
      {view.choice && !known.has(view.choice) ? (
        <p className="notice">
          This choice is not one of the options in the form. The raw value is shown unchanged.
        </p>
      ) : null}
      <Meta model={view.model} confidence={view.confidence} />
      <h3>Option probabilities</h3>
      {probabilities ? (
        <ul className="bars">
          {ranked.map((key) => {
            const value = probabilities[key]
            return (
              <li key={key}>
                <div className="bar-label">
                  <span>
                    {key}
                    {key === view.choice ? " · selected" : ""}
                    {!known.has(key) ? " · not in the request" : ""}
                  </span>
                  <span>{value === undefined ? "No probability" : formatExact(value)}</span>
                </div>
                {value === undefined ? (
                  <p className="hint">No probability was returned for this option.</p>
                ) : (
                  <Bar value={value} label={`${key} probability ${formatExact(value)}`} />
                )}
              </li>
            )
          })}
        </ul>
      ) : (
        <p className="hint">Probabilities were not included. Nothing was filled in for them.</p>
      )}
      <p className="hint">
        Probability is the weight returned for an option. Confidence is a separate number on the
        answer. They are not interchangeable.
      </p>
    </div>
  )
}

function ScoreResult({ body, labels }: { body: unknown; labels: string[] }) {
  const view = readScoreView(body)
  const placement = view.score === null ? null : scorePlacement(view.score, labels.length)
  const percent = view.score === null ? null : scoreTrackPercent(view.score, labels.length)

  return (
    <div>
      {view.warning ? <p className="notice">{view.warning}</p> : null}
      <p className="result-kicker">Score index</p>
      <p className="result-value">{view.score === null ? "Unavailable" : formatExact(view.score)}</p>
      {placement ? <p>{placementText(placement, labels)}</p> : null}
      <Meta model={view.model} confidence={view.confidence} />
      <div
        className="scale"
        role="img"
        aria-label={
          view.score === null
            ? "Score unavailable"
            : `Score ${formatExact(view.score)} on levels 0 through ${Math.max(0, labels.length - 1)}`
        }
      >
        <div className="scale-track">
          {percent !== null ? <span className="scale-mark" style={{ left: `${percent}%` }} /> : null}
        </div>
        <ol className="scale-labels">
          {labels.map((label, index) => (
            <li key={`${index}-${label}`}>
              <span>{index}</span>
              {label || "Untitled"}
            </li>
          ))}
        </ol>
      </div>
      {placement && (placement.kind === "below" || placement.kind === "above") ? (
        <p className="notice">
          The marker stays off the scale so an out-of-range score is not pulled onto a level.
        </p>
      ) : null}
      <h3>Legend</h3>
      {view.legend ? (
        <dl className="legend">
          {Object.entries(view.legend).map(([index, label]) => (
            <div key={index}>
              <dt>{index}</dt>
              <dd>{label}</dd>
            </div>
          ))}
        </dl>
      ) : (
        <p className="hint">Jev did not include a legend.</p>
      )}
      {view.probabilities ? (
        <>
          <h3>Level probabilities</h3>
          <ul className="bars">
            {Object.entries(view.probabilities).map(([index, value]) => (
              <li key={index}>
                <div className="bar-label">
                  <span>Index {index}</span>
                  <span>{formatExact(value)}</span>
                </div>
                <Bar value={value} label={`Index ${index} probability ${formatExact(value)}`} />
              </li>
            ))}
          </ul>
        </>
      ) : (
        <p className="hint">Level probabilities were not included.</p>
      )}
    </div>
  )
}

function NoulResult({ body }: { body: unknown }) {
  const view = readNoulView(body)
  const width = view.noul === null ? 0 : Math.min(100, Math.max(0, view.noul * 100))

  return (
    <div>
      {view.warning ? <p className="notice">{view.warning}</p> : null}
      <p className="result-kicker">Probability the answer is yes</p>
      <p className="result-value">{view.noul === null ? "Unavailable" : formatExact(view.noul)}</p>
      {view.noul !== null ? <p>{formatPercent(view.noul)} for display. The decimal above is exact.</p> : null}
      <Meta model={view.model} confidence={null} hideConfidence />
      <div className="scale" role="img" aria-label={view.noul === null ? "noul unavailable" : `noul ${formatExact(view.noul)}`}>
        <div className="scale-track">
          <span className="scale-fill" style={{ width: `${width}%` }} />
        </div>
        <div className="scale-ends">
          <span>0</span>
          <span>1</span>
        </div>
      </div>
      <p className="hint">
        This is Jev’s probability, not a yes/no and not permission to act. A cutoff, if an
        application uses one, belongs to that application’s policy.
      </p>
    </div>
  )
}

function Meta({
  model,
  confidence,
  hideConfidence = false,
}: {
  model: string | null
  confidence: number | null
  hideConfidence?: boolean
}) {
  return (
    <p className="meta">
      Model: {model ?? "not included"}
      {hideConfidence ? null : (
        <>
          {" "}
          · Confidence: {confidence === null ? "not included" : formatExact(confidence)}
        </>
      )}
    </p>
  )
}

function Bar({ value, label }: { value: number; label: string }) {
  const width = Math.min(100, Math.max(0, value * 100))
  const outside = value < 0 || value > 1
  return (
    <>
      <div className="bar" role="img" aria-label={label}>
        <span style={{ width: `${width}%` }} />
      </div>
      {outside ? <p className="hint">This probability is outside 0–1. The number is not rescaled.</p> : null}
    </>
  )
}

function uniqueKeys(first: string[], second: string[]): string[] {
  return [...new Set([...first, ...second])]
}

function placementText(
  placement: ReturnType<typeof scorePlacement>,
  labels: string[],
): string {
  if (placement.kind === "aligned") {
    const label = labels[placement.index] ?? "untitled"
    return `Aligns with index ${placement.index} (${label}).`
  }
  if (placement.kind === "between") {
    const lower = labels[placement.lower] ?? "untitled"
    const upper = labels[placement.upper] ?? "untitled"
    return `Between index ${placement.lower} (${lower}) and index ${placement.upper} (${upper}).`
  }
  if (placement.kind === "below") {
    return "Below index 0, outside the levels you sent."
  }
  return `Above index ${placement.lastIndex}, outside the levels you sent.`
}
