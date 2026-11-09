/** The view model that src/whatstocks/render.py puts into the page (version 3). Shares are fractions: 0.12 is 12%.
 * Every number here was computed in Python; the page only formats and draws it. */

export type Share = number
export type Period = "1D" | "1W" | "1M" | "3M" | "YTD" | "1Y"
export type Returns = Partial<Record<Period, number | null>>
export type Point = [string, number]
export interface Sector {
  id: string
  label: string
  fund: string | null
  weight: Share
  holdings: string[]
  you: Returns
  average: Returns
  gap: Returns
  lines: { you: Point[]; average: Point[] }
}
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
    compare?: { name: string; symbol: string; returns: Returns; line: Point[] }[]
    sectors?: Sector[]
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
}
