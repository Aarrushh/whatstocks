/** The panels of "Will the bet pay off?" that show the ledger itself: the funnel, how solid each curve is, the four
 * pillars, the open-weight releases, the analogs, the thresholds and the sources. Every figure is Python's; these
 * only lay them out. */
import { useState } from "react"
import { ArrowUpRight } from "lucide-react"
import { CATEGORICAL, CategoryBar, Spark, type Segment } from "@/components/charts"
import { AnalogChart, type AnalogLine } from "@/components/bet-chart"
import { Empty, Legend, Move, Segmented, StateMark, SubHead, Tag, TipIcon, type LegendItem } from "@/components/kit"
import { cn } from "@/lib/utils"
import { DASH, longDate, pct, plural, signed, webUrl } from "@/lib/format"
import { STATE_WORD, figure, num } from "@/lib/bet"
import type { Go } from "@/lib/hooks"
import type { Bet, BetAnalogLine, BetFeeds, BetFigure, BetIndicator, BetRow, GradeMix } from "@/lib/types"

const fin = (x: number | null | undefined): x is number => typeof x === "number" && Number.isFinite(x)

export const GRADES = ["filed", "company", "press", "estimate"] as const
type Grade = (typeof GRADES)[number]

/** Grades from solid to soft, as one ink from strong to faint: the grade is an order, not a category. */
export const GRADE_COLOR: Record<Grade, string> = {
  filed: "color-mix(in oklab, var(--foreground) 82%, var(--card))",
  company: "color-mix(in oklab, var(--foreground) 58%, var(--card))",
  press: "color-mix(in oklab, var(--foreground) 36%, var(--card))",
  estimate: "color-mix(in oklab, var(--foreground) 18%, var(--card))",
}
const GRADE_LABEL: Record<Grade, string> = { filed: "Filed or fetched", company: "Company", press: "Press", estimate: "Estimate" }
export const GRADE_LEGEND: LegendItem[] = GRADES.map((g) => ({ label: GRADE_LABEL[g], kind: "box", color: GRADE_COLOR[g] }))
const GRADE_ABOUT =
  "Filed: in a filing, or fetched from FRED, EDGAR or prices. Company: stated by the company. Press: reported by the press. Estimate: worked out for the ledger, with its reasoning."

export function mixSegments(mix: GradeMix): Segment[] {
  return GRADES.map((g) => ({ id: g, label: GRADE_LABEL[g], value: mix[g] ?? 0, color: GRADE_COLOR[g], tip: `${GRADE_LABEL[g]}: ${pct(mix[g] ?? 0, 0)}` }))
}

