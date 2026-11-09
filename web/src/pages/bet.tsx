/** "Will the bet pay off?": two models side by side. Model A turns the money invested (capex, and what today's
 * valuations assume) into the revenue it needs back; model B adds up what end users pay for AI, tier by tier, and
 * projects it. Python computes every curve, readout, signal and reach (src/whatstocks/bet/); this page only adds up
 * the pieces you switch on and divides two sums (docs/SPEC.md P2, exception b; lib/bet.ts). An indicator or a path in
 * the address (#bet/cds_crwv, #bet/credit_event) is scrolled to and outlined. */
import { useEffect, useMemo, useState, type ReactNode } from "react"
import { motion, useReducedMotion } from "motion/react"
import { Check } from "lucide-react"
import { BetHero, type HeroLayer } from "@/components/bet-chart"
import { Analogs, Funnel, Grades, IndicatorScale, Pillar, Releases, SCALE_LEGEND, SourcesTable, Thresholds, pathOrder } from "@/components/bet-panels"
import { CATEGORICAL, CategoryBar } from "@/components/charts"
import { Cmd, Empty, Legend, Move, PRESS, PageHeader, Panel, Segmented, StateMark, SubHead, TipIcon, type LegendItem, type PageProps } from "@/components/kit"
import { SCAN_SEGMENTS } from "@/pages/overview"
import { cn } from "@/lib/utils"
import { DASH, dateRange, longDate, pct, signed } from "@/lib/format"
import {
  REGIME_STATE,
  SECONDS_A_YEAR,
  STATE_WORD,
  UNIT_WORDS,
  allOn,
  capexGroups,
  capexParts,
  clockNow,
  curves,
  defaultSettings,
  defaultSwitches,
  figure,
  implied,
  inUnits,
  onlyThis,
  quarterPosition,
  readouts,
  sameSwitches,
  scaled,
  stepLabel,
  stepText,
  switchSizes,
  toggle,
  unitFactor,
  usdB,
  type Curves,
  type Ratio,
  type Settings,
  type SliderId,
  type Switches,
  type Units,
} from "@/lib/bet"
import type { Go } from "@/lib/hooks"
import type { Bet, BetPath, BetReach } from "@/lib/types"

const TITLE = "Will the bet pay off?"
const SLIDERS: SliderId[] = ["gpu_life", "cost_of_capital", "deflation", "value_capture", "labour_share"]
const SLIDER_ABOUT: Record<SliderId, string> = {
  gpu_life: "How many years the chips earn before they are replaced. Shorter means more depreciation each year and an earlier deadline.",
  cost_of_capital:
    "The yearly return investors want on the money tied up. It sets the return-on-capital part of the need, and the valuation target.",
  deflation:
    "How fast the price of AI per token falls each year. Trailing is the pace the ledger measured over the last year. It moves only the projected demand.",
  value_capture: "The share of the productivity gain that AI firms keep as revenue. It moves only the implied figures and the work-hours unit.",
  labour_share: "How much of the budget pool is wages rather than IT spending. It moves only the share of the budget pool.",
}
const REACH_LEGEND: LegendItem[] = [
  { label: "Would hurt", kind: "box", color: "var(--neg)" },
  { label: "Mixed", kind: "box", color: "var(--ink-3)" },
  { label: "Would help", kind: "box", color: "var(--pos)" },
  { label: "Not reached", kind: "box", color: "var(--mid)" },
]

const fin = (x: number | null | undefined): x is number => typeof x === "number" && Number.isFinite(x)
const sameSettings = (a: Settings, b: Settings) => SLIDERS.every((k) => a[k] === b[k])
const scrollTo = (id: string) =>
  (document.getElementById(`ind-${id}`) ?? document.getElementById(`path-${id}`) ?? document.getElementById(`bet-${id}`))?.scrollIntoView({
    block: "start",
  })

export function BetPage({ model, item, go }: PageProps) {
  if (!model.bet) {
    return (
      <>
        <PageHeader title={TITLE} sub="The money going into AI against what end users pay for it." />
        <Panel>
          <Empty>
            This page has no bet data yet. Run <Cmd>/morning</Cmd> in Claude Code, or <Cmd>whatstocks prepare</Cmd> and then{" "}
            <Cmd>whatstocks finish</Cmd>.
          </Empty>
        </Panel>
      </>
    )
  }
  return <BetBody bet={model.bet} item={item} go={go} />
}

