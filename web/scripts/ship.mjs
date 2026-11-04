// Copies the built page into the Python package. Before it does, it checks the page is one self-contained file
// with exactly one place for the data, and stamps it with a hash of the sources it was built from, which
// tests/test_render.py recomputes: a test fails when the sources change and nobody rebuilt.
import { createHash } from "node:crypto"
import { mkdirSync, readdirSync, readFileSync, statSync, writeFileSync } from "node:fs"
import { dirname, join, relative, resolve, sep } from "node:path"
import { fileURLToPath } from "node:url"

const web = resolve(dirname(fileURLToPath(import.meta.url)), "..")
const target = resolve(web, "../src/whatstocks/assets/dashboard.html")
const SOURCES = ["index.html", "package.json", "package-lock.json", "vite.config.ts", "src"]

function files(path) {
  const full = join(web, path)
  if (statSync(full).isDirectory()) return readdirSync(full).flatMap((name) => files(join(path, name)))
  return [path.split(sep).join("/")]
}

function sourceHash() {
  const hash = createHash("sha256")
  for (const path of SOURCES.flatMap(files).sort()) {
    hash.update(path + "\n")
    hash.update(readFileSync(join(web, path), "utf8").replaceAll("\r", "") + "\n")
  }
  return hash.digest("hex")
}

const built = readFileSync(join(web, "dist", "index.html"), "utf8")
const problems = []
if (built.split("/*WS_DATA*/").length !== 2) problems.push("the data placeholder must appear exactly once")
for (const outside of ["<script src", "<link ", "@import", "url(http"]) {
  if (built.includes(outside)) problems.push(`it still loads something from outside (${outside})`)
}
if (!built.includes("Content-Security-Policy")) problems.push("the Content-Security-Policy is missing")
if (problems.length) {
  console.error("ship: " + problems.join("; "))
  process.exit(1)
}
const stamped = built.replace("<head>", `<head>\n    <meta name="ws-source" content="${sourceHash()}" />`)
mkdirSync(dirname(target), { recursive: true })
writeFileSync(target, stamped)
console.log(`ship: wrote ${relative(web, target)} (${Math.round(stamped.length / 1024)} kB)`)
