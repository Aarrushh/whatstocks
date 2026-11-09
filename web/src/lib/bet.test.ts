import { existsSync, readFileSync } from "node:fs"
import { resolve } from "node:path"
import { describe, expect, it } from "vitest"
import {
  allOn,
  capexKey,
  capexOn,
  clockNow,
  curves,
  defaultSettings,
  defaultSwitches,
  demandKey,
  figure,
  implied,
  inUnits,
  lifeKey,
  niceTicks,
  onlyThis,
  quarterPosition,
  readouts,
  scaled,
  stepLabel,
  stepText,
  switchSizes,
  toggle,
  usdB,
  type Settings,
  type Switches,
} from "./bet"
import { PAGES } from "./hooks"
import type { Bet, BetBand, BetReadout, BetSeries, Model } from "./types"

/** A piece's series and readouts the way Python writes them, over four quarters with the deadline at the last. */
function piece(rate: number[], spread = 0.5): BetSeries & { readouts: BetBand<BetReadout> } {
  const band = (xs: number[]): BetReadout => ({
    last4: (xs[0] + xs[1]) / 2,
    at_deadline: xs[3],
    to_deadline: xs.reduce((a, b) => a + b, 0) / 4,
  })
  const low = rate.map((x) => x * (1 - spread))
  const high = rate.map((x) => x * (1 + spread))
  return { rate, low, high, readouts: { rate: band(rate), low: band(low), high: band(high) } }
}

const demandPiece = (rate: number[]) => {
  const p = piece(rate, 0.25)
  return { rate: p.rate, low: p.low, high: p.high, readouts: { "5": p.readouts } }
}

const FIXTURE = {
  date: "2023-08-01",
  quarters: ["2023Q1", "2023Q2", "2023Q3", "2023Q4"],
  last_actual: 1,
  deadlines: { "5": { quarter: 3, band: [2, 3], date: "2023-12-31" } },
  sliders: {
    gpu_life: { label: "GPU useful life", unit: "years", steps: [5], default: 5 },
    cost_of_capital: { label: "Cost of capital", unit: "pct", steps: [8], default: 8 },
    deflation: { label: "Price deflation", unit: "pct_per_year", steps: ["trailing", -20], default: "trailing" },
    value_capture: { label: "Value capture", unit: "pct", steps: [2.2, 10], default: 2.2 },
    labour_share: { label: "Budget split, labour share", unit: "pct", steps: [0, 50], default: 50 },
  },
  compute_share: 0.58,
  capex: {
    pieces: [
      { id: "a.depreciation", group: "a", part: "depreciation", label: "A depreciation", on: true, grades: {} },
      { id: "a.return", group: "a", part: "return", label: "A return", on: true, grades: {} },
      { id: "b.depreciation", group: "b", part: "depreciation", label: "B depreciation", on: false, grades: {} },
      { id: "b.return", group: "b", part: "return", label: "B return", on: false, grades: {} },
    ],
    grid: {
      "5|8": {
        "a.depreciation": piece([10, 20, 30, 40]),
        "a.return": piece([5, 5, 10, 10]),
        "b.depreciation": piece([100, 100, 100, 100]),
        "b.return": piece([1, 1, 1, 1]),
      },
    },
  },
  valuation: {
    groups: {
      chips: { label: "Chips", on: true, worth: 1, low: 1, high: 1 },
      labs: { label: "Labs", on: true, worth: 1, low: 1, high: 1 },
    },
    grid: { "5|8": { chips: { target: 100, low: 50, high: 200 }, labs: { target: 60, low: 30, high: 120 } } },
  },
  demand: {
    pieces: [
      { id: "vc", label: "VC-funded", tier: 4, on: true, grades: {} },
      { id: "direct", label: "Direct", tier: 1, on: true, grades: {} },
      { id: "free", label: "Free users", tier: null, on: false, grades: {} },
    ],
    grid: {
      trailing: { deflation: -0.4, pieces: { direct: demandPiece([4, 6, 40, 80]), vc: demandPiece([1, 1, 4, 8]), free: demandPiece([2, 2, 2, 2]) } },
      "-20": { deflation: -0.2, pieces: { direct: demandPiece([4, 6, 60, 120]), vc: demandPiece([1, 1, 6, 12]), free: demandPiece([2, 2, 2, 2]) } },
    },
  },
  units: {
    seat: null,
    seats: 2,
    gain: { "2.2": 45.454545, "10": 10 },
    hours: {
      "2.2": { rate: [0.01, 0.01, 0.02, 0.02], low: [0.005, 0.005, 0.01, 0.01], high: [0.02, 0.02, 0.04, 0.04] },
      "10": { rate: [0.002, 0.002, 0.004, 0.004], low: [0.001, 0.001, 0.002, 0.002], high: [0.004, 0.004, 0.008, 0.008] },
    },
    pool: { "0": [null, null, 1000, 1000], "50": [5000, 5000, 6000, 6000] },
    hour_uplift: 25,
    inputs: { years: [2023], it: [null], labour: [60] },
  },
  clock: { from: "2023-01-01", date: "2023-06-30", capex_out: 10, demand_in: 2, capex_per_second: 1e-6, demand_per_second: 1e-7 },
} as unknown as Bet

