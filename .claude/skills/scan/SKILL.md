---
name: scan
description: Map where a conflict would reach the user's portfolio, next to the world index. The code searches the past week's news for the conflict; you mark which themes and regions it would hurt or help and how strongly; the code computes every share and draws a bubble map on the dashboard's Scenarios page. Use when the user says /scan, or asks how exposed they are to a war, blockade, sanctions or another conflict.
---

# /scan

A scan is a map of where a conflict would reach the user's money. It is not a
forecast of whether the conflict happens, or of what prices will do. The code
does every number; you judge the channels, from the scan payload only.

The user's folder is `my/` unless they say otherwise (the demo is `demo/`):
add `--dir <folder>` to every command when it is not `my/`.

## Steps

1. Take the conflict in the user's own words, for example
   "China blockade of Taiwan". If they gave none, ask which conflict.
2. Run `uv run whatstocks scan prepare "<conflict>"`.
   - If it says to run `whatstocks prepare` first, run that, then step 2 again.
   - It prints the scan's name (its slug) and the payload's path.
3. Read `my/out/scans/<slug>.payload.json`. It holds:
   - `themes`: each theme's id, label, description and the user's and the
     world index's share.
   - `regions`: countries, by the share of the portfolio and of the world index
     whose companies are based there.
   - `holdings`: each holding's share of the portfolio, and the countries and
     themes inside it.
   - `news`: the past week's headlines about the conflict (id, title, source).
4. Write `my/out/scans/<slug>.json` by the rules below.
5. Run `uv run whatstocks scan finish <slug>`.
   - If it lists problems, fix the file and run it once more.
   - Never pass `--allow-advice` yourself. That is the user's call.
6. Tell the user the hurt and help shares it printed, next to the world
   index's, and that the map is on the dashboard's Scenarios page. Add no
   opinions of your own.

## Rules

- Use only the payload. Do not search, browse or add facts from memory, except
  the dates of past episodes (`analogs`), which you may know.
- **Channels** (1 to 12) are the themes and regions the conflict would reach:
  - `kind`: `theme` (an id from `themes`) or `region` (an id from `regions`,
    spelled exactly as there).
  - `effect`: `hurt`, `help` or `mixed`, for the companies in that channel.
  - `strength`: `low`, `medium` or `high`. This is your judgment of how hard
    the conflict would hit that channel's revenue or costs, not of its odds.
  - `why`: the mechanism, in one sentence: supply, demand, prices, sanctions,
    shipping, rules.
  The code counts each company once, at the strongest channel that reaches it,
  so a company in both "Taiwan" and "AI build-out" is not counted twice.
- **Analogs** (up to 4) are past windows that looked like this conflict: name,
  `start`, `end` (YYYY-MM-DD), and `why`. They must start on or after
  2019-12-01 (prices start there), last at most 400 days, and end before
  today. The code replays today's holdings over them.
- **Watch** (up to 6): developments to watch, each citing `news_ids`.
- Cite news by `news_ids` from the payload. Never write a URL.
- Describe, never recommend. No "you should", "consider selling", price
  targets, or any buy, sell, add or trim advice, in any field.
- Never mention amounts of the user's money. The payload has none.

## <slug>.json format

```json
{
  "date": "2026-11-03",
  "summary": "Two or three factual sentences: what the conflict would disrupt, and where that reaches this portfolio.",
  "news_ids": ["a1b2c3d4e5"],
  "channels": [
    {"kind": "region", "id": "Taiwan", "effect": "hurt", "strength": "high", "why": "A blockade would halt exports from the island's chip plants."},
    {"kind": "theme", "id": "ai_buildout", "effect": "hurt", "strength": "high", "why": "Most advanced AI chips are made in Taiwan."},
    {"kind": "theme", "id": "defence", "effect": "help", "strength": "medium", "why": "Governments in the region would order more equipment."}
  ],
  "analogs": [
    {"name": "Pelosi visit and PLA drills", "start": "2022-08-01", "end": "2022-08-15", "why": "Live-fire drills encircled the island for days."}
  ],
  "watch": [
    {"what": "Insurance rates for ships in the Taiwan Strait.", "news_ids": ["a1b2c3d4e5"]}
  ]
}
```

`date` must equal the payload's date. When the news search found nothing,
`news_ids` may be empty lists.
