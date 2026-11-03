---
name: morning
description: Build today's whatstocks dashboard. Refreshes prices and news in code, has you read the news through the four questions into brief.json, then checks the brief and renders the page. Use when the user says /morning, "morning brief", or asks to update their whatstocks dashboard.
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
2. Read `my/out/payload.json`. It holds today's date, holdings as % of the
   portfolio, the themes with the user's and the world index's share, the open
   views, and the news items (id, title, source, published).
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
none of the themes, holdings or views. At most 8 events, most relevant first.

1. **What happened** (`what`): one factual sentence. No adjectives that judge.
2. **Who pays, who gets paid** (`money`): the money mechanism, in one or two
   sentences. Who loses revenue or margin, who gains it, and through what
   channel (prices, volumes, costs, rates, rules).
3. **What it touches** (`touches`): theme ids and holding symbols from the
   payload, only where the mechanism in question 2 reaches them.
4. **For or against which view** (`views`): for each open view the event bears
   on, `for` (makes the statement more likely to come true), `against`, or
   `unclear`, with a one-sentence `why`.

## Rules

- Use only the payload. Do not search, browse or add facts from memory.
- Cite news by `news_ids` from the payload. Never write a URL.
- Never suggest a probability, a change to one, or a number for a view. The
  user owns every probability.
- Describe, never recommend. No "you should", "consider buying", price
  targets, or any buy, sell, add or trim advice.
- Never mention amounts of the user's money. The payload has none, and the
  brief must not guess any.
- If nothing touches the themes, holdings or views, write no events and set
  `quiet_day` to true.

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
  ]
}
```

`date` must equal the payload's date. `touches` and `views` may be empty lists.
