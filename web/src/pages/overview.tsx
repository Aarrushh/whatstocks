/** Overview: the morning in one screen. Headline numbers, your mix against the world index, the brief, your
 * biggest themes, what to watch, the top events and the latest conflict scan. */
import { CategoryBar, YouWorld, type Segment } from "@/components/charts"
import { EventCard, WatchList } from "@/components/brief"
import { Chip, Cmd, Empty, Legend, More, Move, PageHeader, Panel, Stat, StateMark, SubHead, Ticker, YOU_WORLD, type PageProps } from "@/components/kit"
import { SectorPanel } from "@/components/sectors"
import { PriceChart } from "@/components/price-chart"
import { REGIME_STATE } from "@/lib/bet"
import { DASH, heat, longDate, pct, pts } from "@/lib/format"
import type { Go } from "@/lib/hooks"
import type { Bet, Model, Scan, ScanTotals, Theme } from "@/lib/types"
import { cn } from "@/lib/utils"

const count = (x: number) => String(Math.round(x))

function Lead({ model }: { model: Model }) {
  if (model.lead.kind === "summary") return <p className="text-[14px] leading-relaxed text-foreground">{model.lead.text}</p>
  if (model.lead.kind === "quiet") return <p className="text-[13px] leading-relaxed text-ink-2">{model.lead.text}</p>
  return (
    <p className="text-[13px] leading-relaxed text-ink-2">
      No brief today. Run <Cmd>/morning</Cmd> in Claude Code to have your AI read the news.
    </p>
  )
}

export const SCAN_SEGMENTS = (t: ScanTotals): Segment[] => [
  { id: "hurt", label: "Would hurt", value: t.hurt_share, color: "var(--neg)" },
  { id: "mixed", label: "Mixed", value: t.mixed_share, color: "var(--ink-3)" },
  { id: "help", label: "Would help", value: t.help_share, color: "var(--pos)" },
  {
    id: "rest",
    label: "Not reached",
    value: Math.max(0, 1 - t.hurt_share - t.mixed_share - t.help_share),
    color: "var(--mid)",
  },
]

