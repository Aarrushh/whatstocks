/** Charts drawn in plain HTML and SVG: thin marks anchored to one baseline, a 2px gap between fills, a tip on
 * every mark, text in ink colours (docs/DASHBOARD.md section 4). Every number comes from the view model. */
import { useLayoutEffect, useRef, type ReactNode } from "react"
import { cn } from "@/lib/utils"
import { DASH, daysBetween, longDate, pct, plural, prob, pts, shortDate } from "@/lib/format"
import type { Strength, WatchItem } from "@/lib/types"
import { Move } from "./kit"

/** The validated categorical order. Colour follows the entity, never its rank; a ninth series folds into Other. */
export const CATEGORICAL = ["var(--c1)", "var(--c2)", "var(--c3)", "var(--c4)", "var(--c5)", "var(--c6)", "var(--c7)", "var(--c8)"] as const

/** The last 90 days of a price, as a small line: blue if it ended higher, red if lower. */
export function Spark({ values, className }: { values: number[]; className?: string }) {
  if (values.length < 2) return <span className={cn("text-ink-3", className)}>{DASH}</span>
  const lo = Math.min(...values)
  const span = Math.max(...values) - lo || 1
  const d = values
    .map((v, i) => `${i ? "L" : "M"}${((i / (values.length - 1)) * 100).toFixed(2)},${(22 - ((v - lo) / span) * 20).toFixed(2)}`)
    .join("")
  const up = values[values.length - 1] >= values[0]
  return (
    <svg viewBox="0 0 100 24" preserveAspectRatio="none" aria-hidden className={cn("h-6 w-20", className)}>
      <path
        d={d}
        fill="none"
        stroke={up ? "var(--pos)" : "var(--neg)"}
        strokeWidth="1.5"
        strokeLinejoin="round"
        strokeLinecap="round"
        vectorEffect="non-scaling-stroke"
      />
    </svg>
  )
}

/** Your share as a bar, the world index's as a tick on the same scale. */
export function Bullet({ you, world, max }: { you: number; world: number; max: number }) {
  const at = (v: number) => `${Math.min(100, (Math.max(0, v) / (max || 1)) * 100)}%`
  return (
    <span aria-hidden className="relative block h-3.5 min-w-12">
      <span className="absolute inset-x-0 top-1/2 h-px bg-line" />
      <span className="absolute top-1/2 left-0 h-1.5 -translate-y-1/2 rounded-r-[3px] bg-you" style={{ width: at(you) }} />
      <span
        className="absolute top-0 h-full w-[2px] -translate-x-1/2 rounded-full bg-world shadow-[0_0_0_1.5px_var(--card)]"
        style={{ left: at(world) }}
      />
    </span>
  )
}

export interface ShareRow {
  id: string
  label: string
  you: number
  world: number
  sub?: ReactNode
  onClick?: () => void
  active?: boolean
}

/** Rows of you against the world index: a bar, a tick, both shares and the gap in points. */
export function YouWorld({
  rows,
  head = "Theme",
  gap = true,
  className,
}: {
  rows: ShareRow[]
  head?: string
  gap?: boolean
  className?: string
}) {
  const max = Math.max(1e-9, ...rows.flatMap((r) => [r.you, r.world])) * 1.02
  return (
    <div
      className={cn(
        "grid gap-x-3 text-[13px]",
        gap
          ? "grid-cols-[fit-content(17rem)_minmax(3rem,1fr)_auto_auto_auto]"
          : "grid-cols-[fit-content(17rem)_minmax(3rem,1fr)_auto_auto]",
        className,
      )}
    >
      <div className="col-span-full grid grid-cols-subgrid px-1.5 pb-1 text-[11px] text-ink-3">
        <span>{head}</span>
        <span />
        <span className="text-right">You</span>
        <span className="text-right">World</span>
        {gap && <span className="text-right">Gap</span>}
      </div>
      {rows.map((r) => {
        const tip = `${r.label}: you ${pct(r.you)}, world index ${pct(r.world)} (${pts(r.you - r.world)})`
        const inner = (
          <>
            <span className="min-w-0 truncate text-left">
              {r.label}
              {r.sub && <span className="ml-1.5 text-[11px] text-ink-3">{r.sub}</span>}
            </span>
            <Bullet you={r.you} world={r.world} max={max} />
            <span className="num text-right">{pct(r.you)}</span>
            <span className="num text-right text-ink-3">{pct(r.world)}</span>
            {gap && <span className="num text-right text-ink-2">{pts(r.you - r.world)}</span>}
          </>
        )
        const cls = cn("col-span-full grid grid-cols-subgrid items-center rounded-md px-1.5 py-1", r.active && "bg-card-2")
        return r.onClick ? (
          <button
            key={r.id}
            type="button"
            onClick={r.onClick}
            data-tip={tip}
            className={cn(cls, "outline-none transition-colors duration-150 hover:bg-card-2 focus-visible:ring-2 focus-visible:ring-ring/50")}
          >
            {inner}
          </button>
        ) : (
          <div key={r.id} data-tip={tip} className={cls}>
            {inner}
          </div>
        )
      })}
    </div>
  )
}

