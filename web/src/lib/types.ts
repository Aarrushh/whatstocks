/** The view model that src/whatstocks/render.py puts into the page (version 4). Shares are fractions: 0.12 is 12%.
 * Every number here was computed in Python; the page only formats and draws it. The one place it adds and divides
 * is "Will the bet pay off?" (lib/bet.ts), where it sums the pieces you switch on (docs/SPEC.md, P2). */

export type Share = number
export type Period = "1D" | "1W" | "1M" | "3M" | "YTD" | "1Y"
export type Returns = Partial<Record<Period, number | null>>
export type Point = [string, number]
export type Effect = "hurt" | "help" | "mixed"
export type Strength = "low" | "medium" | "high"

export interface NewsItem {
  title: string
  source: string
  url: string | null
}

export interface BriefEvent {
  what: string
  money: string
  news_ids?: string[]
  touches?: { themes?: string[]; holdings?: string[] }
  views?: { view_id: string; effect: string; why?: string }[]
}

export interface Theme {
  id: string
  label: string
  proxy: string
  you: Share
  world: Share
  names_you: [string, Share][]
  names_world: [string, Share][]
  beta_you: number | null
  beta_world: number | null
  worst_weeks: { proxy?: number | null; you?: number | null; world?: number | null }
  heat: number
  proxy_returns: Returns
  weeks: [string, number][]
  blind: boolean
  brief: { state: string; why_it_matters: string; news_ids: string[] } | null
  views: { id: string; probability: number }[]
}

export interface Holding {
  symbol: string
  name: string
  kind: string
  weight: Share
  returns: Returns
  spark: number[]
  line: Point[]
  themes: Record<string, Share>
  countries: [string, Share][]
  inside: [string, Share][]
  note: { symbol: string; note: string; news_ids?: string[] } | null
  events: number[]
  top_themes: [string, Share][]
}

export interface WatchItem {
  n: number
  date: string | null
  what: string
  news_ids: string[]
  themes: string[]
  holdings: string[]
  record: boolean
}

export interface Evidence {
  for: number
  against: number
  unclear: number
}

export interface View {
  id: string
  statement: string
  probability: number
  created: string
  resolves_by: string
  days_left: number
  due: boolean
  forecasts: [string, number][]
  evidence: Record<"7" | "30", Evidence>
  themes: { id: string; label: string; direction: "up" | "down"; you: Share; world: Share }[]
  today: { what: string; effect: string; why: string; news_ids: string[] }[]
}

export interface Scores {
  views: { statement: string; result: string; brier: number | null }[]
  count: number
  mean: number | null
  luck: boolean
  coin_flip: number
}

export interface Decision {
  id: string
  date: string
  action: string
  symbol: string
  size_pct: number | null
  views: string[]
  reason: string
  review_on: string
  flags: string[]
}

export interface Review {
  action: string
  symbol: string
  date: string
  since: number | null
  world: number | null
}

export interface BlindSpot {
  id: string
  label: string
  events: number
  you: Share
  world: Share
  recent: string[]
}

export interface Ripples {
  w: number
  h: number
  nodes: { id: string; label: string; weight: Share; x: number; y: number; r: number; hub: boolean; side: string }[]
  edges: { d: string; from: string; to: string; effect: "hurt" | "help" | "unclear"; why: string; news_ids: string[] }[]
}

export interface Channel {
  kind: string
  id: string
  effect: Effect
  strength: Strength
  why: string
  label: string
  proxy: string | null
  you: Share
  world: Share
}

export interface ScanTotals {
  hurt_share: Share
  hurt_score: Share
  help_share: Share
  help_score: Share
  mixed_share: Share
  mixed_score: Share
}

export interface BubbleGroup {
  effect: Effect
  box: [number, number, number, number]
  bubbles: {
    index: number
    x: number
    y: number
    r: number
    ring: number
    inside: boolean
    beside: { x: number; y: number; anchor: "start" | "end" | "middle" } | null
  }[]
  listed: number[]
}

