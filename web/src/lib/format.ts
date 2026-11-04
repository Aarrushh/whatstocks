/** How the page writes numbers, dates and a few words. Shares match src/whatstocks/geometry.py:pct, whose label
 * widths assume this exact text. */

export const DASH = "–"
const MINUS = "−"
const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

const missing = (x: number | null | undefined): x is null | undefined => x === null || x === undefined || Number.isNaN(x)

export function pct(x: number | null | undefined, digits = 1): string {
  if (missing(x)) return DASH
  const text = (x * 100).toFixed(digits)
  // A share that is there but rounds to nothing reads <0.1%, so it does not look empty.
  if (x > 0 && Number(text) === 0) return `<${(10 ** -digits).toFixed(digits)}%`
  return `${text}%`
}

/** A move or a gap with its sign: +1.2% or −1.2%. */
export function signed(x: number | null | undefined, digits = 1, unit = "%"): string {
  if (missing(x)) return DASH
  const v = (x * 100).toFixed(digits)
  if (Number(v) === 0) return `${(0).toFixed(digits)}${unit}`
  return x > 0 ? `+${v}${unit}` : `${MINUS}${v.slice(1)}${unit}`
}

/** A difference between two shares, in percentage points. */
export function pts(x: number | null | undefined, digits = 1): string {
  return signed(x, digits, " pts")
}

export function prob(p: number): string {
  return `${Math.round(p * 100)}%`
}

export function tone(x: number | null | undefined): "pos" | "neg" | "flat" | "none" {
  if (missing(x)) return "none"
  return x > 0 ? "pos" : x < 0 ? "neg" : "flat"
}

function parts(iso: string): [number, number, number] {
  const [y, m, d] = iso.slice(0, 10).split("-").map(Number)
  return [y, m, d]
}

/** 06 Nov */
export function shortDate(iso: string): string {
  const [, m, d] = parts(iso)
  return `${String(d).padStart(2, "0")} ${MONTHS[m - 1]}`
}

/** 4 Nov 2026 */
export function longDate(iso: string): string {
  const [y, m, d] = parts(iso)
  return `${d} ${MONTHS[m - 1]} ${y}`
}

/** 6 Oct – 23 Oct 2026. Both years show when they differ: 19 Nov 2021 – 13 Oct 2022. */
export function dateRange(from: string, to: string): string {
  const [y1, m1, d1] = parts(from)
  const [y2] = parts(to)
  return `${d1} ${MONTHS[m1 - 1]}${y1 === y2 ? "" : ` ${y1}`} ${DASH} ${longDate(to)}`
}

export function daysBetween(from: string, to: string): number {
  const [y1, m1, d1] = parts(from)
  const [y2, m2, d2] = parts(to)
  return Math.round((Date.UTC(y2, m2 - 1, d2) - Date.UTC(y1, m1 - 1, d1)) / 86_400_000)
}

export function addDays(iso: string, days: number): string {
  const [y, m, d] = parts(iso)
  return new Date(Date.UTC(y, m - 1, d + days)).toISOString().slice(0, 10)
}

/** When something is due, in words: today, tomorrow, in 12 days, 3 days overdue. */
export function due(day: string | null, today: string): string {
  if (!day) return "ongoing"
  const n = daysBetween(today, day)
  if (n === 0) return "today"
  if (n === 1) return "tomorrow"
  return n > 0 ? `in ${n} days` : `${-n} days overdue`
}

export function plural(n: number, word: string, many = `${word}s`): string {
  return `${n} ${n === 1 ? word : many}`
}

/** How busy a theme is in today's brief. */
export function heat(n: number): { level: "busy" | "active" | "quiet"; words: string } {
  if (n >= 2) return { level: "busy", words: `busy · ${n} events today` }
  if (n === 1) return { level: "active", words: "active · 1 event today" }
  return { level: "quiet", words: "quiet today" }
}

export const RIPPLE_WORD = { help: "helps", hurt: "hurts", unclear: "unclear" } as const
export const SCAN_WORD = { hurt: "would hurt", help: "would help", mixed: "mixed" } as const

/** Only web addresses become links. */
export function webUrl(url: string | null | undefined): string | null {
  return url && /^https?:\/\//i.test(url) ? url : null
}
