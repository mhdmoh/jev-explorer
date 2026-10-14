import { useState } from "react"
import {
  formatExact,
  formatPercent,
  scorePlacement,
  scoreTrackPercent,
} from "../lib/decisions.ts"
import { readChoiceView, readNoulView, readScoreView } from "../lib/results.ts"
import type { Primitive } from "../types/decisions.ts"

type Option = { key: string; description: string }

type Props = {
  primitive: Primitive
  phase: "idle" | "loading" | "success" | "error"
  response: unknown | null
  errorMessage: string | null
  errorDetail: string | null
  stale: boolean
  choiceOptions: Option[]
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
  stale,
  choiceOptions,
  scoreLabels,
}: Props) {
  return (
    <aside className="panel result" aria-labelledby="resTitle" aria-live="polite" aria-busy={phase === "loading"}>
      <div className="p-head">
        <h2 id="resTitle">Result</h2>
        <div className="chips">
          {stale ? <span className="chip warn">Inputs changed</span> : null}
        </div>
      </div>

      {phase === "idle" ? (
        <div className="empty">
          <p>{INTRO[primitive]}</p>
          <p className="hint">Nothing here is a sample result. Run the request to see Jev’s answer.</p>
        </div>
      ) : null}

      {phase === "loading" ? (
        <div className="loading-row">
          <span className="spin" aria-hidden="true" />
          <p>Evaluating {primitive}…</p>
        </div>
      ) : null}

      {phase === "error" ? (
        <div className="notice" role="alert">
          <p>{errorMessage}</p>
          {errorDetail ? <p>{errorDetail}</p> : null}
        </div>
      ) : null}

      {phase === "success" && primitive === "choice" ? (
        <ChoiceResult body={response} options={choiceOptions} />
      ) : null}
      {phase === "success" && primitive === "score" ? (
        <ScoreResult body={response} labels={scoreLabels} />
      ) : null}
      {phase === "success" && primitive === "noul" ? <NoulResult body={response} /> : null}
    </aside>
  )
}

function ChoiceResult({ body, options }: { body: unknown; options: Option[] }) {
  const view = readChoiceView(body)
  const [chart, setChart] = useState<"bars" | "columns">("bars")
  const probabilities = view.probabilities
  const optionKeys = options.map((option) => option.key)
  const descriptions = new Map(options.map((option) => [option.key, option.description]))
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
  const selectedIndex = view.choice ? optionKeys.indexOf(view.choice) : -1

  return (
    <div className="body">
      {view.warning ? <p className="notice">{view.warning}</p> : null}
      <div className="hero">
        <span className="kicker">Selected option</span>
        <div className="pick">
          {selectedIndex >= 0 ? (
            <span className="idx" style={{ ["--t" as string]: 34 }} aria-hidden="true">
              {selectedIndex + 1}
            </span>
          ) : null}
          <span className="result-value">{view.choice ?? "Unavailable"}</span>
        </div>
        {view.choice && !known.has(view.choice) ? (
          <p className="notice">
            This choice is not one of the options in the form. The raw value is shown unchanged.
          </p>
        ) : null}
        {view.choice && descriptions.get(view.choice) ? (
          <p className="desc">{descriptions.get(view.choice)}</p>
        ) : null}
        <Confidence value={view.confidence} />
      </div>
      <div>
        <div className="sec-row">
          <h3 className="sec-title">Option probabilities</h3>
          <div className="seg" role="radiogroup" aria-label="Choice chart">
            <label>
              <input
                type="radio"
                name="choice-chart"
                checked={chart === "bars"}
                onChange={() => setChart("bars")}
              />
              Probability bars
            </label>
            <label>
              <input
                type="radio"
                name="choice-chart"
                checked={chart === "columns"}
                onChange={() => setChart("columns")}
              />
              Bar chart
            </label>
          </div>
        </div>
        {probabilities ? (
          chart === "bars" ? (
            <ul className="dist">
              {ranked.map((key) => {
                const value = probabilities[key]
                const selected = key === view.choice
                const position = optionKeys.indexOf(key)
                return (
                  <li key={key} className={selected ? "on" : undefined}>
                    <span className="idx sm" style={{ ["--t" as string]: selected ? 34 : 12 }} aria-hidden="true">
                      {position >= 0 ? position + 1 : "·"}
                    </span>
                    <span className="lbl">
                      {key}
                      {selected ? <em>selected</em> : null}
                      {!known.has(key) ? <em>not in the request</em> : null}
                      {descriptions.get(key) ? <small>{descriptions.get(key)}</small> : null}
                    </span>
                    <span className="bar" title={value === undefined ? `${key}: no probability` : `${key} probability ${formatExact(value)}`}>
                      {value === undefined ? null : <i style={{ width: `${barWidth(value)}%` }} />}
                    </span>
                    <span className="pct">{value === undefined ? "—" : formatExact(value)}</span>
                  </li>
                )
              })}
            </ul>
          ) : (
            <div className="chart" role="img" aria-label="Probability bar chart">
              {keys.map((key) => {
                const value = probabilities[key]
                const selected = key === view.choice
                return (
                  <div
                    key={key}
                    className={selected ? "col on" : "col"}
                    title={`${columnTitle(key, value)}${selected ? ", selected" : ""}`}
                  >
                    <div className="plot">
                      <b>{value === undefined ? "—" : formatExact(value)}</b>
                      {value === undefined ? null : (
                        <i style={{ height: `calc((100% - 22px) * ${Math.min(1, Math.max(0, value))})` }} />
                      )}
                    </div>
                    <span className="clab">{key}</span>
                  </div>
                )
              })}
            </div>
          )
        ) : (
          <p className="hint">Probabilities were not included. Nothing was filled in for them.</p>
        )}
        {probabilities && Object.values(probabilities).some((value) => value < 0 || value > 1) ? (
          <p className="hint">A probability is outside 0–1. The number is not rescaled.</p>
        ) : null}
      </div>
      <p className="fine">
        Probability is the weight returned for an option. Confidence is a separate number on the
        answer. They are not interchangeable.
      </p>
      <Meta model={view.model} />
    </div>
  )
}