function BetBody({ bet, item, go }: { bet: Bet; item: string | null; go: Go }) {
  const base = useMemo(() => ({ s: defaultSettings(bet), sw: defaultSwitches(bet), all: allOn(bet) }), [bet])
  const [s, setS] = useState<Settings>(base.s)
  const [sw, setSw] = useState<Switches>(base.sw)
  const [units, setUnits] = useState<Units>("usd")
  const c = useMemo(() => curves(bet, s, sw), [bet, s, sw])
  const r = useMemo(() => readouts(bet, s, sw), [bet, s, sw])
  const sizes = useMemo(() => switchSizes(bet, s, sw), [bet, s, sw])

  useEffect(() => {
    if (item) scrollTo(item)
  }, [item])
  // A second click on the same link changes no address, so scroll here as well.
  const jump = (id: string) => {
    go("bet", id)
    scrollTo(id)
  }

  const la = bet.last_actual
  const dl = c.deadline.quarter
  const per = units === "usd" ? " a year" : ""
  const inAt = (x: number | null | undefined, q: number) => {
    const f = unitFactor(bet, units, s, q)
    return f === null || !fin(x) ? DASH : inUnits(x * f, units)
  }
  const pieceIndex = Object.fromEntries(bet.demand.pieces.map((p, i) => [p.id, i]))
  const color = (id: string) => CATEGORICAL[(pieceIndex[id] ?? 0) % CATEGORICAL.length]

  const layers: HeroLayer[] = c.layers.map((l) => ({ id: l.id, label: l.label, color: color(l.id), values: scaled(bet, units, s, l.series.rate) }))
  const need = { rate: scaled(bet, units, s, c.need.rate), low: scaled(bet, units, s, c.need.low), high: scaled(bet, units, s, c.need.high) }
  const fdl = unitFactor(bet, units, s, dl)
  const target =
    c.target && fdl !== null
      ? {
          rate: c.target.rate * fdl,
          low: c.target.low * fdl,
          high: c.target.high * fdl,
          tip: `Valuation target: ${inUnits(c.target.rate * fdl, units)}${per} by ${longDate(c.deadline.date)}, range ${inUnits(c.target.low * fdl, units)} to ${inUnits(c.target.high * fdl, units)}. The yearly revenue the switched-on market values need then, at ${s.cost_of_capital}% cost of capital.`,
        }
      : null
  const releases = bet.releases.items
    .map((it) => ({
      id: it.id,
      at: quarterPosition(bet, it.released),
      tip: `${it.name} (${it.lab}), open weights, ${longDate(it.released)}${
        it.market ? `. AI basket ${signed(it.market.ai)}, world index ${signed(it.market.world)} over the next ${bet.releases.days} trading days` : ""
      }`,
    }))
    .filter((x) => x.at >= 0 && x.at <= bet.quarters.length)
  const tipAt = (q: number) =>
    [
      `${bet.quarters[q]}${q > la ? ", projected" : ""}${q === dl ? ", the deadline" : ""}`,
      `Need ${inAt(c.need.rate[q], q)}${per} (${inAt(c.need.low[q], q)} to ${inAt(c.need.high[q], q)})`,
      `Demand ${inAt(c.demand.rate[q], q)}${per} (${inAt(c.demand.low[q], q)} to ${inAt(c.demand.high[q], q)})`,
      ...[...c.layers].reverse().map((l) => `· ${l.label} ${inAt(l.series.rate[q], q)}`),
    ].join("\n")
  const heroLegend: LegendItem[] = [
    ...c.layers.map((l) => ({ label: l.label, kind: "box" as const, color: color(l.id) })),
    { label: "Need", kind: "line", color: "var(--foreground)" },
    { label: "Need range", kind: "box", color: "color-mix(in oklab, var(--foreground) 16%, transparent)" },
    { label: "Gap", kind: "hatch", color: "var(--foreground)" },
    { label: "Projected demand", kind: "dash", color: "var(--ink-2)" },
    ...(target ? [{ label: "Valuation target", kind: "dot" as const, color: "var(--c7)" }] : []),
    { label: "Deadline window", kind: "box", color: "color-mix(in oklab, var(--foreground) 10%, transparent)" },
    { label: "Open-weight release", kind: "tri", color: "var(--ink-2)" },
  ]
  const unitOptions = [
    { id: "usd" as const, label: "$ a year" },
    ...(bet.units.seats !== null ? [{ id: "seats" as const, label: "Seats" }] : []),
    { id: "hours" as const, label: "Work hours" },
  ]
  const deflationWord = stepText("deflation", s.deflation, bet.demand.trailing).toLowerCase()
  const reset = () => {
    setS(base.s)
    setSw(base.sw)
  }

  return (
    <>
      <PageHeader
        title={TITLE}
        sub={
          <>
            What the AI build-out needs back each year (model A, the money invested) against what end users pay for AI (model B,
            adoption). Data to {longDate(bet.date)}.
          </>
        }
        action={
          <div className="flex items-center gap-2">
            <span className="text-xs text-ink-3">Show in</span>
            <Segmented label="Units" value={units} options={unitOptions} onChange={setUnits} />
          </div>
        }
      />

      <div className="grid grid-cols-1 gap-3 lg:grid-cols-12">
        <Regime bet={bet} jump={jump} className="lg:col-span-5" />
        <CashClock clock={bet.clock} className="lg:col-span-7" />
      </div>

      <div className="mt-3 grid grid-cols-1 gap-3 xl:grid-cols-12 xl:items-start">
        <Panel
          id="bet-hero"
          className="xl:col-span-8"
          title="What the build-out needs back, against what end users pay"
          sub={`In ${UNIT_WORDS[units]}, each quarter at a yearly rate: actual to ${bet.quarters[la]}, projected after. The need assumes ${stepText("gpu_life", s.gpu_life)} of GPU life and ${s.cost_of_capital}% cost of capital; projected demand assumes ${deflationWord} price deflation.`}
        >
          <div className="grid grid-cols-1 gap-x-5 gap-y-3 sm:grid-cols-3">
            <Readout
              label="Coverage now"
              ratio={r.coverage}
              sub={`Demand ÷ need, ${bet.quarters[Math.max(0, la - 3)]} to ${bet.quarters[la]}`}
              tip="What end users paid over the last four quarters, divided by what the switched-on capex needed back over them. The range divides low demand by the high need, and high demand by the low need."
            />
            <Readout
              label="Payback by the deadline"
              ratio={r.payback}
              sub={`Each added up from ${bet.quarters[0]} to ${bet.quarters[dl]}`}
              tip={`Demand ÷ need, each added up from ${bet.quarters[0]} to the deadline, ${longDate(c.deadline.date)}: when the switched-on chips must have earned back their cost at ${s.cost_of_capital}%. At 100% they just do.`}
            />
            <Readout
              label="Against the valuation target"
              ratio={r.valuation}
              sub={c.target ? `Demand at the deadline ÷ ${usdB(c.target.rate)} a year` : "Switch on a valuation group to see it"}
              tip="Projected demand at the deadline, divided by the yearly revenue that today's market values of the switched-on groups need by then. At 100% demand meets it."
            />
          </div>
          <BetHero
            className="mt-5"
            quarters={bet.quarters}
            lastActual={la}
            layers={layers}
            need={need}
            target={target}
            deadline={{ quarter: dl, band: c.deadline.band, label: `Deadline ${longDate(c.deadline.date)}` }}
            releases={releases}
            format={(x) => inUnits(x, units)}
            tip={tipAt}
          />
          <Legend className="mt-2" items={heroLegend} />
          <Implied bet={bet} s={s} c={c} la={la} />
          <HeroNotes bet={bet} />
        </Panel>

        <Panel
          id="bet-controls"
          className="xl:col-span-4"
          title="Your assumptions"
          sub="Each change redraws the curves and readouts. Python worked out every step; the page adds up what you switch on."
          action={
            <>
              <SmallButton disabled={sameSettings(s, base.s) && sameSwitches(sw, base.sw)} onClick={reset}>
                Defaults
              </SmallButton>
              <SmallButton disabled={sameSwitches(sw, base.all)} onClick={() => setSw(base.all)}>
                All on
              </SmallButton>
            </>
          }
        >
          {/* Two columns while the panel is wide (under 1280px it spans the page), one beside the hero. */}
          <div className="grid grid-cols-1 gap-x-8 md:grid-cols-2 xl:grid-cols-1">
            <div className="flex flex-col gap-3">
              {SLIDERS.map((id) => (
                <SliderRow key={id} bet={bet} id={id} value={s[id]} onChange={(v) => setS((p) => ({ ...p, [id]: v }) as Settings)} />
              ))}
            </div>
            <div>
              <p className="mt-4 border-t border-line pt-3 text-[11px] leading-snug text-ink-3 md:mt-0 md:border-0 md:pt-0 xl:mt-4 xl:border-t xl:pt-3">
                Each switch shows what it adds at the deadline, {longDate(c.deadline.date)}, in {UNIT_WORDS[units]}. Only keeps that
                one switch on in its group.
              </p>
              <SwitchGroupBox title="Model A: the money invested">
                <SubHead>Who spends</SubHead>
                {capexGroups(bet).map((g) => (
                  <Switch
                    key={g}
                    label={bet.capex.pieces.find((p) => p.group === g)?.label.split(":")[0] ?? g}
                    on={!!sw.capex[g]}
                    size={inAt(sizes.capex[g], dl)}
                    onToggle={() => setSw(toggle(sw, "capex", g))}
                    onOnly={() => setSw(onlyThis(sw, "capex", g))}
                  />
                ))}
                <SubHead className="mt-2">What it must earn back</SubHead>
                {capexParts(bet).map((k) => (
                  <Switch
                    key={k}
                    label={bet.capex.pieces.find((p) => p.part === k)?.label.split(": ")[1] ?? k}
                    on={!!sw.parts[k]}
                    size={inAt(sizes.parts[k], dl)}
                    onToggle={() => setSw(toggle(sw, "parts", k))}
                    onOnly={() => setSw(onlyThis(sw, "parts", k))}
                  />
                ))}
                <SubHead className="mt-2">What valuations assume</SubHead>
                {Object.entries(bet.valuation.groups).map(([id, g]) => (
                  <Switch
                    key={id}
                    label={g.label}
                    on={!!sw.valuation[id]}
                    size={inAt(sizes.valuation[id], dl)}
                    onToggle={() => setSw(toggle(sw, "valuation", id))}
                    onOnly={() => setSw(onlyThis(sw, "valuation", id))}
                  />
                ))}
              </SwitchGroupBox>
              <SwitchGroupBox title="Model B: adoption">
                <SubHead>Who pays, best quality first</SubHead>
                {bet.demand.pieces.map((p) => (
                  <Switch
                    key={p.id}
                    label={p.tier ? `${p.tier}. ${p.label}` : p.label}
                    swatch={color(p.id)}
                    on={!!sw.demand[p.id]}
                    size={inAt(sizes.demand[p.id], dl)}
                    onToggle={() => setSw(toggle(sw, "demand", p.id))}
                    onOnly={() => setSw(onlyThis(sw, "demand", p.id))}
                  />
                ))}
              </SwitchGroupBox>
            </div>
          </div>
        </Panel>
      </div>

      <Section
        title="Signals"
        sub={`Four ways it could crash, and the pace of adoption. Each indicator has an amber and a red level, set in the ledger. The states are at your default settings: ${stepText("gpu_life", bet.signals.at.gpu_life)} of GPU life, ${bet.signals.at.cost_of_capital}% cost of capital, ${stepText("deflation", bet.signals.at.deflation, bet.demand.trailing).toLowerCase()} price deflation.`}
      >
        <div className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-3">
          {pathOrder(bet).map((p) => (
            <PathCard key={p.id} bet={bet} path={p} active={item === p.id} jump={jump} />
          ))}
          <Panel title="How to read the cards">
            <div className="flex flex-col gap-3 text-xs text-ink-2">
              <div className="flex flex-wrap gap-x-3 gap-y-1">
                {(["clear", "amber", "red", "no_data"] as const).map((st) => (
                  <StateMark key={st} state={st} word={STATE_WORD[st]} />
                ))}
              </div>
              <Legend items={SCALE_LEGEND} />
              <p className="leading-relaxed text-ink-3">
                On each scale the shaded side is the worse one. Pick an indicator to see its levels, the reason for them and its
                sources, in the table further down.
              </p>
              <Legend items={REACH_LEGEND} />
              <p className="leading-relaxed text-ink-3">
                Where a path would reach: the share of your portfolio, and of the world index, in themes the path would hurt or help.
                Past sell-offs replay today's mix.
              </p>
            </div>
          </Panel>
        </div>
      </Section>

      <Section title="Adoption" sub="How many use AI, how much, and how many pay; and how solid each curve is.">
        <div className="grid grid-cols-1 gap-3 lg:grid-cols-12">
          <Panel
            id="bet-funnel"
            className="lg:col-span-6"
            title="The adoption funnel"
            sub="Breadth, intensity and monetization: the newest figure, the one before it, and one from a year before."
          >
            <Funnel bet={bet} />
          </Panel>
          <Panel
            id="bet-grades"
            className="lg:col-span-6"
            title="How solid each curve is"
            sub="The share of each curve, at your default settings, that rests on each grade of source."
          >
            <Grades bet={bet} />
          </Panel>
        </div>
      </Section>

      <Section title="The four pillars" sub="The figures behind each part of the question, newest first, with their history.">
        <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
          {bet.panels.pillars.map((p) => (
            <Panel key={p.id} id={`bet-${p.id}`} title={p.label}>
              <Pillar bet={bet} id={p.id} go={go} />
            </Panel>
          ))}
        </div>
      </Section>

      <Section title="Open weights and history" sub="What each open-weight release did to prices and usage, and past build-outs next to this one.">
        <div className="grid grid-cols-1 gap-3 xl:grid-cols-12">
          <Panel id="bet-releases" className="xl:col-span-7" title="Open-weight releases">
            <Releases bet={bet} />
          </Panel>
          <Panel id="bet-analogs" className="xl:col-span-5" title="Analogs">
            <Analogs bet={bet} />
          </Panel>
        </div>
      </Section>

      <Section title="Thresholds" sub="Every indicator, its reading, the levels that turn it amber and red, and why.">
        <Panel id="bet-thresholds">
          <Thresholds bet={bet} item={item} />
        </Panel>
      </Section>

      <Section title="Sources" sub="Every series in the ledger, its newest figure, and what is due.">
        <Panel id="bet-sources">
          <SourcesTable bet={bet} />
        </Panel>
      </Section>

      <p className="mt-4 text-xs leading-relaxed text-ink-3">
        To add a figure or change a level, run <Cmd>/bet</Cmd> in Claude Code, or edit <Cmd>my/bet.yaml</Cmd>.{" "}
        <Cmd>whatstocks bet due</Cmd> lists what is due. Your own figures and levels are marked as yours.
      </p>
    </>
  )
}

