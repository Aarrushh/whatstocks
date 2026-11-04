/** News & world: today's news read through four questions, for the themes that matter to your money. A theme in
 * the address (#world/oil_gas) highlights its card and keeps only the events that touch it. */
import { useEffect } from "react"
import { EventCard, WatchList } from "@/components/brief"
import { Bullet, HeatGrid, ScaleLegend, Timeline, WeekBars, YouWorld, divergeFill, rampFill, type GridRow } from "@/components/charts"
import { Chip, Empty, HeatDot, Legend, More, PageHeader, Panel, Sources, YOU_WORLD, type PageProps } from "@/components/kit"
import { RippleMap } from "@/components/maps"
import { cn } from "@/lib/utils"
import { heat, pct, plural, prob, pts, RIPPLE_WORD, shortDate } from "@/lib/format"
import type { Go } from "@/lib/hooks"
import type { Model, Ripples, Theme } from "@/lib/types"

const EDGE = { hurt: "var(--neg)", help: "var(--pos)", unclear: "var(--world)" } as const

function ThemeCard({ theme: t, model, go, max, active }: { theme: Theme; model: Model; go: Go; max: number; active: boolean }) {
  return (
    <article
      id={`theme-${t.id}`}
      className={cn("flex scroll-mt-24 flex-col gap-3 rounded-lg p-3.5 ring-1", active ? "bg-card-2 ring-you/50" : "bg-card-2/50 ring-line")}
    >
      <header className="flex items-start justify-between gap-3">
        <h3 className="flex items-center gap-2 text-[13px] font-medium">
          <HeatDot n={t.heat} />
          {t.label}
        </h3>
        <span className="shrink-0 pt-px text-[11px] text-ink-3">{heat(t.heat).words}</span>
      </header>
      <div data-tip={`${t.label}: you ${pct(t.you)}, world index ${pct(t.world)} (${pts(t.you - t.world)})`}>
        <Bullet you={t.you} world={t.world} max={max} />
        <div className="mt-1 flex justify-between text-xs">
          <span className="text-ink-2">
            You <span className="num text-foreground">{pct(t.you)}</span>
          </span>
          <span className="text-ink-3">
            World <span className="num">{pct(t.world)}</span>
          </span>
        </div>
      </div>
      {t.blind && <p className="text-xs text-warn">Blind spot: busy in the news, little of it in your portfolio</p>}
      {t.brief ? (
        <div className="flex flex-col gap-2">
          <p className="text-[13px] leading-relaxed">{t.brief.state}</p>
          <p className="text-[13px] leading-relaxed text-ink-2">
            <span className="text-xs font-medium text-ink-3">For you · </span>
            {t.brief.why_it_matters}
          </p>
          <Sources ids={t.brief.news_ids} news={model.news} />
        </div>
      ) : (
        <p className="text-[13px] text-ink-3">Not covered in today's brief.</p>
      )}
      {t.views.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {t.views.map((v) => (
            <Chip
              key={v.id}
              label={
                <>
                  <span className="num">{v.id}</span> <span className="num text-ink-3">{prob(v.probability)}</span>
                </>
              }
              tip="One of your open views names this theme. Open it."
              onClick={() => go("views", v.id)}
            />
          ))}
        </div>
      )}
      {t.weeks.length > 0 && (
        <div className="mt-auto pt-1">
          <WeekBars weeks={t.weeks} proxy={t.proxy} today={model.date} />
          <p className="mt-1 text-[11px] text-ink-3">
            Last {t.weeks.length} weeks, {t.proxy} against the world index
          </p>
        </div>
      )}
    </article>
  )
}

function RippleList({ ripples, model }: { ripples: Ripples; model: Model }) {
  const label = (id: string) => ripples.nodes.find((n) => n.id === id)?.label ?? model.theme_labels[id] ?? id
  return (
    <ul className="mt-4 flex flex-col gap-2.5 border-t border-line pt-3 text-[13px]">
      {ripples.edges.map((e, i) => (
        <li key={i} className="grid grid-cols-[auto_minmax(0,1fr)] gap-x-2">
          <span aria-hidden className="mt-[7px] size-1.5 rounded-full" style={{ background: EDGE[e.effect] }} />
          <div className="min-w-0">
            <span className="text-foreground">
              {label(e.from)} → {label(e.to)}
            </span>{" "}
            <span className="text-xs text-ink-3">{RIPPLE_WORD[e.effect]}</span>
            <p className="leading-relaxed text-ink-2">{e.why}</p>
            <Sources ids={e.news_ids} news={model.news} className="mt-1" />
          </div>
        </li>
      ))}
    </ul>
  )
}