const S: Settings = defaultSettings(FIXTURE)

describe("the switches", () => {
  it("start where Python sets them, a group or part on when any of its pieces is", () => {
    const sw = defaultSwitches(FIXTURE)
    expect(sw).toEqual({
      capex: { a: true, b: false },
      parts: { depreciation: true, return: true },
      valuation: { chips: true, labs: true },
      demand: { vc: true, direct: true, free: false },
    })
    expect(capexOn(FIXTURE, sw)).toEqual(["a.depreciation", "a.return"])
  })

  it("switch one, only one in its group, or all", () => {
    const sw = defaultSwitches(FIXTURE)
    expect(toggle(sw, "capex", "b").capex).toEqual({ a: true, b: true })
    const only = onlyThis(sw, "parts", "return")
    expect(only.parts).toEqual({ depreciation: false, return: true })
    expect(only.capex).toEqual(sw.capex) // the other groups stay as they are
    expect(capexOn(FIXTURE, only)).toEqual(["a.return"])
    expect(capexOn(FIXTURE, allOn(FIXTURE))).toHaveLength(4)
  })
})

describe("the sums", () => {
  it("add the switched-on pieces quarter by quarter, best tier at the bottom", () => {
    const c = curves(FIXTURE, S, defaultSwitches(FIXTURE))
    expect(c.need.rate).toEqual([15, 25, 40, 50])
    expect(c.layers.map((l) => l.id)).toEqual(["direct", "vc"])
    expect(c.demand.rate).toEqual([5, 7, 44, 88])
    expect(c.target).toEqual({ rate: 160, low: 80, high: 320 })
    expect(c.deadline.quarter).toBe(3)
    // Another deflation step picks another grid cell.
    expect(curves(FIXTURE, { ...S, deflation: -20 }, defaultSwitches(FIXTURE)).demand.rate).toEqual([5, 7, 66, 132])
  })

  it("divide two sums for each readout, the range from the opposite ends", () => {
    const r = readouts(FIXTURE, S, defaultSwitches(FIXTURE))
    // Coverage: demand's last four quarters over the need's.
    expect(r.coverage.mid).toBeCloseTo(6 / 20, 10)
    expect(r.coverage.low).toBeCloseTo((6 * 0.75) / (20 * 1.5), 10)
    expect(r.coverage.high).toBeCloseTo((6 * 1.25) / (20 * 0.5), 10)
    // Payback: each added up to the deadline.
    expect(r.payback.mid).toBeCloseTo(144 / 4 / (130 / 4), 10)
    // Valuation: projected demand at the deadline over the target.
    expect(r.valuation.mid).toBeCloseTo(88 / 160, 10)
    expect(r.valuation.low).toBeCloseTo((88 * 0.75) / 320, 10)
  })

  it("show nothing rather than divide by zero", () => {
    const sw: Switches = { ...defaultSwitches(FIXTURE), parts: { depreciation: false, return: false }, valuation: { chips: false, labs: false } }
    const r = readouts(FIXTURE, S, sw)
    expect(r.coverage).toEqual({ mid: null, low: null, high: null })
    expect(r.valuation).toEqual({ mid: null, low: null, high: null })
    expect(curves(FIXTURE, S, sw).target).toBeNull()
  })

  it("size each switch at the deadline", () => {
    const sizes = switchSizes(FIXTURE, S, defaultSwitches(FIXTURE))
    expect(sizes.capex).toEqual({ a: 50, b: 101 }) // what B would add with both parts on
    expect(sizes.parts).toEqual({ depreciation: 40, return: 10 }) // across the groups that are on
    expect(sizes.valuation).toEqual({ chips: 100, labs: 60 })
    expect(sizes.demand).toEqual({ vc: 8, direct: 80, free: 2 })
  })
})

