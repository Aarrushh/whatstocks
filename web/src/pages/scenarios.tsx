/** Scenarios: name a conflict with /scan and your AI maps where it would reach your money. A scan in the address
 * (#scenarios/china-blockade-of-taiwan) picks it; otherwise the newest one shows. */
import { HurtHelp, PairBars, StrengthBars } from "@/components/charts"
import { Banner, Chip, Cmd, Empty, Legend, Move, PageHeader, Panel, Sources, Stat, Ticker, type PageProps } from "@/components/kit"
import { BubbleMap } from "@/components/maps"
import { dateRange, longDate, pct, SCAN_WORD } from "@/lib/format"
import type { Effect } from "@/lib/types"

const INTRO =
  "Name any conflict and your AI maps where it would reach your money, theme by theme and region by region, next to the world index."
const EFFECT_COLOR: Record<Effect, string> = { hurt: "var(--neg)", help: "var(--pos)", mixed: "var(--ink-3)" }

export function Scenarios({ model, item, go }: PageProps) {
  const scans = model.scans
  const scan = scans.find((s) => s.slug === item) ?? scans[0]

  if (!scan) {
    return (
      <>
        <PageHeader title="Scenarios" sub={INTRO} />
        <Panel>
          <Empty>
            In Claude Code, run <Cmd>/scan</Cmd> and name a conflict, for example China blockade of Taiwan or Iran war and the
            Strait of Hormuz.
          </Empty>
          <p className="mt-3 max-w-3xl text-[13px] leading-relaxed text-ink-2">
            The code searches the past week's news for it and sends your AI the themes, regions and holdings as percentages. Your AI
            marks which ones the conflict would hurt or help, and how strongly; the code computes every number and draws the map
            here.
          </p>
        </Panel>
      </>
    )
  }

  const you = scan.totals.you
  const world = scan.totals.world
  const percent = (x: number) => pct(x)
  const holdings = [...scan.holdings].sort((a, b) => b.weight - a.weight)

  return (
    <>
      <PageHeader title="Scenarios" sub={INTRO} />
      {scans.length > 1 && (
        <div className="no-scrollbar relative -mx-1 mb-3 flex gap-1.5 overflow-x-auto px-1 py-0.5">
          {scans.map((s) => (
            <Chip key={s.slug} label={s.conflict} active={s.slug === scan.slug} onClick={() => go("scenarios", s.slug)} />
          ))}
        </div>
      )}
      {scan.advice && (
        <Banner className="mb-3">Parts of this scan read like advice. They were let through with --allow-advice.</Banner>
      )}

      <Panel
        title={<span className="text-[15px]">{scan.conflict}</span>}
        sub={`Scanned ${longDate(scan.date)}, from the past week's news and your holdings as of ${longDate(scan.exposure_date)}.`}
      >
        <p className="max-w-4xl text-[14px] leading-relaxed">{scan.summary}</p>
        <Sources ids={scan.news_ids} news={scan.news} className="mt-2" />
        <p className="mt-3 text-xs text-ink-3">
          A scan maps where a conflict would reach your money. It is not a forecast of whether it happens or of what prices do.
        </p>
      </Panel>

      <div className="mt-3 grid grid-cols-2 gap-3 xl:grid-cols-4">
        <Stat
          label="Where it would hurt"
          tip="Share of the portfolio in any theme or region the scan marks as hurt. Each company counts once."
          value={<Ticker value={you.hurt_share} format={percent} />}
          sub={`World index ${pct(world.hurt_share)}`}
        />
        <Stat
          label="Where it would help"
          tip="Share of the portfolio in any theme or region the scan marks as help. Each company counts once."
          value={<Ticker value={you.help_share} format={percent} />}
          sub={`World index ${pct(world.help_share)}`}
        />
        <Stat
          label="Hurt, weighted by strength"
          tip="Each share counted at the strength of the strongest channel reaching it: low a third, medium two thirds, high in full."
          value={<Ticker value={you.hurt_score} format={percent} />}
          sub={`World index ${pct(world.hurt_score)}`}
        />
        <Stat
          label="Mixed"
          tip="Share of the portfolio in any theme or region the scan marks as mixed: hurt in some ways, helped in others."
          value={<Ticker value={you.mixed_share} format={percent} />}
          sub={`World index ${pct(world.mixed_share)}`}
        />
      </div>

      <Panel className="mt-3" title="Where the conflict reaches you" sub="Every theme and region the conflict reaches, sized by your money in it.">
        {scan.bubbles.length ? (
          <>
            <BubbleMap scan={scan} />
            <Legend
              className="mt-5 justify-center"
              items={[
                { label: "Would hurt", kind: "dot", color: "var(--neg)" },
                { label: "Mixed", kind: "dot", color: "var(--ink-3)" },
                { label: "Would help", kind: "dot", color: "var(--pos)" },
                { label: "World index's share", kind: "ring", color: "var(--world)" },
              ]}
            />
            <p className="mx-auto mt-2 max-w-3xl text-center text-xs leading-relaxed text-ink-3">
              A bubble's area is your share of the portfolio in that theme or region; the dashed ring is the world index's share on
              the same scale, so a ring outside the bubble means the world index holds more of it than you. Solid, lighter and faint
              fills are high, medium and low strength. Hover a bubble for your AI's reason.
            </p>
          </>
        ) : (
          <Empty>The scan marked no theme or region.</Empty>
        )}
      </Panel>

      <div className="mt-3 grid grid-cols-1 gap-3 lg:grid-cols-12">
        <Panel
          className="lg:col-span-6"
          title="Which holdings it reaches"
          sub="The share of each holding that sits in a channel the conflict would hurt, or help."
        >
          {holdings.length ? (
            <HurtHelp
              rows={holdings.map((h) => ({
                id: h.symbol,
                label: <span className="num">{h.symbol}</span>,
                sub: pct(h.weight),
                hurt: h.hurt_share,
                help: h.help_share,
              }))}
            />
          ) : (
            <Empty>No holdings yet.</Empty>
          )}
        </Panel>
        <Panel
          className="lg:col-span-6"
          title="Past episodes that looked like it"
          sub="Today's holdings replayed over windows your AI picked. Every move computed in code."
        >
          {scan.analogs.length ? (
            <>
              <PairBars
                rows={scan.analogs.map((a) => ({
                  id: a.name,
                  label: a.name,
                  sub: dateRange(a.start, a.end),
                  you: a.you,
                  world: a.world,
                  note: (
                    <p className="mt-1.5 text-xs leading-relaxed text-ink-3">
                      {a.why}
                      {a.coverage < 0.999 && ` Prices cover ${pct(a.coverage, 0)} of today's holdings for this window.`}
                    </p>
                  ),
                }))}
              />
              {scan.proxy_channels.length > 0 && (
                <div className="mt-5 border-t border-line pt-3">
                  <p className="text-xs text-ink-3">Each theme channel's proxy ETF over the same windows.</p>
                  <div className="relative -mx-1 mt-2 overflow-x-auto px-1">
                    <table className="w-full text-[13px]">
                      <thead>
                        <tr className="text-[11px] text-ink-3">
                          <th className="pb-1.5 text-left font-normal">Episode</th>
                          {scan.proxy_channels.map((id) => (
                            <th key={id} className="pb-1.5 pl-3 text-right font-normal whitespace-nowrap">
                              {model.theme_labels[id] ?? id}
                            </th>
                          ))}
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-line">
                        {scan.analogs.map((a) => (
                          <tr key={a.name}>
                            <th scope="row" className="py-1.5 pr-3 text-left font-normal">
                              {a.name}
                            </th>
                            {scan.proxy_channels.map((id) => (
                              <td key={id} className="py-1.5 pl-3 text-right">
                                <Move value={a.proxies[id]} className="justify-end" />
                              </td>
                            ))}
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}
            </>
          ) : (
            <Empty>Your AI named no past episodes.</Empty>
          )}
        </Panel>
      </div>

      <div className="mt-3 grid grid-cols-1 gap-3 lg:grid-cols-12">
        <Panel
          className="lg:col-span-8"
          title="Channels"
          sub="Effect and strength are your AI's judgment; every share is computed in code."
        >
          <div className="relative -mx-1 overflow-x-auto px-1">
            <table className="w-full min-w-[640px] text-[13px]">
              <thead>
                <tr className="text-[11px] text-ink-3">
                  <th className="pb-2 text-left font-normal">Channel</th>
                  <th className="pb-2 text-left font-normal">Effect</th>
                  <th className="pb-2 text-left font-normal">Strength</th>
                  <th className="pb-2 text-right font-normal">You</th>
                  <th className="pb-2 text-right font-normal">World</th>
                  <th className="pb-2 pl-4 text-left font-normal">Why</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-line">
                {scan.channels.map((c) => (
                  <tr key={`${c.kind}-${c.id}`} className="align-top">
                    <th scope="row" className="py-2 pr-3 text-left font-normal">
                      {c.label}
                      <span className="block text-[11px] text-ink-3">
                        {c.kind}
                        {c.proxy ? ` · ${c.proxy}` : ""}
                      </span>
                    </th>
                    <td className="py-2 pr-3 whitespace-nowrap">
                      <span className="inline-flex items-center gap-1.5 text-xs text-ink-2">
                        <span aria-hidden className="size-2 rounded-full" style={{ background: EFFECT_COLOR[c.effect] }} />
                        {SCAN_WORD[c.effect]}
                      </span>
                    </td>
                    <td className="py-2 pr-3">
                      <StrengthBars strength={c.strength} />
                    </td>
                    <td className="num py-2 pl-3 text-right">{pct(c.you)}</td>
                    <td className="num py-2 pl-3 text-right text-ink-3">{pct(c.world)}</td>
                    <td className="py-2 pl-4 leading-relaxed text-ink-2">{c.why}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Panel>
        <Panel className="lg:col-span-4" title="What to watch">
          {scan.watch.length ? (
            <ul className="flex flex-col divide-y divide-line">
              {scan.watch.map((w, i) => (
                <li key={i} className="py-2.5 first:pt-0 last:pb-0">
                  <p className="text-[13px] leading-relaxed">{w.what}</p>
                  <Sources ids={w.news_ids} news={scan.news} className="mt-1" />
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-[13px] text-ink-3">None given.</p>
          )}
        </Panel>
      </div>
    </>
  )
}