function Section({ title, sub, children }: { title: string; sub?: string; children: ReactNode }) {
  return (
    <section className="mt-7">
      <h2 className="text-[15px] leading-6 font-semibold tracking-tight">{title}</h2>
      {sub && <p className="mt-0.5 max-w-3xl text-xs leading-relaxed text-ink-3">{sub}</p>}
      <div className="mt-3">{children}</div>
    </section>
  )
}

function Regime({ bet, jump, className }: { bet: Bet; jump: (id: string) => void; className?: string }) {
  const g = bet.signals.regime
  return (
    <div className={cn("flex flex-col justify-center gap-1 rounded-lg bg-card px-4 py-2.5 text-[13px] ring-1 ring-line", className)}>
      <div className="flex flex-wrap items-center gap-x-2 gap-y-0.5">
        <span className="text-xs text-ink-3">Regime</span>
        <StateMark state={REGIME_STATE[g.state]} word={<span className="font-medium">{g.label}</span>} />
        <span className="text-ink-2">{g.about}</span>
      </div>
      {g.because.length > 0 && (
        <div className="flex flex-wrap items-center gap-x-1 text-xs text-ink-3">
          <span>Because of</span>
          {g.because.map((id, i) => (
            <span key={id}>
              <button
                type="button"
                onClick={() => jump(id)}
                className="rounded-sm text-ink-2 underline decoration-line-strong underline-offset-2 outline-none transition-colors duration-150 hover:text-foreground hover:decoration-ink-3 focus-visible:ring-2 focus-visible:ring-ring/50"
              >
                {bet.signals.paths[id]?.label.toLowerCase() ?? id}
              </button>
              {i < g.because.length - 1 ? "," : ""}
            </span>
          ))}
        </div>
      )}
    </div>
  )
}

