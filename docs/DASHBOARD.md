# The dashboard, v0.3: plan and design rules

Status: planned and built 2026-11-04 (v0.3). It replaces the HTML that `render.py` wrote by hand with a React
page that is still one self-contained file. Section 7 records what changed while building it, and section 8 the
eighth page, "Will the bet pay off?" (v0.4, 2026-11-07). The product rules in [SPEC.md](SPEC.md) do not change:
code computes every number (with the two exceptions SPEC section 2 lists for the bet page), the AI writes words
with sources, the page shows your holdings as percentages and never your amounts, and it never recommends.

## 1. What we took from the advice, and what we did not

The advice assumed a Python UI that reruns on every click, like Streamlit. whatstocks v0.2 is already a static
HTML file: nothing reruns, so React is not needed for speed. What React buys here is craft: tested components,
motion, and a command palette.

| Advice | Decision | Why |
|---|---|---|
| React, TypeScript, Tailwind, shadcn/ui | Yes | Tested parts (dialog, tooltip, command palette) with the focus and keyboard handling we would otherwise write by hand. |
| Framer Motion (now called Motion), springs, `layoutId` | Yes, sparingly | A sliding pill on the nav and on segmented controls, a holding row that opens into its card, numbers that count up. Only transform and opacity animate, and all motion stops when the system asks for less. |
| Next.js App Router | No: Vite | There is no server. Next's static export writes many files with absolute paths that do not open from disk. Vite builds one HTML file with everything inlined, which keeps the promise that the page is one file that opens offline and fetches nothing. |
| FastAPI or SQLite backend | No | Python already computes every number and writes files, and the record is an append-only JSONL file (P7). A server would add a process, a port and an attack surface to a page that only reads. |
| Optimistic UI updates | Not needed | The page never writes (P8). Views and decisions change in Claude Code, where the record stays honest. |
| ⌘K palette and keyboard shortcuts | Yes | Jump to any page, holding, theme, view, scan, crash path or bet indicator, and copy the `/morning`, `/bet` or `/scan` command for Claude Code. |
| Monochrome base, hairline borders, one accent, Geist and Geist Mono, tabular numbers, bento grid, small radii | Yes | Section 4. |

## 2. Architecture

```
Python                      dashboard.context()  ->  view model, also written to out/dashboard.json
                            render.page()        ->  the template with the view model in a JSON script tag
web/ (React, contributors)  npm run build        ->  src/whatstocks/assets/dashboard.html (committed)
```

- Users of whatstocks need Python only. Node is needed only by someone changing the page itself.
- The built template is one HTML file: the script, the styles and the two fonts are inlined.
- The view model is escaped before it goes into the page, so no text in it can close the script tag. React
  writes all text as text, and only `http(s)` links become links.
- The template carries a Content-Security-Policy with `default-src 'none'`: the page cannot fetch or send
  anything, even if a headline tried to make it.
- The geometry that needs care stays in Python and is tested there: packing the bubbles of a conflict scan
  and placing their labels, and laying out the ripple map. React only draws what it is given.
- The build stamps a hash of `web/` sources into the template. A pytest test fails when the sources changed
  and nobody rebuilt.

## 3. What came from each site

| Site | Taken | Left out |
|---|---|---|
| shadcn/ui | The dashboard block's shell (sidebar, section cards with a change badge, a chart card with a range control); Card, Badge, Kbd, Tooltip, Dialog, Command (the ⌘K palette), Toggle Group; the Chart wrapper around Recharts for the price lines | The full data table with sorting libraries: our tables are small |
| Tremor | Bar List (themes ranked; what is inside a fund), Category Bar (where a scan would hurt, help or be mixed; evidence for and against a view), Tracker (events per day), spark lines in the holdings rows | Donut charts (shares read better as bars), the default blue palette |
| Magic UI | Number Ticker for the headline figures, Dotted Map for where your companies are based | Border beams, shine, meteors, particles, gradient and aurora text |
| Aceternity UI | The expandable card (a holding row opens into its card with a shared layout move), the sliding tab indicator | Spotlights, background beams, 3D cards, glowing borders |
| Origin UI (now coss ui) | Styling cues for segmented controls, badges and keyboard hints | Its Base UI primitives: one primitive library (Radix, through shadcn) is enough |
| Mobbin | Nothing | The screen library needs an account, and it blocked automated access |
| Godly (now recent.design) | Inspiration: a dark stock card with one big mono number, a change pill and a single line | |

## 4. Design rules

These are the contract for every change to the page. [web/CLAUDE.md](../web/CLAUDE.md) repeats them for Claude
Code.

- **Surfaces.** The page is zinc-950 (`#09090b`), cards are one step lighter, and 1px hairline borders at
  about 8% white separate them. Shadows only on floating layers: the palette, dialogs and tooltips.
- **Colour.** Monochrome, plus one accent, international orange, for "you" and for active states. The world
  index is grey. One polarity pair (help, up, for against hurt, down, against) is checked with the
  colour-blind validator in both themes. A colour never carries meaning alone: signs, words or icons go
  with it. The bet page's states add one amber, `--warn`, for marks only: every state is a shape and a word
  (● clear, ◆ amber, ▲ red, ○ no data).
- **Type.** Geist for words, Geist Mono with tabular figures for every number, date and axis label.
- **Density.** 13 to 14px body text, cards padded 16px, radius 8px at most (6px on controls), tight headings.
- **Motion.** Transform and opacity only, springs at stiffness 380 and damping 30, never `transition-all`,
  and none when the system asks for reduced motion.
- **Banned.** Decorative gradients (purple, indigo, cyan or any), glows, glass and backdrop blur, radii of
  16px or more, heavy shadows, hero banners.