function ScoreResult({ body, labels }: { body: unknown; labels: string[] }) {
  const view = readScoreView(body)
  const placement = view.score === null ? null : scorePlacement(view.score, labels.length)
  const percent = view.score === null ? null : scoreTrackPercent(view.score, labels.length)
  const last = Math.max(0, labels.length - 1)

  return (
    <div className="body">
      {view.warning ? <p className="notice">{view.warning}</p> : null}
      <div className="hero">
        <span className="kicker">Score index</span>
        <div className="bignum result-value">{view.score === null ? "Unavailable" : formatExact(view.score)}</div>
        {placement ? <p className="sentence">{placementText(placement, labels)}</p> : null}
      </div>
      <div
        className="scale"
        role="img"
        aria-label={
          view.score === null
            ? "Score unavailable"
            : `Score ${formatExact(view.score)} on levels 0 through ${last}`
        }
      >
        <div className="track">
          {percent !== null ? <span className="fill" style={{ width: `${percent}%` }} /> : null}
          {labels.length >= 2
            ? labels.map((label, index) => {
                const left = (index / last) * 100
                const hit = percent !== null && left <= percent + 0.001
                return (
                  <span
                    key={`${index}-${label}`}
                    className={hit ? "tick hit" : "tick"}
                    style={{ left: `${left}%` }}
                  />
                )
              })
            : null}
          {percent !== null ? <span className="marker" style={{ left: `${percent}%` }} /> : null}
        </div>
        {labels.length >= 2 ? (
          <div className="nums">
            {labels.map((label, index) => (
              <span key={`${index}-${label}`} style={{ left: `${(index / last) * 100}%` }} title={scaleLabel(view.legend, labels, index)}>
                {index}
              </span>
            ))}
          </div>
        ) : null}
      </div>
      {placement && (placement.kind === "below" || placement.kind === "above") ? (
        <p className="notice">
          The marker stays off the scale so an out-of-range score is not pulled onto a level.
        </p>
      ) : null}
      {view.legend && !legendShownOnScale(view.legend, labels) ? (
        <div>
          <div className="sec-row">
            <h3 className="sec-title">Legend</h3>
          </div>
          <ul className="dist">
            {Object.entries(view.legend).map(([index, label]) => (
              <li key={index}>
                <span className="idx sm">{index}</span>
                <span className="lbl">{label}</span>
              </li>
            ))}
          </ul>
        </div>
      ) : view.legend ? null : (
        <p className="hint">Jev did not include a legend.</p>
      )}
      <div>
        <div className="sec-row">
          <h3 className="sec-title">Probability distribution</h3>
        </div>
        {view.probabilities ? (
          <>
            <p className="fine">
              These values are the probability weights Jev returned for each scale index. They are
              not the score.
            </p>
            <ul className="dist">
              {orderedProbabilityEntries(view.probabilities).map(([index, value]) => {
                const label = scaleLabel(view.legend, labels, Number(index))
                const near =
                  placement?.kind === "aligned"
                    ? placement.index === Number(index)
                    : placement?.kind === "between"
                      ? placement.lower === Number(index) || placement.upper === Number(index)
                      : false
                return (
                  <li key={index} className={near ? "near" : undefined}>
                    <span className="idx sm">{index}</span>
                    <span className="lbl">{label || "Untitled"}</span>
                    <span className="bar" title={`Index ${index} probability ${formatExact(value)}`}>
                      <i style={{ width: `${barWidth(value)}%` }} />
                    </span>
                    <span className="pct">{formatExact(value)}</span>
                  </li>
                )
              })}
            </ul>
          </>
        ) : (
          <p className="hint">Level probabilities were not included. The score above is the full result.</p>
        )}
      </div>
      <Meta model={view.model} confidence={view.confidence} />
    </div>
  )
}