export interface Scan {
  slug: string
  conflict: string
  date: string
  exposure_date: string
  summary: string
  news_ids: string[]
  advice: boolean
  totals: { you: ScanTotals; world: ScanTotals }
  channels: Channel[]
  holdings: (ScanTotals & { symbol: string; name: string; weight: Share })[]
  analogs: { name: string; start: string; end: string; why: string; you: number | null; world: number | null; coverage: Share; proxies: Record<string, number | null> }[]
  watch: { what: string; news_ids?: string[] }[]
  news: Record<string, NewsItem>
  bubbles: BubbleGroup[]
  proxy_channels: string[]
}

export interface Model {
  version: number
  date: string
  home: string
  benchmark: string
  banners: string[]
  notes: string[]
  lead: { kind: "none" | "summary" | "quiet"; text: string }
  has_brief: boolean
  events: BriefEvent[]
  news: Record<string, NewsItem>
  theme_labels: Record<string, string>
  themes: Record<string, Theme>
  theme_order: string[]
  matter: string[]
  others: string[]
  blind_spots: BlindSpot[]
  news_heat: { dates: string[]; rows: { id: string; label: string; counts: number[] }[] }
  proxy_heat: { cols: string[]; rows: { id: string; label: string; proxy: string; cells: (number | null)[] }[] }
  holdings: Holding[]
  performance: {
    returns: { holdings?: Record<string, Returns>; portfolio?: Returns; world?: Returns }
    coverage: Share | null
    lines: { portfolio?: Point[]; world?: Point[] }
    world_weekly: Point[]
  }
  exposure: {
    beta_coverage: Share | null
    unresolved: Share
    sell_offs: { name: string; start: string; end: string; you: number | null; world: number | null; coverage: Share }[]
    countries: { you: Record<string, Share>; world: Record<string, Share> }
    currencies: [string, Share][]
    matrix: { cols: string[]; rows: { symbol: string; cells: Share[] }[]; total: Share[] }
  }
  views: View[]
  scores: Scores
  decisions: Decision[]
  reviews: Review[]
  watch: WatchItem[]
  ripples: Ripples | null
  scans: Scan[]
  /** "Will the bet pay off?"; null in an out/ folder from before the page existed. */
  bet: Bet | null
}

/* "Will the bet pay off?" (the bet block). Dollar figures are public companies' and AI labs', in $B a year unless
 * a unit says otherwise; a figure in a "pct" unit is in percent (12.5 is 12.5%), while a share is a fraction. */

export type BetState = "clear" | "amber" | "red" | "no_data"
export type BetGrade = "fetched" | "filed" | "company" | "press" | "estimate"
/** The share of a curve that rests on each grade of figure, as fractions that add to 1. Empty when it has no weight. */
export type GradeMix = Partial<Record<"filed" | "company" | "press" | "estimate", number>>

/** Three readouts of one piece, in $B: the mean rate of the last four actual quarters, the rate at the deadline,
 * and the total from 2023 to the deadline. */
export interface BetReadout {
  last4: number
  at_deadline: number
  to_deadline: number
}

export interface BetBand<T> {
  rate: T
  low: T
  high: T
}

/** A piece's quarterly rates ($B a year), one per quarter, with its low and high ends. */
export type BetSeries = BetBand<number[]>

export interface BetSlider<T extends number | string> {
  label: string
  unit: string
  steps: T[]
  default: T
}

export interface BetCapexPiece {
  id: string
  group: string
  part: string
  label: string
  on: boolean
  grades: GradeMix
}

export interface BetDemandPiece {
  id: string
  label: string
  tier: number | null
  on: boolean
  grades: GradeMix
}

export interface BetFeeds {
  curves: boolean
  indicators: string[]
  panels: string[]
}

/** One figure from the ledger. `word` is set for a rating or an event, which have no number. */
export interface BetFigure {
  figure: number | null
  low: number | null
  high: number | null
  period: string
  grade: BetGrade
  sources: string[]
  seen: string
  mine: boolean
  covers?: string
  word?: string
}