/** Labelled bars behind their names, largest first (one series, so one hue and no legend). */
export function BarList({
  rows,
  color = "var(--you)",
  format = (v: number) => pct(v),
  className,
}: {
  rows: { id: string; label: ReactNode; value: number; tip?: string }[]
  color?: string
  format?: (v: number) => string
  className?: string
}) {
  const max = Math.max(1e-9, ...rows.map((r) => r.value))
  return (
    <ul className={cn("flex flex-col gap-1", className)}>
      {rows.map((r) => (
        <li key={r.id} data-tip={r.tip} className="flex items-center gap-3 text-[13px]">
          <span className="relative flex h-6 min-w-0 flex-1 items-center">
            <span
              aria-hidden
              className="absolute inset-y-0 left-0 rounded-r-[4px]"
              style={{ width: `${(r.value / max) * 100}%`, background: `color-mix(in oklab, ${color} 22%, transparent)` }}
            />
            <span className="relative truncate px-2">{r.label}</span>
          </span>
          <span className="num shrink-0 text-right text-ink-2">{format(r.value)}</span>
        </li>
      ))}
    </ul>
  )
}

export interface Segment {
  id: string
  label: string
  value: number
  color: string
  tip?: string
}

/** One bar split into parts, with a 2px gap between them. */
export function CategoryBar({ segments, className }: { segments: Segment[]; className?: string }) {
  const shown = segments.filter((s) => s.value > 0)
  const sum = Math.max(1e-9, shown.reduce((a, s) => a + s.value, 0))
  return (
    <div className={cn("flex h-4 w-full items-center gap-[2px]", className)}>
      {shown.map((s) => (
        <span
          key={s.id}
          data-tip={s.tip ?? `${s.label}: ${pct(s.value)}`}
          className="flex h-full min-w-[3px] items-center [&:first-child>span]:rounded-l-[3px] [&:last-child>span]:rounded-r-[3px]"
          style={{ flex: `${s.value / sum} 1 0%` }}
        >
          <span className="h-2 w-full" style={{ background: s.color }} />
        </span>
      ))}
    </div>
  )
}

export interface PairRow {
  id: string
  label: ReactNode
  sub?: ReactNode
  you: number | null
  world: number | null
  note?: ReactNode
}

