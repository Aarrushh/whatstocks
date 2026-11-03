---
name: morning
description: Build today's whatstocks dashboard. Refreshes prices and news in code, has you read the news through the four questions into brief.json (events, the themes that matter, ripples, things to watch), then checks the brief and renders the page. Use when the user says /morning, "morning brief", or asks to update their whatstocks dashboard.
---

# /morning

The code does every number. You write the words, from the payload only.
The user's folder is `my/` unless they say otherwise (the demo is `demo/`):
add `--dir <folder>` to every command when it is not `my/`.

## Steps

1. Run `uv run whatstocks prepare`.
   - If it prints "Fix these first", show the user the list, help them fix
     their files, and stop. Do not edit `views.yaml` probabilities yourself.
   - Notes such as "prices not refreshed" are fine: the page shows them.
2. Read `my/out/payload.json`. It holds:
   - `date`: today.
   - `holdings`: each holding's `weight_pct` of the portfolio, the `countries`
     inside it (`[country, % of the holding]`, top 3) and the `themes` inside it
     (`[theme id, % of the holding]`, 2% or more).
   - `themes`: each theme's `your_share_pct` and `world_share_pct`, whether you
     `must_cover` it, the `open_views` that name it, and `headlines_today`.
   - `views`: the user's open views, with their probabilities. Read them; never
     change them.
   - `news`: today's items (id, title, source, published).
3. Write `my/out/brief.json` by the rules below.
4. Run `uv run whatstocks finish`.
   - If it lists problems with brief.json, fix the brief and run it once more.
   - If it still fails, run `uv run whatstocks finish --no-brief` and tell the
     user why the brief was left out.
   - Never pass `--allow-advice` yourself. That is the user's call.
5. Tell the user where the dashboard is, and give the summary line from the
   brief. Add no opinions of your own.

## How to read the news: four questions per event

Group news items about the same thing into one event. Skip items that touch
none of the themes, holdings or views. At most 10 events, most relevant first.

1. **What happened** (`what`): one factual sentence. No adjectives that judge.
2. **Who pays, who gets paid** (`money`): the money mechanism, in one or two
   sentences. Who loses revenue or margin, who gains it, and through what
   channel (prices, volumes, costs, rates, rules).
3. **What it touches** (`touches`): theme ids and holding symbols from the
   payload, only where the mechanism in question 2 reaches them.
4. **For or against which view** (`views`): for each open view the event bears
   on, `for` (makes the statement more likely to come true), `against`, or
   `unclear`, with a one-sentence `why`.

## The rest of the brief

- **`themes`: the world around the user's money.** One entry for every theme
  with `must_cover: true` (2% or more of the portfolio, or named by an open
  view). The check fails without them. Add any other theme today's news moved
  that matters to this portfolio, and leave the rest out. Each entry:
  - `state`: where the theme stands today, in one or two factual sentences.
  - `why_it_matters`: why it matters to this portfolio, from the payload: which
    holdings sit in it, or which view names it.
  - `news_ids`: the items behind it. On a quiet theme, write
    `"state": "No news in today's feeds."` with an empty `news_ids` list.
- **`holdings`: notes on single holdings** (optional). Only where an item is
  about that company or fund directly: what happened to it, in one sentence,
  with its `news_ids`.
- **`ripples`: knock-on effects between themes** (at most 8). An event in one
  theme that reaches another: energy prices and data centre costs, export
  rules and chip supply, shipping lanes and component lead times. Look hardest
  for ripples into `ai_buildout`: the user wants the smaller geopolitical
  effects on AI. `from` and `to` are different theme ids; `effect` is `help`,
  `hurt` or `unclear` for the companies in the `to` theme; `why` gives the
  mechanism in one sentence; cite at least one `news_ids`.
- **`watch`: things to watch next** (at most 8). A meeting, vote, deadline,
  data release or ruling the news mentions. Give `when` (YYYY-MM-DD) only when
  an item states the date; leave it out otherwise, and never a past date.
  Tag the `themes` and `holdings` it would reach, and cite `news_ids`.

## Rules

- Use only the payload. Do not search, browse or add facts from memory.
- Cite news by `news_ids` from the payload. Never write a URL.
- Never suggest a probability, a change to one, or a number for a view. The
  user owns every probability.
- Describe, never recommend. No "you should", "consider buying", price
  targets, or any buy, sell, add or trim advice. That holds in every field.
- Never mention amounts of the user's money. The payload has none, and the
  brief must not guess any.
- If nothing touches the themes, holdings or views, write no events, set
  `quiet_day` to true, and still give the `must_cover` themes.

## brief.json format

```json
{
  "date": "2026-11-03",
  "summary": "One or two sentences on what mattered today for this portfolio and these views.",
  "quiet_day": false,
  "events": [
    {
      "what": "OPEC+ agreed to extend its output cuts to the end of Q2 2027.",
      "news_ids": ["a1b2c3d4e5", "f6a7b8c9d0"],
      "money": "Producers get a higher price per barrel on lower volumes; refiners and airlines pay more for crude.",
      "touches": {"themes": ["oil_gas"], "holdings": ["SHEL.L"]},
      "views": [
        {"view_id": "brent-above-90-2027", "effect": "for", "why": "Tighter supply into 2027 raises the chance of a quarter averaging above 90 dollars."}
      ]
    }
  ],
  "themes": [
    {"id": "oil_gas", "state": "OPEC+ kept supply tight into mid-2027.", "why_it_matters": "Shell sits in this theme, and your Brent view names it.", "news_ids": ["a1b2c3d4e5"]},
    {"id": "india", "state": "No news in today's feeds.", "why_it_matters": "Infosys and your India GDP view sit in this theme.", "news_ids": []}
  ],
  "holdings": [
    {"symbol": "SHEL.L", "note": "Shell sells crude and gas, so tighter supply lifts what it is paid per barrel.", "news_ids": ["a1b2c3d4e5"]}
  ],
  "ripples": [
    {"from": "oil_gas", "to": "ai_buildout", "effect": "hurt", "why": "Dearer energy raises what data centres pay to run.", "news_ids": ["a1b2c3d4e5"]}
  ],
  "watch": [
    {"what": "OPEC+ meets again on output.", "when": "2026-12-01", "themes": ["oil_gas"], "holdings": ["SHEL.L"], "news_ids": ["a1b2c3d4e5"]}
  ]
}
```

`date` must equal the payload's date. `touches`, `views`, `holdings`,
`ripples` and `watch` may be empty lists.
