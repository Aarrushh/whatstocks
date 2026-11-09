/** The charts of "Will the bet pay off?". The hero stacks the demand tiers against the capex-payback need, quarter by
 * quarter, with the gap, the valuation target at the deadline, the deadline band and the open-weight releases; the
 * analog chart lines AI's build-out up against past ones. SVG draws the marks and HTML the words, as ForecastLine
 * does. Every value comes from lib/bet.ts, which only adds up Python's pieces. */
import { useId } from "react"
import { cn } from "@/lib/utils"
import { niceTicks } from "@/lib/bet"

const W = 1000
const H = 300

export interface HeroLayer {
  id: string
  label: string
  color: string
  /** One per quarter, in the unit shown. */
  values: (number | null)[]
}

export interface HeroProps {
  quarters: string[]
  lastActual: number
  /** The demand tiers, best at the bottom. */
  layers: HeroLayer[]
  need: { rate: (number | null)[]; low: (number | null)[]; high: (number | null)[] }
  target: { rate: number | null; low: number | null; high: number | null; tip: string } | null
  deadline: { quarter: number; band: [number, number]; label: string }
  /** Open-weight releases: where each falls on the quarter axis, and its tip. */
  releases: { id: string; at: number; tip: string }[]
  /** A value in the unit shown, for the axis. */
  format: (x: number) => string
  /** The tip for each quarter's column. */
  tip: (q: number) => string
  className?: string
}

const fin = (x: number | null | undefined): x is number => typeof x === "number" && Number.isFinite(x)