/** Two moves per row, you and the world index, each labelled, from a shared zero line. */
export function PairBars({ rows, labels = ["You", "World index"] }: { rows: PairRow[]; labels?: [string, string] }) {
  const values = rows.flatMap((r) => [r.you, r.world]).filter((v): v is number => typeof v === "number" && !Number.isNaN(v))
  const max = Math.max(1e-9, ...values.map((v) => Math.abs(v)))
  const neg = values.some((v) => v < 0)
  const pos = values.some((v) => v > 0)
  const zero = neg && pos ? 0.5 : neg ? 1 : 0
  const scale = neg && pos ? 0.5 : 1
  const bar = (v: number | null, color: string) => {
    if (v === null || Number.isNaN(v)) return null
    const size = (Math.abs(v) / max) * scale
    return (
      <span
        className={cn("absolute top-1/2 h-2 -translate-y-1/2", v < 0 ? "rounded-l-[3px]" : "rounded-r-[3px]")}
        style={{ left: `${(v < 0 ? zero - size : zero) * 100}%`, width: `${size * 100}%`, background: color }}
      />
    )
  }
  const track = (v: number | null, color: string) => (
    <span aria-hidden className="relative block h-3">
      <span className="absolute inset-y-0 w-px bg-line-strong" style={{ left: `calc(${zero * 100}% - ${zero}px)` }} />
      {bar(v, color)}
    </span>
  )
  return (
    <div className="flex flex-col gap-4">
      {rows.map((r) => (
        <div key={r.id}>
          <div className="flex items-baseline justify-between gap-3">
            <span className="min-w-0 truncate text-[13px]">{r.label}</span>
            {r.sub && <span className="num shrink-0 text-[11px] text-ink-3">{r.sub}</span>}
          </div>
          <div className="mt-1.5 grid grid-cols-[5.5rem_minmax(0,1fr)_4.5rem] items-center gap-x-2 gap-y-1 text-xs">
            <span className="text-ink-2">{labels[0]}</span>
            {track(r.you, "var(--you)")}
            <Move value={r.you} className="justify-end" />
            <span className="text-ink-3">{labels[1]}</span>
            {track(r.world, "var(--world)")}
            <Move value={r.world} className="justify-end text-ink-2" />
          </div>
          {r.note}
        </div>
      ))}
    </div>
  )
}

/** For each row, the share a conflict would hurt (red, to the left) and help (blue, to the right). */
export function HurtHelp({
  rows,
}: {
  rows: { id: string; label: ReactNode; sub?: ReactNode; hurt: number; help: number }[]
}) {
  return (
    <div className="grid grid-cols-[minmax(0,8rem)_auto_minmax(2rem,1fr)_minmax(2rem,1fr)_auto] items-center gap-x-2 gap-y-1.5 text-[13px]">
      <span />
      <span />
      <span className="text-right text-[11px] text-ink-3">would hurt</span>
      <span className="text-[11px] text-ink-3">would help</span>
      <span />
      {rows.map((r) => (
        <div
          key={r.id}
          data-tip={`${typeof r.label === "string" ? r.label : r.id}: ${pct(r.hurt, 0)} of it would be hurt, ${pct(r.help, 0)} helped`}
          className="col-span-full grid grid-cols-subgrid items-center"
        >
          <span className="min-w-0 truncate">
            {r.label}
            {r.sub && <span className="num ml-1.5 text-[11px] text-ink-3">{r.sub}</span>}
          </span>
          <span className="num text-right text-xs text-ink-2">{pct(r.hurt, 0)}</span>
          <span aria-hidden className="relative block h-3 border-r border-line-strong">
            <span className="absolute top-1/2 right-0 h-2 -translate-y-1/2 rounded-l-[3px] bg-neg" style={{ width: `${Math.min(1, r.hurt) * 100}%` }} />
          </span>
          <span aria-hidden className="relative block h-3">
            <span className="absolute top-1/2 left-0 h-2 -translate-y-1/2 rounded-r-[3px] bg-pos" style={{ width: `${Math.min(1, r.help) * 100}%` }} />
          </span>
          <span className="num text-xs text-ink-2">{pct(r.help, 0)}</span>
        </div>
      ))}
    </div>
  )
}

/** Diverging fill: blue above zero, red below, the card's grey at zero, full colour at `full` or more. */
export function divergeFill(v: number | null, full: number): string {
  if (v === null || Number.isNaN(v)) return "transparent"
  const k = Math.min(1, Math.abs(v) / full)
  return `color-mix(in oklab, ${v >= 0 ? "var(--pos)" : "var(--neg)"} ${Math.round(6 + 84 * k)}%, var(--card-2))`
}

/** Sequential fill: one hue from faint to strong. `top` caps it so text on the cell stays readable. */
export function rampFill(v: number | null, max: number, color: string, top = 55): string {
  if (v === null || Number.isNaN(v) || v <= 0 || max <= 0) return "var(--card-2)"
  return `color-mix(in oklab, ${color} ${Math.round(10 + (top - 10) * Math.min(1, v / max))}%, var(--card-2))`
}

