/** Holdings: your mix against the world index, what you hold, and every holding. A holding opens into its own
 * card (the row grows into it): price line, what is inside it, today's news on it, the themes around it.
 * The card is in the address (#holdings/NVDA), so it can be linked and reopened. */
import { useMemo, useState } from "react"
import { AnimatePresence, motion } from "motion/react"
import { Dialog as DialogPrimitive } from "radix-ui"
import { X } from "lucide-react"
import { EventCard } from "@/components/brief"
import { BarList, CATEGORICAL, CategoryBar, Spark, type Segment } from "@/components/charts"
import { Chip, Empty, Legend, Move, PageHeader, Panel, Segmented, Sources, SPRING, SubHead, Swatch, Tag, type PageProps } from "@/components/kit"
import { PriceChart } from "@/components/price-chart"
import { SectorPanel } from "@/components/sectors"
import { pct, plural } from "@/lib/format"
import type { Go } from "@/lib/hooks"
import type { Holding, Model, Period, Returns } from "@/lib/types"

const PERIODS: Period[] = ["1D", "1W", "1M", "3M", "YTD", "1Y"]
type SortKey = "weight" | "1D" | "1M" | "YTD" | "1Y"
const SORTS: readonly { id: SortKey; label: string }[] = [
  { id: "weight", label: "Weight" },
  { id: "1D", label: "1D" },
  { id: "1M", label: "1M" },
  { id: "YTD", label: "YTD" },
  { id: "1Y", label: "1Y" },
]