describe("the units", () => {
  it("scale each quarter by Python's factor", () => {
    const close = (got: (number | null)[], want: number[]) => {
      expect(got).toHaveLength(want.length)
      want.forEach((w, i) => expect(got[i]).toBeCloseTo(w, 10))
    }
    close(scaled(FIXTURE, "usd", S, [10, 20, 30, 40]), [10, 20, 30, 40])
    close(scaled(FIXTURE, "seats", S, [10, 20, 30, 40]), [20, 40, 60, 80])
    close(scaled(FIXTURE, "hours", S, [10, 20, 30, 40]), [0.1, 0.2, 0.6, 0.8])
    close(scaled(FIXTURE, "hours", { ...S, value_capture: 10 }, [10, 20, 30, 40], "high"), [0.04, 0.08, 0.24, 0.32])
  })

  it("work out what a need implies, and nothing where the pool has no figure", () => {
    const now = implied(FIXTURE, S, 100, 1)
    expect(now.gain).toBeCloseTo(4545.4545, 3)
    expect(now.hours).toBeCloseTo(1, 10)
    expect(now.pool).toBeCloseTo(0.02, 10)
    expect(implied(FIXTURE, { ...S, labour_share: 0 }, 100, 1).pool).toBeNull()
  })
})

describe("the cash clock", () => {
  it("adds each rate a second to Python's totals from the end of their date", () => {
    const end = Date.parse("2023-07-01T00:00:00Z")
    expect(clockNow(FIXTURE.clock, end)).toEqual({ capex: 10, demand: 2 })
    const later = clockNow(FIXTURE.clock, end + 1_000_000 * 1000)
    expect(later.capex).toBeCloseTo(11, 10)
    expect(later.demand).toBeCloseTo(2.1, 10)
    expect(clockNow(FIXTURE.clock, end - 5_000_000)).toEqual({ capex: 10, demand: 2 }) // never runs backwards
  })
})

describe("words and axes", () => {
  it("write money, figures and units", () => {
    expect(usdB(2535.693)).toBe("$2.54T")
    expect(usdB(502.4)).toBe("$502B")
    expect(usdB(60.115)).toBe("$60.1B")
    expect(usdB(0.45)).toBe("$450M")
    expect(usdB(-34.837)).toBe("−$34.8B")
    expect(usdB(0)).toBe("$0")
    expect(usdB(-0.0001)).toBe("$0")
    expect(figure(325.45, "bp")).toBe("325 bp")
    expect(figure(-28.8881, "pct")).toBe("−28.9%")
    expect(figure(1, "quarters in a row")).toBe("1 quarter in a row")
    expect(figure(1602.4, "count")).toBe("1,602")
    expect(figure(2000, "count_m")).toBe("2.00B")
    expect(figure(50, "count_m")).toBe("50.0M")
    expect(figure(5, "years")).toBe("5 years")
    expect(figure(5.5, "years")).toBe("5.50 years")
    expect(figure(3, "")).toBe("3")
    expect(inUnits(1.9, "hours")).toBe("190%")
    expect(inUnits(1552, "seats")).toBe("1.55B seats")
  })

  it("label slider steps", () => {
    expect(stepLabel("deflation", -20)).toBe("−20%")
    expect(stepLabel("value_capture", 2.2)).toBe("2.2%")
    expect(stepLabel("gpu_life", 5)).toBe("5y")
    expect(stepText("deflation", "trailing", -0.4358)).toBe("Trailing (−44% a year)")
    expect(stepText("cost_of_capital", 8)).toBe("8%")
  })

  it("pick round ticks and place dates between quarters", () => {
    expect(niceTicks(2600)).toEqual([0, 1000, 2000, 3000])
    expect(niceTicks(594)).toEqual([0, 200, 400, 600])
    expect(quarterPosition(FIXTURE, "2023-01-01")).toBe(0)
    expect(quarterPosition(FIXTURE, "2023-04-01")).toBe(1)
    expect(quarterPosition(FIXTURE, "2024-02-15")).toBeCloseTo(4 + 45 / 91, 10)
  })
})