export function ScaleLegend({ steps, from, to, className }: { steps: string[]; from: string; to: string; className?: string }) {
  return (
    <div className={cn("flex items-center gap-2 text-[11px] text-ink-3", className)}>
      <span>{from}</span>
      <span aria-hidden className="flex gap-[2px]">
        {steps.map((c, i) => (
          <span key={i} className="h-2.5 w-5 rounded-[2px]" style={{ background: c }} />
        ))}
      </span>
      <span>{to}</span>
    </div>
  )
}

export interface GridRow {
  id: string
  label: ReactNode
  sub?: ReactNode
  cells: (number | null)[]
}

/** A heat table. It is a real table, so the values are there for screen readers even when only colour shows. */
export function HeatGrid({
  cols,
  rows,
  foot,
  head,
  colLabel,
  fill,
  tip,
  text,
  showText = false,
  overhang = false,
  className,
}: {
  cols: string[]
  rows: GridRow[]
  foot?: GridRow
  head: string
  colLabel: (col: string, i: number) => ReactNode
  fill: (v: number | null) => string
  tip: (row: GridRow, col: string, v: number | null) => string
  text: (v: number | null) => string
  showText?: boolean
  /** Let sparse column labels overhang their column, so columns stay as narrow as the cells. The last label is right-aligned. */
  overhang?: boolean
  className?: string
}) {
  const cells = (r: GridRow, strong = false) =>
    r.cells.map((v, i) => (
      <td
        key={i}
        data-tip={tip(r, cols[i], v)}
        className={cn("num h-7 min-w-6 rounded-[3px] px-0.5 text-center text-[11px]", strong && "font-medium")}
        style={{ background: fill(v) }}
      >
        <span className={showText ? undefined : "sr-only"}>{text(v)}</span>
      </td>
    ))
  // The newest column is on the right. When the grid is wider than its panel, open it scrolled to the newest.
  const scroller = useRef<HTMLDivElement>(null)
  useLayoutEffect(() => {
    const el = scroller.current
    if (el) el.scrollLeft = el.scrollWidth
  }, [cols.length])
  return (
    <div ref={scroller} className={cn("relative -mx-1 overflow-x-auto px-1", className)}>
      <table className="w-full border-separate border-spacing-[2px]">
        <thead>
          <tr>
            <th scope="col" className="sticky left-0 z-10 bg-card pr-2 text-left text-[11px] font-normal text-ink-3">
              {head}
            </th>
            {cols.map((c, i) =>
              overhang ? (
                <th key={c} scope="col" className="num relative h-5 p-0 text-[10.5px] font-normal text-ink-3">
                  <span className={cn("absolute bottom-1 whitespace-nowrap", i === cols.length - 1 ? "right-0" : "left-1/2 -translate-x-1/2")}>
                    {colLabel(c, i)}
                  </span>
                </th>
              ) : (
                <th key={c} scope="col" className="num px-0.5 pb-1 text-center text-[10.5px] font-normal whitespace-nowrap text-ink-3">
                  {colLabel(c, i)}
                </th>
              ),
            )}
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.id}>
              <th scope="row" className="sticky left-0 z-10 bg-card pr-3 text-left text-xs font-normal whitespace-nowrap">
                {r.label}
                {r.sub && <span className="num ml-1.5 text-[11px] text-ink-3">{r.sub}</span>}
              </th>
              {cells(r)}
            </tr>
          ))}
        </tbody>
        {foot && (
          <tfoot>
            <tr>
              <th scope="row" className="sticky left-0 z-10 bg-card pt-1 pr-3 text-left text-xs font-medium whitespace-nowrap">
                {foot.label}
              </th>
              {cells(foot, true)}
            </tr>
          </tfoot>
        )}
      </table>
    </div>
  )
}