export function BetHero({ quarters, lastActual, layers, need, target, deadline, releases, format, tip, className }: HeroProps) {
  const hatch = `gap-${useId().replace(/[^a-zA-Z0-9]/g, "")}`
  const n = quarters.length
  const la = Math.min(Math.max(lastActual, 0), n - 1)
  // The stack, layer on layer: cum[i][q] is the top of layer i.
  const cum: number[][] = []
  layers.forEach((l, i) => cum.push(l.values.map((v, q) => (i ? cum[i - 1][q] : 0) + (fin(v) ? v : 0))))
  const total = cum.length ? cum[cum.length - 1] : new Array<number>(n).fill(0)
  const peak = Math.max(
    1e-9,
    ...total,
    ...need.rate.filter(fin),
    ...need.high.filter(fin),
    ...(target && fin(target.rate) ? [target.rate] : []),
  )
  const ticks = niceTicks(peak * 1.04)
  const top = ticks[ticks.length - 1]
  const X = (q: number) => ((q + 0.5) / n) * W
  const edge = (pos: number) => (pos / n) * W
  const Y = (v: number) => H - (Math.min(Math.max(v, 0), top) / top) * H
  const xy = (q: number, v: number) => `${X(q).toFixed(2)},${Y(v).toFixed(2)}`

  const line = (vals: (number | null)[], from: number, to: number) => {
    let d = ""
    let pen = false
    for (let q = from; q <= to; q++) {
      const v = vals[q]
      if (!fin(v)) {
        pen = false
        continue
      }
      d += `${pen ? "L" : "M"}${xy(q, v)}`
      pen = true
    }
    return d
  }
  const area = (upper: number[], lower: number[] | null, from: number, to: number) => {
    if (to < from) return ""
    let d = ""
    for (let q = from; q <= to; q++) d += `${q === from ? "M" : "L"}${xy(q, upper[q])}`
    for (let q = to; q >= from; q--) d += `L${xy(q, lower ? lower[q] : 0)}`
    return `${d}Z`
  }
  const needBand = (() => {
    const qs = need.low.map((v, q) => (fin(v) && fin(need.high[q]) ? q : -1)).filter((q) => q >= 0)
    if (qs.length < 2) return ""
    let d = ""
    qs.forEach((q, i) => (d += `${i ? "L" : "M"}${xy(q, need.high[q] as number)}`))
    for (let i = qs.length - 1; i >= 0; i--) d += `L${xy(qs[i], need.low[qs[i]] as number)}`
    return `${d}Z`
  })()

  // The gap: wherever the need runs above the stack, with the crossing points placed between quarters.
  const gaps: string[] = []
  let widest: { q: number; size: number } | null = null
  {
    let upper: string[] = []
    let lower: string[] = []
    const flush = () => {
      if (upper.length > 1) gaps.push(`M${upper.join("L")}L${lower.reverse().join("L")}Z`)
      upper = []
      lower = []
    }
    for (let q = 0; q < n; q++) {
      const v = need.rate[q]
      if (!fin(v)) {
        flush()
        continue
      }
      const g = v - total[q]
      if (g > 0) {
        upper.push(xy(q, v))
        lower.push(xy(q, total[q]))
        const size = Y(total[q]) - Y(v)
        if (!widest || size > widest.size) widest = { q, size }
      }
      const v1 = need.rate[q + 1]
      if (q + 1 < n && fin(v1)) {
        const g1 = v1 - total[q + 1]
        if (g > 0 !== g1 > 0 && g !== g1) {
          const t = g / (g - g1)
          const at = `${(X(q) + t * (X(q + 1) - X(q))).toFixed(2)},${Y(v + t * (v1 - v)).toFixed(2)}`
          upper.push(at)
          lower.push(at)
          if (g > 0) flush()
        }
      }
    }
    flush()
  }
  const gapLabel = widest && widest.size > H * 0.07 ? widest : null

  const dq = deadline.quarter
  const hasDeadline = dq >= 0 && dq < n
  const years = quarters
    .map((q, i) => (q.endsWith("Q1") ? { i, year: q.slice(0, 4) } : null))
    .filter((y): y is { i: number; year: string } => !!y)
  const pctX = (x: number) => `${(x / W) * 100}%`
  const pctY = (y: number) => `${(y / H) * 100}%`
  const goal = hasDeadline && target && fin(target.rate) ? { ...target, rate: target.rate } : null

  return (
    <div className={className}>
      <div className="relative h-60 sm:h-72">
        <svg viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none" aria-hidden className="absolute inset-0 size-full overflow-visible">
          <defs>
            <pattern id={hatch} width="7" height="7" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
              <line x1="0" y1="0" x2="0" y2="7" stroke="var(--foreground)" strokeOpacity="0.34" strokeWidth="1.6" />
            </pattern>
          </defs>
          <rect
            x={edge(deadline.band[0])}
            width={Math.max(0, edge(deadline.band[1] + 1) - edge(deadline.band[0]))}
            y="0"
            height={H}
            fill="var(--foreground)"
            fillOpacity="0.045"
          />
          {ticks.map((t) => (
            <line key={t} x1="0" x2={W} y1={Y(t)} y2={Y(t)} stroke={t ? "var(--line)" : "var(--line-strong)"} vectorEffect="non-scaling-stroke" />
          ))}
          {needBand && <path d={needBand} fill="var(--foreground)" fillOpacity="0.07" />}
          {layers.map((l, i) => (
            <g key={l.id} fill={l.color}>
              <path d={area(cum[i], i ? cum[i - 1] : null, 0, la)} fillOpacity="0.9" />
              <path d={area(cum[i], i ? cum[i - 1] : null, la, n - 1)} fillOpacity="0.3" />
            </g>
          ))}
          {total.some((v) => v > 0) && (
            <path d={line(total, la, n - 1)} fill="none" stroke="var(--ink-2)" strokeWidth="1.2" strokeDasharray="4 3" vectorEffect="non-scaling-stroke" />
          )}
          {gaps.map((d, i) => (
            <path key={i} d={d} fill={`url(#${hatch})`} />
          ))}
          <path d={line(need.rate, 0, la)} fill="none" stroke="var(--foreground)" strokeWidth="2" strokeLinejoin="round" vectorEffect="non-scaling-stroke" />
          <path
            d={line(need.rate, la, n - 1)}
            fill="none"
            stroke="var(--foreground)"
            strokeWidth="2"
            strokeDasharray="6 4"
            strokeLinejoin="round"
            vectorEffect="non-scaling-stroke"
          />
          <line x1={X(la)} x2={X(la)} y1="0" y2={H} stroke="var(--line-strong)" vectorEffect="non-scaling-stroke" />
          {hasDeadline && <line x1={X(dq)} x2={X(dq)} y1="0" y2={H} stroke="var(--ink-3)" strokeDasharray="2 3" vectorEffect="non-scaling-stroke" />}
          {goal && (
            <g stroke="var(--c7)">
              <path d={`M${xy(la, total[la])}L${xy(dq, goal.rate)}`} fill="none" strokeWidth="1.5" strokeDasharray="3 3" vectorEffect="non-scaling-stroke" />
              {fin(goal.low) && fin(goal.high) && (
                <>
                  <line x1={X(dq)} x2={X(dq)} y1={Y(goal.low)} y2={Y(goal.high)} strokeWidth="2" vectorEffect="non-scaling-stroke" />
                  <line x1={X(dq) - 6} x2={X(dq) + 6} y1={Y(goal.low)} y2={Y(goal.low)} strokeWidth="2" vectorEffect="non-scaling-stroke" />
                  {goal.high <= top ? (
                    <line x1={X(dq) - 6} x2={X(dq) + 6} y1={Y(goal.high)} y2={Y(goal.high)} strokeWidth="2" vectorEffect="non-scaling-stroke" />
                  ) : (
                    <path d={`M${X(dq) - 6},10L${X(dq)},2L${X(dq) + 6},10`} fill="none" strokeWidth="2" vectorEffect="non-scaling-stroke" />
                  )}
                </>
              )}
            </g>
          )}
        </svg>

        {ticks.slice(1).map((t) => (
          <span
            key={t}
            className="num pointer-events-none absolute left-0 -translate-y-full pb-0.5 text-[10.5px] text-ink-3"
            style={{ top: pctY(Y(t)) }}
          >
            {format(t)}
          </span>
        ))}
        <span className="pointer-events-none absolute top-1 pl-1.5 text-[10.5px] whitespace-nowrap text-ink-3" style={{ left: pctX(X(la)) }}>
          {quarters[la]} · last actual
        </span>
        {hasDeadline && (
          // A line below the last-actual label, so the two never collide when the deadline is near.
          <span
            className="pointer-events-none absolute top-5 -translate-x-full pr-1.5 text-right text-[10.5px] whitespace-nowrap text-ink-2"
            style={{ left: pctX(X(dq)) }}
          >
            {deadline.label}
          </span>
        )}

        {/* One column per quarter, each with its numbers in a tip. */}
        <div className="absolute inset-0 flex">
          {quarters.map((q, i) => (
            <div key={q} data-tip={tip(i)} className="h-full flex-1 transition-colors duration-150 hover:bg-foreground/[0.05]" />
          ))}
        </div>

        {gapLabel && (
          <span
            className="pointer-events-none absolute -translate-x-1/2 -translate-y-1/2 rounded-[3px] bg-card px-1 text-[11px] leading-4 font-medium text-foreground ring-1 ring-line"
            style={{ left: pctX(X(gapLabel.q)), top: pctY(Y(total[gapLabel.q]) - gapLabel.size / 2) }}
          >
            gap
          </span>
        )}
        {goal && (
          <span
            tabIndex={0}
            role="img"
            aria-label={goal.tip}
            data-tip={goal.tip}
            className="absolute size-2.5 -translate-x-1/2 -translate-y-1/2 rounded-full bg-c7 ring-2 ring-card outline-none focus-visible:ring-ring/50"
            style={{ left: pctX(X(dq)), top: pctY(Y(goal.rate)) }}
          />
        )}
      </div>

      <div className="relative mt-1 h-8">
        {releases.map((r) => (
          <span
            key={r.id}
            tabIndex={0}
            role="img"
            aria-label={r.tip}
            data-tip={r.tip}
            className="absolute top-0 flex h-3 w-2.5 -translate-x-1/2 items-start justify-center rounded-[2px] outline-none focus-visible:ring-2 focus-visible:ring-ring/50"
            style={{ left: pctX(edge(r.at)) }}
          >
            <svg viewBox="0 0 8 8" aria-hidden className="size-2 fill-ink-2">
              <path d="M4 .5 7.5 7.5H.5z" />
            </svg>
          </span>
        ))}
        {years.map(({ i, year }, k) => (
          <span key={year} className={cn("num absolute top-3.5 text-[10.5px] text-ink-3", k % 2 && "hidden sm:block")} style={{ left: pctX(edge(i)) }}>
            {year}
          </span>
        ))}
      </div>
    </div>
  )
}

