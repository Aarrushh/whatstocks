/** "Will the bet pay off?": the page's only arithmetic (docs/SPEC.md, P2 exception b; the bet spec, section 7).
 * Python works out every piece of both models for every slider step, and the unit factors. The page picks the grid
 * cell for the sliders, adds up the pieces you switch on, scales the sums by Python's factors, and divides two sums
 * for each readout. It never makes up a figure. */
import { DASH, pct, plural } from "./format"
import type { Bet, BetBand, BetReadout, BetSeries } from "./types"

const MINUS = "−"

export type Deflation = number | "trailing"

export interface Settings {
  gpu_life: number
  cost_of_capital: number
  deflation: Deflation
  value_capture: number
  labour_share: number
}
export type SliderId = keyof Settings

/** Which switches are on, by id, in each group. A capex piece counts when both its group and its part are on. */
export interface Switches {
  capex: Record<string, boolean>
  parts: Record<string, boolean>
  valuation: Record<string, boolean>
  demand: Record<string, boolean>
}
export type SwitchGroup = keyof Switches

/** Dollars a year, paying-seat equivalents, or the share of work hours that must use AI (spec 6). */
export type Units = "usd" | "seats" | "hours"

export const capexKey = (s: Settings) => `${s.gpu_life}|${s.cost_of_capital}`
export const demandKey = (s: Settings) => String(s.deflation)
export const lifeKey = (s: Settings) => String(s.gpu_life)

const unique = (xs: string[]) => [...new Set(xs)]
export const capexGroups = (bet: Bet) => unique(bet.capex.pieces.map((p) => p.group))
export const capexParts = (bet: Bet) => unique(bet.capex.pieces.map((p) => p.part))

export function defaultSettings(bet: Bet): Settings {
  const s = bet.sliders
  return {
    gpu_life: s.gpu_life.default,
    cost_of_capital: s.cost_of_capital.default,
    deflation: s.deflation.default,
    value_capture: s.value_capture.default,
    labour_share: s.labour_share.default,
  }
}

/** The switches as Python sets them: a group or part is on when any of its pieces is on by default. */
export function defaultSwitches(bet: Bet): Switches {
  const pieces = bet.capex.pieces
  return {
    capex: Object.fromEntries(capexGroups(bet).map((g) => [g, pieces.some((p) => p.group === g && p.on)])),
    parts: Object.fromEntries(capexParts(bet).map((k) => [k, pieces.some((p) => p.part === k && p.on)])),
    valuation: Object.fromEntries(Object.entries(bet.valuation.groups).map(([id, g]) => [id, g.on])),
    demand: Object.fromEntries(bet.demand.pieces.map((p) => [p.id, p.on])),
  }
}

export function allOn(bet: Bet): Switches {
  const on = (ids: string[]) => Object.fromEntries(ids.map((id) => [id, true]))
  return {
    capex: on(capexGroups(bet)),
    parts: on(capexParts(bet)),
    valuation: on(Object.keys(bet.valuation.groups)),
    demand: on(bet.demand.pieces.map((p) => p.id)),
  }
}

export function toggle(sw: Switches, group: SwitchGroup, id: string): Switches {
  return { ...sw, [group]: { ...sw[group], [id]: !sw[group][id] } }
}

/** "Only this": this switch on and the others in its group off. The other groups stay as they are. */
export function onlyThis(sw: Switches, group: SwitchGroup, id: string): Switches {
  return { ...sw, [group]: Object.fromEntries(Object.keys(sw[group]).map((k) => [k, k === id])) }
}

export const sameSwitches = (a: Switches, b: Switches) =>
  (Object.keys(a) as SwitchGroup[]).every((g) => Object.keys(a[g]).every((id) => !!a[g][id] === !!b[g][id]))

export const capexOn = (bet: Bet, sw: Switches) =>
  bet.capex.pieces.filter((p) => sw.capex[p.group] && sw.parts[p.part]).map((p) => p.id)
export const demandOn = (bet: Bet, sw: Switches) => bet.demand.pieces.filter((p) => sw.demand[p.id]).map((p) => p.id)
export const valuationOn = (bet: Bet, sw: Switches) => Object.keys(bet.valuation.groups).filter((id) => sw.valuation[id])

const ENDS = ["rate", "low", "high"] as const

/** Quarter by quarter, the sum of some pieces' rates and of their low and high ends. */
export function sumSeries(series: BetSeries[], n: number): BetSeries {
  const out: BetSeries = { rate: new Array(n).fill(0), low: new Array(n).fill(0), high: new Array(n).fill(0) }
  for (const s of series) for (const end of ENDS) for (let i = 0; i < n; i++) out[end][i] += s[end][i] ?? 0
  return out
}

