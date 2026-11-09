# web/: the dashboard page

This is the React app that `npm run build` turns into `../src/whatstocks/assets/dashboard.html`. That is one
self-contained HTML file, and Python fills it with the view model. The plan and its reasons are in
[docs/DASHBOARD.md](../docs/DASHBOARD.md); the product rules are in [docs/SPEC.md](../docs/SPEC.md). The rules
below are the contract for every change in this folder.

## Commands (run them in web/)

- `npm run dev` serves the page on localhost with the demo's data (`../demo/out/dashboard.json`; set `WS_DATA`
  to use another file). First render the demo from the repository root with `uv run whatstocks --dir demo finish`.
- `npm run build` type-checks, builds and copies the template into the Python package. Run it after any change
  here, and commit the template together with the sources: `tests/test_render.py` fails when they are out of
  step.
- `npm run typecheck` and `npm test` (Vitest) run the checks alone.

## What the page promises

- Every number comes from the view model (`src/lib/types.ts`), computed in Python. The page formats, sorts and
  picks a time window; it never makes up a figure. It shows your holdings as percentages only, never your
  amounts. The bet page shows public figures in dollars (a company's capex, a lab's revenue); none of them is
  yours.
- The bet page alone does arithmetic, the two exceptions to P2 in `docs/SPEC.md` section 2: it adds the pieces
  you switch on and divides two such sums, multiplies by Python's unit factors, and runs the cash clock. Keep it
  in `src/lib/bet.ts`, and test any change against the demo's figures in `src/lib/bet.test.ts`. The regime, the
  paths and the indicators are Python's: never work them out here.
- Text is always text: never use `dangerouslySetInnerHTML`. Only `webUrl()` makes links (http and https), and
  each link has `target="_blank" rel="noopener noreferrer"`.
- The page fetches nothing. The build adds a Content-Security-Policy with `default-src 'none'`. Do not use a
  CDN, a web font or an image from outside.
- The data placeholder (`WS_DATA` between `/*` and `*/`) appears once, in `index.html`. Never write it in a
  source file: `scripts/ship.mjs` refuses a build in which it appears twice.
- The page never writes. Views, decisions and briefs change in Claude Code.

## Design rules

- **Surfaces.** Use only the tokens in `src/index.css`: `bg-background`, `bg-card`, `bg-card-2`, `bg-raised`,
  `border-line`, `text-foreground`, `text-ink-2`, `text-ink-3`. No raw hex values in components.
- **Colour.**
  - One accent, orange (`--you`), for you and for active states.
  - The world index is grey (`--world`), drawn dashed or as a tick, and always labelled.
  - Up, help and for are blue (`--pos`); down, hurt and against are red (`--neg`).
  - Categories use `--c1` to `--c8` in that order, by entity and never by rank. A ninth folds into Other.
  - Orange never appears in a chart that also uses red. `--c2` is an orange too, so a chart that uses it takes
    no `--neg` (the bet page's hero hatches its gap in ink instead).
  - States (the bet page): clear is a blue circle (`--pos`), amber a diamond (`--warn`), red a triangle
    (`--neg`), no data a hollow circle (`--ink-3`). Draw them with `StateMark`, always with the word. `--warn`
    is for marks only, never text: it is too pale on white.
- **Meaning.** Colour never carries meaning alone: a sign, a word, a triangle or an icon goes with it. Text
  keeps the ink colours, with the coloured mark beside it.
- **Type.** Geist for words. Geist Mono with tabular figures (the `num` utility) for every number, date,
  ticker and axis label. Body text is 13 to 14px.
- **Density.**
  - Cards are the `Panel` from `components/kit.tsx`.
  - Radius 8px at most (`rounded-lg`), and 6px on controls (`rounded-md`).
  - Shadows only on floating layers: the palette, dialogs and tooltips.
- **Motion.**
  - Use `SPRING` (stiffness 380, damping 30), `PRESS` (scale 0.97) and `EASE` from `kit.tsx`.
  - Animate transform and opacity only.
  - Use `transition-colors` or `transition-opacity`, never `transition-all`.
  - `MotionConfig reducedMotion="user"` covers Motion. Check `useReducedMotion` for anything else that moves.
- **Banned.**
  - Gradients used for decoration, glows, glass and `backdrop-blur`.
  - `rounded-xl` and larger, and `shadow-xl` and heavier.
  - Hero banners.
- **Icons.** Lucide only, at a 1.5px stroke (set once in `index.css`).

## Charts

- Use the parts in `components/charts.tsx`, `maps.tsx` and `price-chart.tsx` before you add a new one.
- Every mark has a hover tip. Put the text in `data-tip`, and `TipLayer` shows it for the mouse and for
  keyboard focus.
- Two or more series get a legend (`Legend`, `YOU_WORLD`). One series needs none: the title names it. A
  legend's swatch matches its mark: `SwatchKind` in `kit.tsx` has line, dash, box, tick, ring, dot, hatch and
  tri.
- One axis per chart. Thin marks, and a 2px gap between fills.
- Geometry that needs care (packing the bubbles, laying out the ripple map) is computed and tested in Python
  (`geometry.py`). React only draws it.
- A table wider than its panel scrolls inside the panel. Its scroll box must be `relative`, or the
  screen-reader text inside it widens the whole page.
- Check every change in dark and light themes, at 1440, 1024 and 375 pixels wide, before you call it done.
