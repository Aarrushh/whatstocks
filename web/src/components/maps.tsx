/** The three maps: a conflict scan's bubbles, the ripple map of how today's events spread between themes, and
 * where your companies are based. Python lays out the bubbles and the ripple map (geometry.py); the page draws
 * them, so labels and positions match what the tests check. */
import { useId, useMemo, type CSSProperties } from "react"
import { createMap } from "svg-dotted-map"
import { pct, RIPPLE_WORD, SCAN_WORD } from "@/lib/format"
import { PLACES } from "@/lib/geo"
import type { BubbleGroup, Channel, Effect, Ripples, Scan } from "@/lib/types"
import { Swatch } from "./kit"

const FILL: Record<Effect, string> = { hurt: "var(--neg)", help: "var(--pos)", mixed: "var(--ink-3)" }
const OPACITY = { high: 0.9, medium: 0.6, low: 0.32 } as const
const GROUP_WORD: Record<Effect, string> = { hurt: "Would hurt", mixed: "Mixed", help: "Would help" }
/** A faint ring of the card colour behind text that sits on a coloured bubble. */
const HALO: CSSProperties = { paintOrder: "stroke", stroke: "var(--card)", strokeWidth: 3, strokeOpacity: 0.55, strokeLinejoin: "round" }

function bubbleTip(c: Channel): string {
  return `${c.label} (${c.kind}): ${SCAN_WORD[c.effect]}, ${c.strength} strength. You ${pct(c.you)}, world index ${pct(c.world)}.\n${c.why}`
}

/** One group of bubbles (hurt, mixed or help), drawn at the size geometry.py measured its labels for. */
function BubbleChart({ group, channels }: { group: BubbleGroup; channels: Channel[] }) {
  const [x0, y0, w, h] = group.box
  return (
    <svg
      viewBox={`${x0} ${y0} ${w} ${h}`}
      width={w}
      height={h}
      role="group"
      aria-label={`${GROUP_WORD[group.effect]}: ${group.bubbles.length} channels`}
      className="h-auto max-w-full overflow-visible font-mono"
    >
      {group.bubbles.map((b) => {
        const c = channels[b.index]
        if (!c) return null
        const tip = bubbleTip(c)
        return (
          <g key={b.index} tabIndex={0} aria-label={tip} data-tip={tip} className="outline-none [&:focus-visible>circle:first-child]:stroke-foreground">
            <circle cx={b.x} cy={b.y} r={b.r} fill={FILL[c.effect]} fillOpacity={OPACITY[c.strength]} stroke="transparent" strokeWidth={2} />
            {b.ring > 0 && (
              <circle cx={b.x} cy={b.y} r={b.ring} fill="none" stroke="var(--world)" strokeWidth={1.25} strokeDasharray="3 3" />
            )}
            {b.inside && (
              <>
                <text x={b.x} y={b.y - 2} textAnchor="middle" fontSize={11} fill="var(--foreground)" style={HALO}>
                  {c.label}
                </text>
                <text x={b.x} y={b.y + 12} textAnchor="middle" fontSize={10.5} fill="var(--foreground)" style={HALO}>
                  {pct(c.you)}
                </text>
              </>
            )}
            {b.beside && (
              <text x={b.beside.x} y={b.beside.y} textAnchor={b.beside.anchor} fontSize={10.5} fill="var(--foreground)">
                {c.label} <tspan fill="var(--ink-2)">{pct(c.you)}</tspan>
              </text>
            )}
          </g>
        )
      })}
    </svg>
  )
}

/** Every theme and region a conflict reaches, one bubble map per effect, sized by your money in it. */
export function BubbleMap({ scan }: { scan: Scan }) {
  const share = (effect: Effect, who: "you" | "world") => scan.totals[who][`${effect}_share` as const]
  return (
    <div className="flex flex-wrap items-start justify-center gap-x-12 gap-y-8">
      {scan.bubbles.map((g) => (
        <figure key={g.effect} className="flex max-w-full min-w-0 flex-col items-center">
          <figcaption className="mb-3 flex flex-wrap items-center justify-center gap-x-2 text-xs">
            <Swatch kind="dot" color={FILL[g.effect]} />
            <span className="font-medium text-foreground">{GROUP_WORD[g.effect]}</span>
            <span className="num text-ink-3">
              you {pct(share(g.effect, "you"))} · world {pct(share(g.effect, "world"))}
            </span>
          </figcaption>
          <BubbleChart group={g} channels={scan.channels} />
          {g.listed.length > 0 && (
            <p className="mt-2 max-w-72 text-center text-xs text-ink-3">
              Too small to draw:{" "}
              {g.listed
                .map((i) => scan.channels[i])
                .filter((c): c is Channel => !!c)
                .map((c) => `${c.label} ${pct(c.you)}`)
                .join(", ")}
            </p>
          )}
        </figure>
      ))}
    </div>
  )
}

const EDGE = { hurt: "var(--neg)", help: "var(--pos)", unclear: "var(--world)" } as const

/** How today's events spread from theme to theme. Positions and label sides come from geometry.network_layout;
 * labels are HTML placed by the .net/.nl rules in index.css so they stay crisp at any width. */
