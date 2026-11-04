/** One tooltip for every element with a data-tip attribute: chart marks, chips, sources. It follows the pointer,
 * and shows under an element that takes keyboard focus. Text can break lines with \n. */
import { useEffect, useState } from "react"

interface Tip {
  text: string
  x: number
  y: number
}

export function TipLayer() {
  const [tip, setTip] = useState<Tip | null>(null)

  useEffect(() => {
    let current: Element | null = null
    const find = (target: EventTarget | null) => (target instanceof Element ? target.closest("[data-tip]") : null)
    const show = (el: Element, x: number, y: number) => {
      const text = el.getAttribute("data-tip")
      current = text ? el : null
      setTip(text ? { text, x, y } : null)
    }
    const hide = () => {
      if (!current) return
      current = null
      setTip(null)
    }
    const onOver = (e: PointerEvent) => {
      const el = find(e.target)
      if (el) show(el, e.clientX, e.clientY)
      else hide()
    }
    const onMove = (e: PointerEvent) => {
      if (!current) return
      if (!current.isConnected) return hide()
      setTip((t) => (t ? { ...t, x: e.clientX, y: e.clientY } : t))
    }
    const onFocus = (e: FocusEvent) => {
      const el = find(e.target)
      if (!el || !(e.target instanceof Element) || !e.target.matches(":focus-visible")) return
      const r = el.getBoundingClientRect()
      show(el, r.left + r.width / 2, r.bottom + 2)
    }
    const root = document.documentElement
    document.addEventListener("pointerover", onOver)
    document.addEventListener("pointermove", onMove, { passive: true })
    document.addEventListener("focusin", onFocus)
    document.addEventListener("focusout", hide)
    root.addEventListener("pointerleave", hide)
    window.addEventListener("scroll", hide, { capture: true, passive: true })
    window.addEventListener("blur", hide)
    window.addEventListener("hashchange", hide)
    return () => {
      document.removeEventListener("pointerover", onOver)
      document.removeEventListener("pointermove", onMove)
      document.removeEventListener("focusin", onFocus)
      document.removeEventListener("focusout", hide)
      root.removeEventListener("pointerleave", hide)
      window.removeEventListener("scroll", hide, { capture: true })
      window.removeEventListener("blur", hide)
      window.removeEventListener("hashchange", hide)
    }
  }, [])

  if (!tip) return null
  // Flip to the other side of the pointer near the right and bottom edges, so the tip never leaves the window.
  const left = tip.x > window.innerWidth * 0.62
  const above = tip.y > window.innerHeight * 0.7
  return (
    <div
      role="tooltip"
      className="pointer-events-none fixed z-[70] w-max max-w-[min(320px,calc(100vw-24px))] rounded-md bg-popover px-2.5 py-1.5 text-xs/normal whitespace-pre-line text-foreground shadow-lg ring-1 shadow-black/25 ring-line-strong"
      style={{
        left: tip.x,
        top: tip.y,
        transform: `translate(${left ? "calc(-100% - 12px)" : "12px"}, ${above ? "calc(-100% - 12px)" : "16px"})`,
      }}
    >
      {tip.text}
    </div>
  )
}
