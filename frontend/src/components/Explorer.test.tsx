import { cleanup, render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { afterEach, describe, expect, it, vi } from "vitest"
import { Explorer } from "./Explorer.tsx"

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  })
}

function installFetch(
  decision: (url: string, init: RequestInit | undefined) => Response | Promise<Response>,
) {
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input)
    if (url.endsWith("/health")) {
      return jsonResponse({ status: "ok" })
    }
    return decision(url, init)
  })
  vi.stubGlobal("fetch", fetchMock)
  return fetchMock
}

function decisionCalls(fetchMock: ReturnType<typeof installFetch>) {
  return fetchMock.mock.calls.filter(([input]) => String(input).includes("/api/v1/jev/"))
}

async function renderExplorer() {
  render(<Explorer />)
  expect(await screen.findByText("Backend connected")).toBeTruthy()
}

describe("Explorer", () => {
  it("switches primitive forms", async () => {
    const user = userEvent.setup()
    installFetch(() => jsonResponse({}))
    await renderExplorer()
    expect(screen.getByRole("group", { name: "Options" })).toBeTruthy()
    await user.click(screen.getByRole("radio", { name: /Score/ }))
    expect(screen.getByRole("group", { name: "Levels, low to high" })).toBeTruthy()
    expect(screen.queryByRole("group", { name: "Options" })).toBeNull()
    await user.click(screen.getByRole("radio", { name: /Noul/ }))
    expect(screen.queryByRole("group", { name: "Levels, low to high" })).toBeNull()
    expect(screen.getByText(/probability from 0 to 1/i)).toBeTruthy()
  })

  it("posts the choice body that the inspector shows", async () => {
    const user = userEvent.setup()
    const fetchMock = installFetch((url) => {
      expect(url).toContain("/api/v1/jev/choice")
      return jsonResponse({
        model: "jev-1.13.0",
        type: "choice",
        choice: "billing",
        confidence: 0.99,
        probabilities: { billing: 0.99, bug: 0.01, account: 0 },
      })
    })
    await renderExplorer()
    await user.click(screen.getByRole("button", { name: "Run choice" }))
    expect(await screen.findByText("billing", { selector: ".result-value" })).toBeTruthy()
    const calls = decisionCalls(fetchMock)
    expect(calls).toHaveLength(1)
    const sent = JSON.parse(String(calls[0]?.[1]?.body))
    expect(sent).toEqual({
      state: "Customer: I was charged twice and nobody has replied for 3 days.",
      instructions: "Where should this go?",
      criteria: {
        billing: "payments, refunds, invoices",
        bug: "the product is broken",
        account: "login or access",
      },
    })
    expect(document.querySelector("#request-json")?.textContent).toContain('"criteria"')
    expect(document.querySelector("#response-json")?.textContent).toContain('"choice": "billing"')
  })

  it("does not call the API for malformed JSON state", async () => {
    const user = userEvent.setup()
    const fetchMock = installFetch(() => jsonResponse({}))
    await renderExplorer()
    await user.click(screen.getByRole("radio", { name: "JSON" }))
    const input = screen.getByLabelText("State JSON")
    await user.clear(input)
    await user.type(input, "{{")
    expect(screen.getByText(/State JSON is not valid/)).toBeTruthy()
    expect(screen.getByRole("button", { name: "Run choice" }).hasAttribute("disabled")).toBe(true)
    expect(decisionCalls(fetchMock)).toHaveLength(0)
  })

  it("blocks duplicate choice keys before sending", async () => {
    const user = userEvent.setup()
    const fetchMock = installFetch(() => jsonResponse({}))
    await renderExplorer()
    const keys = screen.getAllByRole("textbox", { name: "Key" })
    await user.clear(keys[1]!)
    await user.type(keys[1]!, "billing")
    expect(screen.getAllByText(/unique/i).length).toBeGreaterThan(0)
    expect(screen.getByRole("button", { name: "Run choice" }).hasAttribute("disabled")).toBe(true)
    expect(decisionCalls(fetchMock)).toHaveLength(0)
  })

  it("shows a fractional score and an out-of-range score exactly", async () => {
    const user = userEvent.setup()
    let score = 2.97
    installFetch(() =>
      jsonResponse({
        model: "jev-1.13.0",
        type: "score",
        score,
        probabilities: { "0": 0, "3": 1 },
      }),
    )
    await renderExplorer()
    await user.click(screen.getByRole("radio", { name: /Score/ }))
    await user.click(screen.getByRole("button", { name: "Run score" }))
    expect(await screen.findByText("2.97", { selector: ".result-value" })).toBeTruthy()
    expect(screen.getByText(/Between index 2/)).toBeTruthy()
    expect(screen.getByText("Jev did not include a legend.")).toBeTruthy()
    expect(screen.getByText(/Confidence: not included/)).toBeTruthy()
    score = 10.5
    await user.click(screen.getByRole("button", { name: "Run score" }))
    expect(await screen.findByText("10.5", { selector: ".result-value" })).toBeTruthy()
    expect(screen.getByText(/Above index 3/)).toBeTruthy()
  })

  it("shows noul 0 and 1 without turning them into a boolean", async () => {
    const user = userEvent.setup()
    let noul = 0
    installFetch(() => jsonResponse({ model: "jev-1.13.0", type: "noul", noul }))
    await renderExplorer()
    await user.click(screen.getByRole("radio", { name: /Noul/ }))
    await user.click(screen.getByRole("button", { name: "Run noul" }))
    expect(await screen.findByText(/0% for display/)).toBeTruthy()
    expect(document.querySelector(".result-value")?.textContent).toBe("0")
    noul = 1
    await user.click(screen.getByRole("button", { name: "Run noul" }))
    expect(await screen.findByText(/100% for display/)).toBeTruthy()
    expect(document.querySelector(".result-value")?.textContent).toBe("1")
    expect(screen.queryByText(/approved|permitted|authorized/i)).toBeNull()
  })

  it.each([
    [422, "validation_error", "Request validation failed.", /invalid/i],
    [503, "jev_not_configured", "Jev is not configured. Set JEV_API_KEY on the server.", /JEV_API_KEY/],
    [429, "jev_rate_limited", "Jev API rate limit exceeded.", /too many requests/i],
    [504, "jev_timeout", "The Jev request timed out.", /timed out/i],
  ] as const)("shows %s %s", async (status, code, message, pattern) => {
    const user = userEvent.setup()
    installFetch(() => jsonResponse({ error: { code, message } }, status))
    await renderExplorer()
    await user.click(screen.getByRole("button", { name: "Run choice" }))
    expect(await screen.findByRole("alert")).toHaveProperty("textContent")
    expect((await screen.findByRole("alert")).textContent ?? "").toMatch(pattern)
    expect(document.querySelector("#response-json")?.textContent ?? "").toContain(`"${code}"`)
  })

  it("loads an example without sending a request or inventing a result", async () => {
    const user = userEvent.setup()
    const fetchMock = installFetch(() => jsonResponse({}))
    await renderExplorer()
    await user.click(screen.getByRole("radio", { name: /Score/ }))
    await user.click(screen.getByRole("button", { name: "Load example" }))
    expect((screen.getByLabelText("State") as HTMLTextAreaElement).value).toMatch(/checkout fails/)
    expect((screen.getByLabelText("Instructions") as HTMLTextAreaElement).value).toBe(
      "How urgent is this incident?",
    )
    expect(screen.getByText(/Nothing here is a sample result/)).toBeTruthy()
    expect(decisionCalls(fetchMock)).toHaveLength(0)
    await user.click(screen.getByRole("radio", { name: /Choice/ }))
    expect(screen.getByDisplayValue("billing")).toBeTruthy()
  })

  it("disables submit while a request is in flight", async () => {
    const user = userEvent.setup()
    let release: (value: Response) => void = () => {}
    installFetch(
      () =>
        new Promise<Response>((resolve) => {
          release = resolve
        }),
    )
    await renderExplorer()
    const button = screen.getByRole("button", { name: "Run choice" })
    await user.click(button)
    expect(screen.getByRole("button", { name: "Evaluating choice…" }).hasAttribute("disabled")).toBe(true)
    release(
      jsonResponse({
        model: "jev-1.13.0",
        type: "choice",
        choice: "bug",
        confidence: 1,
        probabilities: { billing: 0, bug: 1, account: 0 },
      }),
    )
    expect(await screen.findByText("bug", { selector: ".result-value" })).toBeTruthy()
  })
})
