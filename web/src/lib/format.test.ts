import { describe, expect, it } from "vitest"
import { dateRange, daysBetween, due, heat, pct, pts, shortDate, signed, webUrl } from "./format"
import { parseRoute, routeHash } from "./hooks"

describe("format", () => {
  it("writes shares the way geometry.py measures them", () => {
    expect(pct(0.1234)).toBe("12.3%")
    expect(pct(null)).toBe("–")
    expect(pct(0.5, 0)).toBe("50%")
    expect(pct(0.0002)).toBe("<0.1%")
    expect(pct(0)).toBe("0.0%")
    expect(pct(0.004, 0)).toBe("<1%")
  })

  it("gives moves a sign, and a real minus", () => {
    expect(signed(0.0123)).toBe("+1.2%")
    expect(signed(-0.0123)).toBe("−1.2%")
    expect(signed(0.00001)).toBe("0.0%")
    expect(pts(-0.031)).toBe("−3.1 pts")
  })

  it("counts days and says when things are due", () => {
    expect(daysBetween("2026-11-04", "2026-11-06")).toBe(2)
    expect(due("2026-11-04", "2026-11-04")).toBe("today")
    expect(due("2026-11-05", "2026-11-04")).toBe("tomorrow")
    expect(due("2026-11-01", "2026-11-04")).toBe("3 days overdue")
    expect(due(null, "2026-11-04")).toBe("ongoing")
    expect(shortDate("2026-11-06")).toBe("06 Nov")
  })

  it("writes date ranges with the start year only when it differs", () => {
    expect(dateRange("2026-10-06", "2026-10-23")).toBe("6 Oct – 23 Oct 2026")
    expect(dateRange("2021-11-19", "2022-10-13")).toBe("19 Nov 2021 – 13 Oct 2022")
  })

  it("names how busy a theme is", () => {
    expect(heat(3).level).toBe("busy")
    expect(heat(1).level).toBe("active")
    expect(heat(0).words).toBe("quiet today")
  })

  it("links web addresses only", () => {
    expect(webUrl("https://example.com/a")).toBe("https://example.com/a")
    expect(webUrl("javascript:alert(1)")).toBeNull()
    expect(webUrl("data:text/html,x")).toBeNull()
    expect(webUrl(null)).toBeNull()
  })
})

describe("routes", () => {
  it("reads a page and an item from the address", () => {
    expect(parseRoute("#holdings/NVDA")).toEqual({ page: "holdings", item: "NVDA" })
    expect(parseRoute("#world")).toEqual({ page: "world", item: null })
    expect(parseRoute("#nowhere/x")).toEqual({ page: "overview", item: null })
    expect(parseRoute("")).toEqual({ page: "overview", item: null })
  })

  it("writes items so they read back", () => {
    const route = { page: "holdings" as const, item: "VWCE.DE" }
    expect(parseRoute(routeHash(route))).toEqual(route)
  })
})