/** Python's totals since the start of the year, carried forward at the last actual quarter's pace. Modelled. */
function CashClock({ clock, className }: { clock: Bet["clock"]; className?: string }) {
  const reduce = useReducedMotion()
  const [now, setNow] = useState(() => Date.now())
  useEffect(() => {
    const id = window.setInterval(() => setNow(Date.now()), reduce ? 60_000 : 1_000)
    return () => window.clearInterval(id)
  }, [reduce])
  const t = clockNow(clock, now)
  const dollars = (b: number) => `$${Math.round(b * 1e9).toLocaleString("en-US")}`
  const tip = [
    `Modelled, not live. Python's totals from ${longDate(clock.from)} to ${longDate(clock.date)}, then the last actual quarter's pace, at your default switches.`,
    `AI capex runs at ${usdB(clock.capex_per_second * SECONDS_A_YEAR)} a year; end-user demand at ${usdB(clock.demand_per_second * SECONDS_A_YEAR)} a year.`,
  ].join("\n")
  return (
    <div data-tip={tip} className={cn("flex flex-wrap items-center gap-x-6 gap-y-1.5 rounded-lg bg-card px-4 py-2.5 ring-1 ring-line", className)}>
      <span className="text-xs text-ink-3">Since {longDate(clock.from)}, modelled</span>
      <span className="flex flex-col">
        <span className="text-[11px] text-ink-3">AI capex out</span>
        <span className="num text-[15px] leading-5 font-medium">{dollars(t.capex)}</span>
      </span>
      <span className="flex flex-col">
        <span className="text-[11px] text-ink-3">End-user AI demand in</span>
        <span className="num text-[15px] leading-5 font-medium">{dollars(t.demand)}</span>
      </span>
    </div>
  )
}