export interface AnalogLine {
  id: string
  label: string
  color: string
  points: [number, number][]
  /** Low and high ends at each point, drawn as a faint band. */
  band?: [number, number, number][]
  dashed?: boolean
  tip: (x: number, y: number) => string
}

/** Lines against years since each one's start, on one axis: an index (start = 100) or a share. */
export function AnalogChart({ lines, format, xLabel }: { lines: AnalogLine[]; format: (y: number) => string; xLabel: string }) {
  const xs = lines.flatMap((l) => l.points.map((p) => p[0]))
  const ys = lines.flatMap((l) => [...l.points.map((p) => p[1]), ...(l.band ?? []).map((b) => b[2])])
  const x0 = Math.min(0, ...xs)
  const x1 = Math.max(x0 + 1, ...xs)
  const ticks = niceTicks(Math.max(1e-9, ...ys) * 1.04)
  const top = ticks[ticks.length - 1]
  const X = (x: number) => ((x - x0) / (x1 - x0)) * W
  const Y = (y: number) => H - (Math.max(0, Math.min(y, top)) / top) * H
  const step = niceTicks(x1 - x0, 5)[1] ?? 1
  const xTicks: number[] = []
  for (let t = Math.ceil(x0 / step) * step; t <= x1 + 1e-9; t += step) xTicks.push(Number(t.toPrecision(10)))
  const d = (pts: [number, number][]) => pts.map(([x, y], i) => `${i ? "L" : "M"}${X(x).toFixed(2)},${Y(y).toFixed(2)}`).join("")
  return (
    <div>
      <div className="relative h-52">
        <svg viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none" aria-hidden className="absolute inset-0 size-full overflow-visible">
          {ticks.map((t) => (
            <line key={t} x1="0" x2={W} y1={Y(t)} y2={Y(t)} stroke={t ? "var(--line)" : "var(--line-strong)"} vectorEffect="non-scaling-stroke" />
          ))}
          {lines.map((l) =>
            l.band && l.band.length > 1 ? (
              <path
                key={`${l.id}-band`}
                d={`${d(l.band.map(([x, , hi]) => [x, hi]))}L${[...l.band]
                  .reverse()
                  .map(([x, lo]) => `${X(x).toFixed(2)},${Y(lo).toFixed(2)}`)
                  .join("L")}Z`}
                fill={l.color}
                fillOpacity="0.12"
              />
            ) : null,
          )}
          {lines.map((l) =>
            l.points.length > 1 ? (
              <path
                key={l.id}
                d={d(l.points)}
                fill="none"
                stroke={l.color}
                strokeWidth="2"
                strokeDasharray={l.dashed ? "5 4" : undefined}
                strokeLinejoin="round"
                vectorEffect="non-scaling-stroke"
              />
            ) : null,
          )}
        </svg>
        {ticks.slice(1).map((t) => (
          <span
            key={t}
            className="num pointer-events-none absolute left-0 -translate-y-full pb-0.5 text-[10.5px] text-ink-3"
            style={{ top: `${(Y(t) / H) * 100}%` }}
          >
            {format(t)}
          </span>
        ))}
        {lines.flatMap((l) =>
          l.points.map(([x, y]) => (
            <span
              key={`${l.id}-${x}`}
              tabIndex={0}
              role="img"
              aria-label={l.tip(x, y)}
              data-tip={l.tip(x, y)}
              className="absolute size-2 -translate-x-1/2 -translate-y-1/2 rounded-full ring-2 ring-card outline-none focus-visible:ring-ring/50"
              style={{ left: `${(X(x) / W) * 100}%`, top: `${(Y(y) / H) * 100}%`, background: l.color }}
            />
          )),
        )}
      </div>
      <div className="num relative mt-1 h-4 text-[10.5px] text-ink-3">
        {xTicks.map((t) => (
          <span key={t} className="absolute -translate-x-1/2" style={{ left: `${(X(t) / W) * 100}%` }}>
            {t}
          </span>
        ))}
      </div>
      <p className="mt-1 text-center text-[11px] text-ink-3">{xLabel}</p>
    </div>
  )
}