export function World({ model, item, go }: PageProps) {
  const focus = item && model.themes[item] ? item : null
  const matter = model.matter.map((id) => model.themes[id]).filter((t): t is Theme => !!t)
  const sorted = [...matter].sort((a, b) => b.heat - a.heat || b.you - a.you)
  const max = Math.max(1e-9, ...matter.flatMap((t) => [t.you, t.world])) * 1.05
  const events = model.events
    .map((e, i) => ({ e, n: i + 1 }))
    .filter(({ e }) => !focus || (e.touches?.themes ?? []).includes(focus))
  const others = model.others.map((id) => model.themes[id]).filter((t): t is Theme => !!t)
  const proxies = new Map(model.proxy_heat.rows.map((r) => [r.id, r.proxy]))
  const newsMax = Math.max(1, ...model.news_heat.rows.flatMap((r) => r.counts))
  const label = (id: string) => model.theme_labels[id] ?? id

  useEffect(() => {
    if (focus) document.getElementById(`theme-${focus}`)?.scrollIntoView({ block: "center" })
  }, [focus])

  const proxyRows: GridRow[] = model.proxy_heat.rows.map((r) => ({ id: r.id, label: r.label, sub: r.proxy, cells: r.cells }))
  const newsRows: GridRow[] = model.news_heat.rows.map((r) => ({ id: r.id, label: r.label, cells: r.counts }))
  const cols = model.proxy_heat.cols
  const parity = (cols.length - 1) % 2
  // Every other week gets a date; the one just before "this week" stays quiet so the two labels never touch.
  const partial = cols.length > 0 && cols[cols.length - 1] > model.date
  const showDate = (i: number) => i % 2 === parity && !(partial && i === cols.length - 3)

  return (
    <>
      <PageHeader title="News & world" sub="Today's news, read through four questions, for the themes that matter to your money." />
      {sorted.length > 0 && (
        <div className="no-scrollbar relative -mx-1 mb-3 flex gap-1.5 overflow-x-auto px-1 py-0.5">
          <Chip label="All themes" active={!focus} onClick={() => go("world")} />
          {sorted.map((t) => (
            <Chip
              key={t.id}
              label={t.label}
              count={t.heat}
              active={t.id === focus}
              tip={t.id === focus ? "Show every theme again" : `Keep only the events that touch ${t.label}`}
              onClick={() => go("world", t.id === focus ? null : t.id)}
            />
          ))}
        </div>
      )}

      <Panel
        title="Morning brief"
        sub={model.has_brief ? `${plural(model.events.length, "event")} from today's headlines. Every claim links to its source.` : undefined}
      >
        <p className={cn("max-w-4xl leading-relaxed", model.lead.kind === "summary" ? "text-[14px]" : "text-[13px] text-ink-2")}>
          {model.lead.text}
        </p>
      </Panel>

      <Panel
        className="mt-3"
        title="Themes that matter to you"
        sub="2% or more of your portfolio, named by one of your open views, covered by your AI today, or a blind spot. Busiest first."
      >
        {sorted.length ? (
          <>
            <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
              {sorted.map((t) => (
                <ThemeCard key={t.id} theme={t} model={model} go={go} max={max} active={t.id === focus} />
              ))}
            </div>
            <Legend
              className="mt-3"
              items={[
                ...YOU_WORLD,
                { label: "Week the proxy beat the world index", kind: "box", color: "var(--pos)" },
                { label: "Week it lagged", kind: "box", color: "var(--neg)" },
              ]}
            />
          </>
        ) : (
          <Empty>No theme reaches 2% of your portfolio, and nothing in today's brief touched one.</Empty>
        )}
      </Panel>

      <div className="mt-3 grid grid-cols-1 gap-3 xl:grid-cols-12">
        <Panel
          className="xl:col-span-7"
          title="Ripple map"
          sub="How today's events spread from one theme to another, as your AI traced them from the news. AI build-out sits in the middle when a ripple reaches it."
        >
          {model.ripples && model.ripples.nodes.length > 0 ? (
            <div className="@container">
              {/* The map needs room for its labels; on a narrow screen the list below carries every ripple. */}
              <div className="hidden @min-[30rem]:block">
                <RippleMap ripples={model.ripples} />
                <Legend
                  className="mt-3"
                  items={[
                    { label: "Hurts", kind: "line", color: "var(--neg)" },
                    { label: "Helps", kind: "line", color: "var(--pos)" },
                    { label: "Unclear", kind: "dash", color: "var(--world)" },
                    { label: "A bigger circle is a bigger share of your portfolio", kind: "ring", color: "var(--ink-3)" },
                  ]}
                />
              </div>
              <p className="text-xs text-ink-3 @min-[30rem]:hidden">The map shows on a wider screen. Every ripple is listed here.</p>
              <RippleList ripples={model.ripples} model={model} />
            </div>
          ) : (
            <Empty>No ripples traced today.</Empty>
          )}
        </Panel>
        <Panel
          className="xl:col-span-5"
          title="Things to watch"
          sub="Dates and developments from the news, and deadlines from your own record. The numbered dots are the next 90 days."
        >
          {model.watch.length ? (
            <>
              <Timeline items={model.watch} today={model.date} />
              <div className="mt-4 border-t border-line pt-3">
                <WatchList items={model.watch} model={model} go={go} />
              </div>
            </>
          ) : (
            <Empty>Nothing to watch yet.</Empty>
          )}
        </Panel>
      </div>

      <Panel
        className="mt-3"
        title="Today's events"
        sub="1. What happened · 2. Who pays, who gets paid · 3. What it touches · 4. For or against your views"
        action={focus ? <More onClick={() => go("world")}>{`Only ${label(focus)}: show all`}</More> : undefined}
      >
        {events.length ? (
          <div className="divide-y divide-line">
            {events.map(({ e, n }) => (
              <EventCard key={n} event={e} n={n} model={model} go={go} />
            ))}
          </div>
        ) : (
          <Empty>{focus ? `No event today touches ${label(focus)}.` : model.has_brief ? "No events today." : "No brief yet today."}</Empty>
        )}
      </Panel>

      <div className="mt-3 grid grid-cols-1 gap-3 lg:grid-cols-12">
        <Panel
          className="lg:col-span-6"
          title="Theme proxies against the world index, last 12 weeks"
          sub="Each proxy ETF's weekly return minus the world index's, in your currency. Full colour is 5 points or more."
        >
          {proxyRows.length && cols.length ? (
            <>
              <HeatGrid
                head="Theme"
                cols={cols}
                rows={proxyRows}
                overhang
                colLabel={(c, i) =>
                  c > model.date ? "this week" : showDate(i) ? shortDate(c) : <span className="sr-only">{shortDate(c)}</span>
                }
                fill={(v) => divergeFill(v, 0.05)}
                text={(v) => (v === null ? "no data" : pts(v))}
                tip={(r, c, v) =>
                  `${label(r.id)} (${proxies.get(r.id) ?? ""}), week to ${shortDate(c)}${c > model.date ? " so far" : ""}: ${
                    v === null ? "no prices" : `${pts(v)} against the world index`
                  }`
                }
              />
              <ScaleLegend
                className="mt-3"
                from="Proxy behind, 5 pts"
                to="ahead, 5 pts"
                steps={[-0.05, -0.025, 0, 0.025, 0.05].map((v) => divergeFill(v, 0.05))}
              />
            </>
          ) : (
            <Empty>No proxy prices yet.</Empty>
          )}
        </Panel>
        <Panel
          className="lg:col-span-6"
          title="Events per theme, last 14 days"
          sub="From your evidence log: one count for each event that touched the theme."
        >
          {newsRows.length ? (
            <>
              <HeatGrid
                head="Theme"
                cols={model.news_heat.dates}
                rows={newsRows}
                colLabel={(d) => String(Number(d.slice(8)))}
                fill={(v) => rampFill(v, newsMax, "var(--foreground)", 70)}
                text={(v) => plural(v ?? 0, "event")}
                tip={(r, d, v) => `${label(r.id)}, ${shortDate(d)}: ${plural(v ?? 0, "event")}`}
              />
              <ScaleLegend
                className="mt-3"
                from="0"
                to={plural(newsMax, "event")}
                steps={[0, 0.25, 0.5, 0.75, 1].map((k) => rampFill(k * newsMax, newsMax, "var(--foreground)", 70))}
              />
            </>
          ) : (
            <Empty>No events logged in the last 14 days.</Empty>
          )}
        </Panel>
      </div>

      <div className="mt-3 grid grid-cols-1 gap-3 lg:grid-cols-2">
        <Panel title="Other themes" sub="Under 2% of your portfolio, named by no open view, and not in today's brief.">
          {others.length ? (
            <YouWorld rows={others.map((t) => ({ id: t.id, label: t.label, you: t.you, world: t.world }))} />
          ) : (
            <Empty>None.</Empty>
          )}
        </Panel>
        <Panel
          title="Blind spots"
          sub="Busy in the news this week, where you hold nothing or under a quarter of the world index's share. Where to look, not what to buy."
        >
          {model.blind_spots.length ? (
            <ul className="flex flex-col divide-y divide-line">
              {model.blind_spots.map((b) => (
                <li key={b.id} className="py-2.5 first:pt-0 last:pb-0">
                  <div className="flex items-baseline justify-between gap-3">
                    <span className="font-medium">{b.label}</span>
                    <span className="num text-xs text-ink-3">{plural(b.events, "event")} this week</span>
                  </div>
                  <div className="num mt-0.5 text-xs text-ink-2">
                    you {pct(b.you)} · world index {pct(b.world)}
                  </div>
                  {b.recent.length > 0 && (
                    <ul className="mt-1.5 flex flex-col gap-1 text-[13px] text-ink-2">
                      {b.recent.map((r, i) => (
                        <li key={i} className="leading-relaxed">
                          {r}
                        </li>
                      ))}
                    </ul>
                  )}
                </li>
              ))}
            </ul>
          ) : (
            <Empty>No blind spots this week.</Empty>
          )}
        </Panel>
      </div>
    </>
  )
}
