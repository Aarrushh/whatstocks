/** Views: your calls, in your words, with your probability over time and the evidence the briefs logged. A view
 * in the address (#views/ai-capex-cut-2027) is scrolled to and outlined. */
import { useEffect } from "react"
import { TriangleAlert } from "lucide-react"
import { EffectTag } from "@/components/brief"
import { CategoryBar, ForecastLine } from "@/components/charts"
import { Banner, Cmd, Empty, Legend, PageHeader, Panel, Sources, SubHead, type PageProps } from "@/components/kit"
import { cn } from "@/lib/utils"
import { longDate, pct, plural, prob } from "@/lib/format"
import type { Go } from "@/lib/hooks"
import type { Model, View } from "@/lib/types"

function ViewCard({ view: v, model, go, active }: { view: View; model: Model; go: Go; active: boolean }) {
  const week = v.evidence["7"]
  const month = v.evidence["30"]
  const any = week.for + week.against + week.unclear > 0
  return (
    <Panel
      id={`view-${v.id}`}
      className={cn(active && "ring-you/50")}
      title={<span className="num text-xs font-normal text-ink-3">{v.id}</span>}
      action={
        <span className="num inline-flex items-center gap-1 text-xs text-ink-2">
          {v.due && <TriangleAlert className="size-3 shrink-0 text-warn" aria-hidden />}
          {v.due ? "past its deadline" : `${plural(v.days_left, "day")} left`}
        </span>
      }
    >
      <p className="text-[15px] leading-snug font-medium text-foreground">{v.statement}</p>
      {v.due && <Banner className="mt-3">Past its deadline: resolve it now.</Banner>}
      <div className="mt-4 grid gap-4 sm:grid-cols-[8.5rem_minmax(0,1fr)]">
        <div>
          <div className="text-xs text-ink-3">Your probability</div>
          <div className="num mt-1 text-[28px] leading-8 font-medium">{prob(v.probability)}</div>
          <div className="mt-1 text-xs text-ink-2">
            resolves by <span className="num">{longDate(v.resolves_by)}</span>
          </div>
        </div>
        <ForecastLine points={v.forecasts} start={v.created} end={v.resolves_by} today={model.date} />
      </div>
      <div className="mt-5 grid gap-5 sm:grid-cols-2">
        <section>
          <SubHead>Last 7 days</SubHead>
          {any ? (
            <>
              <CategoryBar
                className="mt-2"
                segments={[
                  { id: "for", label: "For", value: week.for, color: "var(--pos)", tip: `${week.for} for` },
                  { id: "against", label: "Against", value: week.against, color: "var(--neg)", tip: `${week.against} against` },
                  { id: "unclear", label: "Unclear", value: week.unclear, color: "var(--ink-3)", tip: `${week.unclear} unclear` },
                ]}
              />
              <Legend
                className="mt-2"
                items={[
                  { label: `${week.for} for`, kind: "box", color: "var(--pos)" },
                  { label: `${week.against} against`, kind: "box", color: "var(--neg)" },
                  { label: `${week.unclear} unclear`, kind: "box", color: "var(--ink-3)" },
                ]}
              />
            </>
          ) : (
            <p className="mt-2 text-[13px] text-ink-3">No evidence logged this week.</p>
          )}
          <p className="num mt-2 text-xs text-ink-3">
            Last 30 days: {month.for} for, {month.against} against, {month.unclear} unclear
          </p>
        </section>
        <section>
          <SubHead>Themes it names</SubHead>
          {v.themes.length ? (
            <ul className="mt-2 flex flex-col gap-1.5 text-[13px]">
              {v.themes.map((t) => (
                <li key={t.id} className="min-w-0">
                  <button
                    type="button"
                    onClick={() => (model.matter.includes(t.id) ? go("world", t.id) : go("exposure"))}
                    className="block max-w-full truncate rounded-sm text-left underline decoration-line-strong underline-offset-2 outline-none hover:decoration-ink-3 focus-visible:ring-2 focus-visible:ring-ring/50"
                  >
                    {t.label}
                  </button>
                  <span className="num mt-0.5 block text-xs text-ink-2">
                    implies {t.direction} · you {pct(t.you)} · world {pct(t.world)}
                  </span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="mt-2 text-[13px] text-ink-3">Names no theme.</p>
          )}
        </section>
      </div>
      {v.today.length > 0 && (
        <section className="mt-5 border-t border-line pt-3">
          <SubHead>Today</SubHead>
          <ul className="mt-2 flex flex-col gap-3">
            {v.today.map((t, i) => (
              <li key={i} className="text-[13px] leading-relaxed">
                <EffectTag effect={t.effect} /> <span className="text-foreground">{t.what}</span>
                {t.why && <p className="text-ink-2">{t.why}</p>}
                <Sources ids={t.news_ids} news={model.news} className="mt-1" />
              </li>
            ))}
          </ul>
        </section>
      )}
    </Panel>
  )
}

export function Views({ model, item, go }: PageProps) {
  useEffect(() => {
    if (item) document.getElementById(`view-${item}`)?.scrollIntoView({ block: "start" })
  }, [item])
  return (
    <>
      <PageHeader
        title="Views"
        sub="Your calls, in your words. The evidence counts come from the briefs; only you change a probability."
      />
      {model.views.length ? (
        <div className="grid grid-cols-1 gap-3 xl:grid-cols-2">
          {model.views.map((v) => (
            <ViewCard key={v.id} view={v} model={model} go={go} active={v.id === item} />
          ))}
        </div>
      ) : (
        <Panel>
          <Empty>
            No open views. Run <Cmd>/setup</Cmd> to write your first ones.
          </Empty>
        </Panel>
      )}
    </>
  )
}