const READOUTS = ["last4", "at_deadline", "to_deadline"] as const

export function sumReadouts(rs: BetBand<BetReadout>[]): BetBand<BetReadout> {
  const zero = (): BetReadout => ({ last4: 0, at_deadline: 0, to_deadline: 0 })
  const out: BetBand<BetReadout> = { rate: zero(), low: zero(), high: zero() }
  for (const r of rs) for (const end of ENDS) for (const k of READOUTS) out[end][k] += r[end][k]
  return out
}

export interface Target {
  rate: number
  low: number
  high: number
}

/** The curves the hero draws, in $B a year: the need, each switched-on demand piece (best tier first) and their sum,
 * and the valuation target at the deadline. */
export interface Curves {
  need: BetSeries
  layers: { id: string; label: string; tier: number | null; series: BetSeries }[]
  demand: BetSeries
  target: Target | null
  deadline: { quarter: number; band: [number, number]; date: string }
}

export function curves(bet: Bet, s: Settings, sw: Switches): Curves {
  const n = bet.quarters.length
  const cell = bet.capex.grid[capexKey(s)] ?? {}
  const step = bet.demand.grid[demandKey(s)]?.pieces ?? {}
  const need = sumSeries(capexOn(bet, sw).flatMap((id) => (cell[id] ? [cell[id]] : [])), n)
  const layers = bet.demand.pieces
    .filter((p) => sw.demand[p.id] && step[p.id])
    .sort((a, b) => (a.tier ?? 99) - (b.tier ?? 99))
    .map((p) => ({ id: p.id, label: p.label, tier: p.tier, series: step[p.id] }))
  const vals = valuationOn(bet, sw)
  return {
    need,
    layers,
    demand: sumSeries(layers.map((l) => l.series), n),
    target: vals.length ? valuationTarget(bet, s, vals) : null,
    deadline: bet.deadlines[lifeKey(s)],
  }
}

function valuationTarget(bet: Bet, s: Settings, ids: string[]): Target {
  const cell = bet.valuation.grid[capexKey(s)] ?? {}
  return ids.reduce<Target>(
    (t, id) => (cell[id] ? { rate: t.rate + cell[id].target, low: t.low + cell[id].low, high: t.high + cell[id].high } : t),
    { rate: 0, low: 0, high: 0 },
  )
}

/** A readout and its range: the low end divides the low demand by the high need, and the high end the reverse. */
export interface Ratio {
  mid: number | null
  low: number | null
  high: number | null
}

export const ratio = (a: number, b: number): number | null => (b > 0 ? a / b : null)

export interface Readouts {
  need: BetBand<BetReadout>
  demand: BetBand<BetReadout>
  target: Target | null
  /** Actual ÷ need over the last four quarters. */
  coverage: Ratio
  /** Actual ÷ need, each added up from 2023 to the deadline. 100% is break-even at the cost of capital. */
  payback: Ratio
  /** Projected actual at the deadline ÷ the revenue today's valuations need then. */
  valuation: Ratio
}

export function readouts(bet: Bet, s: Settings, sw: Switches): Readouts {
  const cell = bet.capex.grid[capexKey(s)] ?? {}
  const step = bet.demand.grid[demandKey(s)]?.pieces ?? {}
  const life = lifeKey(s)
  const need = sumReadouts(capexOn(bet, sw).flatMap((id) => (cell[id] ? [cell[id].readouts] : [])))
  const demand = sumReadouts(demandOn(bet, sw).flatMap((id) => (step[id]?.readouts[life] ? [step[id].readouts[life]] : [])))
  const vals = valuationOn(bet, sw)
  const target = vals.length ? valuationTarget(bet, s, vals) : null
  const band = (k: (typeof READOUTS)[number]): Ratio => ({
    mid: ratio(demand.rate[k], need.rate[k]),
    low: ratio(demand.low[k], need.high[k]),
    high: ratio(demand.high[k], need.low[k]),
  })
  return {
    need,
    demand,
    target,
    coverage: band("last4"),
    payback: band("to_deadline"),
    valuation: target
      ? {
          mid: ratio(demand.rate.at_deadline, target.rate),
          low: ratio(demand.low.at_deadline, target.high),
          high: ratio(demand.high.at_deadline, target.low),
        }
      : { mid: null, low: null, high: null },
  }
}

/** The size each switch adds at the deadline, in $B a year: a capex group across the parts that are on, a part
 * across the groups that are on, a valuation group's target, and a demand piece's rate. */