describe("the page", () => {
  it("is the eighth, on key 8", () => {
    expect(PAGES.findIndex((p) => p.id === "bet")).toBe(7)
    expect(PAGES[7].label).toBe("The bet")
  })
})

// The demo's own numbers: the page's sums must equal what Python precomputed.
const demo = resolve(import.meta.dirname, "../../../demo/out/dashboard.json")
describe.skipIf(!existsSync(demo))("the demo", () => {
  const bet = existsSync(demo) ? ((JSON.parse(readFileSync(demo, "utf8")) as Model).bet as Bet) : FIXTURE
  const near = (a: number | null, b: number, tol = 0.1) =>
    expect(Math.abs((a ?? NaN) - b)).toBeLessThanOrEqual(Math.max(tol, 1e-4 * Math.abs(b)))

  it("has every grid cell the sliders can pick", () => {
    const sl = bet.sliders
    for (const life of sl.gpu_life.steps) {
      expect(bet.deadlines[String(life)]).toBeTruthy()
      for (const wacc of sl.cost_of_capital.steps) {
        const s = { ...defaultSettings(bet), gpu_life: life, cost_of_capital: wacc }
        expect(bet.capex.grid[capexKey(s)]).toBeTruthy()
        expect(bet.valuation.grid[capexKey(s)]).toBeTruthy()
      }
    }
    for (const step of sl.deflation.steps) {
      const s = { ...defaultSettings(bet), deflation: step }
      for (const life of sl.gpu_life.steps) {
        for (const id of Object.keys(bet.demand.grid[demandKey(s)].pieces)) {
          expect(bet.demand.grid[demandKey(s)].pieces[id].readouts[lifeKey({ ...s, gpu_life: life })]).toBeTruthy()
        }
      }
    }
    for (const vc of sl.value_capture.steps) expect(bet.units.hours[String(vc)] && bet.units.gain[String(vc)]).toBeTruthy()
    for (const w of sl.labour_share.steps) expect(bet.units.pool[String(w)]).toBeTruthy()
  })

  it("switches each capex piece on exactly where Python does", () => {
    const sw = defaultSwitches(bet)
    for (const p of bet.capex.pieces) expect(!!(sw.capex[p.group] && sw.parts[p.part])).toBe(p.on)
  })

  it("reads coverage now and payback as the regime's indicators do, at your default settings", () => {
    const r = readouts(bet, defaultSettings(bet), defaultSwitches(bet))
    const ind = bet.signals.indicators
    near((r.coverage.mid ?? NaN) * 100, ind.coverage_now.reading ?? NaN, 0.01)
    near((r.payback.mid ?? NaN) * 100, ind.payback.reading ?? NaN, 0.01)
  })

  it("adds the series to the same readouts Python precomputed, for sample sets of switches", () => {
    const base = defaultSwitches(bet)
    const sets: Switches[] = [
      base,
      allOn(bet),
      onlyThis(base, "capex", "hyperscalers"),
      onlyThis(base, "parts", "depreciation"),
      onlyThis(onlyThis(base, "demand", "direct"), "capex", "oracle"),
    ]
    const la = bet.last_actual
    const other: Settings = { ...defaultSettings(bet), gpu_life: 3, cost_of_capital: 12, deflation: -40 }
    for (const sw of sets) {
      for (const s of [defaultSettings(bet), other]) {
        const c = curves(bet, s, sw)
        const r = readouts(bet, s, sw)
        const dl = c.deadline.quarter
        for (const [series, sums] of [
          [c.need, r.need],
          [c.demand, r.demand],
        ] as const) {
          for (const end of ["rate", "low", "high"] as const) {
            const xs = series[end]
            near(xs.slice(la - 3, la + 1).reduce((a, b) => a + b, 0) / 4, sums[end].last4)
            near(xs[dl], sums[end].at_deadline)
            near(xs.slice(0, dl + 1).reduce((a, b) => a + b, 0) / 4, sums[end].to_deadline)
          }
        }
      }
    }
  })

  it("starts the clock at Python's totals", () => {
    const end = Date.parse(`${bet.clock.date}T00:00:00Z`) + 86_400_000
    expect(clockNow(bet.clock, end)).toEqual({ capex: bet.clock.capex_out, demand: bet.clock.demand_in })
  })
})
