---
name: bet
description: Bring the "Will the bet pay off?" page's figures up to date. The code lists which ledger figures are due and the open gaps; you research them, show the user each proposed figure with its source, and write only what they approve to my/bet.yaml; the code then works the bet out again and redraws the page. Use when the user says /bet, or asks to update the AI bet page's figures.
---

# /bet

The bet page is only as good as its ledger: every figure the code cannot fetch,
each with a source. This skill keeps the user's part of it, `my/bet.yaml`, up to
date. The code does every number; you find sourced figures and the user approves
each one.

The user's folder is `my/` unless they say otherwise (the demo is `demo/`): add
`--dir <folder>` to every command when it is not `my/`.

## Steps

1. Run `uv run whatstocks bet due`. It lists the series with a newer figure due,
   the ones that move the curves first, then the open gaps. Skip a line marked
   as fetched by the code (FRED, Yahoo, or EDGAR once `sec_contact` is set):
   `whatstocks prepare` fills those.
2. Research from the top of the list, within the session's web-search budget.
   Tell the user how far you got.
3. Show each proposed figure: the series and company, the period, the value
   (and `low`/`high` where sources disagree), the grade, the source link, the
   date you read it, and the figure it replaces. Wait for the user's yes, one by
   one or all together.
4. Copy `my/bet.yaml` (if it exists) to `my/backups/<YYYY-MM-DD>/`, and tell the
   user where the copy is.
5. Write the approved figures to `my/bet.yaml`, under `series:`.
6. Run `uv run whatstocks check`. If it lists problems, fix them and run it again.
7. Run `uv run whatstocks bet`. Tell the user what it says moved, in its own
   words and numbers. Add no opinions of your own.

## Rules

- **Every figure has a source** you read yourself: an `http(s)` link, and `seen`
  the date you read it. No source, no figure.
- **Grades:** `filed` (filings, official statistics), `company` (calls, releases,
  company blogs), `press`, `estimate` (analysts, third parties). Never raise a
  grade without a better source.
- A guidance figure that changed records `why`: `accounting`, `supply`, `demand`
  or `unstated`.
- Never edit `sources/bet/`: a shipped change goes on a branch (CLAUDE.md, level 3).
- Never set, suggest or change a probability, and never suggest a threshold. The
  user's own amber and red levels are theirs to set, with their reason.
- Describe, never recommend. No buy, sell or price-target wording anywhere.
- Your amounts never enter this work: the ledger holds public figures only.

## my/bet.yaml format

```yaml
series:
  lab_runrate:                 # a series id from 'whatstocks bet due'
    points:
      perplexity:              # the company or item id it printed
        - {period: 2026-10-31, value: 0.4, grade: press, source: "https://...", seen: 2026-11-07,
           note: "Annualized revenue, as reported"}
```

A figure with the same series, company and period as a shipped one replaces it,
and the page marks it as yours. `whatstocks check` explains anything it cannot
read.
