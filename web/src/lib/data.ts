import type { Model } from "./types"

/** The view model Python put into the page; in development, the demo's out/dashboard.json (vite.config.ts). */
export async function loadModel(): Promise<Model | null> {
  const text = document.getElementById("ws-data")?.textContent?.trim() ?? ""
  if (text.startsWith("{")) return JSON.parse(text) as Model
  if (import.meta.env.DEV) {
    const res = await fetch("/dev-data.json")
    return (await res.json()) as Model | null
  }
  return null
}
