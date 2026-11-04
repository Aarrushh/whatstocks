/** The frame around every page: the sidebar on wide screens, a top bar with the pages on narrow ones, the
 * footer and the toast. */
import { AnimatePresence, motion } from "motion/react"
import { BookCheck, ChartPie, LayoutDashboard, Moon, Newspaper, Radar, Search, Sun, Target, Wallet, type LucideIcon } from "lucide-react"
import type { MouseEvent } from "react"
import { Kbd } from "@/components/ui/kbd"
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip"
import { cn } from "@/lib/utils"
import { longDate } from "@/lib/format"
import { PAGES, routeHash, type Go, type PageId, type ThemeName } from "@/lib/hooks"
import type { Model } from "@/lib/types"
import { PRESS, SPRING } from "./kit"

export const PAGE_ICONS: Record<PageId, LucideIcon> = {
  overview: LayoutDashboard,
  holdings: Wallet,
  world: Newspaper,
  exposure: ChartPie,
  scenarios: Radar,
  views: Target,
  record: BookCheck,
}

const MAC = typeof navigator !== "undefined" && /Mac|iPhone|iPad/.test(navigator.userAgent)
export const PALETTE_KEY = MAC ? "⌘K" : "Ctrl K"

export interface ShellProps {
  model: Model
  page: PageId
  go: Go
  theme: ThemeName
  toggleTheme: () => void
  openPalette: () => void
}

function link(go: Go, page: PageId) {
  return {
    href: routeHash({ page, item: null }),
    onClick: (e: MouseEvent) => {
      if (e.metaKey || e.ctrlKey || e.shiftKey || e.button !== 0) return
      e.preventDefault()
      go(page)
    },
  }
}

function Brand({ model }: { model: Model }) {
  return (
    <div className="min-w-0">
      <div className="flex items-center gap-2 text-[15px] leading-5 font-semibold tracking-tight">
        <span aria-hidden className="size-2.5 rounded-[3px] bg-you" />
        whatstocks
      </div>
      <div className="num mt-0.5 truncate text-[11px] text-ink-3">
        {longDate(model.date)} · {model.home}
      </div>
    </div>
  )
}

function SearchButton({ onClick }: { onClick: () => void }) {
  return (
    <motion.button
      type="button"
      whileTap={PRESS}
      onClick={onClick}
      className="flex h-8 w-full items-center gap-2 rounded-md bg-card px-2.5 text-[13px] text-ink-3 ring-1 ring-line outline-none transition-colors duration-150 hover:text-ink-2 hover:ring-line-strong focus-visible:ring-2 focus-visible:ring-ring/50"
    >
      <Search className="size-3.5" aria-hidden />
      <span className="flex-1 text-left">Search</span>
      <Kbd>{PALETTE_KEY}</Kbd>
    </motion.button>
  )
}

function ThemeButton({ theme, onClick }: { theme: ThemeName; onClick: () => void }) {
  const next = theme === "dark" ? "light" : "dark"
  const Icon = theme === "dark" ? Sun : Moon
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <motion.button
          type="button"
          whileTap={PRESS}
          onClick={onClick}
          aria-label={`Switch to the ${next} theme`}
          className="grid size-8 shrink-0 place-items-center rounded-md text-ink-2 ring-1 ring-line outline-none transition-colors duration-150 hover:bg-card-2 hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring/50"
        >
          <Icon className="size-4" aria-hidden />
        </motion.button>
      </TooltipTrigger>
      <TooltipContent side="top">
        Switch to {next} <Kbd>T</Kbd>
      </TooltipContent>
    </Tooltip>
  )
}

