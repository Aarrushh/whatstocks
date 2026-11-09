/** Record: were your calls right, and did your trades follow your own views? Append-only, scored in code. */
import { TriangleAlert } from "lucide-react"
import { Caution, Empty, Move, PageHeader, Panel, Tag, type PageProps } from "@/components/kit"
import { DASH, longDate, plural } from "@/lib/format"

export function RecordPage({ model, go }: PageProps) {
  const s = model.scores
  const worst = Math.max(s.coin_flip * 2, ...s.views.map((v) => v.brier ?? 0))
  return (
    <>
      <PageHeader title="Record" sub="Were your calls right, and did your trades follow your own views?" />
      <div className="grid grid-cols-1 gap-3 lg:grid-cols-12">
        <Panel
          className="lg:col-span-4"
          title="Your calls, scored"
          sub="A time-weighted Brier score: every day's probability against what happened."
        >
          {s.count && s.mean !== null ? (
            <>
              <div className="text-xs text-ink-3">Mean Brier score</div>
              <div className="num mt-1 text-[28px] leading-8 font-medium">{s.mean.toFixed(3)}</div>
              <p className="mt-1 text-xs leading-relaxed text-ink-2">
                over {plural(s.count, "resolved view")}. Lower is better; always saying 50% scores {s.coin_flip.toFixed(2)}.
              </p>
              {s.luck && <Caution className="mt-2">Under 20 resolved views, the score is mostly luck.</Caution>}
            </>
          ) : (
            <Empty>No views have resolved yet. The score starts with the first one.</Empty>
          )}
        </Panel>
        <Panel className="lg:col-span-8" title="Resolved views" sub="Each view's own score, with the coin-flip score marked.">
          {s.views.length ? (
            <ul className="flex flex-col divide-y divide-line">
              {s.views.map((v, i) => (
                <li key={i} className="grid gap-x-4 gap-y-1 py-2.5 first:pt-0 last:pb-0 sm:grid-cols-[minmax(0,1fr)_12rem]">
                  <div className="min-w-0">
                    <p className="text-[13px] leading-relaxed">{v.statement}</p>
                    <span className="text-xs text-ink-3">{v.result}</span>
                  </div>
                  <div
                    data-tip={`Brier ${v.brier === null ? DASH : v.brier.toFixed(3)}; always saying 50% scores ${s.coin_flip.toFixed(2)}`}
                    className="flex items-center gap-2"
                  >
                    <span aria-hidden className="relative block h-3 flex-1">
                      <span className="absolute inset-x-0 top-1/2 h-px bg-line" />
                      <span
                        className="absolute top-1/2 left-0 h-1.5 -translate-y-1/2 rounded-r-[3px] bg-foreground/70"
                        style={{ width: `${((v.brier ?? 0) / worst) * 100}%` }}
                      />
                      <span
                        className="absolute top-0 h-full w-[2px] -translate-x-1/2 rounded-full bg-world"
                        style={{ left: `${(s.coin_flip / worst) * 100}%` }}
                      />
                    </span>
                    <span className="num w-12 text-right text-xs">{v.brier === null ? DASH : v.brier.toFixed(3)}</span>
                  </div>
                </li>
              ))}
            </ul>
          ) : (
            <Empty>None yet.</Empty>
          )}
        </Panel>
      </div>

      <Panel className="mt-3" title="Decisions" sub="Your trades, next to the views they cite. Flags are shown, never blocking.">
        {model.decisions.length ? (
          <div className="relative -mx-1 overflow-x-auto px-1">
            <table className="w-full min-w-[760px] text-[13px]">
              <thead>
                <tr className="text-[11px] text-ink-3">
                  <th className="pb-2 text-left font-normal">Date</th>
                  <th className="pb-2 text-left font-normal">Trade</th>
                  <th className="pb-2 text-right font-normal">Size</th>
                  <th className="pb-2 pl-4 text-left font-normal">Views cited</th>
                  <th className="pb-2 pl-4 text-left font-normal">Reason</th>
                  <th className="pb-2 pl-4 text-left font-normal">Review on</th>
                  <th className="pb-2 pl-4 text-left font-normal">Flags</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-line">
                {model.decisions.map((d) => (
                  <tr key={d.id} className="align-top">
                    <td className="num py-2 pr-3 whitespace-nowrap text-ink-2">{longDate(d.date)}</td>
                    <td className="py-2 pr-3 whitespace-nowrap">
                      <Tag className="mr-2">{d.action}</Tag>
                      <button
                        type="button"
                        onClick={() => go("holdings", d.symbol)}
                        className="num rounded-sm underline decoration-line-strong underline-offset-2 outline-none hover:decoration-ink-3 focus-visible:ring-2 focus-visible:ring-ring/50"
                      >
                        {d.symbol}
                      </button>
                    </td>
                    <td className="num py-2 text-right">{d.size_pct === null ? DASH : `${d.size_pct.toFixed(1)}%`}</td>
                    <td className="py-2 pl-4">
                      {d.views.length ? (
                        <div className="flex flex-col gap-0.5">
                          {d.views.map((id) => (
                            <button
                              key={id}
                              type="button"
                              onClick={() => go("views", id)}
                              className="num w-fit rounded-sm text-left text-xs whitespace-nowrap underline decoration-line-strong underline-offset-2 outline-none hover:decoration-ink-3 focus-visible:ring-2 focus-visible:ring-ring/50"
                            >
                              {id}
                            </button>
                          ))}
                        </div>
                      ) : (
                        <span className="text-ink-3">none</span>
                      )}
                    </td>
                    <td className="py-2 pl-4 leading-relaxed text-ink-2">{d.reason}</td>
                    <td className="num py-2 pl-4 whitespace-nowrap text-ink-2">{longDate(d.review_on)}</td>
                    <td className="py-2 pl-4">
                      {d.flags.length ? (
                        <ul className="flex flex-col gap-1">
                          {d.flags.map((f, i) => (
                            <li key={i} className="flex items-start gap-1.5 text-xs leading-relaxed">
                              <TriangleAlert className="mt-0.5 size-3.5 shrink-0 text-warn" aria-hidden />
                              {f}
                            </li>
                          ))}
                        </ul>
                      ) : (
                        <span className="text-xs text-ink-3">none</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <Empty>No decisions logged yet.</Empty>
        )}
      </Panel>

      <Panel
        className="mt-3"
        title="What happened after"
        sub="Decisions past their review date: what the stock did since, next to the world index."
      >
        {model.reviews.length ? (
          <div className="relative -mx-1 overflow-x-auto px-1">
            <table className="w-full min-w-[480px] text-[13px]">
              <thead>
                <tr className="text-[11px] text-ink-3">
                  <th className="pb-2 text-left font-normal">Trade</th>
                  <th className="pb-2 text-left font-normal">Date</th>
                  <th className="pb-2 text-right font-normal">Stock since</th>
                  <th className="pb-2 text-right font-normal">World since</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-line">
                {model.reviews.map((r, i) => (
                  <tr key={i}>
                    <td className="py-2 pr-3">
                      <Tag className="mr-2">{r.action}</Tag>
                      <span className="num">{r.symbol}</span>
                    </td>
                    <td className="num py-2 pr-3 text-ink-2">{longDate(r.date)}</td>
                    <td className="py-2 text-right">
                      <Move value={r.since} className="justify-end" />
                    </td>
                    <td className="py-2 text-right">
                      <Move value={r.world} className="justify-end text-ink-2" />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <Empty>No decision has reached its review date yet.</Empty>
        )}
        <p className="mt-3 text-xs text-ink-3">One trade's outcome is mostly noise. This is a record, not a verdict.</p>
      </Panel>
    </>
  )
}
