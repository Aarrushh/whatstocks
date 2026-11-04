/** The dashboard: a sidebar, seven pages, the command palette and the keys. Everything it shows comes from the view
 * model Python embedded in the page (src/whatstocks/render.py); nothing is fetched and nothing is computed that
 * Python did not already decide. */
import { useCallback, useEffect, useMemo, useState, type ComponentType } from "react"
import { MotionConfig, motion } from "motion/react"
import { TooltipProvider } from "@/components/ui/tooltip"
import { Banner, EASE, type PageProps } from "@/components/kit"
import { Palette } from "@/components/palette"
import { Footer, Sidebar, Toast, TopBar } from "@/components/shell"
import { TipLayer } from "@/components/tip"
import { longDate } from "@/lib/format"
import { PAGES, useKeys, useRoute, useTheme, type PageId } from "@/lib/hooks"
import type { Model } from "@/lib/types"
import { Exposure } from "@/pages/exposure"
import { Holdings } from "@/pages/holdings"
import { Overview } from "@/pages/overview"
import { RecordPage } from "@/pages/record"
import { Scenarios } from "@/pages/scenarios"
import { Views } from "@/pages/views"
import { World } from "@/pages/world"

const PAGE: Record<PageId, ComponentType<PageProps>> = {
  overview: Overview,
  holdings: Holdings,
  world: World,
  exposure: Exposure,
  scenarios: Scenarios,
  views: Views,
  record: RecordPage,
}

export function App({ model }: { model: Model }) {
  const [route, go] = useRoute()
  const [theme, toggleTheme] = useTheme()
  const [palette, setPalette] = useState(false)
  const [toast, setToast] = useState<string | null>(null)
  const openPalette = useCallback(() => setPalette(true), [])

  const keys = useMemo(() => {
    const map: Record<string, () => void> = { t: toggleTheme }
    PAGES.forEach((p, i) => {
      map[String(i + 1)] = () => go(p.id)
    })
    return map
  }, [go, toggleTheme])
  useKeys(keys, openPalette)

  useEffect(() => {
    document.title = `whatstocks · ${longDate(model.date)}`
  }, [model.date])
  useEffect(() => {
    if (!toast) return
    const timer = setTimeout(() => setToast(null), 2600)
    return () => clearTimeout(timer)
  }, [toast])
  useEffect(() => {
    // A new page starts at the top; a page opened at an item scrolls to that item itself.
    if (!route.item) window.scrollTo({ top: 0 })
  }, [route.page, route.item])

  const Page = PAGE[route.page]
  const shell = { model, page: route.page, go, theme, toggleTheme, openPalette }
  return (
    <MotionConfig reducedMotion="user">
      <TooltipProvider>
        <div className="min-h-dvh lg:grid lg:grid-cols-[232px_minmax(0,1fr)]">
          <Sidebar {...shell} />
          <div className="min-w-0">
            <TopBar {...shell} />
            <main className="mx-auto w-full max-w-[1320px] px-4 py-5 sm:px-6 lg:px-8 lg:py-7">
              {model.banners.length > 0 && (
                <div className="mb-4 flex flex-col gap-2">
                  {model.banners.map((b, i) => (
                    <Banner key={i}>{b}</Banner>
                  ))}
                </div>
              )}
              <motion.div
                key={route.page}
                initial={{ opacity: 0, y: 6 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.22, ease: EASE }}
              >
                <Page model={model} item={route.item} go={go} />
              </motion.div>
              <Footer date={model.date} />
            </main>
          </div>
        </div>
        <Palette
          open={palette}
          onOpenChange={setPalette}
          model={model}
          go={go}
          theme={theme}
          toggleTheme={toggleTheme}
          notify={setToast}
        />
        <TipLayer />
        <Toast text={toast} />
      </TooltipProvider>
    </MotionConfig>
  )
}

/** Shown when the page holds no data: opened straight from web/ without Python, or the data failed to load. */
export function NoData({ error }: { error?: string }) {
  return (
    <main className="mx-auto max-w-xl px-6 py-16 text-[13px] leading-relaxed">
      <div className="flex items-center gap-2 text-[15px] font-semibold tracking-tight">
        <span aria-hidden className="size-2.5 rounded-[3px] bg-you" />
        whatstocks
      </div>
      <p className="mt-4 text-ink-2">
        This page has no portfolio data in it. Build it with <code className="num text-foreground">whatstocks finish</code>, or
        run <code className="num text-foreground">/morning</code> in Claude Code, then open <code className="num">out/dashboard.html</code>.
      </p>
      {error && <p className="num mt-3 text-xs text-ink-3">{error}</p>}
    </main>
  )
}
