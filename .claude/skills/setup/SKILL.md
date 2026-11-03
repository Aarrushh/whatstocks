---
name: setup
description: First-time whatstocks setup. Creates the user's my/ folder, maps a broker export to holdings.csv, tags holdings to themes with the user's yes or no, and interviews the user into 2 or 3 checkable views. Use when the user says /setup or wants to start using whatstocks.
---

# /setup

About 15 minutes. Go one step at a time and show the user each file you write.
The rules for every file are in `docs/SPEC.md` section 6.

## Steps

1. **Folder.** Run `uv sync`. Copy `demo/settings.yaml` to `my/settings.yaml`.
   Create `my/views.yaml` with `views: []` and `my/decisions.yaml` with
   `decisions: []`. Check that `.gitignore` lists `my/`. Tell the user that
   `my/` stays on their computer and is never committed.
2. **Settings.** Ask for the home currency (the one they think in) and keep the
   benchmark `IUSQ.DE` (MSCI ACWI, the world index) unless they want another
   fund from `sources/funds.yaml`.
3. **Holdings.** Ask the user to drop in a broker CSV export, or type their
   holdings. Map the columns to `my/holdings.csv`:
   `symbol,isin,name,quantity,value,currency,account,kind`.
   - Symbols are Yahoo-style: `ASML.AS`, `SHEL.L`, `INFY.NS`, `NVDA`.
   - Give a quantity for stocks and funds; the code prices them. Give a value
     and currency only for cash (`CASH-EUR`) or anything Yahoo cannot price.
   - Show the result and ask the user to check it.
   - Read-only: whatstocks never connects to a broker and never places orders.
4. **Check.** Run `uv run whatstocks check`. Fix any problems it lists.
5. **Themes.** `check` prints the stocks that are in no theme. For each, propose
   at most one theme from `themes/themes.yaml` with a one-line reason (core if
   most of its revenue depends on the theme, partial if a real but smaller
   part does), or say it fits none. The user accepts or rejects each one.
   Write accepted tags to `my/themes.yaml`:
   ```yaml
   themes:
     defence:
       members:
         core: [{symbol: QQ.L, reason: "QinetiQ earns most of its revenue from defence ministries"}]
   ```
6. **Views.** Ask what the user believes about the world for the next one to
   three years. Turn 2 or 3 beliefs into views that pass the checklist:
   specific, dated (at least 30 days out), checkable by a stranger from a named
   public source, not certain, and linked to at least one theme with up or down.
   - You write the wording and the resolution rule. Read them back.
   - **The user sets the probability.** Never suggest a number, a range, or a
     base rate, even if asked. Say that the score only means something if the
     number is theirs.
   - Write each view to `my/views.yaml` with `created` as today and a first
     forecast dated today.
7. **First run.** Run `/morning`, then open `my/out/dashboard.html`.

## Later

- **A decision** ("I trimmed NVDA, about 2%, because of my capex view"): write
  the entry to `my/decisions.yaml` (format in SPEC 6.3), show it, and ask the
  user to confirm. Log it even if no view is cited.
- **A new probability**: append a forecast with today's date and the user's
  note. Never edit or delete an earlier forecast.
- **Resolving a view**: when a view is past its date, propose an outcome with
  a source link; the user confirms. Views are never deleted: a view that cannot
  be resolved gets `result: void` and a note.