export function RippleMap({ ripples }: { ripples: Ripples }) {
  const id = useId().replace(/[^a-zA-Z0-9]/g, "")
  const label = (nodeId: string) => ripples.nodes.find((n) => n.id === nodeId)?.label ?? nodeId
  return (
    <div className="net relative mx-auto w-full max-w-[720px]" style={{ aspectRatio: `${ripples.w} / ${ripples.h}` }}>
      <svg viewBox={`0 0 ${ripples.w} ${ripples.h}`} role="group" aria-label="Ripple map" className="absolute inset-0 size-full overflow-visible">
        <defs>
          {(["hurt", "help", "unclear"] as const).map((e) => (
            <marker
              key={e}
              id={`${id}-${e}`}
              viewBox="0 0 10 10"
              refX="8"
              refY="5"
              markerWidth="2.4"
              markerHeight="2.4"
              markerUnits="userSpaceOnUse"
              orient="auto-start-reverse"
            >
              <path d="M0,1 L9,5 L0,9 z" fill={EDGE[e]} />
            </marker>
          ))}
        </defs>
        {ripples.edges.map((e, i) => {
          const tip = `${label(e.from)} → ${label(e.to)}: ${RIPPLE_WORD[e.effect]}.\n${e.why}`
          return (
            <g key={i} data-tip={tip} tabIndex={0} aria-label={tip} className="outline-none [&:focus-visible>path:last-child]:stroke-foreground">
              <path d={e.d} fill="none" stroke="transparent" strokeWidth={12} vectorEffect="non-scaling-stroke" />
              <path
                d={e.d}
                fill="none"
                stroke={EDGE[e.effect]}
                strokeWidth={1.5}
                strokeDasharray={e.effect === "unclear" ? "4 3" : undefined}
                vectorEffect="non-scaling-stroke"
                markerEnd={`url(#${id}-${e.effect})`}
              />
            </g>
          )
        })}
        {ripples.nodes.map((n) => (
          <circle
            key={n.id}
            cx={n.x}
            cy={n.y}
            r={n.r}
            data-tip={`${n.label}: ${pct(n.weight)} of your portfolio`}
            fill={n.hub ? "color-mix(in oklab, var(--you) 22%, var(--card))" : "var(--card-2)"}
            stroke={n.hub ? "var(--you)" : "var(--line-strong)"}
            strokeWidth={1.25}
            vectorEffect="non-scaling-stroke"
          />
        ))}
      </svg>
      {ripples.nodes.map((n) => (
        <span
          key={n.id}
          className={`nl ${n.side} text-xs`}
          style={{ left: `${(n.x / ripples.w) * 100}%`, top: `${(n.y / ripples.h) * 100}%`, "--r": n.r, "--x": n.x / ripples.w } as CSSProperties}
        >
          <span className="text-foreground">{n.label}</span> <span className="num text-ink-3">{pct(n.weight)}</span>
        </span>
      ))}
    </div>
  )
}

const MAP_W = 150
const MAP_H = 75
let dotted: ReturnType<typeof createMap> | null = null
/** The dotted world is the same on every visit, so it is worked out once. */
function world() {
  dotted ??= createMap({ width: MAP_W, height: MAP_H, mapSamples: 4200 })
  return dotted
}

/** Where your companies are based: a dot per country sized by your share, a dashed ring for the world index's. */
export function WorldMap({ you, world: theirs }: { you: Record<string, number>; world: Record<string, number> }) {
  const map = world()
  const dots = useMemo(() => map.points.map((p) => `M${p.x.toFixed(2)},${p.y.toFixed(2)}h0`).join(""), [map])
  const names = [...new Set([...Object.keys(you), ...Object.keys(theirs)])].filter((k) => PLACES[k])
  const top = Math.max(1e-9, ...names.flatMap((k) => [you[k] ?? 0, theirs[k] ?? 0]))
  const markers = map
    .addMarkers(names.map((name) => ({ lat: PLACES[name][0], lng: PLACES[name][1], name })))
    .map((m) => ({ ...m, mine: you[m.name] ?? 0, index: theirs[m.name] ?? 0 }))
    .sort((a, b) => Math.max(b.mine, b.index) - Math.max(a.mine, a.index))
  const radius = (share: number) => 5 * Math.sqrt(share / top)
  return (
    <svg viewBox={`0 0 ${MAP_W} ${MAP_H}`} role="group" aria-label="Where your companies are based" className="h-auto w-full">
      <path d={dots} stroke="var(--ink-3)" strokeOpacity={0.5} strokeWidth={0.8} strokeLinecap="round" />
      {markers.map((m) => {
        const r = radius(m.mine)
        const ring = radius(m.index)
        return (
          <g key={m.name} data-tip={`${m.name}: you ${pct(m.mine)}, world index ${pct(m.index)}`}>
            {m.mine > 0 && <circle cx={m.x} cy={m.y} r={Math.max(r, 0.7)} fill="var(--you)" fillOpacity={0.85} />}
            {ring > 0 && <circle cx={m.x} cy={m.y} r={ring} fill="none" stroke="var(--world)" strokeWidth={0.35} strokeDasharray="0.9 0.7" />}
            <circle cx={m.x} cy={m.y} r={Math.max(r, ring, 2.2)} fill="transparent" />
          </g>
        )
      })}
    </svg>
  )
}
