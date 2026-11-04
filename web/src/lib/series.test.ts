import { readFileSync, existsSync } from "node:fs"
import { resolve } from "node:path"
import { describe, expect, it } from "vitest"
import { change, cutDate, windowed } from "./series"
import type { Model, Point } from "./types"

const line: Point[] = [
  ["2025-11-03", 100],
  ["2025-12-31", 104],
  ["2026-08-05", 110],
  ["2026-10-05", 120],
  ["2026-11-03", 126],
]

describe("windows", () => {
  it("cut where performance.py cuts its period figures", () => {
    expect(cutDate("2026-11-03", "1M")).toBe("2026-10-04")
    expect(cutDate("2026-11-03", "3M")).toBe("2026-08-04")
    expect(cutDate("2026-11-03", "YTD")).toBe("2025-12-31")
    expect(cutDate("2026-11-03", "1Y")).toBe("2025-11-03")
  })

  it("start from the last point at or before the cut, rebased to 100", () => {
    const ytd = windowed(line, "YTD")
    expect(ytd[0]).toEqual(["2025-12-31", 100])
    expect(change(ytd)).toBeCloseTo(126 / 104 - 1, 10)
    expect(change(windowed(line, "1M"))).toBeCloseTo(126 / 110 - 1, 10)
    expect(windowed(line.slice(0, 1), "1Y")).toEqual([])
  })

  // The demo's own numbers: the line for each window must end where Python's period figure says.
  const demo = resolve(import.meta.dirname, "../../../demo/out/dashboard.json")
  it.skipIf(!existsSync(demo))("end where the demo's period figures say", () => {
    const model = JSON.parse(readFileSync(demo, "utf8")) as Model
    const lines = model.performance.lines
    for (const [name, key] of [["portfolio", "portfolio"], ["world", "world"]] as const) {
      const points = lines[name] ?? []
      for (const w of ["1M", "3M", "YTD", "1Y"] as const) {
        const want = model.performance.returns[key]?.[w]
        if (want === null || want === undefined) continue
        expect(change(windowed(points, w))).toBeCloseTo(want, 3)
      }
    }
  })
})
