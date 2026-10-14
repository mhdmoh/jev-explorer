import { describe, expect, it } from "vitest"
import {
  buildChoiceBody,
  buildNoulBody,
  buildScoreBody,
  explainError,
  formatExact,
  parseState,
  scorePlacement,
  scoreTrackPercent,
  validateChoiceDrafts,
  validateScoreDrafts,
} from "./decisions.ts"
import { readChoiceView, readNoulView, readScoreView } from "./results.ts"

describe("parseState", () => {
  it("sends text mode as a string", () => {
    expect(parseState("text", "  hello")).toEqual({ ok: true, state: "  hello" })
  })

  it("parses a JSON object or array and rejects other JSON types", () => {
    expect(parseState("json", '{"ticket":1}')).toEqual({ ok: true, state: { ticket: 1 } })
    expect(parseState("json", '["a"]')).toEqual({ ok: true, state: ["a"] })
    expect(parseState("json", '"still a string"')).toEqual({ ok: true, state: "still a string" })
    expect(parseState("json", "{")).toMatchObject({ ok: false })
    expect(parseState("json", "12")).toMatchObject({ ok: false })
    expect(parseState("json", "true")).toMatchObject({ ok: false })
  })
})

describe("criteria validation", () => {
  it("rejects duplicate choice keys and empty descriptions", () => {
    const errors = validateChoiceDrafts([
      { id: "a", key: "billing", description: "money" },
      { id: "b", key: " billing ", description: "" },
    ])
    expect(errors.rows?.b).toBeTruthy()
  })

  it("rejects duplicate trimmed keys", () => {
    const errors = validateChoiceDrafts([
      { id: "a", key: "bug", description: "broken" },
      { id: "b", key: "bug", description: "also broken" },
    ])
    expect(errors.rows?.a).toMatch(/unique/i)
    expect(errors.rows?.b).toMatch(/unique/i)
  })

  it("requires 2 to 10 score levels", () => {
    expect(validateScoreDrafts([{ id: "a", label: "only" }]).criteria).toMatch(/2–10/)
    expect(validateScoreDrafts([{ id: "a", label: "low" }, { id: "b", label: "high" }])).toEqual({})
  })
})

describe("request bodies", () => {
  it("builds each primitive without a model override", () => {
    const choice = buildChoiceBody("note", " route ", [
      { id: "1", key: " bug ", description: " broken " },
    ])
    expect(choice).toEqual({
      state: "note",
      instructions: "route",
      criteria: { bug: "broken" },
    })
    expect(choice).not.toHaveProperty("model")

    const score = buildScoreBody({ ticket: 1 }, "urgent?", [
      { id: "1", label: "low" },
      { id: "2", label: "high" },
    ])
    expect(score).toEqual({
      state: { ticket: 1 },
      instructions: "urgent?",
      criteria: ["low", "high"],
    })
    expect(score).not.toHaveProperty("model")

    expect(buildNoulBody(["ctx"], "yes?")).toEqual({
      state: ["ctx"],
      instructions: "yes?",
    })
  })
})

describe("score and noul interpretation", () => {
  it("keeps fractional scores and flags values outside the index range", () => {
    expect(formatExact(2.97)).toBe("2.97")
    expect(scorePlacement(2.97, 4)).toEqual({ kind: "between", lower: 2, upper: 3 })
    expect(scorePlacement(0, 4)).toEqual({ kind: "aligned", index: 0 })
    expect(scorePlacement(10.5, 4)).toEqual({ kind: "above", lastIndex: 3 })
    expect(scoreTrackPercent(10.5, 4)).toBeNull()
    expect(scoreTrackPercent(0, 2)).toBe(0)
    expect(scoreTrackPercent(1, 2)).toBe(100)
  })

  it("reads 0 and 1 and missing metadata without inventing values", () => {
    expect(readNoulView({ noul: 0 }).noul).toBe(0)
    expect(readNoulView({ noul: 1 }).warning).toBeNull()
    expect(readScoreView({ score: 2.97 }).legend).toBeNull()
    expect(readScoreView({ score: 2.97 }).confidence).toBeNull()
    expect(readChoiceView({ choice: "billing" }).probabilities).toBeNull()
    expect(readChoiceView({ choice: "billing" }).confidence).toBeNull()
  })
})

describe("error explanations", () => {
  it("maps configuration, rate limit, and timeout codes", () => {
    expect(explainError("jev_not_configured", 503)).toMatch(/JEV_API_KEY/)
    expect(explainError("jev_rate_limited", 429)).toMatch(/too many requests/i)
    expect(explainError("jev_timeout", 504)).toMatch(/timed out/i)
    expect(explainError("validation_error", 422)).toMatch(/invalid/i)
    expect(explainError(undefined, undefined)).toMatch(/could not be reached/i)
  })
})
