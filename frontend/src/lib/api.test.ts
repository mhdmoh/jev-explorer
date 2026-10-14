import { describe, expect, it } from "vitest"

import { apiBaseUrl, apiUrl } from "./api.ts"

describe("apiUrl", () => {
  it("uses same-origin paths for health and the three decision routes", () => {
    expect(apiBaseUrl()).toBe("")
    expect(apiUrl("/health")).toBe("/health")
    expect(apiUrl("/api/v1/jev/choice")).toBe("/api/v1/jev/choice")
    expect(apiUrl("/api/v1/jev/score")).toBe("/api/v1/jev/score")
    expect(apiUrl("/api/v1/jev/noul")).toBe("/api/v1/jev/noul")
    expect(apiUrl("api/v1/jev/choice")).toBe("/api/v1/jev/choice")
  })
})