function ScanSummary({ scan }: { scan: Scan }) {
  const rows = [
    { who: "You", t: scan.totals.you },
    { who: "World index", t: scan.totals.world },
  ]
  return (
    <div>
      <div className="text-[14px] font-medium">{scan.conflict}</div>
      <div className="num mt-0.5 text-[11px] text-ink-3">Scanned {longDate(scan.date)}</div>
      <p className="mt-2 line-clamp-3 text-[13px] leading-relaxed text-ink-2">{scan.summary}</p>
      <div className="mt-4 grid grid-cols-[5.5rem_minmax(0,1fr)] items-center gap-x-3 gap-y-2 text-xs">
        {rows.map(({ who, t }) => (
          <div key={who} className="contents">
            <span className="text-ink-2">{who}</span>
            <CategoryBar segments={SCAN_SEGMENTS(t)} />
          </div>
        ))}
      </div>
      <table className="mt-3 w-full text-xs">
        <thead>
          <tr className="text-[11px] text-ink-3">
            <th className="pb-1 text-left font-normal">
              <span className="sr-only">Who</span>
            </th>
            <th className="pb-1 text-right font-normal">Would hurt</th>
            <th className="pb-1 text-right font-normal">Mixed</th>
            <th className="pb-1 text-right font-normal">Would help</th>
          </tr>
        </thead>
        <tbody>
          {rows.map(({ who, t }) => (
            <tr key={who}>
              <th scope="row" className="py-0.5 text-left font-normal text-ink-2">
                {who}
              </th>
              <td className="num py-0.5 text-right">{pct(t.hurt_share)}</td>
              <td className="num py-0.5 text-right">{pct(t.mixed_share)}</td>
              <td className="num py-0.5 text-right">{pct(t.help_share)}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <Legend
        className="mt-3"
        items={[
          { label: "Would hurt", kind: "box", color: "var(--neg)" },
          { label: "Mixed", kind: "box", color: "var(--ink-3)" },
          { label: "Would help", kind: "box", color: "var(--pos)" },
          { label: "Not reached", kind: "box", color: "var(--mid)" },
        ]}
      />
    </div>
  )
}

/** The bet in one tile: Python's coverage-now and payback readings and the regime, all at your default settings. */
function BetStat({ bet, go }: { bet: Bet; go: Go }) {
  const coverage = bet.signals.indicators.coverage_now?.reading
  const payback = bet.signals.indicators.payback?.reading
  const regime = bet.signals.regime
  const deadline = bet.deadlines[String(bet.signals.at.gpu_life)]
  return (
    <Stat
      label="The bet, coverage now"
      tip="What end users pay for AI ÷ what the build-out needs back, over the last four quarters, at your default settings."
      value={typeof coverage === "number" ? <Ticker value={coverage} format={(x) => `${Math.round(x)}%`} /> : DASH}
      sub={
        <>
          <StateMark state={REGIME_STATE[regime.state]} word={regime.label} className="align-[-1px]" />
          {typeof payback === "number" && ` · payback ${Math.round(payback)}%${deadline ? ` by ${deadline.date.slice(0, 4)}` : ""}`}
        </>
      }
      onClick={() => go("bet")}
    />
  )
}

export function Overview({ model, go }: PageProps) {
  const port = model.performance.returns.portfolio ?? {}
  const world = model.performance.returns.world ?? {}
  const themes = model.theme_order.map((id) => model.themes[id]).filter((t): t is Theme => !!t)
  const tilt = themes.reduce<Theme | null>((best, t) => (!best || t.you - t.world > best.you - best.world ? t : best), null)
  const matter = model.matter.map((id) => model.themes[id]).filter((t): t is Theme => !!t)
  const busiest = [...matter].sort((a, b) => b.heat - a.heat)[0]
  const deadline = model.views.map((v) => v.resolves_by).sort()[0]
  const biggest = [...themes].sort((a, b) => b.you - a.you).slice(0, 6)
  const scan = model.scans[0]
  const lines = model.performance.lines

  return (
    <>
      <PageHeader
        title="Overview"
        sub={`${longDate(model.date)} · shares of your portfolio, valued in ${model.home}, next to a world index fund`}
      />
      <div className={cn("grid grid-cols-2 gap-3 md:grid-cols-3", model.bet ? "xl:grid-cols-6" : "xl:grid-cols-5")}>
        <Stat label="Today" value={<Move value={port["1D"]} count />} sub={<>World index <Move value={world["1D"]} /></>} />
        <Stat
          label="Past year, today's mix"
          tip="Today's holdings at today's weights, replayed over the past year. It is not your actual past return."
          value={<Move value={port["1Y"]} count />}
          sub={<>World index <Move value={world["1Y"]} /></>}
        />
        <Stat
          label="Biggest tilt"
          value={tilt ? <Ticker value={tilt.you - tilt.world} format={(x) => pts(x)} /> : DASH}
          sub={tilt ? `${tilt.label}: ${pct(tilt.you)} against ${pct(tilt.world)}` : "No themes yet"}
          onClick={() => go("exposure")}
        />
        <Stat
          label="News today"
          value={model.has_brief ? <Ticker value={model.events.length} format={count} /> : DASH}
          sub={!model.has_brief ? "No brief yet today" : busiest && busiest.heat > 0 ? `Busiest: ${busiest.label}` : "A quiet day"}
          onClick={() => go("world")}
        />
        <Stat
          label="Open views"
          value={<Ticker value={model.views.length} format={count} />}
          sub={deadline ? `Next deadline ${longDate(deadline)}` : <>Write one with <Cmd>/setup</Cmd></>}
          onClick={() => go("views")}
        />
        {model.bet && <BetStat bet={model.bet} go={go} />}
      </div>

      <div className="mt-3 grid grid-cols-1 gap-3 lg:grid-cols-12">
        <Panel
          className="lg:col-span-8"
          title={model.performance.compare?.length ? `Your mix against the world index and ${model.performance.compare.map((c) => c.name).join(", ")}` : "Your mix against the world index"}
          sub={`In ${model.home}, indexed to the start of the window. Prices cover ${pct(model.performance.coverage, 0)} of your portfolio.`}
        >
          <PriceChart
            series={[
              { key: "you", label: "You (today's mix)", points: lines.portfolio ?? [] },
              { key: "world", label: `World index (${model.benchmark})`, points: lines.world ?? [] },
              ...(model.performance.compare ?? []).map((c) => ({ key: "compare" as const, label: `${c.name} (${c.symbol})`, points: c.line })),
            ]}
          />
        </Panel>
        <Panel className="lg:col-span-4" title="Morning brief" action={<More onClick={() => go("world")}>News &amp; world</More>}>
          <Lead model={model} />
          {matter.length > 0 && (
            <>
              <SubHead className="mt-4">Themes that matter to you today</SubHead>
              <div className="mt-2 flex flex-wrap gap-1.5">
                {matter.map((t) => (
                  <Chip
                    key={t.id}
                    label={t.label}
                    count={t.heat}
                    tip={`${t.label}: ${heat(t.heat).words}. You ${pct(t.you)}, world index ${pct(t.world)}.`}
                    onClick={() => go("world", t.id)}
                  />
                ))}
              </div>
              <p className="mt-2 text-[11px] text-ink-3">Filled dot: two or more events today. Faint: one. Hollow: none.</p>
            </>
          )}
        </Panel>
      </div>

      <SectorPanel model={model} className="mt-3" />

      <div className="mt-3 grid grid-cols-1 gap-3 lg:grid-cols-12">
        <Panel
          className="lg:col-span-7"
          title="Your biggest themes"
          sub="Share of your portfolio, looked through funds, next to a world index fund."
          action={<More onClick={() => go("exposure")}>Exposure</More>}
        >
          {biggest.length ? (
            <>
              <YouWorld
                rows={biggest.map((t) => ({
                  id: t.id,
                  label: t.label,
                  you: t.you,
                  world: t.world,
                  onClick: () => (model.matter.includes(t.id) ? go("world", t.id) : go("exposure")),
                }))}
              />
              <Legend className="mt-3 px-1.5" items={YOU_WORLD} />
            </>
          ) : (
            <Empty>No themes yet.</Empty>
          )}
        </Panel>
        <Panel
          className="lg:col-span-5"
          title="Things to watch"
          action={model.watch.length > 5 ? <More onClick={() => go("world")}>All {model.watch.length}</More> : undefined}
        >
          {model.watch.length ? <WatchList items={model.watch} model={model} go={go} limit={5} /> : <Empty>Nothing to watch yet.</Empty>}
        </Panel>
      </div>

      <div className="mt-3 grid grid-cols-1 gap-3 lg:grid-cols-12">
        <Panel
          className="lg:col-span-7"
          title="Top events today"
          sub="What happened, who pays and who gets paid, and what it touches."
          action={model.events.length > 3 ? <More onClick={() => go("world")}>All {model.events.length} events</More> : undefined}
        >
          {model.events.length ? (
            <div className="divide-y divide-line">
              {model.events.slice(0, 3).map((e, i) => (
                <EventCard key={i} event={e} n={i + 1} model={model} go={go} />
              ))}
            </div>
          ) : (
            <Empty>{model.has_brief ? "No events today." : "No brief yet today."}</Empty>
          )}
        </Panel>
        <Panel
          className="lg:col-span-5"
          title="Latest conflict scan"
          action={scan ? <More onClick={() => go("scenarios", scan.slug)}>Open</More> : undefined}
        >
          {scan ? (
            <ScanSummary scan={scan} />
          ) : (
            <Empty>
              No scans yet. In Claude Code, run <Cmd>/scan</Cmd> with any conflict, for example China blockade of Taiwan, to see
              where it would reach your money.
            </Empty>
          )}
        </Panel>
      </div>
    </>
  )
}