- **Charts.** Every mark has a hover tip; two or more series get a legend; light and dark are both checked.

## 5. Pages

A 12-column bento grid on desktop, one column on a phone. The primary cards of each page sit above the fold
at 1440 by 900.

- **Overview.** Five figures (today, past year with today's mix, biggest tilt, news today, open views), and a
  sixth when there is a bet: coverage now, with the regime and payback by the deadline. The price line
  against the world index, next to the morning brief and the themes that matter today. Top events, things to
  watch, and your biggest themes against the world. The latest conflict scan.
- **Holdings.** Your mix against the world index over six periods. One row per holding (weight, moves, a
  90-day spark line, its themes), sortable with a segmented control. A row opens into its card: the price
  line, what is inside it, today's news on it and the world around it.
- **News & world.** The brief, a theme filter, a card per theme that matters, the ripple map, things to
  watch on a 90-day line, today's events through the four questions, the two heat maps, other themes and
  blind spots.
- **Exposure.** Four figures, every theme against the world index, past sell-offs replayed, where each theme
  comes from, the theme table, a dotted map and bars of where your companies are based, currencies.
- **Scenarios.** A picker for the scans, the bubble map, which holdings it reaches, past episodes, what to
  watch, the channel table. With no scans yet: how to run one, with the command ready to copy.
- **Views.** One card per view: the probability, its path over time, the deadline, evidence for and against.
- **Record.** The Brier score, resolved views, decisions with their flags, what happened after.
- **The bet** ("Will the bet pay off?", SPEC section 3.6). The regime and the cash clock. The hero: what
  the build-out needs back against what end users pay, with three readouts and what the need implies, beside
  the sliders and switches. A card for each crash path and for adoption pace, with each indicator on its
  scale and your reach next to the world's. The adoption funnel and the grades. The four pillars.
  Open-weight releases and the analogs. Every threshold, and every source with what is due.

Keys: ⌘K, Ctrl K or `/` opens the palette, `1` to `8` switch pages, `T` switches the theme, Esc closes.

## 6. Steps

1. Scaffold `web/`: Vite, React, TypeScript, Tailwind 4, shadcn/ui, Motion, Geist; the tokens in `index.css`.
2. Python: the view model and `out/dashboard.json`; the template with escaping and the CSP; the geometry kept,
   the old HTML chart code removed.
3. The shell (sidebar, header, palette, routing by `#page/item`), the parts, the charts.
4. The seven pages.
5. Tests: pytest for the view model, escaping, a self-contained page and the template being in step with its
   sources; Vitest for formatting and routing.
6. Build, render the demo, check desktop and phone, dark and light, in a browser.
7. README, SPEC and `web/CLAUDE.md`.

## 7. What changed while building

- **A raised surface.** `--raised` (zinc-800 in dark, white in light) is the pill under the active option of a
  segmented control, one step above `--card-2`.
- **Tests have their own TypeScript config.** `tsconfig.test.json` adds Node's types for the Vitest files, so
  the app's config keeps browser types only.
- **The shadcn parts were brought into line with section 4.** Dialog and palette radii went down to 8px,
  `transition-all` became `transition-colors`, the dialog overlay lost its blur, and the chart wrapper sets
  its colours as inline CSS variables instead of writing a `<style>` tag with `dangerouslySetInnerHTML`.
- **The ripple map needs room.** Its labels wrap before they would leave the map, and in a panel narrower
  than 30rem (a phone) the map gives way to the list under it, which carries every ripple. On screens
  narrower than 1280px it takes the full width.
- **Heat maps open on the newest column.** A heat map wider than its panel scrolls inside the panel and
  starts scrolled to the right. Sparse column labels may overhang their column, so the columns stay as
  narrow as the cells.
- **A bug found on the way.** The portfolio line in `performance.py` counted its year back from today, while
  the period figures count back from the last close. On a morning before today's close the line began too
  late, so the one-year move read off it did not match the 1Y figure. `index_line` now cuts its window the
  way `change` does, and a test checks the line against the 1M, 3M and 1Y figures.
- **Tiny shares no longer look empty.** Shipping and trade routes is about 0.02% of the demo and 0.05% of the
  world index, which one decimal showed as 0.0% for both. A share that is there but rounds to nothing now
  reads <0.1%, in the page and in `geometry.pct`.
- **Size.** The page is about 1.2 MB, almost all of it React, Recharts and the two inlined fonts. It opens
  from disk without a network.

## 8. The bet page (v0.4)

- **One amber.** `--warn` (#f5b041 dark, #e09b00 light) marks an amber state. It is for marks only: amber text
  is too pale on white, so words beside it stay in ink (`StateMark`, `Caution` in `kit.tsx`).
- **No red in the hero.** The demand tiers use `--c1` to `--c5`, and `--c2` is an orange, so the gap between
  the curves is hatched in ink rather than tinted with `--neg`, and the valuation target is drawn in `--c7`.
- **The page's arithmetic.** It adds the pieces you leave switched on, divides two such sums, multiplies by
  Python's unit factors and runs the cash clock: the two exceptions to P2 in SPEC section 2. `bet.test.ts`
  checks them against the demo's figures. The regime, the paths and every indicator are Python's, and the
  Overview tile shows Python's readings, not the page's.
- **Layout.** From 1280px the hero takes 8 columns and the controls 4. Below that both take the full width,
  with the sliders and the switches side by side, and on a phone they stack. The deadline label sits a line
  below the last-actual label, so the two never collide.
- **Legend swatches** gained `hatch` (the gap) and `tri` (an open-weight release).
- **Size.** About 1.8 MB with the demo's bet data: Python precomputes every slider step for every piece.