/** A theme proxy's weekly gap to the world index: blue weeks it did better, red weeks it did worse. */
export function WeekBars({ weeks, proxy, today }: { weeks: [string, number][]; proxy: string; today: string }) {
  const max = Math.max(0.02, ...weeks.map(([, v]) => Math.abs(v)))
  return (
    <div className="relative flex h-9 gap-[2px]">
      <span aria-hidden className="absolute inset-x-0 top-1/2 h-px bg-line" />
      {weeks.map(([d, v]) => (
        <span
          key={d}
          data-tip={`Week to ${shortDate(d)}${d > today ? " (so far)" : ""}: ${proxy} ${pts(v)} against the world index`}
          className="relative flex-1"
        >
          <span
            className={cn("absolute inset-x-0", v >= 0 ? "bottom-1/2 rounded-t-[2px] bg-pos" : "top-1/2 rounded-b-[2px] bg-neg")}
            style={{ height: `${(Math.abs(v) / max) * 50}%` }}
          />
        </span>
      ))}
    </div>
  )
}

/** A numbered dot for a thing to watch: filled for news, hollow for a deadline from your own record. */
export function NumDot({ n, record }: { n: number; record: boolean }) {
  return (
    <span
      className={cn(
        "num grid size-[18px] shrink-0 place-items-center rounded-full text-[10px] font-medium",
        record ? "text-foreground ring-1 ring-foreground/60 ring-inset" : "bg-foreground text-background",
      )}
    >
      {n}
    </span>
  )
}

/** The next `days` days, with each dated thing to watch as a numbered dot. Dots that would touch stack upwards. */
export function Timeline({ items, today, days = 90 }: { items: WatchItem[]; today: string; days?: number }) {
  const dated = items
    .flatMap((w) => (w.date ? [{ w, d: daysBetween(today, w.date) }] : []))
    .filter(({ d }) => d >= 0 && d <= days)
    .sort((a, b) => a.d - b.d)
  const ends: number[] = []
  const placed = dated.map(({ w, d }) => {
    const at = d / days
    let row = ends.findIndex((end) => at - end >= 0.06)
    if (row === -1) {
      row = ends.length
      ends.push(at)
    } else ends[row] = at
    return { w, at, row }
  })
  const months: { at: number; label: string }[] = []
  let y = Number(today.slice(0, 4))
  let m = Number(today.slice(5, 7))
  for (;;) {
    m += 1
    if (m > 12) {
      m = 1
      y += 1
    }
    const iso = `${y}-${String(m).padStart(2, "0")}-01`
    const d = daysBetween(today, iso)
    if (d > days) break
    // Keep month labels clear of the Today and +90 days labels at the ends.
    if (d / days >= 0.1 && d / days <= 0.86) months.push({ at: d / days, label: shortDate(iso).slice(3) })
  }
  const height = 26 + 22 * Math.max(1, ends.length)
  return (
    <div className="px-2.5">
      <div className="relative" style={{ height }}>
        <span aria-hidden className="absolute inset-x-0 bottom-[18px] h-px bg-line-strong" />
        <span className="absolute bottom-0 left-0 -translate-x-2.5 text-[10.5px] text-ink-3">Today</span>
        {months.map((mo) => (
          <span key={mo.label} aria-hidden>
            <span className="absolute bottom-[15px] h-[7px] w-px bg-line-strong" style={{ left: `${mo.at * 100}%` }} />
            <span className="absolute bottom-0 -translate-x-1/2 text-[10.5px] text-ink-3" style={{ left: `${mo.at * 100}%` }}>
              {mo.label}
            </span>
          </span>
        ))}
        <span className="absolute right-0 bottom-0 translate-x-2.5 text-[10.5px] text-ink-3">+{days} days</span>
        {placed.map(({ w, at, row }) => {
          const tip = `${w.n}. ${w.what}\n${longDate(w.date as string)}${w.record ? " · from your own record" : ""}`
          return (
            <span
              key={w.n}
              tabIndex={0}
              aria-label={tip}
              data-tip={tip}
              className="absolute -translate-x-1/2 rounded-full outline-none focus-visible:ring-2 focus-visible:ring-ring/50"
              style={{ left: `${at * 100}%`, bottom: 24 + row * 22 }}
            >
              <span aria-hidden className="absolute top-full left-1/2 w-px -translate-x-1/2 bg-line-strong" style={{ height: 6 + row * 22 }} />
              <NumDot n={w.n} record={w.record} />
            </span>
          )
        })}
      </div>
    </div>
  )
}