function Readout({ label, ratio, sub, tip }: { label: string; ratio: Ratio; sub: ReactNode; tip: string }) {
  const range = ratio.low !== null && ratio.high !== null ? `${pct(ratio.low, 0)}${DASH}${pct(ratio.high, 0)}` : null
  return (
    <div className="min-w-0">
      <div className="flex items-center gap-1 text-xs text-ink-2">
        {label}
        <TipIcon text={tip} />
      </div>
      <div className="mt-0.5 flex flex-wrap items-baseline gap-x-2">
        <span className="num text-[26px] leading-8 font-medium tracking-tight">{ratio.mid === null ? DASH : pct(ratio.mid, 0)}</span>
        {range && <span className="num text-xs text-ink-3">range {range}</span>}
      </div>
      <div className="mt-0.5 text-[11px] leading-snug text-ink-3">{sub}</div>
    </div>
  )
}

function HeroNotes({ bet }: { bet: Bet }) {
  const u = bet.demand.usage
  const left = Object.entries(bet.demand.left_out)
  return (
    <ul className="mt-3 flex flex-col gap-1 border-t border-line pt-3 text-xs leading-relaxed text-ink-3">
      {fin(u.growth) && u.since && u.to && (
        <li>
          After {bet.quarters[bet.last_actual]}, demand is usage times the price per token. Usage starts at the yearly pace the ledger
          measured, <span className="num">{signed(u.growth, 0)}</span> ({dateRange(u.since, u.to)}), and slows toward a long-run rate;
          the price changes at the deflation you pick.
        </li>
      )}
      {bet.notes.map((n) => (
        <li key={n}>{n}</li>
      ))}
      {left.map(([id, why]) => (
        <li key={id}>Left out: {why}</li>
      ))}
    </ul>
  )
}

