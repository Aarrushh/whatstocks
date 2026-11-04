/** Pieces of the morning brief shared by several pages: an event read through the four questions, the list of
 * things to watch, and the small tag that says whether news counts for or against a view. */
import { cn } from "@/lib/utils"
import { due, longDate, shortDate } from "@/lib/format"
import type { Go } from "@/lib/hooks"
import type { BriefEvent, Model, WatchItem } from "@/lib/types"
import { NumDot } from "./charts"
import { Chip, Sources } from "./kit"

const EFFECT_COLOR: Record<string, string> = { for: "var(--pos)", against: "var(--neg)" }

/** For, against or unclear: a small coloured dot, with the word in ink. */
export function EffectTag({ effect }: { effect: string }) {
  return (
    <span className="inline-flex items-center gap-1 text-xs whitespace-nowrap text-ink-2">
      <span aria-hidden className="size-1.5 rounded-full" style={{ background: EFFECT_COLOR[effect] ?? "var(--ink-3)" }} />
      {effect}
    </span>
  )
}

/** One event: what happened, who pays and who gets paid, what it touches, and what it means for your views. */
export function EventCard({ event, n, model, go }: { event: BriefEvent; n: number; model: Model; go: Go }) {
  const themes = event.touches?.themes ?? []
  const holdings = event.touches?.holdings ?? []
  const views = event.views ?? []
  return (
    <article className="grid grid-cols-[1.25rem_minmax(0,1fr)] gap-x-2 py-3 first:pt-0 last:pb-0">
      <span className="num pt-0.5 text-xs text-ink-3">{n}</span>
      <div className="min-w-0">
        <p className="text-[13px] leading-relaxed text-foreground">{event.what}</p>
        <dl className="mt-2 grid gap-y-1.5 text-[13px] sm:grid-cols-[5.5rem_minmax(0,1fr)] sm:gap-x-3">
          <dt className="text-xs text-ink-3 sm:pt-0.5">Money</dt>
          <dd className="leading-relaxed text-ink-2">{event.money}</dd>
          <dt className="text-xs text-ink-3 sm:pt-1">Touches</dt>
          <dd className="flex flex-wrap gap-1">
            {themes.map((id) => (
              <Chip key={id} label={model.theme_labels[id] ?? id} onClick={() => go("world", id)} />
            ))}
            {holdings.map((s) => (
              <Chip key={s} label={<span className="num">{s}</span>} onClick={() => go("holdings", s)} />
            ))}
            {themes.length === 0 && holdings.length === 0 && <span className="text-ink-3 sm:pt-0.5">nothing you hold</span>}
          </dd>
          {views.length > 0 && (
            <>
              <dt className="text-xs text-ink-3 sm:pt-0.5">Your views</dt>
              <dd className="flex flex-col gap-1">
                {views.map((v) => (
                  <div key={v.view_id} className="leading-relaxed">
                    <EffectTag effect={v.effect} />{" "}
                    <button
                      type="button"
                      onClick={() => go("views", v.view_id)}
                      className="num rounded-sm text-xs text-foreground underline decoration-line-strong underline-offset-2 outline-none hover:decoration-ink-3 focus-visible:ring-2 focus-visible:ring-ring/50"
                    >
                      {v.view_id}
                    </button>
                    {v.why && <span className="text-ink-2"> · {v.why}</span>}
                  </div>
                ))}
              </dd>
            </>
          )}
        </dl>
        <Sources ids={event.news_ids} news={model.news} className="mt-2" />
      </div>
    </article>
  )
}

/** Things to watch, numbered like the dots on the timeline. */
export function WatchList({ items, model, go, limit }: { items: WatchItem[]; model: Model; go: Go; limit?: number }) {
  const shown = limit ? items.slice(0, limit) : items
  return (
    <ol className="flex flex-col divide-y divide-line">
      {shown.map((w) => (
        <li key={w.n} className="grid grid-cols-[1.5rem_minmax(0,1fr)_auto] gap-x-2 py-2.5 first:pt-0 last:pb-0">
          <NumDot n={w.n} record={w.record} />
          <div className="min-w-0">
            <p className="text-[13px] leading-relaxed">{w.what}</p>
            {(w.themes.length > 0 || w.holdings.length > 0) && (
              <div className="mt-1.5 flex flex-wrap gap-1">
                {w.themes.map((id) => (
                  <Chip key={id} label={model.theme_labels[id] ?? id} onClick={() => go("world", id)} />
                ))}
                {w.holdings.map((s) => (
                  <Chip key={s} label={<span className="num">{s}</span>} onClick={() => go("holdings", s)} />
                ))}
              </div>
            )}
            {w.record && <p className="mt-1 text-xs text-ink-3">From your own record</p>}
            <Sources ids={w.news_ids} news={model.news} className="mt-1.5" />
          </div>
          <span className={cn("num text-right text-xs whitespace-nowrap", w.date ? "text-ink-2" : "text-ink-3")}>
            {w.date ? (
              <span data-tip={longDate(w.date)}>
                {shortDate(w.date)}
                <span className="block text-[11px] text-ink-3">{due(w.date, model.date)}</span>
              </span>
            ) : (
              "ongoing"
            )}
          </span>
        </li>
      ))}
    </ol>
  )
}