export interface BetIndicator {
  id: string
  label: string
  path: string
  rule: string
  trigger: boolean
  state: BetState
  reading: number | null
  unit: string
  text: string
  as_of: string | null
  amber: number | null
  red: number | null
  /** Which way is worse: up (a higher reading) or down; null for a rule that is not one threshold. */
  direction: "up" | "down" | null
  why: string
  mine: boolean
  ledger: string[]
  sources: string[]
}

export interface BetPath {
  id: string
  label: string
  kind: "crash" | "adoption"
  about: string
  state: BetState
  drivers: string[]
  counts: Record<BetState, number>
  themes: string[]
  view_links: Record<string, string>
}

export interface BetRelease {
  id: string
  name: string
  lab: string
  released: string
  source: string
  press: string | null
  /** Moves over the days after the release, as fractions; ai and hyperscalers are baskets, world the index. */
  market: { from: string; to: string; world: number | null; ai: number | null; hyperscalers: number | null } | null
  adoption: { series: string; entity: string; label: string; unit: string; change: Record<string, number | null> }[]
}

export interface BetMean {
  mean: number | null
  n: number
}

export interface BetAnalogLine {
  id: string
  label: string
  series: string
  unit: string
  indexed: boolean
  start: number | null
  /** [years since the start, figure]; indexed lines start at 100. */
  points: [number, number][]
  sources: string[]
}

export interface BetAnalog {
  label: string
  shows: string
  by: string
  start: number | null
  lines: BetAnalogLine[]
}

export interface BetMeasure {
  series: string
  entity: string
  label: string
  unit: string
  now: BetFigure | null
  before: BetFigure | null
  year_ago: BetFigure | null
}

export interface BetLeakage {
  id: string
  label: string
  /** The unit of both figures: the ledger check makes them share one. */
  unit: string
  /** of ÷ per, as a fraction. */
  ratio: number | null
  of: BetFigure | null
  per: BetFigure | null
  before: { ratio: number; period: string } | null
}

export interface BetRowEntity extends BetFigure {
  id: string
  label: string
  history: [string, number][]
}

export interface BetRow {
  id: string
  label: string
  unit: string
  about: string
  derived: boolean
  entities: BetRowEntity[]
}

export interface BetPillar {
  id: string
  label: string
  indicators: string[]
  rows: BetRow[]
  derived: BetRow[]
}

export interface BetSourceRow {
  id: string
  label: string
  unit: string
  cadence: string
  period: string
  entities: number
  points: number
  newest: (BetFigure & { entity: string; label: string }) | null
  due: { id: string; label: string; period: string; expected: string }[]
  closed: boolean
  fetcher: string | null
  feeds: BetFeeds
}

export interface BetGap {
  /** Null for a gap no series holds yet (a tier, a parameter, an analog). */
  series: string | null
  entity: string | null
  what: string
  /** The series' label. */
  label: string | null
  /** The company or item, by name (Nebius, not nbis). */
  name: string | null
  feeds: BetFeeds
}

export interface BetReach {
  id: string
  label: string
  kind: string
  channels: { kind: string; id: string; effect: Effect; strength: Strength; label: string; you: Share; world: Share }[]
  you: ScanTotals
  world: ScanTotals
  holdings: (ScanTotals & { symbol: string; weight: Share })[]
  replays: { id: string; name: string; start: string; end: string; you: number | null; world: number | null; coverage: Share }[]
}

export interface BetSettingsAt {
  gpu_life: number
  cost_of_capital: number
  deflation: number | "trailing"
}