function SmallButton({ children, onClick, disabled }: { children: ReactNode; onClick: () => void; disabled?: boolean }) {
  return (
    <motion.button
      type="button"
      whileTap={disabled ? undefined : PRESS}
      onClick={onClick}
      disabled={disabled}
      className="h-6 rounded-md px-2 text-xs text-ink-2 ring-1 ring-line outline-none transition-colors duration-150 hover:bg-card-2 hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring/50 disabled:pointer-events-none disabled:opacity-45"
    >
      {children}
    </motion.button>
  )
}

function SliderRow<K extends SliderId>({ bet, id, value, onChange }: { bet: Bet; id: K; value: Settings[K]; onChange: (v: Settings[K]) => void }) {
  const slider = bet.sliders[id]
  const steps = slider.steps as unknown as Settings[K][]
  return (
    <div className="flex flex-col gap-1">
      <div className="flex items-center justify-between gap-2 text-xs">
        <span className="flex items-center gap-1 text-ink-2">
          {slider.label}
          <TipIcon text={SLIDER_ABOUT[id]} />
        </span>
        <span className="num text-foreground">{stepText(id, value, bet.demand.trailing)}</span>
      </div>
      <div className="no-scrollbar relative -mx-0.5 overflow-x-auto px-0.5 py-0.5">
        <Segmented
          label={slider.label}
          value={String(value)}
          options={steps.map((st) => ({ id: String(st), label: stepLabel(id, st) }))}
          onChange={(v) => {
            const st = steps.find((x) => String(x) === v)
            if (st !== undefined) onChange(st)
          }}
        />
      </div>
    </div>
  )
}

