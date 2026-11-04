/** Exposure: where your money actually sits, looked through funds, next to a world index fund. */
import { BarList, HeatGrid, PairBars, YouWorld, rampFill, type GridRow } from "@/components/charts"
import { Empty, Legend, Move, PageHeader, Panel, Stat, Ticker, YOU_WORLD, type PageProps } from "@/components/kit"
import { WorldMap } from "@/components/maps"
import { DASH, dateRange, pct, pts } from "@/lib/format"
import type { Theme } from "@/lib/types"

const beta = (b: number | null) => (b === null || Number.isNaN(b) ? DASH : b.toFixed(2))

export function Exposure({ model, go }: PageProps) {
  const ex = model.exposure
  const themes = model.theme_order.map((id) => model.themes[id]).filter((t): t is Theme => !!t)
  const byGap = [...themes].sort((a, b) => b.you - b.world - (a.you - a.world))
  const over = byGap[0]
  const under = byGap.length > 1 ? byGap[byGap.length - 1] : undefined
  const names = [...new Set([...Object.keys(ex.countries.you), ...Object.keys(ex.countries.world)])]
  const countries = names
    .map((name) => ({ id: name, label: name, you: ex.countries.you[name] ?? 0, world: ex.countries.world[name] ?? 0 }))
    .sort((a, b) => b.you - a.you || b.world - a.world)
  const matrixMax = Math.max(1e-9, ...ex.matrix.rows.flatMap((r) => r.cells))
  const label = (id: string) => model.theme_labels[id] ?? id
  const matrixRows: GridRow[] = ex.matrix.rows.map((r) => ({ id: r.symbol, label: <span className="num">{r.symbol}</span>, cells: r.cells }))

  return (
    <>
      <PageHeader title="Exposure" sub="Where your money actually sits, looked through funds, next to a world index fund." />
      <div className="grid grid-cols-2 gap-3 xl:grid-cols-4">
        <Stat
          label="Most over the world index"
          value={over ? <Ticker value={over.you - over.world} format={(x) => pts(x)} /> : DASH}
          sub={over ? `${over.label}: ${pct(over.you)} against ${pct(over.world)}` : "No themes yet"}
        />
        <Stat
          label="Most under the world index"
          value={under ? <Ticker value={under.you - under.world} format={(x) => pts(x)} /> : DASH}
          sub={under ? `${under.label}: ${pct(under.you)} against ${pct(under.world)}` : "No themes yet"}
        />
        <Stat
          label="Theme betas cover"
          tip="The share of your portfolio with two years of weekly prices, so a theme beta can be worked out for it."
          value={ex.beta_coverage === null ? DASH : <Ticker value={ex.beta_coverage} format={(x) => pct(x, 0)} />}
          sub="of your portfolio, from 2 years of weekly prices"
        />
        <Stat
          label="Not looked through"
          tip="Funds whose holdings the tool cannot open count as a single company in no theme."
          value={<Ticker value={ex.unresolved} format={(x) => pct(x)} />}
          sub="of your portfolio, in funds the tool cannot open"
        />
      </div>

      <div className="mt-3 grid grid-cols-1 gap-3 lg:grid-cols-12">
        <Panel
          className="lg:col-span-7"
          title="Every theme: you against the world index"
          sub="Funds are broken into the companies they hold. Core members count in full, partial members half."
        >
          {themes.length ? (
            <>
              <YouWorld
                rows={themes.map((t) => ({
                  id: t.id,
                  label: t.label,
                  sub: t.proxy,
                  you: t.you,
                  world: t.world,
                  onClick: model.matter.includes(t.id) ? () => go("world", t.id) : undefined,
                }))}
              />
              <Legend className="mt-3 px-1.5" items={YOU_WORLD} />
            </>
          ) : (
            <Empty>No themes yet.</Empty>
          )}
        </Panel>
        <Panel className="lg:col-span-5" title="Where your companies are based" sub="Look-through shares by country. Smaller ones fold into Other.">
          <WorldMap you={ex.countries.you} world={ex.countries.world} />
          <Legend
            className="mt-2"
            items={[
              { label: "You", kind: "dot", color: "var(--you)" },
              { label: "World index", kind: "ring", color: "var(--world)" },
            ]}
          />
          <YouWorld className="mt-4" head="Country" gap={false} rows={countries.slice(0, 9)} />
        </Panel>
      </div>

      <Panel className="mt-3" title="Theme betas and worst weeks" sub="How your portfolio has moved with each theme's proxy ETF.">
        <div className="relative -mx-1 overflow-x-auto px-1">
          <table className="w-full min-w-[720px] text-[13px]">
            <thead>
              <tr className="text-[11px] text-ink-3">
                <th className="pb-2 text-left font-normal">Theme</th>
                <th className="pb-2 text-left font-normal">Proxy</th>
                <th className="pb-2 text-right font-normal">You</th>
                <th className="pb-2 text-right font-normal">World</th>
                <th className="pb-2 text-right font-normal">Beta, you</th>
                <th className="pb-2 text-right font-normal">Beta, world</th>
                <th className="pb-2 text-right font-normal">Worst weeks: proxy</th>
                <th className="pb-2 text-right font-normal">you</th>
                <th className="pb-2 text-right font-normal">world</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-line">
              {themes.map((t) => (
                <tr key={t.id}>
                  <th scope="row" className="py-1.5 pr-3 text-left font-normal">
                    {t.label}
                  </th>
                  <td className="num py-1.5 pr-3 text-ink-2">{t.proxy}</td>
                  <td className="num py-1.5 pl-3 text-right">{pct(t.you)}</td>
                  <td className="num py-1.5 pl-3 text-right text-ink-3">{pct(t.world)}</td>
                  <td className="num py-1.5 pl-3 text-right">{beta(t.beta_you)}</td>
                  <td className="num py-1.5 pl-3 text-right text-ink-3">{beta(t.beta_world)}</td>
                  <td className="py-1.5 pl-3 text-right">
                    <Move value={t.worst_weeks.proxy} className="justify-end" />
                  </td>
                  <td className="py-1.5 pl-3 text-right">
                    <Move value={t.worst_weeks.you} className="justify-end" />
                  </td>
                  <td className="py-1.5 pl-3 text-right">
                    <Move value={t.worst_weeks.world} className="justify-end text-ink-2" />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="mt-3 max-w-4xl text-xs leading-relaxed text-ink-3">
          Theme beta: how much the portfolio moved per 1% move in the theme's proxy ETF, weekly over 2 years, in {model.home}. Worst
          weeks: the average return in the proxy's 10 worst weeks of those 2 years. Betas from calm years understate how closely
          things move together in a real crash.
        </p>
      </Panel>

      <div className="mt-3 grid grid-cols-1 gap-3 lg:grid-cols-12">
        <Panel
          className="lg:col-span-6"
          title="Past sell-offs, replayed on today's holdings"
          sub="Today's mix held through each window, next to the world index, in your currency."
        >
          {ex.sell_offs.length ? (
            <PairBars
              rows={ex.sell_offs.map((s) => ({
                id: s.name,
                label: s.name,
                sub: dateRange(s.start, s.end),
                you: s.you,
                world: s.world,
                note:
                  s.coverage < 0.999 ? (
                    <p className="mt-1 text-[11px] text-ink-3">Prices cover {pct(s.coverage, 0)} of today's holdings for this window.</p>
                  ) : undefined,
              }))}
            />
          ) : (
            <Empty>No price history long enough to replay a sell-off.</Empty>
          )}
        </Panel>
        <Panel
          className="lg:col-span-3"
          title="Currencies under your holdings"
          sub="The currency of each company's listing, after looking through funds."
        >
          {ex.currencies.length ? (
            <BarList rows={ex.currencies.map(([c, share]) => ({ id: c, label: <span className="num">{c}</span>, value: share }))} />
          ) : (
            <Empty>None.</Empty>
          )}
        </Panel>
        <Panel className="lg:col-span-3" title="Data notes">
          {model.notes.length ? (
            <ul className="flex flex-col gap-2 text-xs leading-relaxed text-ink-2">
              {model.notes.map((n, i) => (
                <li key={i}>{n}</li>
              ))}
            </ul>
          ) : (
            <p className="text-xs text-ink-3">Every holding was looked through.</p>
          )}
        </Panel>
      </div>

      <Panel
        className="mt-3"
        title="Where each theme comes from"
        sub="Each cell is the share of your whole portfolio that one holding puts into one theme."
      >
        {matrixRows.length && ex.matrix.cols.length ? (
          <HeatGrid
            head="Holding"
            cols={ex.matrix.cols}
            rows={matrixRows}
            foot={{ id: "all", label: "All holdings", cells: ex.matrix.total }}
            colLabel={(c) => <span className="inline-block max-w-24 truncate align-bottom font-sans">{label(c)}</span>}
            fill={(v) => rampFill(v, matrixMax, "var(--you)", 55)}
            showText
            text={(v) => (v && v >= 0.0005 ? pct(v) : "")}
            tip={(r, c, v) => `${r.id === "all" ? "All holdings" : r.id} → ${label(c)}: ${pct(v ?? 0)} of your portfolio`}
          />
        ) : (
          <Empty>No look-through yet.</Empty>
        )}
      </Panel>
    </>
  )
}