function NoulResult({ body }: { body: unknown }) {
  const view = readNoulView(body)
  const inRange = view.noul !== null && view.noul >= 0 && view.noul <= 1
  const marker = inRange && view.noul !== null ? view.noul * 100 : null

  return (
    <div className="body">
      {view.warning ? <p className="notice">{view.warning}</p> : null}
      <div className="hero">
        <span className="kicker">Probability the answer is yes</span>
        <div className="bignum result-value">{view.noul === null ? "Unavailable" : formatExact(view.noul)}</div>
        {view.noul !== null ? (
          <p className="sentence">{formatPercent(view.noul)} for display. The decimal above is exact.</p>
        ) : null}
      </div>
      <div
        className="scale gauge"
        role="img"
        aria-label={view.noul === null ? "noul unavailable" : `noul ${formatExact(view.noul)}`}
      >
        <div className="track">
          {marker !== null ? <span className="fill" style={{ width: `${marker}%` }} /> : null}
          {marker !== null ? <span className="marker" style={{ left: `${marker}%` }} /> : null}
        </div>
        <div className="nums">
          <span style={{ left: "0%" }}>0</span>
          <span style={{ left: "100%" }}>1</span>
        </div>
      </div>
      <p className="fine">
        This is Jev’s probability, not a yes/no and not permission to act. A cutoff, if an
        application uses one, belongs to that application’s policy.
      </p>
      <Meta model={view.model} />
    </div>
  )
}

function Confidence({ value }: { value: number | null }) {
  if (value === null) {
    return <p className="sentence">Confidence: not included</p>
  }
  return (
    <p className="conf">
      Confidence <b>{formatExact(value)}</b>
      <span className="meter" aria-hidden="true">
        <i style={{ width: `${barWidth(value)}%` }} />
      </span>
    </p>
  )
}

function Meta({ model, confidence }: { model: string | null; confidence?: number | null }) {
  const showConfidence = confidence !== undefined
  return (
    <div className="meta">
      {model ? <span className="chip mono">{model}</span> : null}
      {showConfidence ? <Confidence value={confidence ?? null} /> : null}
    </div>
  )
}

function barWidth(value: number): number {
  return Math.min(100, Math.max(0, value * 100))
}

function columnTitle(key: string, value: number | undefined): string {
  return value === undefined ? `${key}: no probability` : `${key} probability ${formatExact(value)}`
}

function uniqueKeys(first: string[], second: string[]): string[] {
  return [...new Set([...first, ...second])]
}

function orderedProbabilityEntries(probabilities: Record<string, number>): [string, number][] {
  return Object.entries(probabilities).sort((left, right) => Number(left[0]) - Number(right[0]))
}

function scaleLabel(legend: Record<string, string> | null, labels: string[], index: number): string {
  return legend?.[String(index)] ?? labels[index] ?? ""
}

function legendShownOnScale(legend: Record<string, string>, labels: string[]): boolean {
  return Object.entries(legend).every(([index, label]) => labels[Number(index)] === label)
}

function placementText(placement: ReturnType<typeof scorePlacement>, labels: string[]): string {
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