function SwitchGroupBox({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="mt-3">
      <h3 className="text-[13px] font-medium">{title}</h3>
      <div className="mt-1.5 flex flex-col gap-0.5">{children}</div>
    </section>
  )
}

function Switch({
  label,
  on,
  size,
  swatch,
  onToggle,
  onOnly,
}: {
  label: string
  on: boolean
  size: string
  swatch?: string
  onToggle: () => void
  onOnly: () => void
}) {
  return (
    <div className="-mx-1.5 flex items-center gap-1 rounded-md transition-colors duration-150 hover:bg-card-2">
      <button
        type="button"
        role="switch"
        aria-checked={on}
        onClick={onToggle}
        className="flex min-w-0 flex-1 items-center gap-2 rounded-md px-1.5 py-1 text-left outline-none focus-visible:ring-2 focus-visible:ring-ring/50"
      >
        <span
          aria-hidden
          className={cn(
            "grid size-3.5 shrink-0 place-items-center rounded-[3px] ring-1 transition-colors duration-150",
            on ? "bg-foreground text-background ring-foreground" : "ring-line-strong",
          )}
        >
          {on && <Check className="size-2.5" strokeWidth={3} />}
        </span>
        {swatch && <span aria-hidden className={cn("size-2.5 shrink-0 rounded-[2px]", !on && "opacity-35")} style={{ background: swatch }} />}
        <span className={cn("min-w-0 flex-1 text-[13px] leading-snug", on ? "text-foreground" : "text-ink-3")}>{label}</span>
        <span className={cn("num shrink-0 text-xs", on ? "text-ink-2" : "text-ink-3")}>{size}</span>
      </button>
      <button
        type="button"
        onClick={onOnly}
        aria-label={`Only ${label}`}
        className="mr-0.5 shrink-0 rounded-sm px-1 text-[11px] text-ink-3 outline-none transition-colors duration-150 hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring/50"
      >
        Only
      </button>
    </div>
  )
}

/** What the need implies, now and at the deadline (spec 6): Python's factors times the switched-on need. */
function Implied({ bet, s, c, la }: { bet: Bet; s: Settings; c: Curves; la: number }) {
  const dl = c.deadline.quarter
  const now = implied(bet, s, c.need.rate[la] ?? 0, la)
  const then = implied(bet, s, c.need.rate[dl] ?? 0, dl)
  const rows = [
    {
      id: "gain",
      label: "Productivity gain it needs",
      tip: `The extra output a year the need implies, if AI firms keep ${s.value_capture}% of it as revenue.`,
      now: usdB(now.gain),
      then: usdB(then.gain),
    },
    {
      id: "hours",
      label: "Work hours that must use AI",
      tip: `The share of all paid work hours that would have to use AI to make that gain, at the ${bet.units.hour_uplift}% gain an hour the ledger assumes.`,
      now: pct(now.hours, 1),
      then: pct(then.hours, 1),
    },
    {
      id: "pool",
      label: "Share of the budget pool",
      tip: `The need as a share of IT spending and wages, weighted ${100 - s.labour_share}% IT and ${s.labour_share}% wages.`,
      now: pct(now.pool, 1),
      then: pct(then.pool, 1),
    },
  ]
  return (
    <section className="mt-4 border-t border-line pt-3">
      <h3 className="text-xs font-medium text-ink-2">What the need implies</h3>
      <div className="mt-2 grid grid-cols-1 gap-x-5 gap-y-3 sm:grid-cols-3">
        {rows.map((row) => (
          <div key={row.id} className="min-w-0">
            <div className="flex items-center gap-1 text-xs text-ink-2">
              {row.label}
              <TipIcon text={row.tip} />
            </div>
            <div className="num mt-0.5 text-[17px] leading-6 font-medium">{row.now}</div>
            <div className="num text-[11px] text-ink-3">
              in {bet.quarters[la]}; {row.then} at the deadline
            </div>
          </div>
        ))}
      </div>
    </section>
  )
}