/** Links to the pages behind a figure, by their site's name. Only web addresses become links. */
export function SourceLinks({ urls, max = 3, className }: { urls: string[]; max?: number; className?: string }) {
  const links = [...new Set(urls.map(webUrl).filter((u): u is string => !!u))]
  if (!links.length) return <span className={cn("text-xs text-ink-3", className)}>{DASH}</span>
  const host = (u: string) => {
    try {
      return new URL(u).hostname.replace(/^www\./, "")
    } catch {
      return "source"
    }
  }
  // Two pages on one site are told apart by the end of their address.
  const repeated = (u: string) => links.filter((v) => host(v) === host(u)).length > 1
  const name = (u: string) => {
    if (!repeated(u)) return host(u)
    const tail = u.replace(/[?#].*$/, "").replace(/\/+$/, "").split("/").pop() ?? ""
    return `${host(u)} · ${tail.length > 16 ? `${tail.slice(0, 15)}…` : tail}`
  }
  return (
    <span className={cn("inline-flex flex-wrap items-center gap-x-2 gap-y-0.5 text-xs text-ink-3", className)}>
      {links.slice(0, max).map((u) => (
        <a
          key={u}
          href={u}
          target="_blank"
          rel="noopener noreferrer"
          data-tip={u}
          className="inline-flex max-w-[12rem] items-center gap-0.5 rounded-sm underline decoration-line-strong underline-offset-2 outline-none transition-colors duration-150 hover:text-foreground hover:decoration-ink-3 focus-visible:ring-2 focus-visible:ring-ring/50"
        >
          <span className="truncate">{name(u)}</span>
          <ArrowUpRight className="size-3 shrink-0" aria-hidden />
        </a>
      ))}
      {links.length > max && <span data-tip={links.slice(max).join("\n")}>+{links.length - max}</span>}
    </span>
  )
}

const gradeWord = (g: string) => (g === "fetched" ? "fetched" : g)

/** A figure in its unit. Its period, grade and any range across sources go in the tip. */
function Fig({ f, unit, className }: { f: BetFigure | null | undefined; unit: string; className?: string }) {
  if (!f) return <span className={cn("num text-ink-3", className)}>{DASH}</span>
  const text = f.word ?? figure(f.figure, unit)
  const range = fin(f.low) && fin(f.high) && (f.low !== f.figure || f.high !== f.figure) ? `sources range ${figure(f.low, unit)} to ${figure(f.high, unit)}` : null
  const tip = [`${text}, ${f.period}`, range, `${gradeWord(f.grade)}${f.mine ? ", your own figure" : ""}`].filter(Boolean).join(" · ")
  return (
    <span data-tip={tip} className={cn("num whitespace-nowrap", className)}>
      {text}
    </span>
  )
}

/** An indicator's reading against its amber and red levels, on the indicator's own scale. Nothing without levels. */
export function IndicatorScale({ ind, className }: { ind: BetIndicator; className?: string }) {
  const amber = fin(ind.amber) ? ind.amber : null
  const red = fin(ind.red) ? ind.red : null
  if (!fin(ind.reading) || (amber === null && red === null)) return null
  const values = [ind.reading, ...(amber !== null ? [amber] : []), ...(red !== null ? [red] : [])]
  const span = Math.max(...values) - Math.min(...values)
  const pad = span * 0.2 || Math.abs(ind.reading) * 0.2 || 1
  const lo = Math.min(...values) - pad
  const hi = Math.max(...values) + pad
  const at = (v: number) => ((v - lo) / (hi - lo)) * 100
  const zone = (from: number, to: number, color: string) => (
    <span
      aria-hidden
      className="absolute top-1/2 h-1.5 -translate-y-1/2"
      style={{ left: `${at(Math.min(from, to))}%`, width: `${Math.abs(at(to) - at(from))}%`, background: color }}
    />
  )
  const warn = "color-mix(in oklab, var(--warn) 30%, transparent)"
  const neg = "color-mix(in oklab, var(--neg) 30%, transparent)"
  const worse = ind.direction === "up" ? "higher is worse" : ind.direction === "down" ? "lower is worse" : null
  const tip = [
    `Reading ${figure(ind.reading, ind.unit)}`,
    amber !== null ? `amber at ${figure(amber, ind.unit)}` : null,
    red !== null ? `red at ${figure(red, ind.unit)}` : null,
    worse,
  ]
    .filter(Boolean)
    .join(" · ")
  return (
    <span data-tip={tip} className={cn("relative block h-3.5 min-w-16", className)}>
      <span aria-hidden className="absolute inset-x-0 top-1/2 h-px bg-line-strong" />
      {ind.direction === "up" && amber !== null && zone(amber, red ?? hi, warn)}
      {ind.direction === "up" && red !== null && zone(red, hi, neg)}
      {ind.direction === "down" && amber !== null && zone(red ?? lo, amber, warn)}
      {ind.direction === "down" && red !== null && zone(lo, red, neg)}
      {amber !== null && <span aria-hidden className="absolute top-0 h-full w-[2px] -translate-x-1/2 rounded-full bg-warn" style={{ left: `${at(amber)}%` }} />}
      {red !== null && <span aria-hidden className="absolute top-0 h-full w-[2px] -translate-x-1/2 rounded-full bg-neg" style={{ left: `${at(red)}%` }} />}
      <span
        aria-hidden
        className="absolute top-1/2 size-2 -translate-x-1/2 -translate-y-1/2 rounded-full bg-foreground ring-2 ring-card"
        style={{ left: `${at(ind.reading)}%` }}
      />
      <span className="sr-only">{tip}</span>
    </span>
  )
}

/** The legend under every indicator scale. */
export const SCALE_LEGEND: LegendItem[] = [
  { label: "Reading", kind: "dot", color: "var(--foreground)" },
  { label: "Amber level", kind: "tick", color: "var(--warn)" },
  { label: "Red level", kind: "tick", color: "var(--neg)" },
]

export function Funnel({ bet }: { bet: Bet }) {
  const { layers, leakage } = bet.panels.funnel
  return (
    <div className="flex flex-col gap-4">
      {layers.map((layer) => (
        <section key={layer.id}>
          <SubHead>{layer.label}</SubHead>
          <ul className="mt-1 divide-y divide-line">
            {layer.measures.map((m) => (
              <li key={`${m.series}.${m.entity}`} className="grid grid-cols-[minmax(0,1fr)_auto] items-baseline gap-x-3 py-1.5">
                <span className="min-w-0 text-[13px]">{m.label}</span>
                <Fig f={m.now} unit={m.unit} className="text-right text-[13px] font-medium" />
                <span className="num col-span-full text-[11px] leading-relaxed text-ink-3">
                  {m.now ? `${m.now.period} · ${gradeWord(m.now.grade)}` : "no figure yet"}
                  {m.before && (
                    <>
                      {" · before: "}
                      <Fig f={m.before} unit={m.unit} className="text-ink-2" /> ({m.before.period})
                    </>
                  )}
                  {m.year_ago && (
                    <>
                      {" · a year before: "}
                      <Fig f={m.year_ago} unit={m.unit} className="text-ink-2" /> ({m.year_ago.period})
                    </>
                  )}
                </span>
              </li>
            ))}
          </ul>
        </section>
      ))}
      {leakage.length > 0 && (
        <section>
          <SubHead>Between the layers</SubHead>
          <ul className="mt-1 divide-y divide-line">
            {leakage.map((l) => (
              <li key={l.id} className="grid grid-cols-[minmax(0,1fr)_auto] items-baseline gap-x-3 py-1.5">
                <span className="min-w-0 text-[13px]">{l.label}</span>
                <span className="num text-right text-[13px] font-medium">{fin(l.ratio) ? pct(l.ratio, 1) : DASH}</span>
                <span className="num col-span-full text-[11px] leading-relaxed text-ink-3">
                  {l.of && l.per
                    ? `${l.of.word ?? figure(l.of.figure, l.unit)} of ${l.per.word ?? figure(l.per.figure, l.unit)} (${
                        l.of.period === l.per.period ? l.of.period : `${l.of.period} and ${l.per.period}`
                      })`
                    : "no two figures close enough in time yet"}
                  {l.before && ` · before: ${pct(l.before.ratio, 1)} (${l.before.period})`}
                </span>
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  )
}

export function Grades({ bet }: { bet: Bet }) {
  const g = bet.panels.grades
  const curves = [
    { id: "need", label: "Capex-payback need", mix: g.need },
    { id: "demand", label: "End-user demand", mix: g.demand },
  ]
  const judgmentLabels: Record<string, string> = { need: "The need", demand: "Demand", valuation: "The valuation target" }
  return (
    <div className="flex flex-col gap-4">
      <div className="grid grid-cols-[8rem_minmax(0,1fr)] items-center gap-x-3 gap-y-2.5 text-xs">
        {curves.map((c) => (
          <div key={c.id} className="contents">
            <span className="text-ink-2">{c.label}</span>
            {Object.keys(c.mix).length ? <CategoryBar segments={mixSegments(c.mix)} /> : <span className="text-ink-3">no weight yet</span>}
          </div>
        ))}
      </div>
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
        <Legend items={GRADE_LEGEND} />
        <TipIcon text={GRADE_ABOUT} />
      </div>
      <div className="relative -mx-1 overflow-x-auto px-1">
        <table className="w-full min-w-[22rem] text-[13px]">
          <thead>
            <tr className="text-[11px] text-ink-3">
              <th className="pb-1.5 text-left font-normal">Demand tier</th>
              <th className="pb-1.5 text-right font-normal">Share of demand</th>
              <th className="pb-1.5 pl-4 text-left font-normal">Rests on</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-line">
            {g.tiers.map((t) => (
              <tr key={t.id}>
                <th scope="row" className="py-1.5 pr-3 text-left font-normal">
                  {t.label}
                </th>
                <td className="num py-1.5 text-right">{pct(t.share, 0)}</td>
                <td className="w-2/5 py-1.5 pl-4">
                  {Object.keys(t.grades).length ? <CategoryBar segments={mixSegments(t.grades)} /> : <span className="text-xs text-ink-3">no figures yet</span>}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="flex flex-col gap-2">
        {Object.entries(g.judgments)
          .filter(([, labels]) => labels.length)
          .map(([curve, labels]) => (
            <p key={curve} className="text-xs leading-relaxed text-ink-2">
              <span className="text-foreground">{judgmentLabels[curve] ?? curve}</span> also rests on {plural(labels.length, "judgment")}:{" "}
              {labels.join("; ")}.
            </p>
          ))}
      </div>
    </div>
  )
}

function RowTable({ row }: { row: BetRow }) {
  return (
    <div>
      <div className="flex items-center gap-1.5">
        <SubHead className="text-foreground">{row.label}</SubHead>
        {row.derived && <Tag className="h-4 px-1 text-[10px]">worked out</Tag>}
        {row.about && <TipIcon text={row.about} />}
      </div>
      {row.entities.length ? (
        <ul className="mt-1 divide-y divide-line">
          {row.entities.map((e) => (
            <li key={e.id} className="grid grid-cols-[minmax(0,1fr)_auto_auto] items-center gap-x-3 py-1 text-[13px]">
              <span className="min-w-0 truncate">{e.label}</span>
              {e.history.length > 1 ? (
                <span data-tip={e.history.map(([p, v]) => `${p}: ${figure(v, row.unit)}`).join("\n")}>
                  <Spark values={e.history.map(([, v]) => v)} className="h-5 w-16" />
                </span>
              ) : (
                <span />
              )}
              <span className="flex flex-col items-end">
                <Fig f={e} unit={row.unit} />
                <span className="num text-[10.5px] text-ink-3">
                  {e.period} · {gradeWord(e.grade)}
                </span>
              </span>
            </li>
          ))}
        </ul>
      ) : (
        <p className="mt-1 text-xs text-ink-3">No figures yet.</p>
      )}
    </div>
  )
}

export function Pillar({ bet, id, go }: { bet: Bet; id: string; go: Go }) {
  const pillar = bet.panels.pillars.find((p) => p.id === id)
  if (!pillar) return null
  const inds = pillar.indicators.map((i) => bet.signals.indicators[i]).filter((i): i is BetIndicator => !!i)
  return (
    <div className="flex flex-col gap-4">
      {inds.length > 0 && (
        <ul className="-mx-1.5 flex flex-col">
          {inds.map((ind) => (
            <li key={ind.id}>
              <button
                type="button"
                onClick={() => go("bet", ind.id)}
                data-tip={`${STATE_WORD[ind.state]}: ${ind.text}`}
                className="grid w-full grid-cols-[auto_minmax(0,1fr)_auto] items-center gap-x-2 rounded-md px-1.5 py-1 text-left text-[13px] outline-none transition-colors duration-150 hover:bg-card-2 focus-visible:ring-2 focus-visible:ring-ring/50"
              >
                <StateMark state={ind.state} />
                <span className="min-w-0 truncate">{ind.label}</span>
                <span className="num text-xs text-ink-2">{fin(ind.reading) ? figure(ind.reading, ind.unit) : STATE_WORD[ind.state]}</span>
              </button>
            </li>
          ))}
        </ul>
      )}
      {[...pillar.derived, ...pillar.rows].map((row) => (
        <RowTable key={row.id} row={row} />
      ))}
    </div>
  )
}

export function Releases({ bet }: { bet: Bet }) {
  const r = bet.releases
  const items = [...r.items].sort((a, b) => (a.released < b.released ? 1 : -1))
  const after = r.after[r.after.length - 1]
  const usage = items[0]?.adoption ?? []
  const adoptionCell = (unit: string, x: number | null | undefined) =>
    !fin(x) ? (
      <span className="num text-ink-3">{DASH}</span>
    ) : unit === "pct" ? (
      // A share moves in points; Python gives the difference of two percentages.
      <span className="num">{signed(x / 100, 1, " pts")}</span>
    ) : (
      <Move value={x} className="justify-end" />
    )
  return (
    <div className="flex flex-col gap-3">
      <div className="relative -mx-1 overflow-x-auto px-1">
        <table className="w-full min-w-[36rem] text-[13px]">
          <thead>
            <tr className="align-bottom text-[11px] text-ink-3">
              <th className="pb-1.5 text-left font-normal">Release</th>
              <th className="pb-1.5 pl-3 text-right font-normal">AI basket</th>
              <th className="pb-1.5 pl-3 text-right font-normal">Hyperscalers</th>
              <th className="pb-1.5 pl-3 text-right font-normal">World index</th>
              {usage.map((u) => (
                <th key={`${u.series}.${u.entity}`} data-tip={u.label} className="max-w-[8.5rem] pb-1.5 pl-3 text-right font-normal">
                  {u.label.split(":")[0]}, {after} days
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-line">
            {items.map((it) => {
              const link = webUrl(it.source) ?? webUrl(it.press)
              return (
                <tr key={it.id}>
                  <th scope="row" className="py-1.5 pr-3 text-left font-normal">
                    {link ? (
                      <a
                        href={link}
                        target="_blank"
                        rel="noopener noreferrer"
                        data-tip={link}
                        className="rounded-sm underline decoration-line-strong underline-offset-2 outline-none transition-colors duration-150 hover:decoration-ink-3 focus-visible:ring-2 focus-visible:ring-ring/50"
                      >
                        {it.name}
                      </a>
                    ) : (
                      it.name
                    )}
                    <span className="num block text-[11px] text-ink-3">
                      {it.lab} · {longDate(it.released)}
                    </span>
                  </th>
                  <td className="py-1.5 pl-3 text-right" data-tip={it.market ? `${it.market.from} to ${it.market.to}` : "no prices for these days"}>
                    <Move value={it.market?.ai} className="justify-end" />
                  </td>
                  <td className="py-1.5 pl-3 text-right">
                    <Move value={it.market?.hyperscalers} className="justify-end" />
                  </td>
                  <td className="py-1.5 pl-3 text-right">
                    <Move value={it.market?.world} className="justify-end" />
                  </td>
                  {usage.map((u) => {
                    const own = it.adoption.find((a) => a.series === u.series && a.entity === u.entity)
                    return (
                      <td key={`${u.series}.${u.entity}`} className="py-1.5 pl-3 text-right">
                        {adoptionCell(u.unit, own?.change[String(after)])}
                      </td>
                    )
                  })}
                </tr>
              )
            })}
          </tbody>
          <tfoot>
            <tr className="border-t border-line-strong">
              <th scope="row" className="py-1.5 pr-3 text-left text-xs font-medium">
                Average
                <span className="num block text-[11px] font-normal text-ink-3">{plural(r.average.market.ai?.n ?? 0, "release")}</span>
              </th>
              {(["ai", "hyperscalers", "world"] as const).map((k) => (
                <td key={k} className="py-1.5 pl-3 text-right">
                  <Move value={r.average.market[k]?.mean} className="justify-end" />
                </td>
              ))}
              {usage.map((u) => (
                <td key={`${u.series}.${u.entity}`} className="py-1.5 pl-3 text-right">
                  {adoptionCell(u.unit, r.average.adoption[`${u.series}.${u.entity}`]?.[String(after)]?.mean)}
                </td>
              ))}
            </tr>
          </tfoot>
        </table>
      </div>
      <p className="text-xs leading-relaxed text-ink-3">
        Each basket's move over the {r.days} trading days from the day before a release, from prices. Each is shown as it is, with
        nothing taken away. Usage over the {r.after.join(" and ")} days after, from the ledger. The triangles under the hero chart mark
        the same releases.
      </p>
      {r.notes.map((n) => (
        <p key={n} className="text-xs leading-relaxed text-ink-3">
          {n}
        </p>
      ))}
    </div>
  )
}

const lineName = (l: BetAnalogLine) => (l.label === "United States" ? l.series : `${l.series}: ${l.label.toLowerCase()}`)

export function Analogs({ bet }: { bet: Bet }) {
  const ids = Object.keys(bet.analogs.items)
  const [pick, setPick] = useState(ids[0] ?? "")
  const a = bet.analogs.items[pick]
  if (!a) return <Empty>No analogs in the ledger yet.</Empty>
  // Adoption by launch, or an analog of shares only, is drawn in percent; a build-out is drawn indexed to 100.
  const share = a.by === "launch" || a.lines.every((l) => !l.indexed)
  const drawn = a.lines.filter((l) => (share ? !l.indexed && l.unit === "pct" : l.indexed))
  const listed = a.lines.filter((l) => !drawn.includes(l))
  const lines: AnalogLine[] = drawn.map((l, i) => ({
    id: l.id,
    label: lineName(l),
    color: CATEGORICAL[i % CATEGORICAL.length],
    points: l.points,
    tip: (x, y) => `${lineName(l)}: ${share ? `${num(y, 0)}%` : num(y, 0)}, ${num(x, x % 1 ? 1 : 0)} years in${l.start ? ` (${l.start} + ${num(x, 0)})` : ""}`,
  }))
  const ai = bet.analogs.ai_capex
  if (!share && ai.points.length) {
    lines.push({
      id: "ai_capex",
      label: `AI capex placed, from ${bet.analogs.ai_start}`,
      color: "var(--foreground)",
      points: ai.points.map(([x, mid]) => [x, mid]),
      band: ai.points.map(([x, , lo, hi]) => [x, lo, hi]),
      tip: (x, y) => `AI capex placed: ${num(y, 0)}, ${num(x, 0)} years in (${bet.analogs.ai_start} = 100; actual to ${ai.actual_through})`,
    })
  }
  const sources = [...new Set(a.lines.flatMap((l) => l.sources))]
  return (
    <div className="flex flex-col gap-3">
      <div className="no-scrollbar relative -mx-1 overflow-x-auto px-1 py-0.5">
        <Segmented
          label="Analog"
          value={pick}
          options={ids.map((id) => ({ id, label: bet.analogs.items[id].label.replace(/,.*$/, "") }))}
          onChange={setPick}
        />
      </div>
      <p className="text-[13px] leading-relaxed">
        <span className="font-medium">{a.label}.</span> <span className="text-ink-2">{a.shows}</span>
      </p>
      {lines.length ? (
        <>
          <AnalogChart
            lines={lines}
            format={(y) => (share ? `${num(y, 0)}%` : num(y, 0))}
            xLabel={a.by === "launch" ? "Years since each technology launched" : `Years since the build-out began (${a.start}; AI ${bet.analogs.ai_start})`}
          />
          <Legend items={lines.map((l) => ({ label: l.label, kind: "line", color: l.color }))} />
          {!share && <p className="text-xs text-ink-3">Each line is 100 in its first year with a figure, so the shapes compare. The band around AI capex is its low-to-high range.</p>}
        </>
      ) : (
        <Empty>No series for this analog in the ledger yet.</Empty>
      )}
      {listed.length > 0 && (
        <ul className="flex flex-col gap-1 text-xs leading-relaxed text-ink-2">
          {listed.map((l) => (
            <li key={l.id}>
              <span className="text-foreground">{lineName(l)}</span>:{" "}
              {[...l.points]
                .sort((p, q) => p[0] - q[0])
                .map(([x, y]) => `${figure(y, l.unit)} after ${num(x, x % 1 ? 1 : 0)} ${x === 1 ? "year" : "years"}`)
                .join("; ")}
            </li>
          ))}
        </ul>
      )}
      {sources.length > 0 && <SourceLinks urls={sources} max={4} />}
    </div>
  )
}

/** Paths in reading order: adoption pace first, then the crash paths. */
export function pathOrder(bet: Bet) {
  const paths = Object.values(bet.signals.paths)
  return [...paths.filter((p) => p.kind === "adoption"), ...paths.filter((p) => p.kind !== "adoption")]
}

export function Thresholds({ bet, item }: { bet: Bet; item: string | null }) {
  const inds = Object.values(bet.signals.indicators)
  const level = (x: number | null, unit: string) => (fin(x) ? figure(x, unit) : DASH)
  return (
    <div className="relative -mx-1 overflow-x-auto px-1">
      <table className="w-full min-w-[58rem] text-[13px]">
        <thead>
          <tr className="text-[11px] text-ink-3">
            <th className="pb-2 text-left font-normal">Indicator</th>
            <th className="pb-2 pl-3 text-left font-normal">Reading</th>
            <th className="pb-2 pl-3 text-right font-normal">
              <StateMark state="amber" word="Amber at" />
            </th>
            <th className="pb-2 pl-3 text-right font-normal">
              <StateMark state="red" word="Red at" />
            </th>
            <th className="pb-2 pl-4 text-left font-normal">Why this level</th>
            <th className="pb-2 pl-3 text-left font-normal">Sources</th>
          </tr>
        </thead>
        {pathOrder(bet).map((p) => (
          <tbody key={p.id} className="divide-y divide-line">
            <tr>
              <th colSpan={6} scope="colgroup" className="pt-4 pb-1.5 text-left text-xs font-medium text-ink-2">
                {p.label}
              </th>
            </tr>
            {inds
              .filter((i) => i.path === p.id)
              .map((ind) => (
                <tr key={ind.id} id={`ind-${ind.id}`} className={cn("scroll-mt-24 align-top transition-colors duration-150", item === ind.id && "bg-card-2")}>
                  <th scope="row" className="py-2 pr-3 text-left font-normal">
                    <StateMark state={ind.state} word={<span className="font-medium whitespace-normal">{ind.label}</span>} className="items-start [&>svg]:mt-1" />
                    <span className="mt-0.5 block pl-3.5 text-[11px] text-ink-3">
                      {STATE_WORD[ind.state]}
                      {ind.trigger ? "" : " · watched, not a trigger"}
                      {ind.mine ? " · your own level" : ""}
                    </span>
                  </th>
                  <td className="py-2 pl-3">
                    <span className="block max-w-[18rem] leading-snug">{ind.text}</span>
                    <IndicatorScale ind={ind} className="mt-1.5 max-w-[12rem]" />
                    {ind.as_of && <span className="num mt-1 block text-[11px] text-ink-3">as of {ind.as_of}</span>}
                  </td>
                  <td className="num py-2 pl-3 text-right whitespace-nowrap">{level(ind.amber, ind.unit)}</td>
                  <td className="num py-2 pl-3 text-right whitespace-nowrap">{level(ind.red, ind.unit)}</td>
                  <td className="max-w-[24rem] py-2 pl-4 text-xs leading-relaxed text-ink-2">
                    {ind.why}
                  </td>
                  <td className="py-2 pl-3">
                    <SourceLinks urls={ind.sources} max={2} />
                  </td>
                </tr>
              ))}
          </tbody>
        ))}
      </table>
    </div>
  )
}

const feedsText = (f: BetFeeds) =>
  [f.curves ? "the curves" : null, f.indicators.length ? plural(f.indicators.length, "indicator") : null, ...f.panels].filter(Boolean).join(", ") ||
  "nothing yet"

export function SourcesTable({ bet }: { bet: Bet }) {
  const { rows, gaps } = bet.panels.sources
  const [all, setAll] = useState(false)
  const due = rows.filter((r) => r.due.length)
  const ordered = [...due, ...rows.filter((r) => !r.due.length)]
  const first = Math.max(12, due.length)
  const shown = all ? ordered : ordered.slice(0, first)
  return (
    <div className="flex flex-col gap-4">
      <p className="text-xs leading-relaxed text-ink-3">
        {plural(rows.length, "series", "series")}, {due.length} with a newer figure due. A figure falls due one period after the last,
        plus the time it usually takes to publish. Fetched series refresh with each prepare; the rest change in the ledger, by hand or
        with <span className="num">/bet</span>.
      </p>
      <div className="relative -mx-1 overflow-x-auto px-1">
        <table className="w-full min-w-[54rem] text-[13px]">
          <thead>
            <tr className="text-[11px] text-ink-3">
              <th className="pb-2 text-left font-normal">Series</th>
              <th className="pb-2 pl-3 text-left font-normal">Newest figure</th>
              <th className="pb-2 pl-3 text-left font-normal">Cadence</th>
              <th className="pb-2 pl-3 text-left font-normal">Due</th>
              <th className="pb-2 pl-3 text-left font-normal">Feeds</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-line">
            {shown.map((r) => (
              <tr key={r.id} className="align-top">
                <th scope="row" className="py-1.5 pr-3 text-left font-normal">
                  {r.label}
                  <span className="num block text-[11px] text-ink-3">
                    {plural(r.points, "figure")} · {plural(r.entities, "entity", "entities")}
                    {r.fetcher ? ` · fetched from ${r.fetcher}` : ""}
                  </span>
                </th>
                <td className="py-1.5 pl-3">
                  {r.newest ? (
                    <>
                      <Fig f={r.newest} unit={r.unit} />
                      <span className="num block text-[11px] text-ink-3">
                        {r.newest.label} · {r.newest.period} · {gradeWord(r.newest.grade)}
                      </span>
                    </>
                  ) : (
                    <span className="text-ink-3">{DASH}</span>
                  )}
                </td>
                <td className="py-1.5 pl-3 text-xs text-ink-2">{r.closed ? "history only" : r.cadence}</td>
                <td className="py-1.5 pl-3">
                  {r.due.length ? (
                    <span className="flex flex-col gap-0.5">
                      {r.due.map((d) => (
                        <StateMark
                          key={d.id}
                          state="amber"
                          word={
                            <span className="text-xs text-ink-2">
                              {d.label} <span className="num text-ink-3">since {longDate(d.expected)}</span>
                            </span>
                          }
                        />
                      ))}
                    </span>
                  ) : (
                    <span className="text-xs text-ink-3">{r.closed ? DASH : "up to date"}</span>
                  )}
                </td>
                <td className="py-1.5 pl-3 text-xs text-ink-2">{feedsText(r.feeds)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {ordered.length > first && (
        <button
          type="button"
          onClick={() => setAll((x) => !x)}
          className="self-start rounded-md px-1.5 text-xs text-ink-2 underline decoration-line-strong underline-offset-2 outline-none transition-colors duration-150 hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring/50"
        >
          {all ? "Show fewer" : `Show all ${rows.length} series`}
        </button>
      )}
      {gaps.length > 0 && (
        <section>
          <SubHead>Open gaps in the ledger</SubHead>
          <ul className="mt-1.5 divide-y divide-line">
            {gaps.map((g, i) => {
              const where = [g.label, g.name].filter(Boolean).join(", ")
              return (
                // Many gaps have no series or entity, so the place in the list is the key.
                <li key={i} className="py-1.5 text-[13px]">
                  {g.what}
                  <span className="num block text-[11px] text-ink-3">
                    {where ? `${where} · ` : ""}would feed {feedsText(g.feeds)}
                  </span>
                </li>
              )
            })}
          </ul>
        </section>
      )}
    </div>
  )
}