/** A view's probability over its life: a step at each change, up to today, on a 0 to 100% scale. */
export function ForecastLine({ points, start, end, today }: { points: [string, number][]; start: string; end: string; today: string }) {
  const W = 300
  const H = 64
  const span = Math.max(1, daysBetween(start, end))
  const x = (d: string) => Math.min(1, Math.max(0, daysBetween(start, d) / span))
  const y = (p: number) => 5 + (1 - p) * (H - 10)
  const sorted = [...points].sort((a, b) => (a[0] < b[0] ? -1 : a[0] > b[0] ? 1 : 0))
  const now = x(today)
  let d = ""
  sorted.forEach(([day, p], i) => {
    d += i === 0 ? `M${x(day) * W},${y(p)}` : `H${x(day) * W}V${y(p)}`
  })
  if (sorted.length) d += `H${Math.max(now, x(sorted[sorted.length - 1][0])) * W}`
  return (
    <div>
      <div className="relative h-16">
        <svg viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none" aria-hidden className="absolute inset-0 size-full overflow-visible">
          <line x1="0" x2={W} y1={y(0.5)} y2={y(0.5)} stroke="var(--line-strong)" strokeDasharray="2 3" vectorEffect="non-scaling-stroke" />
          <line x1="0" x2={W} y1={H} y2={H} stroke="var(--line)" vectorEffect="non-scaling-stroke" />
          <line x1={now * W} x2={now * W} y1="0" y2={H} stroke="var(--line-strong)" vectorEffect="non-scaling-stroke" />
          <path d={d} fill="none" stroke="var(--you)" strokeWidth="2" strokeLinejoin="round" vectorEffect="non-scaling-stroke" />
        </svg>
        <span className="absolute right-0 text-[10px] text-ink-3" style={{ top: y(0.5) - 15 }}>
          50%
        </span>
        {sorted.map(([day, p]) => (
          <span
            key={day}
            tabIndex={0}
            aria-label={`${longDate(day)}: ${prob(p)}`}
            data-tip={`${longDate(day)}: ${prob(p)}`}
            className="absolute size-2 -translate-x-1/2 -translate-y-1/2 rounded-full bg-you outline-none ring-2 ring-card focus-visible:ring-ring/50"
            style={{ left: `${x(day) * 100}%`, top: y(p) }}
          />
        ))}
      </div>
      <div className="num relative mt-1 flex justify-between text-[10.5px] text-ink-3">
        <span>set {shortDate(start)}</span>
        {now > 0.16 && now < 0.84 && (
          <span className="absolute -translate-x-1/2" style={{ left: `${now * 100}%` }}>
            today
          </span>
        )}
        <span>resolves {shortDate(end)}</span>
      </div>
    </div>
  )
}

const LEVEL: Record<Strength, number> = { low: 1, medium: 2, high: 3 }

/** Strength as one, two or three bars, with the word beside it. */
export function StrengthBars({ strength }: { strength: Strength }) {
  const n = LEVEL[strength]
  return (
    <span className="inline-flex items-center gap-1.5">
      <span aria-hidden className="inline-flex items-end gap-[2px]">
        {[1, 2, 3].map((i) => (
          <span key={i} className={cn("w-[3px] rounded-[1px]", i <= n ? "bg-foreground" : "bg-line-strong")} style={{ height: 3 + i * 3 }} />
        ))}
      </span>
      <span className="text-xs text-ink-2">{strength}</span>
    </span>
  )
}

/** Counts per day as a row of small blocks, darker for more. */
export function Tracker({ dates, counts }: { dates: string[]; counts: number[] }) {
  const max = Math.max(1, ...counts)
  return (
    <div className="flex gap-[2px]">
      {counts.map((n, i) => (
        <span
          key={dates[i] ?? i}
          data-tip={`${dates[i] ? shortDate(dates[i]) : ""}: ${plural(n, "event")}`}
          className="h-3.5 flex-1 rounded-[2px]"
          style={{ background: rampFill(n, max, "var(--foreground)", 75) }}
        />
      ))}
    </div>
  )
}
