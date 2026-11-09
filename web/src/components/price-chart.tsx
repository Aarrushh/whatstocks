/** Price lines against the world index, on the shadcn chart container (Recharts). You in solid orange, the world
 * index dashed grey. The window control cuts each line the way performance.py cuts its period figures, so the
 * change beside each name matches the numbers elsewhere on the page (series.test.ts checks it on the demo). */
import { useMemo, useState } from "react"
import { CartesianGrid, Line, LineChart, ReferenceLine, XAxis, YAxis } from "recharts"
import { ChartContainer, ChartTooltip, type ChartConfig } from "@/components/ui/chart"
import { longDate, shortDate, signed } from "@/lib/format"
import { WINDOWS, change, windowed, type WindowId } from "@/lib/series"
import type { Point } from "@/lib/types"
import { Empty, Move, Segmented, Swatch } from "./kit"

export interface LineSeries {
  key: "you" | "world" | "compare"
  label: string
  points: Point[]
}

const STYLE = {
  you: { color: "var(--you)", width: 2, dash: undefined, swatch: "line" },
  world: { color: "var(--world)", width: 1.5, dash: "4 3", swatch: "dash" },
  compare: { color: "var(--c7)", width: 1.5, dash: "1 3", swatch: "dash" },
} as const

type Row = { date: string; you?: number; world?: number; compare?: number }

export function PriceChart({ series, height = 240 }: { series: LineSeries[]; height?: number }) {
  const [win, setWin] = useState<WindowId>("1Y")
  const cut = useMemo(() => series.map((s) => ({ ...s, line: windowed(s.points, win) })), [series, win])
  const data = useMemo(() => {
    const rows = new Map<string, Row>()
    for (const s of cut) {
      for (const [d, v] of s.line) {
        const row = rows.get(d) ?? { date: d }
        row[s.key] = v / 100 - 1
        rows.set(d, row)
      }
    }
    return [...rows.values()].sort((a, b) => (a.date < b.date ? -1 : a.date > b.date ? 1 : 0))
  }, [cut])
  const config = useMemo<ChartConfig>(
    () => Object.fromEntries(series.map((s) => [s.key, { label: s.label, color: STYLE[s.key].color }])),
    [series],
  )
  const options = WINDOWS.map((w) => ({ id: w.id, label: w.label }))

  if (series.every((s) => s.points.length < 2)) return <Empty>No price history yet.</Empty>
  return (
    <div>
      <div className="mb-3 flex flex-wrap items-center justify-between gap-x-4 gap-y-2">
        <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs">
          {cut.map((s) => (
            <span key={s.key} className="inline-flex items-center gap-1.5 text-ink-2">
              <Swatch kind={STYLE[s.key].swatch} color={STYLE[s.key].color} />
              {s.label}
              <Move value={change(s.line)} className="text-foreground" />
            </span>
          ))}
        </div>
        <Segmented value={win} options={options} onChange={setWin} label="Window" />
      </div>
      <ChartContainer config={config} className="aspect-auto w-full" style={{ height }}>
        <LineChart data={data} margin={{ top: 6, right: 6, bottom: 0, left: 0 }}>
          <CartesianGrid vertical={false} stroke="var(--line)" />
          <XAxis
            dataKey="date"
            tickLine={false}
            axisLine={false}
            tickMargin={8}
            minTickGap={44}
            tickFormatter={(d: string) => shortDate(d)}
            tick={{ fontFamily: "var(--font-mono)", fontSize: 10.5 }}
          />
          <YAxis
            tickLine={false}
            axisLine={false}
            width={44}
            tickFormatter={(v: number) => signed(v, 0)}
            tick={{ fontFamily: "var(--font-mono)", fontSize: 10.5 }}
            domain={["auto", "auto"]}
          />
          <ReferenceLine y={0} stroke="var(--line-strong)" />
          <ChartTooltip
            cursor={{ stroke: "var(--line-strong)", strokeWidth: 1 }}
            content={({ active, payload, label }) =>
              active && payload?.length ? (
                <div className="rounded-md bg-popover px-2.5 py-1.5 text-xs shadow-lg ring-1 shadow-black/25 ring-line-strong">
                  <div className="mb-1 text-ink-3">{longDate(String(label))}</div>
                  {payload.map((p) => {
                    const key = String(p.dataKey) as LineSeries["key"]
                    return (
                      <div key={key} className="flex items-center gap-2">
                        <Swatch kind={STYLE[key].swatch} color={STYLE[key].color} />
                        <span className="text-ink-2">{config[key]?.label}</span>
                        <Move value={typeof p.value === "number" ? p.value : null} className="ml-auto pl-3" />
                      </div>
                    )
                  })}
                  <div className="mt-1 text-[11px] text-ink-3">since the window opened</div>
                </div>
              ) : null
            }
          />
          {cut.map((s) => (
            <Line
              key={s.key}
              dataKey={s.key}
              type="linear"
              stroke={STYLE[s.key].color}
              strokeWidth={STYLE[s.key].width}
              strokeDasharray={STYLE[s.key].dash}
              dot={false}
              activeDot={{ r: 3.5, fill: STYLE[s.key].color, stroke: "var(--card)", strokeWidth: 2 }}
              connectNulls
              isAnimationActive={false}
            />
          ))}
        </LineChart>
      </ChartContainer>
    </div>
  )
}