export interface Bet {
  date: string
  /** "2023Q1" to "2033Q4"; every series has one entry per quarter. */
  quarters: string[]
  /** The index of the last quarter with actual figures; later ones are projected. */
  last_actual: number
  /** By GPU life: the quarter the readouts use, the band of write-off quarters, and its date. */
  deadlines: Record<string, { quarter: number; band: [number, number]; date: string }>
  sliders: {
    gpu_life: BetSlider<number>
    cost_of_capital: BetSlider<number>
    deflation: BetSlider<number | "trailing">
    value_capture: BetSlider<number>
    labour_share: BetSlider<number>
  }
  compute_share: Share
  capex: {
    pieces: BetCapexPiece[]
    /** By "gpu life|cost of capital", then piece: the need, already divided by the compute share. */
    grid: Record<string, Record<string, BetSeries & { readouts: BetBand<BetReadout> }>>
    placed: Record<string, { by_kind: Record<string, number>; last_quarter: string | null }>
    by_year: { years: number[]; actual_through: string; mid: number[]; low: number[]; high: number[] }
  }
  valuation: {
    start: string
    world: string
    groups: Record<string, { label: string; on: boolean; worth: number; low: number; high: number }>
    companies: {
      id: string
      group: string
      symbol?: string
      market: number | null
      added: number | null
      kept: number | null
      basis: string
      listed_since?: boolean | string
      date?: string
      grade?: string
      source: string
    }[]
    /** By "gpu life|cost of capital", then group: the end-user revenue needed at the deadline (R_T). */
    grid: Record<string, Record<string, { target: number; low: number; high: number }>>
  }
  demand: {
    pieces: BetDemandPiece[]
    /** By deflation step ("trailing", "-20"…): its yearly rate, and each piece with readouts by GPU life. */
    grid: Record<string, { deflation: number; pieces: Record<string, BetSeries & { readouts: Record<string, BetBand<BetReadout>> }> }>
    usage: {
      series: string
      entity: string
      growth: number
      since: string
      to: string
      check: { series: string; entity: string; since: string; to: string; growth: number } | null
    }
    trailing: number
    left_out: Record<string, string>
  }
  /** Factors that turn $B a year into the adoption units and the readouts that scale (spec 6). */
  units: {
    seat: { date: string; dollars: number; users_m: number; runrate_b: number } | null
    /** Paying-seat equivalents, in millions, per $B a year. */
    seats: number | null
    /** The productivity gain implied per $B a year, by value capture. */
    gain: Record<string, number>
    /** The share of work hours (a fraction) per $B a year, by value capture, per quarter. */
    hours: Record<string, BetBand<(number | null)[]>>
    /** The budget pool in $B a year, by labour share, per quarter. */
    pool: Record<string, (number | null)[]>
    hour_uplift: number
    inputs: { years: number[]; it: (number | null)[]; labour: (number | null)[] }
  }
  /** Totals since 1 January at `date`, in $B, and each one's latest rate a second. */
  clock: { from: string; date: string; capex_out: number; demand_in: number; capex_per_second: number; demand_per_second: number }
  notes: string[]
  fetched: { figures: number; differences: unknown[] }
  signals: {
    date: string
    indicators: Record<string, BetIndicator>
    paths: Record<string, BetPath>
    regime: { state: "absorbing" | "straining" | "breaking"; label: string; about: string; because: string[] }
    at: BetSettingsAt
  }
  releases: {
    days: number
    after: number[]
    items: BetRelease[]
    average: { market: Record<string, BetMean>; adoption: Record<string, Record<string, BetMean>> }
    notes: string[]
  }
  analogs: {
    ai_start: number
    items: Record<string, BetAnalog>
    ai_capex: { label: string; indexed: boolean; points: [number, number, number, number][]; actual_through: string }
  }
  panels: {
    funnel: { layers: { id: string; label: string; measures: BetMeasure[] }[]; leakage: BetLeakage[] }
    pillars: BetPillar[]
    grades: {
      at: BetSettingsAt
      need: GradeMix
      demand: GradeMix
      tiers: { id: string; label: string; share: Share; grades: GradeMix }[]
      judgments: Record<string, string[]>
    }
    sources: { rows: BetSourceRow[]; gaps: BetGap[] }
  }
  /** How much of your portfolio each path reaches, next to the world index (the scan method). */
  reach: Record<string, BetReach>
}
