/** The small pieces every page is built from: cards, headers, numbers, chips, sources, legends and controls.
 * Design rules live in docs/DASHBOARD.md section 4; web/CLAUDE.md has the short list. */
import { animate, motion, useReducedMotion } from "motion/react"
import { useEffect, useId, useLayoutEffect, useRef, type ReactNode } from "react"
import { ArrowRight, ArrowUpRight, Info, TriangleAlert } from "lucide-react"
import { Card, CardAction, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { cn } from "@/lib/utils"
import { heat, signed, tone, webUrl } from "@/lib/format"
import type { Go } from "@/lib/hooks"
import type { BetState, Model, NewsItem } from "@/lib/types"

/** The one spring everything moves on, the press, and the ease for fades. */
export const SPRING = { type: "spring", stiffness: 380, damping: 30 } as const
export const PRESS = { scale: 0.97 } as const
export const EASE = [0.16, 1, 0.3, 1] as const

export interface PageProps {
  model: Model
  item: string | null
  go: Go
}

/** A card one step lighter than the page, with a hairline edge. */
export function Panel({
  title,
  sub,
  action,
  id,
  className,
  bodyClassName,
  children,
}: {
  title?: ReactNode
  sub?: ReactNode
  action?: ReactNode
  id?: string
  className?: string
  bodyClassName?: string
  children?: ReactNode
}) {
  return (
    <Card id={id} className={cn("min-w-0 scroll-mt-20 gap-3 py-3.5 text-[13px]/normal ring-line", className)}>
      {(title || action) && (
        <CardHeader className="px-4">
          {title && (
            <CardTitle role="heading" aria-level={2} className="text-[13px] leading-5 font-medium">
              {title}
            </CardTitle>
          )}
          {sub && <CardDescription className="text-xs/normal text-ink-3">{sub}</CardDescription>}
          {action && <CardAction className="flex items-center gap-2">{action}</CardAction>}
        </CardHeader>
      )}
      <CardContent className={cn("min-w-0 flex-1 px-4", bodyClassName)}>{children}</CardContent>
    </Card>
  )
}

export function PageHeader({ title, sub, action }: { title: string; sub?: ReactNode; action?: ReactNode }) {
  return (
    <header className="mb-4 flex flex-wrap items-end justify-between gap-3">
      <div className="min-w-0">
        <h1 className="text-lg leading-7 font-semibold tracking-tight">{title}</h1>
        {sub && <p className="mt-0.5 max-w-3xl text-[13px] text-ink-2">{sub}</p>}
      </div>
      {action}
    </header>
  )
}

/** A small heading inside a card. */
export function SubHead({ children, className }: { children: ReactNode; className?: string }) {
  return <h3 className={cn("text-xs font-medium text-ink-2", className)}>{children}</h3>
}

/** A number that counts up once when it appears. The final text is always in the page for screen readers. */
export function Ticker({ value, format }: { value: number; format: (x: number) => string }) {
  const ref = useRef<HTMLSpanElement>(null)
  const fmt = useRef(format)
  const reduce = useReducedMotion()
  const text = format(value)
  useEffect(() => {
    fmt.current = format
  })
  useLayoutEffect(() => {
    if (ref.current) ref.current.textContent = text
  }, [text])
  useEffect(() => {
    const el = ref.current
    if (!el || reduce) return
    const controls = animate(0, value, {
      duration: 0.7,
      ease: EASE,
      onUpdate: (v) => {
        el.textContent = fmt.current(v)
      },
    })
    return () => {
      controls.stop()
      el.textContent = text
    }
  }, [value, text, reduce])
  return (
    <>
      <span className="sr-only">{text}</span>
      <span ref={ref} aria-hidden />
    </>
  )
}

function Triangle({ up }: { up: boolean }) {
  return (
    <svg viewBox="0 0 8 8" aria-hidden className={cn("size-[7px] shrink-0", up ? "fill-pos" : "fill-neg")}>
      <path d={up ? "M4 .6 7.6 7H.4z" : "M4 7.4 .4 1h7.2z"} />
    </svg>
  )
}

/** A move with its sign. The text stays in ink; a small blue or red triangle beside it carries the direction. */
export function Move({
  value,
  digits = 1,
  unit = "%",
  count = false,
  className,
}: {
  value: number | null | undefined
  digits?: number
  unit?: string
  count?: boolean
  className?: string
}) {
  const t = tone(value)
  return (
    <span className={cn("num inline-flex items-center gap-1 whitespace-nowrap", t === "none" && "text-ink-3", className)}>
      {t === "pos" && <Triangle up />}
      {t === "neg" && <Triangle up={false} />}
      {count && typeof value === "number" && !Number.isNaN(value) ? (
        <Ticker value={value} format={(x) => signed(x, digits, unit)} />
      ) : (
        signed(value, digits, unit)
      )}
    </span>
  )
}

export function TipIcon({ text }: { text: string }) {
  return (
    <span
      tabIndex={0}
      role="img"
      aria-label={text}
      data-tip={text}
      className="inline-flex cursor-help rounded-sm text-ink-3 outline-none hover:text-ink-2 focus-visible:ring-2 focus-visible:ring-ring/50"
    >
      <Info className="size-3" />
    </span>
  )
}

/** A headline number in its own small card. */
export function Stat({
  label,
  tip,
  value,
  sub,
  onClick,
}: {
  label: string
  tip?: string
  value: ReactNode
  sub?: ReactNode
  onClick?: () => void
}) {
  const body = (
    <>
      <span className="flex items-center gap-1 text-xs text-ink-3">
        {label}
        {tip && !onClick && <TipIcon text={tip} />}
      </span>
      <span className="num mt-1.5 block text-[22px] leading-7 font-medium tracking-tight text-foreground">{value}</span>
      {sub && <span className="mt-1 line-clamp-2 text-xs text-ink-2">{sub}</span>}
    </>
  )
  const cls = "flex min-w-0 flex-col rounded-lg bg-card px-4 py-3.5 text-left ring-1 ring-line"
  if (onClick) {
    return (
      <motion.button
        type="button"
        whileTap={PRESS}
        onClick={onClick}
        data-tip={tip}
        className={cn(cls, "transition-colors duration-150 hover:bg-card-2 focus-visible:ring-2 focus-visible:ring-ring/50")}
      >
        {body}
      </motion.button>
    )
  }
  return <div className={cls}>{body}</div>
}

/** How busy a theme is today: filled is two or more events, faint is one, hollow is none. */
export function HeatDot({ n }: { n: number }) {
  const level = heat(n).level
  return (
    <span
      aria-hidden
      className={cn(
        "size-2 shrink-0 rounded-full",
        level === "busy" && "bg-foreground",
        level === "active" && "bg-foreground/35",
        level === "quiet" && "ring-1 ring-ink-3 ring-inset",
      )}
    />
  )
}

export function Chip({
  label,
  count,
  tip,
  active,
  onClick,
  className,
}: {
  label: ReactNode
  count?: number
  tip?: string
  /** Set only on filter chips, so they read as pressed or not; a chip that just links leaves it out. */
  active?: boolean
  onClick?: () => void
  className?: string
}) {
  const cls = cn(
    "inline-flex h-6 max-w-full items-center gap-1.5 rounded-md border px-2 text-xs whitespace-nowrap",
    active ? "border-you/50 bg-you/10 text-foreground" : "border-line bg-card-2 text-foreground",
    className,
  )
  const inner = (
    <>
      {count !== undefined && <HeatDot n={count} />}
      <span className="truncate">{label}</span>
    </>
  )
  if (onClick) {
    return (
      <motion.button
        type="button"
        whileTap={PRESS}
        onClick={onClick}
        data-tip={tip}
        aria-pressed={active}
        className={cn(cls, "cursor-pointer transition-colors duration-150 hover:border-line-strong")}
      >
        {inner}
      </motion.button>
    )
  }
  return (
    <span data-tip={tip} className={cls}>
      {inner}
    </span>
  )
}

/** Inline code for a command the user types in Claude Code. */
export function Cmd({ children }: { children: ReactNode }) {
  return <code className="num rounded-[4px] bg-card-2 px-1 py-px text-[12px] text-foreground">{children}</code>
}

/** The sources behind a claim, as links that open in a new tab. Only web addresses become links. */
export function Sources({ ids, news, className }: { ids?: string[]; news: Record<string, NewsItem>; className?: string }) {
  const items = (ids ?? []).map((id) => news[id]).filter((n): n is NewsItem => !!n)
  if (!items.length) return null
  return (
    <div className={cn("flex flex-wrap items-center gap-x-2.5 gap-y-1 text-xs text-ink-3", className)}>
      {items.map((item, i) => {
        const url = webUrl(item.url)
        const label = item.source || "Source"
        return url ? (
          <a
            key={i}
            href={url}
            target="_blank"
            rel="noopener noreferrer"
            data-tip={item.title}
            className="inline-flex items-center gap-0.5 rounded-sm underline decoration-line-strong underline-offset-2 outline-none hover:text-foreground hover:decoration-ink-3 focus-visible:ring-2 focus-visible:ring-ring/50"
          >
            {label}
            <ArrowUpRight className="size-3" aria-hidden />
          </a>
        ) : (
          <span key={i} data-tip={item.title}>
            {label}
          </span>
        )
      })}
    </div>
  )
}

export function Empty({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <div className={cn("rounded-md border border-dashed border-line-strong px-4 py-5 text-center text-[13px] text-ink-2", className)}>
      {children}
    </div>
  )
}

export type SwatchKind = "line" | "dash" | "box" | "tick" | "ring" | "dot" | "hatch" | "tri"

export function Swatch({ kind, color }: { kind: SwatchKind; color: string }) {
  switch (kind) {
    case "line":
      return (
        <svg width="14" height="8" aria-hidden className="shrink-0">
          <line x1="1" y1="4" x2="13" y2="4" stroke={color} strokeWidth="2" strokeLinecap="round" />
        </svg>
      )
    case "dash":
      return (
        <svg width="14" height="8" aria-hidden className="shrink-0">
          <line x1="0" y1="4" x2="14" y2="4" stroke={color} strokeWidth="1.5" strokeDasharray="3 2" />
        </svg>
      )
    case "box":
      return <span aria-hidden className="size-2.5 shrink-0 rounded-[2px]" style={{ background: color }} />
    case "tick":
      return <span aria-hidden className="h-3 w-[2px] shrink-0 rounded-full" style={{ background: color }} />
    case "ring":
      return <span aria-hidden className="size-2.5 shrink-0 rounded-full border border-dashed" style={{ borderColor: color }} />
    case "dot":
      return <span aria-hidden className="size-2 shrink-0 rounded-full" style={{ background: color }} />
    case "hatch":
      return (
        <svg width="10" height="10" aria-hidden className="shrink-0 overflow-hidden rounded-[2px]">
          <rect width="10" height="10" fill={color} fillOpacity="0.12" />
          <path d="M-2 4 4-2M-2 10 10-2M4 12 12 4" stroke={color} strokeWidth="1" />
        </svg>
      )
    case "tri":
      return (
        <svg viewBox="0 0 8 8" aria-hidden className="size-2 shrink-0">
          <path d="M4 .5 7.5 7.5H.5z" fill={color} />
        </svg>
      )
  }
}

const STATE_WORDS = { clear: "Clear", amber: "Amber", red: "Red", no_data: "No data" } as const

/** A state as a shape and a word, never colour alone: clear ● blue, amber ◆, red ▲, no data ○. The word stays in
 * ink; without one, the state is read out to screen readers. */
export function StateMark({ state, word, className }: { state: BetState; word?: ReactNode; className?: string }) {
  return (
    <span className={cn("inline-flex items-center gap-1.5 whitespace-nowrap", className)}>
      <svg viewBox="0 0 8 8" aria-hidden className="size-2 shrink-0">
        {state === "clear" && <circle cx="4" cy="4" r="3.4" className="fill-pos" />}
        {state === "amber" && <path d="M4 .2 7.8 4 4 7.8 .2 4z" className="fill-warn" />}
        {state === "red" && <path d="M4 .5 7.7 7.4H.3z" className="fill-neg" />}
        {state === "no_data" && <circle cx="4" cy="4" r="3" fill="none" strokeWidth="1.2" className="stroke-ink-3" />}
      </svg>
      {word ?? <span className="sr-only">{STATE_WORDS[state]}</span>}
    </span>
  )
}

/** A caution in words: ink text with a small amber mark, since amber is too pale for text in the light theme. */
export function Caution({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <p className={cn("flex items-start gap-1.5 text-xs text-ink-2", className)}>
      <TriangleAlert className="mt-px size-3.5 shrink-0 text-warn" aria-hidden />
      <span className="min-w-0">{children}</span>
    </p>
  )
}

export interface LegendItem {
  label: ReactNode
  kind: SwatchKind
  color: string
}

export function Legend({ items, className }: { items: LegendItem[]; className?: string }) {
  return (
    <div className={cn("flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-ink-2", className)}>
      {items.map((it, i) => (
        <span key={i} className="inline-flex items-center gap-1.5">
          <Swatch kind={it.kind} color={it.color} />
          {it.label}
        </span>
      ))}
    </div>
  )
}

/** The legend under every you-against-the-world-index chart. */
export const YOU_WORLD: LegendItem[] = [
  { label: "You", kind: "box", color: "var(--you)" },
  { label: "World index", kind: "tick", color: "var(--world)" },
]

/** A row of buttons where one is on; the marker slides between them on a spring. */
export function Segmented<T extends string>({
  value,
  options,
  onChange,
  label,
  className,
}: {
  value: T
  options: readonly { id: T; label: ReactNode }[]
  onChange: (v: T) => void
  label: string
  className?: string
}) {
  const id = useId()
  return (
    <div role="group" aria-label={label} className={cn("inline-flex items-center gap-0.5 rounded-md bg-card-2 p-0.5 ring-1 ring-line", className)}>
      {options.map((o) => {
        const on = o.id === value
        return (
          <motion.button
            key={o.id}
            type="button"
            whileTap={PRESS}
            aria-pressed={on}
            onClick={() => onChange(o.id)}
            className={cn(
              "relative h-6 rounded-[5px] px-2 text-xs outline-none transition-colors duration-150 focus-visible:ring-2 focus-visible:ring-ring/50",
              on ? "text-foreground" : "text-ink-3 hover:text-ink-2",
            )}
          >
            {on && (
              <motion.span
                layoutId={`seg-${id}`}
                transition={SPRING}
                className="absolute inset-0 rounded-[5px] bg-raised ring-1 ring-line-strong"
              />
            )}
            <span className="relative">{o.label}</span>
          </motion.button>
        )
      })}
    </div>
  )
}

export function Banner({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <div role="status" className={cn("flex items-start gap-2 rounded-md bg-card px-3 py-2 text-[13px] ring-1 ring-line", className)}>
      <TriangleAlert className="mt-0.5 size-4 shrink-0 text-warn" aria-hidden />
      <div className="min-w-0">{children}</div>
    </div>
  )
}

/** A quiet link to the page that has the rest. */
export function More({ children, onClick }: { children: ReactNode; onClick: () => void }) {
  return (
    <motion.button
      type="button"
      whileTap={PRESS}
      onClick={onClick}
      className="inline-flex h-6 items-center gap-1 rounded-md px-1.5 text-xs whitespace-nowrap text-ink-2 outline-none transition-colors duration-150 hover:bg-card-2 hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring/50"
    >
      {children}
      <ArrowRight className="size-3.5" aria-hidden />
    </motion.button>
  )
}

/** A small label for a kind of thing: fund, stock, region. */
export function Tag({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <span className={cn("inline-flex h-5 items-center rounded-[4px] px-1.5 text-[11px] text-ink-2 ring-1 ring-line", className)}>
      {children}
    </span>
  )
}