function PathCard({ bet, path, active, jump }: { bet: Bet; path: BetPath; active: boolean; jump: (id: string) => void }) {
  const inds = Object.values(bet.signals.indicators).filter((i) => i.path === path.id)
  const reach = bet.reach[path.id]
  return (
    <Panel
      id={`path-${path.id}`}
      className={cn(active && "ring-you/50")}
      title={<StateMark state={path.state} word={<span>{path.label}</span>} />}
      sub={path.about}
      action={<span className="text-xs text-ink-2">{STATE_WORD[path.state]}</span>}
    >
      <ul className="-mx-1.5 flex flex-col">
        {inds.map((ind) => (
          <li key={ind.id}>
            <button
              type="button"
              onClick={() => jump(ind.id)}
              className="grid w-full grid-cols-[auto_minmax(0,1fr)] gap-x-2 rounded-md px-1.5 py-1.5 text-left outline-none transition-colors duration-150 hover:bg-card-2 focus-visible:ring-2 focus-visible:ring-ring/50"
            >
              <StateMark state={ind.state} className="mt-[5px] self-start" />
              <span className="min-w-0">
                <span className="flex items-baseline justify-between gap-2 text-[13px] leading-snug">
                  <span className="min-w-0">{ind.label}</span>
                  <span className="num shrink-0 text-xs text-ink-2">{fin(ind.reading) ? figure(ind.reading, ind.unit) : STATE_WORD[ind.state]}</span>
                </span>
                <span className="mt-0.5 block text-[11px] leading-snug text-ink-3">{ind.text}</span>
                <IndicatorScale ind={ind} className="mt-1" />
              </span>
            </button>
          </li>
        ))}
      </ul>
      {/* Adoption pace reaches no theme of its own: it is the pace, not a crash. */}
      {reach && reach.channels.length > 0 && <Reach reach={reach} />}
    </Panel>
  )
}

function Reach({ reach }: { reach: BetReach }) {
  const rows = [
    { who: "You", t: reach.you },
    { who: "World index", t: reach.world },
  ]
  return (
    <section className="mt-3 border-t border-line pt-3">
      <SubHead>Where it would reach</SubHead>
      <p
        className="mt-1 text-[11px] leading-snug text-ink-3"
        data-tip={reach.channels
          .map((ch) => `${ch.label}: ${ch.effect === "hurt" ? "would hurt" : ch.effect === "help" ? "would help" : "mixed"}, ${ch.strength}; you ${pct(ch.you)}, world index ${pct(ch.world)}`)
          .join("\n")}
      >
        Through {reach.channels.map((ch) => ch.label).join(", ")}
      </p>
      <div className="mt-2 grid grid-cols-[5.5rem_minmax(0,1fr)_auto] items-center gap-x-3 gap-y-1.5 text-xs">
        {rows.map(({ who, t }) => (
          <div key={who} className="contents">
            <span className="text-ink-2">{who}</span>
            <CategoryBar segments={SCAN_SEGMENTS(t).map((seg) => ({ ...seg, tip: `${who}: ${seg.label.toLowerCase()} ${pct(seg.value)}` }))} />
            <span className="num text-right text-ink-2" data-tip={`${who}: ${pct(t.hurt_share)} in themes it would hurt`}>
              {pct(t.hurt_share, 0)}
            </span>
          </div>
        ))}
      </div>
      {reach.replays.length > 0 && (
        <div className="mt-3 grid grid-cols-[minmax(0,1fr)_auto_auto] items-baseline gap-x-3 gap-y-1 text-xs">
          <span className="text-[11px] text-ink-3">Past sell-offs, today's mix</span>
          <span className="text-right text-[11px] text-ink-3">You</span>
          <span className="text-right text-[11px] text-ink-3">World</span>
          {reach.replays.map((rp) => (
            <div key={rp.id} className="contents">
              <span
                className="min-w-0 truncate text-ink-2"
                data-tip={`${rp.name}, ${dateRange(rp.start, rp.end)}. Prices cover ${pct(rp.coverage, 0)} of your portfolio.`}
              >
                {rp.name}
              </span>
              <Move value={rp.you} className="justify-end" />
              <Move value={rp.world} className="justify-end text-ink-2" />
            </div>
          ))}
        </div>
      )}
    </section>
  )
}