export function switchSizes(bet: Bet, s: Settings, sw: Switches): Record<SwitchGroup, Record<string, number>> {
  const cell = bet.capex.grid[capexKey(s)] ?? {}
  const step = bet.demand.grid[demandKey(s)]?.pieces ?? {}
  const vcell = bet.valuation.grid[capexKey(s)] ?? {}
  const life = lifeKey(s)
  const at = (id: string) => cell[id]?.readouts.rate.at_deadline ?? 0
  const sizes: Record<SwitchGroup, Record<string, number>> = { capex: {}, parts: {}, valuation: {}, demand: {} }
  for (const p of bet.capex.pieces) {
    sizes.capex[p.group] = (sizes.capex[p.group] ?? 0) + (sw.parts[p.part] ? at(p.id) : 0)
    sizes.parts[p.part] = (sizes.parts[p.part] ?? 0) + (sw.capex[p.group] ? at(p.id) : 0)
  }
  for (const id of Object.keys(bet.valuation.groups)) sizes.valuation[id] = vcell[id]?.target ?? 0
  for (const p of bet.demand.pieces) sizes.demand[p.id] = step[p.id]?.readouts[life]?.rate.at_deadline ?? 0
  return sizes
}

/** The factor that turns $B a year in quarter q into the unit shown; null where Python has none. */
export function unitFactor(bet: Bet, units: Units, s: Settings, q: number, end: keyof BetBand<unknown> = "rate"): number | null {
  if (units === "usd") return 1
  if (units === "seats") return bet.units.seats
  return bet.units.hours[String(s.value_capture)]?.[end][q] ?? null
}

export function scaled(bet: Bet, units: Units, s: Settings, values: number[], end: keyof BetBand<unknown> = "rate"): (number | null)[] {
  return values.map((v, q) => {
    const f = unitFactor(bet, units, s, q, end)
    return f === null ? null : v * f
  })
}

/** What a need of so many $B a year implies in quarter q (spec 6): the productivity gain at the value-capture
 * share ($B a year), the share of work hours that must use AI, and its share of the budget pool. */
export interface Implied {
  gain: number | null
  hours: number | null
  pool: number | null
}

export function implied(bet: Bet, s: Settings, need: number, q: number): Implied {
  const gain = bet.units.gain[String(s.value_capture)]
  const hours = bet.units.hours[String(s.value_capture)]?.rate[q]
  const pool = bet.units.pool[String(s.labour_share)]?.[q]
  return {
    gain: gain === undefined ? null : need * gain,
    hours: hours === null || hours === undefined ? null : need * hours,
    pool: pool ? need / pool : null,
  }
}

/** The cash clock now: Python's totals at the end of its date, plus each rate a second times the seconds since. */
export function clockNow(clock: Bet["clock"], now: number): { capex: number; demand: number } {
  const from = Date.parse(`${clock.date}T00:00:00Z`) + 86_400_000
  const seconds = Math.max(0, (now - from) / 1000)
  return { capex: clock.capex_out + clock.capex_per_second * seconds, demand: clock.demand_in + clock.demand_per_second * seconds }
}

export const SECONDS_A_YEAR = 365.25 * 86_400

/** Where a date falls on the quarter axis: 0 is the start of the first quarter, 1 the start of the second. */
export function quarterPosition(bet: Bet, iso: string): number {
  const [y, m, d] = iso.slice(0, 10).split("-").map(Number)
  const first = Number(bet.quarters[0]?.slice(0, 4))
  const q0 = Math.floor((m - 1) / 3)
  const start = Date.UTC(y, q0 * 3, 1)
  const end = Date.UTC(y, q0 * 3 + 3, 1)
  return (y - first) * 4 + q0 + (Date.UTC(y, m - 1, d) - start) / (end - start)
}

/* Words for numbers. Figures in a "pct" unit are already in percent; shares and readouts are fractions. */

function fixed(x: number, digits: number): string {
  const text = Math.abs(x).toLocaleString("en-US", { minimumFractionDigits: digits, maximumFractionDigits: digits })
  return x < 0 && Number(text.replace(/,/g, "")) !== 0 ? `${MINUS}${text}` : text
}

/** Three significant figures or so, with a true minus sign: 1,234, 123, 12.3, 1.23. */
export function num(x: number | null | undefined, digits?: number): string {
  if (x === null || x === undefined || Number.isNaN(x)) return DASH
  const a = Math.abs(x)
  return fixed(x, digits ?? (a >= 100 ? 0 : a >= 10 ? 1 : 2))
}