export function Sidebar({ model, page, go, theme, toggleTheme, openPalette }: ShellProps) {
  const counts: Partial<Record<PageId, number>> = {
    world: model.events.length,
    scenarios: model.scans.length,
    views: model.views.length,
  }
  return (
    <aside className="sticky top-0 hidden h-dvh flex-col gap-4 border-r border-line px-3 py-4 lg:flex">
      <div className="px-2">
        <Brand model={model} />
      </div>
      <SearchButton onClick={openPalette} />
      <nav aria-label="Pages" className="flex flex-col gap-0.5">
        {PAGES.map((p, i) => {
          const active = p.id === page
          const Icon = PAGE_ICONS[p.id]
          const count = counts[p.id]
          return (
            <motion.a
              key={p.id}
              {...link(go, p.id)}
              whileTap={PRESS}
              aria-current={active ? "page" : undefined}
              className={cn(
                "group relative flex h-8 items-center gap-2.5 rounded-md px-2 text-[13px] outline-none transition-colors duration-150 focus-visible:ring-2 focus-visible:ring-ring/50",
                active ? "text-foreground" : "text-ink-2 hover:text-foreground",
              )}
            >
              {active && (
                <motion.span layoutId="nav-side" transition={SPRING} className="absolute inset-0 rounded-md bg-card-2 ring-1 ring-line" />
              )}
              <Icon className={cn("relative size-4 shrink-0", active ? "text-you" : "text-ink-3 group-hover:text-ink-2")} aria-hidden />
              <span className="relative flex-1 truncate">{p.label}</span>
              {count ? <span className="num relative text-[11px] text-ink-3 group-hover:hidden">{count}</span> : null}
              <Kbd className="relative hidden group-hover:inline-flex">{i + 1}</Kbd>
            </motion.a>
          )
        })}
      </nav>
      <div className="mt-auto flex flex-col gap-3 px-2">
        <div className="flex items-center gap-2.5">
          <ThemeButton theme={theme} onClick={toggleTheme} />
          <p className="text-[11px] leading-snug text-ink-3">
            <Kbd>1</Kbd>–<Kbd>7</Kbd> pages · <Kbd>/</Kbd> search
          </p>
        </div>
        <p className="text-[11px] leading-relaxed text-ink-3">Percentages only: no amounts leave your computer.</p>
      </div>
    </aside>
  )
}

export function TopBar({ model, page, go, theme, toggleTheme, openPalette }: ShellProps) {
  return (
    <header className="sticky top-0 z-30 border-b border-line bg-background lg:hidden">
      <div className="flex h-12 items-center gap-2 px-4">
        <Brand model={model} />
        <div className="ml-auto flex items-center gap-1.5">
          <motion.button
            type="button"
            whileTap={PRESS}
            onClick={openPalette}
            aria-label="Search"
            className="grid size-8 place-items-center rounded-md text-ink-2 ring-1 ring-line outline-none focus-visible:ring-2 focus-visible:ring-ring/50"
          >
            <Search className="size-4" aria-hidden />
          </motion.button>
          <ThemeButton theme={theme} onClick={toggleTheme} />
        </div>
      </div>
      <nav aria-label="Pages" className="no-scrollbar relative flex gap-1 overflow-x-auto px-3 pb-2">
        {PAGES.map((p) => {
          const active = p.id === page
          return (
            <motion.a
              key={p.id}
              {...link(go, p.id)}
              whileTap={PRESS}
              aria-current={active ? "page" : undefined}
              className={cn(
                "relative flex h-7 shrink-0 items-center rounded-md px-2.5 text-[13px] whitespace-nowrap outline-none focus-visible:ring-2 focus-visible:ring-ring/50",
                active ? "text-foreground" : "text-ink-2",
              )}
            >
              {active && (
                <motion.span layoutId="nav-top" transition={SPRING} className="absolute inset-0 rounded-md bg-card-2 ring-1 ring-line" />
              )}
              <span className="relative">{p.label}</span>
            </motion.a>
          )
        })}
      </nav>
    </header>
  )
}

export function Footer({ date }: { date: string }) {
  return (
    <footer className="mt-10 border-t border-line pt-4 text-[11px] leading-relaxed text-ink-3">
      whatstocks describes your own portfolio and your own stated views. It makes no recommendations and is not financial
      advice. Numbers are computed in code; the words are written by your AI from the linked sources. Built {longDate(date)}.
    </footer>
  )
}

export function Toast({ text }: { text: string | null }) {
  return (
    <div aria-live="polite" className="pointer-events-none fixed inset-x-0 bottom-4 z-[80] flex justify-center px-4">
      <AnimatePresence>
        {text && (
          <motion.div
            key={text}
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: 8 }}
            transition={SPRING}
            className="rounded-md bg-popover px-3 py-2 text-[13px] shadow-lg ring-1 shadow-black/25 ring-line-strong"
          >
            {text}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}
