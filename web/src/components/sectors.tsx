/** Your stocks by sector against the sector average. Every figure comes from performance.py: your stocks in a
 * sector at today's weights inside it, the sector's MSCI World fund, and the gap between them. The page only
 * picks the window. */
import { useState } from "react"
import { pct } from "@/lib/format"
import type { Model, Period } from "@/lib/types"
import { Empty, Move, Panel, Segmented } from "./kit"

const WINDOWS: readonly { id: Period; label: string }[] = [
  { id: "1M", label: "1M" },
  { id: "3M", label: "3M" },
  { id: "YTD", label: "YTD" },
  { id: "1Y", label: "1Y" },
]

export function SectorPanel({ model, className }: { model: Model; className?: string }) {
  const [win, setWin] = useState<Period>("1Y")
  const rows = model.performance.sectors ?? []
  return (
    <Panel
      className={className}
      title="Your sectors against the sector average"
      sub={`Your stocks in each sector, at today's weights, next to that sector's MSCI World fund, all in ${model.home}. Funds and cash have no single sector and are left out.`}
      action={<Segmented value={win} options={WINDOWS} onChange={setWin} label="Window" />}
    >
      {rows.length ? (
        <div className="relative -mx-1 overflow-x-auto px-1">
          <table className="w-full min-w-[520px] text-[13px]">
            <thead>
              <tr className="text-[11px] text-ink-3">
                <th className="pb-2 text-left font-normal">Sector</th>
                <th className="pb-2 text-right font-normal">Share of you</th>
                <th className="pb-2 text-right font-normal">Your stocks</th>
                <th className="pb-2 text-right font-normal">Sector average</th>
                <th className="pb-2 text-right font-normal">Difference</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-line">
              {rows.map((r) => (
                <tr key={r.id}>
                  <th scope="row" className="py-2 pr-3 text-left font-normal">
                    <div>{r.label}</div>
                    <div className="num text-[11px] text-ink-3">
                      {r.holdings.join(" · ")}
                      {r.fund ? ` vs ${r.fund}` : " · no sector fund"}
                    </div>
                  </th>
                  <td className="num py-2 pl-3 text-right text-ink-2">{pct(r.weight)}</td>
                  <td className="py-2 pl-3 text-right">
                    <Move value={r.you[win]} />
                  </td>
                  <td className="py-2 pl-3 text-right">
                    <Move value={r.average[win]} />
                  </td>
                  <td className="py-2 pl-3 text-right">
                    <Move value={r.gap[win]} unit=" pts" />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="mt-2 text-[11px] text-ink-3">
            A replay of today's stocks, not your actual past return. A dash means a price history too short for the
            window.
          </p>
        </div>
      ) : (
        <Empty>No sectors yet. They appear after the next prepare run.</Empty>
      )}
    </Panel>
  )
}
