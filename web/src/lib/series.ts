/** Cutting a price line to a window the way src/whatstocks/performance.py cuts its period figures, so a line
 * always ends where its period figure says. */
import { addDays } from "./format"
import type { Point } from "./types"

export const WINDOWS = [
  { id: "1M", label: "1M", days: 30 },
  { id: "3M", label: "3M", days: 91 },
  { id: "YTD", label: "YTD", days: 0 },
  { id: "1Y", label: "1Y", days: 365 },
] as const
export type WindowId = (typeof WINDOWS)[number]["id"]

/** The last date at or before which the window starts: the base the period figure is measured from. */
export function cutDate(last: string, window: WindowId): string {
  if (window === "YTD") return `${Number(last.slice(0, 4)) - 1}-12-31`
  const days = WINDOWS.find((w) => w.id === window)!.days
  return addDays(last, -days)
}

/** The points from the base (the last point at or before the cut) to the end, rebased to 100 at the base. */
export function windowed(points: Point[], window: WindowId, last?: string): Point[] {
  if (points.length < 2) return []
  const cut = cutDate(last ?? points[points.length - 1][0], window)
  let start = 0
  for (let i = 0; i < points.length; i++) if (points[i][0] <= cut) start = i
  const kept = points.slice(start)
  const base = kept[0][1]
  if (!base || kept.length < 2) return []
  return kept.map(([d, v]) => [d, (100 * v) / base])
}

/** The change over a rebased line: its last value against 100. */
export function change(points: Point[]): number | null {
  return points.length ? points[points.length - 1][1] / 100 - 1 : null
}
