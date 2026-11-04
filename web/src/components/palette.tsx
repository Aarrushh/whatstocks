/** The command palette (Ctrl K, Cmd K or /): jump to a page, holding, theme, view or scan, or copy a command to
 * paste into Claude Code. The page itself never runs anything. */
import { useState } from "react"
import { Copy, Moon, Radar, Sun } from "lucide-react"
import {
  Command,
  CommandDialog,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
  CommandSeparator,
  CommandShortcut,
} from "@/components/ui/command"
import { pct, prob } from "@/lib/format"
import { PAGES, copyText, type Go, type ThemeName } from "@/lib/hooks"
import type { Model, Theme } from "@/lib/types"
import { PAGE_ICONS } from "./shell"

export function Palette({
  open,
  onOpenChange,
  model,
  go,
  theme,
  toggleTheme,
  notify,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  model: Model
  go: Go
  theme: ThemeName
  toggleTheme: () => void
  notify: (text: string) => void
}) {
  const [query, setQuery] = useState("")
  const q = query.trim()
  const setOpen = (next: boolean) => {
    onOpenChange(next)
    if (!next) setQuery("")
  }
  const run = (fn: () => void) => () => {
    setOpen(false)
    fn()
  }
  const copy = (text: string) =>
    run(() => {
      void copyText(text).then((ok) =>
        notify(ok ? `Copied ${text.trim()}. Paste it into Claude Code.` : "Could not copy. Type it into Claude Code instead."),
      )
    })
  const themes = model.theme_order.map((id) => model.themes[id]).filter((t): t is Theme => !!t)

  return (
    <CommandDialog
      open={open}
      onOpenChange={setOpen}
      title="Search whatstocks"
      description="Go to a page, holding, theme, view or scan, or copy a command for Claude Code."
      className="sm:max-w-xl"
    >
      <Command loop className="rounded-lg">
        <CommandInput value={query} onValueChange={setQuery} placeholder="Search pages, holdings, themes, views, scans…" />
        <CommandList className="max-h-[min(60dvh,420px)]">
          <CommandEmpty>Nothing matches.</CommandEmpty>
          <CommandGroup heading="Pages">
            {PAGES.map((p, i) => {
              const Icon = PAGE_ICONS[p.id]
              return (
                <CommandItem key={p.id} value={`page ${p.label}`} onSelect={run(() => go(p.id))}>
                  <Icon aria-hidden />
                  {p.label}
                  <CommandShortcut>{i + 1}</CommandShortcut>
                </CommandItem>
              )
            })}
          </CommandGroup>
          <CommandGroup heading="Holdings">
            {model.holdings.map((h) => (
              <CommandItem key={h.symbol} value={`holding ${h.symbol} ${h.name}`} onSelect={run(() => go("holdings", h.symbol))}>
                <span className="num w-20 shrink-0">{h.symbol}</span>
                <span className="truncate text-ink-2">{h.name}</span>
                <CommandShortcut className="num tracking-normal">{pct(h.weight)}</CommandShortcut>
              </CommandItem>
            ))}
          </CommandGroup>
          <CommandGroup heading="Themes">
            {themes.map((t) => {
              const covered = model.matter.includes(t.id)
              return (
                <CommandItem
                  key={t.id}
                  value={`theme ${t.label} ${t.proxy}`}
                  onSelect={run(() => (covered ? go("world", t.id) : go("exposure")))}
                >
                  <span className="truncate">{t.label}</span>
                  <CommandShortcut className="num tracking-normal">
                    you {pct(t.you)} · world {pct(t.world)}
                  </CommandShortcut>
                </CommandItem>
              )
            })}
          </CommandGroup>
          {model.views.length > 0 && (
            <CommandGroup heading="Views">
              {model.views.map((v) => (
                <CommandItem key={v.id} value={`view ${v.id} ${v.statement}`} onSelect={run(() => go("views", v.id))}>
                  <span className="truncate">{v.statement}</span>
                  <CommandShortcut className="num tracking-normal">{prob(v.probability)}</CommandShortcut>
                </CommandItem>
              ))}
            </CommandGroup>
          )}
          {model.scans.length > 0 && (
            <CommandGroup heading="Scans">
              {model.scans.map((s) => (
                <CommandItem key={s.slug} value={`scan ${s.conflict}`} onSelect={run(() => go("scenarios", s.slug))}>
                  <Radar aria-hidden />
                  <span className="truncate">{s.conflict}</span>
                </CommandItem>
              ))}
            </CommandGroup>
          )}
          <CommandSeparator />
          <CommandGroup heading="Actions" forceMount={q ? true : undefined}>
            <CommandItem value="action switch theme dark light" onSelect={run(toggleTheme)}>
              {theme === "dark" ? <Sun aria-hidden /> : <Moon aria-hidden />}
              Switch to the {theme === "dark" ? "light" : "dark"} theme
              <CommandShortcut>T</CommandShortcut>
            </CommandItem>
            <CommandItem value="action copy morning brief news" onSelect={copy("/morning")}>
              <Copy aria-hidden />
              Copy /morning: have your AI read today's news
            </CommandItem>
            {q ? (
              <CommandItem forceMount value={`action copy scan ${q}`} onSelect={copy(`/scan ${q}`)}>
                <Copy aria-hidden />
                <span className="truncate">Copy /scan {q}</span>
              </CommandItem>
            ) : (
              <CommandItem value="action copy scan conflict" onSelect={copy("/scan ")}>
                <Copy aria-hidden />
                Copy /scan: map a conflict (type its name here first)
              </CommandItem>
            )}
          </CommandGroup>
        </CommandList>
        <div className="flex items-center gap-3 border-t border-line px-3 pt-2 pb-1 text-[11px] text-ink-3">
          <span>↑↓ move</span>
          <span>Enter open</span>
          <span>Esc close</span>
        </div>
      </Command>
    </CommandDialog>
  )
}