/** $B as money words: $2.54T, $502B, $60.1B, $1.84B, $450M. */
export function usdB(x: number | null | undefined): string {
  if (x === null || x === undefined || Number.isNaN(x)) return DASH
  const a = Math.abs(x)
  if (a * 1000 < 0.5) return "$0" // nothing, not "$0M" or "−$0M"
  const sign = x < 0 ? MINUS : ""
  if (a >= 1000) return `${sign}$${fixed(a / 1000, a >= 100_000 ? 0 : a >= 10_000 ? 1 : 2)}T`
  if (a >= 1) return `${sign}$${fixed(a, a >= 100 ? 0 : a >= 10 ? 1 : 2)}B`
  return `${sign}$${fixed(a * 1000, 0)}M`
}

/** A whole number without decimals (5 years, 3), anything else as num writes it. */
const whole = (x: number) => (Number.isInteger(x) ? num(x, 0) : num(x))

/** A ledger figure in its unit. */
export function figure(x: number | null | undefined, unit: string): string {
  if (x === null || x === undefined || Number.isNaN(x)) return DASH
  switch (unit) {
    case "usd_b":
      return usdB(x)
    case "usd_t":
      return usdB(x * 1000)
    case "pct":
      return `${num(x)}%`
    case "pct_per_year":
      return `${num(x)}% a year`
    case "points":
      return `${num(x)} pts`
    case "bp":
      return `${num(x, 0)} bp`
    case "count_m":
      return Math.abs(x) >= 1000 ? `${num(x / 1000)}B` : `${num(x)}M`
    case "count":
      return num(x, 0)
    case "tokens_t":
      return `${num(x)}T tokens`
    case "tokens_b":
      return `${num(x)}B tokens`
    case "twd_b":
      return `NT$${num(x)}B`
    case "shares_b":
      return `${num(x)}B shares`
    case "usd_per_gpu_hour":
      return `$${fixed(x, 2)} a GPU-hour`
    case "usd_per_mtok":
      return `$${fixed(x, 2)} per M tokens`
    case "usd_per_mbps_month":
      return `$${num(x)} per Mbps a month`
    case "years":
      return `${whole(x)} years`
    case "companies":
      return plural(Math.round(x), "company", "companies")
    case "quarters in a row":
      return plural(Math.round(x), "quarter") + " in a row"
    case "readings in a row":
      return plural(Math.round(x), "reading") + " in a row"
    default:
      return whole(x)
  }
}

/** A curve's value in the unit shown: dollars a year, paying-seat equivalents, or a share of work hours. */
export function inUnits(x: number | null | undefined, units: Units): string {
  if (x === null || x === undefined || Number.isNaN(x)) return DASH
  if (units === "usd") return usdB(x)
  if (units === "seats") return Math.abs(x) >= 1000 ? `${fixed(x / 1000, 2)}B seats` : `${num(x)}M seats`
  return pct(x, 0)
}

export const UNIT_WORDS: Record<Units, string> = {
  usd: "$ a year",
  seats: "paying-seat equivalents",
  hours: "share of work hours",
}

/** A ratio readout with its range: 18% (14–26%). */
export function ratioText(r: Ratio): string {
  if (r.mid === null) return DASH
  return r.low === null || r.high === null ? pct(r.mid, 0) : `${pct(r.mid, 0)} (${pct(r.low, 0)}${DASH}${pct(r.high, 0)})`
}

/** Round numbers for an axis from zero to at least `max`: steps of 1, 2, 2.5 or 5 times a power of ten. */
export function niceTicks(max: number, count = 4): number[] {
  if (!(max > 0)) return [0, 1]
  const raw = max / count
  const power = 10 ** Math.floor(Math.log10(raw))
  const step = [1, 2, 2.5, 5, 10].map((m) => m * power).find((s) => s >= raw) ?? 10 * power
  const ticks: number[] = []
  for (let v = 0; v < max + step * 0.999; v += step) ticks.push(Number(v.toPrecision(12)))
  return ticks
}

export const STATE_WORD = { clear: "Clear", amber: "Amber", red: "Red", no_data: "No data" } as const
export const REGIME_STATE = { absorbing: "clear", straining: "amber", breaking: "red" } as const

/** A slider step in words: 5 years, 8%, Trailing (−44% a year), −20% a year. */
export function stepText(id: SliderId, step: number | string, trailing?: number): string {
  if (id === "gpu_life") return `${step} years`
  if (id === "deflation") {
    if (step === "trailing") return trailing === undefined ? "Trailing" : `Trailing (${pct(trailing, 0).replace("-", MINUS)} a year)`
    return `${num(Number(step), 0)}% a year`
  }
  return `${step}%`
}

/** The short label on a slider's segmented control. */
export function stepLabel(id: SliderId, step: number | string): string {
  if (id === "gpu_life") return `${step}y`
  if (step === "trailing") return "Trailing"
  return `${num(Number(step), Number(step) % 1 ? 1 : 0)}%`
}
