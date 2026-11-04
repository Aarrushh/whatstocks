import fs from "node:fs"
import path from "node:path"
import tailwindcss from "@tailwindcss/vite"
import react from "@vitejs/plugin-react"
import { defineConfig, type Plugin } from "vite"
import { viteSingleFile } from "vite-plugin-singlefile"

/** Dev only: serve a whatstocks out/dashboard.json (the demo's by default) at /dev-data.json. */
function devData(): Plugin {
  const file = path.resolve(import.meta.dirname, process.env.WS_DATA ?? "../demo/out/dashboard.json")
  return {
    name: "whatstocks-dev-data",
    apply: "serve",
    configureServer(server) {
      server.middlewares.use("/dev-data.json", (_req, res) => {
        res.setHeader("Content-Type", "application/json")
        res.end(fs.existsSync(file) ? fs.readFileSync(file) : "null")
      })
    },
  }
}

/** Build only: the finished page may fetch nothing at all. The dev server keeps fetch for /dev-data.json. */
function noFetching(): Plugin {
  const policy = [
    "default-src 'none'",
    "script-src 'unsafe-inline'",
    "style-src 'unsafe-inline'",
    "font-src data:",
    "img-src data:",
    "base-uri 'none'",
    "form-action 'none'",
  ].join("; ")
  return {
    name: "whatstocks-csp",
    apply: "build",
    transformIndexHtml: (html) =>
      html.replace("<!--CSP-->", `<meta http-equiv="Content-Security-Policy" content="${policy}" />`),
  }
}

export default defineConfig({
  plugins: [react(), tailwindcss(), devData(), noFetching(), viteSingleFile({ removeViteModuleLoader: true })],
  resolve: { alias: { "@": path.resolve(import.meta.dirname, "./src") } },
  build: { assetsInlineLimit: 100_000_000, cssCodeSplit: false, chunkSizeWarningLimit: 5000 },
})