function PeriodTable({ rows }: { rows: { label: string; returns: Returns; kind: "you" | "world" | "compare" }[] }) {
  return (
    <div className="relative -mx-1 overflow-x-auto px-1">
      <table className="w-full min-w-[480px] text-[13px]">
        <thead>
          <tr className="text-[11px] text-ink-3">
            <th className="pb-2 text-left font-normal">
              <span className="sr-only">Series</span>
            </th>
            {PERIODS.map((p) => (
              <th key={p} className="pb-2 text-right font-normal">
                {p}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-line">
          {rows.map((r) => (
            <tr key={r.label}>
              <th scope="row" className="py-2 pr-3 text-left font-normal">
                <span className="inline-flex items-center gap-2">
                  <Swatch
                    kind={r.kind === "you" ? "line" : "dash"}
                    color={r.kind === "you" ? "var(--you)" : r.kind === "compare" ? "var(--c7)" : "var(--world)"}
                  />
                  {r.label}
                </span>
              </th>
              {PERIODS.map((p) => (
                <td key={p} className="py-2 pl-3 text-right">
                  <Move value={r.returns[p]} />
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

/** Each holding keeps its colour wherever the list is sorted: the seven largest get the categorical order, the
 * rest fold into Other. */
function colours(holdings: Holding[]): Map<string, string> {
  const byWeight = [...holdings].sort((a, b) => b.weight - a.weight)
  return new Map(byWeight.map((h, i) => [h.symbol, i < 7 ? CATEGORICAL[i] : "var(--ink-3)"]))
}

function Mix({ holdings, colour }: { holdings: Holding[]; colour: Map<string, string> }) {
  const byWeight = [...holdings].sort((a, b) => b.weight - a.weight)
  const top = byWeight.slice(0, 7)
  const other = byWeight.slice(7).reduce((a, h) => a + h.weight, 0)
  const segments: Segment[] = top.map((h) => ({
    id: h.symbol,
    label: h.symbol,
    value: h.weight,
    color: colour.get(h.symbol) ?? "var(--ink-3)",
    tip: `${h.symbol} · ${h.name}: ${pct(h.weight)}`,
  }))
  if (other > 0) segments.push({ id: "other", label: "Other", value: other, color: "var(--ink-3)" })
  return (
    <>
      <CategoryBar segments={segments} />
      <Legend
        className="mt-3"
        items={segments.map((s) => ({
          label: (
            <>
              <span className="num text-foreground">{s.label}</span> <span className="num text-ink-3">{pct(s.value)}</span>
            </>
          ),
          kind: "box",
          color: s.color,
        }))}
      />
    </>
  )
}

function HoldingList({
  rows,
  labels,
  colour,
  go,
}: {
  rows: Holding[]
  labels: Record<string, string>
  colour: Map<string, string>
  go: Go
}) {
  const maxWeight = Math.max(1e-9, ...rows.map((r) => r.weight))
  return (
    <div className="grid grid-cols-[minmax(0,1fr)_6rem_4.5rem] gap-x-4 text-[13px] md:grid-cols-[minmax(0,1.3fr)_6.5rem_4.5rem_4.5rem_4.5rem_4.5rem_5rem_minmax(0,1fr)]">
      <div aria-hidden className="col-span-full grid grid-cols-subgrid border-b border-line px-2 pb-2 text-[11px] text-ink-3">
        <span>Holding</span>
        <span className="text-right">Weight</span>
        <span className="text-right">1D</span>
        <span className="hidden text-right md:block">1M</span>
        <span className="hidden text-right md:block">YTD</span>
        <span className="hidden text-right md:block">1Y</span>
        <span className="hidden md:block">90 days</span>
        <span className="hidden md:block">Biggest themes</span>
      </div>
      <ul className="col-span-full grid grid-cols-subgrid">
        {rows.map((h) => (
          <li key={h.symbol} className="col-span-full grid grid-cols-subgrid">
            <motion.button
              type="button"
              whileTap={{ scale: 0.995 }}
              onClick={() => go("holdings", h.symbol)}
              aria-label={`${h.symbol}, ${h.name}, ${pct(h.weight)} of your portfolio. Open its card.`}
              className="group relative col-span-full grid grid-cols-subgrid items-center rounded-md px-2 py-2 text-left outline-none transition-colors duration-150 hover:bg-card-2 focus-visible:ring-2 focus-visible:ring-ring/50"
            >
              <motion.span layoutId={`holding-${h.symbol}`} transition={SPRING} aria-hidden className="pointer-events-none absolute inset-0 rounded-md" />
              <span className="relative min-w-0">
                <span className="flex items-center gap-2">
                  <Swatch kind="box" color={colour.get(h.symbol) ?? "var(--ink-3)"} />
                  <span className="num font-medium">{h.symbol}</span>
                  {h.events.length > 0 && <span className="text-[11px] text-ink-3">{plural(h.events.length, "event")} today</span>}
                </span>
                <span className="block truncate text-xs text-ink-3">{h.name}</span>
              </span>
              <span className="relative flex flex-col items-end gap-1">
                <span className="num">{pct(h.weight)}</span>
                <span aria-hidden className="block h-1 w-full rounded-full bg-line">
                  <span className="block h-full rounded-full bg-you" style={{ width: `${(h.weight / maxWeight) * 100}%` }} />
                </span>
              </span>
              <Move value={h.returns["1D"]} className="relative justify-end" />
              <Move value={h.returns["1M"]} className="relative hidden justify-end md:flex" />
              <Move value={h.returns["YTD"]} className="relative hidden justify-end md:flex" />
              <Move value={h.returns["1Y"]} className="relative hidden justify-end md:flex" />
              <span className="relative hidden md:block">
                <Spark values={h.spark} />
              </span>
              <span className="relative hidden min-w-0 truncate text-xs text-ink-2 md:block">
                {h.top_themes.length
                  ? h.top_themes
                      .slice(0, 2)
                      .map(([id, share]) => `${labels[id] ?? id} ${pct(share, 0)}`)
                      .join(" · ")
                  : "–"}
              </span>
            </motion.button>
          </li>
        ))}
      </ul>
    </div>
  )
}

function Detail({ holding: h, model, go }: { holding: Holding; model: Model; go: Go }) {
  const cash = h.kind === "cash"
  const fund = h.inside.length > 0
  const events = h.events.map((i) => ({ e: model.events[i], n: i + 1 })).filter((x) => !!x.e)
  return (
    <>
      <header className="flex items-start gap-4 border-b border-line px-5 py-4">
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <span className="num text-lg leading-7 font-semibold">{h.symbol}</span>
            <Tag>{h.kind}</Tag>
          </div>
          <DialogPrimitive.Title className="truncate text-[13px] text-ink-2">{h.name}</DialogPrimitive.Title>
        </div>
        <div className="text-right">
          <div className="num text-lg leading-7 font-medium">{pct(h.weight)}</div>
          <div className="text-[11px] text-ink-3">of your portfolio</div>
        </div>
        <DialogPrimitive.Close asChild>
          <button
            type="button"
            aria-label="Close"
            className="-mr-1 grid size-8 shrink-0 place-items-center rounded-md text-ink-2 outline-none transition-colors duration-150 hover:bg-card-2 hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring/50"
          >
            <X className="size-4" aria-hidden />
          </button>
        </DialogPrimitive.Close>
      </header>
      <div className="flex flex-col gap-6 px-5 py-4">
        {!cash && (
          <div className="grid grid-cols-3 gap-x-4 gap-y-3 sm:grid-cols-6">
            {PERIODS.map((p) => (
              <div key={p}>
                <div className="text-[11px] text-ink-3">{p}</div>
                <Move value={h.returns[p]} className="mt-0.5 text-[14px]" />
              </div>
            ))}
          </div>
        )}
        {cash ? (
          <p className="text-[13px] text-ink-2">Cash has no price line. It counts as a zero return in every replay.</p>
        ) : (
          <PriceChart
            height={200}
            series={[
              { key: "you", label: h.symbol, points: h.line },
              { key: "world", label: `World index (${model.benchmark})`, points: model.performance.world_weekly },
            ]}
          />
        )}
        <section>
          <SubHead>In today's brief</SubHead>
          {h.note || events.length ? (
            <div className="mt-2">
              {h.note && (
                <div className="mb-3">
                  <p className="text-[13px] leading-relaxed">{h.note.note}</p>
                  <Sources ids={h.note.news_ids} news={model.news} className="mt-1.5" />
                </div>
              )}
              <div className="divide-y divide-line">
                {events.map(({ e, n }) => (
                  <EventCard key={n} event={e} n={n} model={model} go={go} />
                ))}
              </div>
            </div>
          ) : (
            <p className="mt-2 text-[13px] text-ink-3">Nothing in today's brief touches it directly.</p>
          )}
        </section>
        <section>
          <SubHead>The world around it</SubHead>
          {h.top_themes.length ? (
            <ul className="mt-2 flex flex-col divide-y divide-line">
              {h.top_themes.map(([id, share]) => {
                const t = model.themes[id]
                return (
                  <li key={id} className="grid gap-x-3 gap-y-1 py-2.5 first:pt-0 last:pb-0 sm:grid-cols-[11rem_minmax(0,1fr)]">
                    <div>
                      <Chip
                        label={model.theme_labels[id] ?? id}
                        count={t?.heat}
                        onClick={() => (model.matter.includes(id) ? go("world", id) : go("exposure"))}
                      />
                      <div className="num mt-1 text-[11px] text-ink-3">{pct(share)} of this holding</div>
                    </div>
                    <p className="text-[13px] leading-relaxed text-ink-2">{t?.brief?.state ?? "Not covered in today's brief."}</p>
                  </li>
                )
              })}
            </ul>
          ) : (
            <p className="mt-2 text-[13px] text-ink-3">In no theme above 2%.</p>
          )}
        </section>
        {fund ? (
          <div className="grid gap-6 sm:grid-cols-2">
            <section>
              <SubHead>Largest companies inside</SubHead>
              <BarList className="mt-2" rows={h.inside.slice(0, 10).map(([name, share]) => ({ id: name, label: name, value: share }))} />
            </section>
            <section>
              <SubHead>Countries inside</SubHead>
              <BarList className="mt-2" rows={h.countries.slice(0, 10).map(([name, share]) => ({ id: name, label: name, value: share }))} />
            </section>
          </div>
        ) : (
          !cash &&
          h.countries.length > 0 && (
            <section>
              <SubHead>Where it is listed or based</SubHead>
              <BarList className="mt-2" rows={h.countries.map(([name, share]) => ({ id: name, label: name, value: share }))} />
            </section>
          )
        )}
      </div>
    </>
  )
}

/** The card a holding opens into. Radix gives it focus handling and Esc; Motion grows it out of its row. */
function HoldingCard({ holding, model, go }: { holding: Holding | null; model: Model; go: Go }) {
  return (
    <DialogPrimitive.Root open={!!holding} onOpenChange={(open) => !open && go("holdings")}>
      <AnimatePresence>
        {holding && (
          <DialogPrimitive.Portal forceMount>
            <DialogPrimitive.Overlay asChild forceMount>
              <motion.div
                className="fixed inset-0 z-50 bg-black/60"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                transition={{ duration: 0.15 }}
              />
            </DialogPrimitive.Overlay>
            <div className="pointer-events-none fixed inset-0 z-50 flex items-start justify-center p-3 sm:items-center sm:p-6">
              <DialogPrimitive.Content asChild forceMount aria-describedby={undefined}>
                <motion.div
                  layoutId={`holding-${holding.symbol}`}
                  transition={SPRING}
                  className="pointer-events-auto max-h-[calc(100dvh-1.5rem)] w-full max-w-3xl overflow-y-auto rounded-lg bg-popover shadow-lg ring-1 shadow-black/30 ring-line-strong outline-none sm:max-h-[calc(100dvh-3rem)]"
                >
                  <motion.div
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1, transition: { delay: 0.06, duration: 0.16 } }}
                    exit={{ opacity: 0, transition: { duration: 0.06 } }}
                  >
                    <Detail holding={holding} model={model} go={go} />
                  </motion.div>
                </motion.div>
              </DialogPrimitive.Content>
            </div>
          </DialogPrimitive.Portal>
        )}
      </AnimatePresence>
    </DialogPrimitive.Root>
  )
}

export function Holdings({ model, item, go }: PageProps) {
  const [sort, setSort] = useState<SortKey>("weight")
  const rows = useMemo(
    () =>
      [...model.holdings].sort((a, b) =>
        sort === "weight" ? b.weight - a.weight : (b.returns[sort] ?? -Infinity) - (a.returns[sort] ?? -Infinity),
      ),
    [model.holdings, sort],
  )
  const colour = useMemo(() => colours(model.holdings), [model.holdings])
  const open = item ? (model.holdings.find((h) => h.symbol === item) ?? null) : null
  const returns = model.performance.returns

  return (
    <>
      <PageHeader
        title="Holdings"
        sub="Open a holding to see its price line, what is inside it, today's news on it and the themes around it."
      />
      <div className="grid grid-cols-1 gap-3 lg:grid-cols-12">
        <Panel
          className="lg:col-span-7"
          title="Your mix against the world index"
          sub={`Price moves in ${model.home}. Your mix is today's holdings at today's weights.`}
        >
          <PeriodTable
            rows={[
              { label: "You (today's mix)", returns: returns.portfolio ?? {}, kind: "you" },
              { label: `World index (${model.benchmark})`, returns: returns.world ?? {}, kind: "world" },
              ...(model.performance.compare ?? []).map((c) => ({ label: `${c.name} (${c.symbol})`, returns: c.returns, kind: "compare" as const })),
            ]}
          />
        </Panel>
        <Panel className="lg:col-span-5" title="What you hold" sub="Today's weights, largest first.">
          {model.holdings.length ? <Mix holdings={model.holdings} colour={colour} /> : <Empty>No holdings yet.</Empty>}
        </Panel>
      </div>
      <SectorPanel model={model} className="mt-3" />
      <Panel
        className="mt-3"
        title="Every holding"
        sub="Moves in your currency. Select a holding to open its card."
        action={<Segmented value={sort} options={SORTS} onChange={setSort} label="Sort holdings by" />}
      >
        {rows.length ? (
          <HoldingList rows={rows} labels={model.theme_labels} colour={colour} go={go} />
        ) : (
          <Empty>No holdings yet.</Empty>
        )}
      </Panel>
      <HoldingCard holding={open} model={model} go={go} />
    </>
  )
}
