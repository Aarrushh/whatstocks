import { useCallback, useEffect, useState } from "react"

export const PAGES = [
  { id: "overview", label: "Overview" },
  { id: "holdings", label: "Holdings" },
  { id: "world", label: "News & world" },
  { id: "exposure", label: "Exposure" },
  { id: "scenarios", label: "Scenarios" },
  { id: "views", label: "Views" },
  { id: "record", label: "Record" },
] as const
export type PageId = (typeof PAGES)[number]["id"]

export interface Route {
  page: PageId
  item: string | null
}

/** "#holdings/NVDA" -> holdings, NVDA. Anything unknown is the overview. */
export function parseRoute(hash: string): Route {
  const [page, ...rest] = hash.replace(/^#/, "").split("/")
  const known = PAGES.find((p) => p.id === page)
  const item = rest.length ? decodeURIComponent(rest.join("/")) : null
  return known ? { page: known.id, item } : { page: "overview", item: null }
}

export function routeHash(route: Route): string {
  return `#${route.page}${route.item ? `/${encodeURIComponent(route.item)}` : ""}`
}

/** Go to a page, and optionally to one item on it (a holding, theme, view or scan). */
export type Go = (page: PageId, item?: string | null) => void

/** The page and item in the address. State is the source of truth: some places (a page opened from a data: URL)
 * ignore changes to the address, so the page must switch even when the address cannot. */
export function useRoute(): [Route, Go] {
  const [route, setRoute] = useState<Route>(() => parseRoute(window.location.hash))
  useEffect(() => {
    const fromAddress = () => setRoute(parseRoute(window.location.hash))
    window.addEventListener("hashchange", fromAddress)
    window.addEventListener("popstate", fromAddress)
    return () => {
      window.removeEventListener("hashchange", fromAddress)
      window.removeEventListener("popstate", fromAddress)
    }
  }, [])
  const go = useCallback((page: PageId, item: string | null = null) => {
    const next = { page, item }
    try {
      window.history.pushState(null, "", routeHash(next))
    } catch {
      // the address cannot change here; the page still switches
    }
    setRoute(next)
  }, [])
  return [route, go]
}

export type ThemeName = "dark" | "light"

export function useTheme(): [ThemeName, () => void] {
  const [theme, setTheme] = useState<ThemeName>(() =>
    document.documentElement.getAttribute("data-theme") === "light" ? "light" : "dark",
  )
  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme)
    try {
      localStorage.setItem("whatstocks-theme", theme)
    } catch {
      // storage can be blocked; the toggle still works for this visit
    }
  }, [theme])
  return [theme, useCallback(() => setTheme((t) => (t === "dark" ? "light" : "dark")), [])]
}

function typing(target: EventTarget | null): boolean {
  const el = target as HTMLElement | null
  return !!el && (el.isContentEditable || /^(INPUT|TEXTAREA|SELECT)$/.test(el.tagName))
}

/** Single keys (no modifier) while nothing is being typed, plus the palette chord (Ctrl K or Cmd K). */
export function useKeys(keys: Record<string, () => void>, onPalette: () => void): void {
  useEffect(() => {
    const onKey = (ev: KeyboardEvent) => {
      if ((ev.metaKey || ev.ctrlKey) && ev.key.toLowerCase() === "k") {
        ev.preventDefault()
        onPalette()
        return
      }
      if (ev.metaKey || ev.ctrlKey || ev.altKey || typing(ev.target)) return
      if (ev.key === "/") {
        ev.preventDefault()
        onPalette()
        return
      }
      const run = keys[ev.key.toLowerCase()]
      if (run) {
        ev.preventDefault()
        run()
      }
    }
    window.addEventListener("keydown", onKey)
    return () => window.removeEventListener("keydown", onKey)
  }, [keys, onPalette])
}

/** Copy text to the clipboard, with a fallback for pages opened from disk. */
export async function copyText(text: string): Promise<boolean> {
  try {
    await navigator.clipboard.writeText(text)
    return true
  } catch {
    const area = document.createElement("textarea")
    area.value = text
    area.setAttribute("readonly", "")
    area.style.position = "fixed"
    area.style.opacity = "0"
    document.body.appendChild(area)
    area.select()
    let ok = false
    try {
      ok = document.execCommand("copy")
    } catch {
      ok = false
    }
    area.remove()
    return ok
  }
}
