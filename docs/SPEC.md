# whatstocks v1 spec (draft)

Status: draft, 2026-11-03. Nothing here is built yet. Section 12 records
the owner's decisions on the first round of open questions.

## 1. Purpose

**You hold the views, and the tool holds you to them.**

The user states falsifiable views about the world, each with a probability
and a deadline. Every morning, the tool:

- measures how the user's portfolio is exposed to the themes those views are about,
- reads the day's news through a fixed four-question method and logs evidence for or against each view,
- keeps an append-only record of views, probability changes and trades, and scores the views when they resolve.

The intended user is a retail investor with a broker account who wants to
understand how world events touch their money. It is not for traders.

## 2. Principles

These are rules, not goals. Each one has a check in code (section 8).

| # | Rule | Why |
|---|---|---|
| P1 | The user owns the views. The AI may draft the wording for the user to approve, but it never sets, suggests or changes a probability, and never edits a view on its own. | Accountability only works if the calls are the user's own. |
| P2 | Code computes every number. The AI only writes words. | The same input files must always give the same numbers. |
| P3 | Every factual claim in the brief cites a news item that the code fetched, by id. The AI never sees a URL and cannot introduce one. | This stops invented sources. |
| P4 | The AI sees tickers and portfolio percentages, never quantities or money amounts. | Privacy. Amounts stay on disk. |
| P5 | Every exposure number is shown next to the same number for a world index fund. | "12% AI" means nothing without "the world is 30%". |
| P6 | The tool describes, and never recommends. It does not say buy, sell, add, avoid or "you should", and gives no price targets. | Personal recommendations are regulated. This tool is not that. |
| P7 | The record is append-only. Probability changes add a new entry, views can be voided but not deleted, and decisions are corrected by adding a new entry. | A record you can rewrite is not a record. |
| P8 | All data access is read-only. A broker connection is a read-only import or a CSV, never trading credentials. | No path from this tool to an order. |

## 3. What the user sees

One HTML page, `my/out/dashboard.html`, rebuilt by `/morning`.

### 3.1 Morning brief (top of the page)

5 to 10 events from the last 24 hours, picked because they touch the user's
themes, holdings or views. Each event answers the same four questions:

1. **What happened?** One sentence, with a source link and the source headline next to it.
2. **Where does money move?** Who pays, and who gets paid (governments, companies, consumers). This is the most important question, because money flows are what reach share prices.
3. **What does it touch?** Themes, regions, and the user's holdings (by ticker and portfolio %).
4. **Which views?** For each view it touches, the event counts as *for*, *against*, or *unclear*, with one line on why.

A quiet day is a valid result. If no view was touched, the brief says so
plainly and does not invent drama.

### 3.2 Views panel

For each open view:

- the statement, the current probability, the deadline, and days left,
- a probability line over time, built from the `forecasts` history,
- evidence counts for the last 7 and 30 days (for / against / unclear), with each item linking to its brief entry,
- the themes it implies a direction for, and the user's exposure to those themes.

Views past their deadline are shown at the top with a **resolve now** prompt
(section 4.4).

### 3.3 Exposure panel

All figures are look-through, which means funds are broken into the
companies they hold (section 7.1). Each one is shown next to the world
benchmark.

| Measure | Meaning |
|---|---|
| Theme share | % of the portfolio in each theme, with the list of names counted. |
| Theme beta | How much the portfolio moves when the theme's proxy ETF moves 1%. Weekly data, 2 years, in home currency. |
| Worst weeks | The portfolio's average return in the theme proxy's 10 worst weeks of the last 2 years. |
| Crash replay | Today's holdings replayed over named past sell-offs (2020 Covid, 2022 rates, and others). |
| Region and currency | Split by company domicile and listing currency. |
| Blind spots | Themes that are busy in the news this week where the user's share is zero, or under a quarter of the world's. Shown as the news and the world share only, with no tickers to buy. |

### 3.4 Record panel

- **Resolved views**: outcome, the time-weighted Brier score per view and overall, and the coin-flip reference of 0.25.
- **Calibration**: shown only after 20 or more views have resolved. Before that, the panel says the score is mostly luck.
- **Decisions**: each trade, the views it cited, and any flags (section 7.6). On its review date, it shows what the stock did since the decision against the world index, labelled "what happened after", not "right" or "wrong".

## 4. User flow

### 4.1 `/setup` (once, about 15 minutes)

1. It creates `my/` from `demo/` and confirms that git ignores `my/`.
2. It asks for the home currency and the benchmark (default: ACWI).
3. **Holdings**: the user drops in a broker CSV export, and the AI maps its columns to `holdings.csv`. The user checks the result. A manual CSV also works.
4. **Themes**: the code tags holdings from `themes/themes.yaml`. For untagged companies, the AI proposes a theme with a one-line reason, and the user accepts or rejects each one. Accepted tags go to `my/themes.yaml`.
5. **Views**: the AI interviews the user to turn 2 or 3 beliefs into views that pass the checklist (section 6.2). It writes the wording, and the user sets the probability. The AI never suggests a number.
6. It runs `/morning` once and opens the page.

### 4.2 `/morning` (daily, a few minutes)

See section 8.

### 4.3 Logging a decision

The user says something like "I trimmed NVDA, about 2% of the portfolio,
because of my capex view". The AI writes the entry to `my/decisions.yaml`,
shows it, and asks for confirmation. If no view is cited, the entry is
still logged, with the flag "no view cited".

### 4.4 Resolving a view

When a view passes its `resolves_by` date, or the brief finds evidence that
it has already resolved, the AI proposes an outcome with a source link. The
user confirms or corrects it. The outcome is written once and then scored.

## 5. Folder layout

```text
whatstocks/
  README.md
  LICENSE                  MIT
  pyproject.toml           uv project
  docs/SPEC.md, docs/DATA_SOURCES.md
  themes/themes.yaml       shipped starter theme map, community-maintained
  sources/funds.yaml       funds that can be looked through, and where their holdings files are
  sources/feeds.yaml       news feeds, and the search used for each theme's news_query
  demo/                    a complete fictional user, used for first run and tests
    settings.yaml
    holdings.csv
    views.yaml
    decisions.yaml
  my/                      created by /setup, git-ignored
    settings.yaml
    holdings.csv
    views.yaml
    decisions.yaml
    themes.yaml            optional: the user's additions and overrides
    cache/                 prices, FX, fund holdings, news
    out/                   exposure.json, brief.json, evidence.jsonl, dashboard.html
  .claude/skills/          setup, morning (decide and resolve are covered inside setup for now)
  src/whatstocks/          code: files, market, funds, exposure, news, brief, record, render, morning, cli
  tests/                   offline tests with synthetic prices, holdings files and news
```

Commands (the skills run these):

| Command | What it does |
|---|---|
| `uv run whatstocks check` | Check the files in `my/` and list stocks that are in no theme. |
| `uv run whatstocks prepare` | Steps 1 to 6 of section 8: data in, `payload.json` out. `--offline` uses the cache only. |
| `uv run whatstocks finish` | Steps 8 to 11: check `brief.json`, update the evidence log, build the page. `--no-brief` skips the brief. |

Every command takes `--dir <folder>` (default `my`), so `--dir demo` runs the demo user.

## 6. File formats

There are four contract files and one small settings file. All dates use
`YYYY-MM-DD`, and all files are UTF-8. The `demo/` folder holds a valid
example of each one.

### 6.0 `settings.yaml`

```yaml
home_currency: EUR        # ISO 4217 code. All values and returns are converted to this.
benchmark: IUSQ.DE        # The world fund used for every comparison (iShares MSCI ACWI).
```

### 6.1 `holdings.csv`

One row per position. Amounts live only in this file.

| Column | Required | Meaning |
|---|---|---|
| `symbol` | `symbol` or `isin` | Yahoo-style ticker, for example `NVDA`, `ASML.AS`, `RHM.DE`, `VWCE.DE`, `INFY.NS`. Cash uses `CASH-<CCY>`. |
| `isin` | no | Used to find the symbol when it is missing, and to find a fund's holdings file. |
| `name` | no | Display only. |
| `quantity` | `quantity` or `value` | Number of shares or units. |
| `value` | `quantity` or `value` | Current value in `currency`. Used for cash, and when no price is available. |
| `currency` | if `value` is set | ISO code for `value`. For quantity rows, the currency comes from the listing. |
| `account` | no | Free text, used for grouping only. |
| `kind` | no | `stock`, `fund` or `cash`. Detected automatically if blank. |

No cost basis is needed. This is not a profit-and-loss tracker.

Validation: each row needs an identifier and a size. Symbols must be unique
within an account. Unknown symbols are reported with the row number, and the
run stops.

### 6.2 `views.yaml`

```yaml
views:
  - id: ai-capex-cut-2027                 # kebab-case, unique, never reused
    statement: >-                         # the claim, in one sentence
      At least two of Microsoft, Alphabet, Amazon and Meta report lower
      capital expenditure for calendar 2027 than for calendar 2026.
    created: 2026-09-10
    resolves_by: 2028-03-31
    resolution: >-                        # how a stranger would check it
      Sum each company's quarterly capex for calendar 2027 and 2026 from
      its earnings releases. YES if two or more are lower in 2027.
    themes:                               # what YES would mean for each theme
      ai_buildout: down
    forecasts:                            # append-only; the last entry is current
      - {date: 2026-09-10, probability: 0.30, note: first call}
      - {date: 2026-10-20, probability: 0.40, note: two guidance cuts at Q3 results}
    outcome:                              # absent until resolved
      result: yes                         # yes | no | void
      date: 2028-02-05
      source: https://...
      note: ...
```

The view checklist, which `/setup` enforces in conversation:

1. **Specific**: names the companies, indicators or countries.
2. **Dated**: has a `resolves_by` date at least 30 days after `created`.
3. **Checkable by a stranger**: `resolution` names a public source.
4. **Not certain**: probability is between 0.01 and 0.99.
5. **Linked**: implies a direction (`up` or `down`) for at least one theme in the theme map.

Validation: the first forecast date equals `created`, and forecast dates
strictly increase. Every theme id exists. If `result: void`, the `note`
field is required. A view is never deleted. Deleting one is a validation
error, detected by comparing against `my/out/views_seen.json`.

### 6.3 `decisions.yaml`

```yaml
decisions:
  - id: d-2026-09-15-nvda          # d-<date>-<symbol>[-n]
    date: 2026-09-15
    action: trim                   # buy | add | trim | sell | hold
    symbol: NVDA
    size_pct: 2.0                  # optional: rough % of the portfolio moved. Never an amount.
    views: [ai-capex-cut-2027]     # may be empty
    reason: >-
      Cutting AI chip exposure because I give a capex slowdown a real chance.
    review_on: 2027-09-15          # default: date + 365 days
    corrects: null                 # id of an earlier entry this one replaces
```

`hold` records a deliberate choice not to act. Doing nothing is a decision
too.

Validation: ids are unique. The symbol exists in holdings, or existed on
that date (sells can remove a holding). Every view id exists. `corrects`
points to an earlier entry.

### 6.4 `themes.yaml`

The shipped file is `themes/themes.yaml`. The optional `my/themes.yaml` has
the same shape and is merged on top of it: it adds themes, adds members,
and can remove members with `remove:`.

```yaml
version: 1
themes:
  ai_buildout:
    label: AI build-out
    description: Companies whose revenue depends on AI data-centre spending.
    proxy: SOXX                    # ETF used for theme beta and worst weeks
    news_query: '"AI data center" OR "AI chips"'  # the only text sent to the news search
    members:
      core: [NVDA, AVGO, ...]      # counts 1.0 toward theme share
      partial: [MSFT, GOOGL, ...]  # counts 0.5
    notes: ...
```

Rules:

- Members are companies, not funds. Funds are always looked through.
- A company can sit in more than one theme.
- The top-level `aliases:` map lists other lines of the same company, for example `TSM: [2330.TW]`. Index funds usually hold the home-market line. List each company once under `members` and put its other lines in `aliases`.
- Every member added by the AI carries a `reason` in `my/themes.yaml`.
- `news_query` is sent to the news search engine as it is. Keep it about the theme; never put a holding or a view in it.

## 7. Calculations

All of these are code. None is done by the AI.

### 7.1 Values and look-through

- **Value** = quantity × latest close, converted to home currency at the ECB reference rate. `value` rows are converted the same way.
- **Look-through**: each fund's value is spread across its constituents using the issuer's published holdings file. The run uses every constituent. Rows that are not equities (cash, futures, FX) are grouped as "Cash and other". A fund held inside a fund is looked through when the inner fund is listed in `sources/funds.yaml` with its `lines`, up to three levels deep; otherwise its value is shown as not looked through, and the data notes name it. A holdings file older than 90 days is flagged.
- **Matching** (from the [source check](DATA_SOURCES.md)):
  - Match a constituent to a theme member on ticker **and** exchange, never on ticker alone (`BA.L` is not `BA`).
  - Exchange names are mapped per issuer file, because the same exchange can appear under different names.
  - Try each member's alias lines (section 6.4), and count a company only once.
- **Fund in fund**: a constituent that is itself a fund is looked through recursively, up to 3 levels. The UCITS ACWI fund holds India through `NDIA`.
- The benchmark goes through the same look-through, using the US `ACWI` holdings file. It tracks the same index and lists Indian stocks directly.

### 7.2 Theme share

```text
share(theme) = Σ value(company) × weight(company, theme) / total value
weight = 1.0 for core, 0.5 for partial, 0 otherwise
```

The panel always lists the names that were counted, because the definition
of the theme drives the number.

### 7.3 Theme beta

This is the OLS slope of weekly portfolio returns on weekly proxy returns,
over the last 104 weeks, in home currency. The portfolio means today's
holdings at today's weights, replayed backward. The benchmark gets the same
calculation.

Holdings with fewer than 52 weeks of history are left out, and the % of value
that is covered is shown.

### 7.4 Worst weeks and crash replay

- **Worst weeks**: take the proxy's 10 worst weekly returns in the last 104 weeks, and report the portfolio's mean return and the benchmark's mean return in those same weeks.
- **Crash replay**: the return of today's holdings over named windows that are fixed in code, for example `2020-02-19..2020-03-23` (Covid) and `2021-11-19..2022-10-13` (2022 tech bear). Holdings that did not exist yet are reported as uncovered, with the coverage %.
- Caveat, printed on the page: betas measured in calm years understate how closely things move together in a real crash.

### 7.5 View scoring

The score is a time-weighted Brier score. For each day from `created` to
the resolution date, it takes the probability in force that day, computes
`(p − o)²` with `o = 1` for YES and `0` for NO, and averages over the days.

- Lower is better. Always saying 50% scores 0.25.
- Raising a probability the day before the deadline earns almost nothing, because that probability stood for only one day.
- Void views are not scored, but they are listed with their reason.
- The overall score is the mean over resolved views, always shown with the count. Under 20 views, the page says the score is mostly luck.

### 7.6 Decision flags

Flags are shown, never blocking:

| Flag | When |
|---|---|
| No view cited | `views` is empty. |
| Low-confidence view | A cited view was under 50% on the decision date. |
| Against your view | Take a cited view at 50% or more that implies `down` for a theme. Buying or adding a core member of that theme gets this flag, and so does selling or trimming a core member of a theme the view implies `up` for. |
| Busy news day | The decision was made on a day the brief had 3 or more events touching that symbol's themes. This is a gentle check for news-driven trading. |

## 8. The `/morning` pipeline

Steps 1 to 6 are `whatstocks prepare`, step 7 is the user's AI, and steps 8 to 11 are `whatstocks finish`.

| Step | Who | What | Check |
|---|---|---|---|
| 1 | code | Load and validate the `my/` files. | Stop with a row or line number on any error. |
| 2 | code | Refresh prices and FX into the cache. If a source fails, keep the last cached values. | Show a "prices from <date>" banner when any price is older than the last trading day. Stop only when a holding has no cached price at all. |
| 3 | code | Refresh fund holdings files when they are older than 30 days. | Flag files older than 90 days. |
| 4 | code | Compute exposure (section 7) into `exposure.json`. | Theme shares within [0, 1], and the benchmark computed too. |
| 5 | code | Fetch news into `news.json`: the publisher feeds, plus one search per theme built from its `news_query`. Each item gets a stable id (a hash of its URL). | Deduplicate by URL and title. Only theme queries go to the search engine, never holdings or views. |
| 6 | code | Build the AI payload: news items (id, title, source, time, no URL), tickers with portfolio %, the themes with your share and the world's, and open views (statement, current probability, themes). | **Payload check**: no money fields, and none of the user's amounts or quantities written anywhere outside public text such as headlines. |
| 7 | AI | Write `brief.json`: a summary, and events with `news_ids` and the four answers (`what`, `money`, `touches`, and `views` with `for`, `against` or `unclear` and a `why`). The format is in `.claude/skills/morning/SKILL.md`. | Checked in step 8. Blind spots are computed in code, not by the AI. |
| 8 | code | Validate the brief. | Every event cites at least one `news_id` from today's payload, and only known themes, holdings and open views. Any URL is an error. Advice-like wording ("you should", "consider buying", price targets and others) stops the run; the `/morning` skill rewrites once, and only the user can let it through with `--allow-advice`, which adds a warning banner. |
| 9 | code | Append today's events to `evidence.jsonl`. | Earlier days are never changed. A re-run on the same day replaces that day's entries. |
| 10 | code | Render `dashboard.html` from a template. | The page works offline, with no external scripts. |
| 11 | code | Mark the views that are past their `resolves_by` date. | — |

The AI is the user's own Claude, running inside Claude Code. The tool needs
no API key of its own, and the user pays their own model usage.

## 9. Data sources (tested 2026-11-03, see [DATA_SOURCES.md](DATA_SOURCES.md))

| Need | Source | Notes |
|---|---|---|
| Daily prices | Yahoo via `yfinance`, with the local cache as backup | 97 of 97 test symbols OK. It's unofficial, so when it fails the last cached prices are used and marked stale (decision 3). Stooq is blocked by a bot check. London prices come in pence. |
| FX | ECB reference rates | Tested OK. Covers EUR crosses only, so other pairs go through EUR. |
| Fund holdings | Issuer files: iShares tested OK via `/latest-holdings.csv`. Vanguard, SPDR and Invesco are untested. | Formats differ by issuer, so each needs its own parser. Exchange names differ even within one issuer. |
| News | Publisher RSS feeds (main source), GDELT DOC 2.0 (optional) | 7 RSS feeds tested OK. GDELT rate-limited every request after the first. |
| Macro, for resolving views | FRED, EIA, national statistics offices | FRED needs a free key. Only used when the user resolves a view. |
| US company facts | SEC EDGAR | Free, but needs a User-Agent. v2. |

The default install must work with **no keys at all**. Keys only add sources.

## 10. Out of scope for v1

- Undervalued screens and stock picks (planned as a later experimental module, which will publish its own track record)
- Order placement of any kind
- Hosting, multiple users, or a mobile app
- Push alerts or email
- Tax or cost basis
- Backtests of views or strategies

## 11. Known weaknesses

- **Theme tags are judgement calls.** Whether Microsoft counts as core or partial AI moves the world benchmark's AI share by several points. Mitigation: the names counted are always listed, and the user can edit them.
- **Look-through is approximate.** It uses only the top constituents, and issuer files change format without warning.
- **Betas from calm periods understate crashes.** This is printed on the page, and the worst-weeks and crash-replay measures are there to help.
- **Scores are noise for a long time.** Most users will need one to two years to resolve 20 views. The page must say this, not hide it.
- **The code checks that a brief's sources exist, not that the brief reads them correctly.** It also cannot check which important events the brief left out. Mitigation: the source headline sits next to every claim, so a mismatch is visible.
- **Daily news invites overtrading.** Mitigation: "no view touched today" is shown as a normal result, decisions ask for a cited view, and the busy-news-day flag catches news-driven trades.
- **Free data breaks.** Every source needs a fallback, or a clear message when it is down.
- **Wording can drift toward advice.** The banned-phrase scan is crude. The real protection is the design: the AI is never asked what to do.

## 12. Decisions (owner, 2026-11-03)

| # | Question | Decision | Effect |
|---|---|---|---|
| 1 | License | **MIT** | `LICENSE` added. |
| 2 | Default benchmark | **MSCI ACWI** (`IUSQ.DE`) | Includes emerging markets and India, and is close to FTSE All-World (VWCE), the most common EU retail ETF. A user can change it in `settings.yaml`. |
| 3 | Price source | **`yfinance`, with the local price cache as backup.** Re-decided 2026-11-03, after Stooq turned out to block scripts. | If Yahoo fails, the run uses the last cached prices and the page shows a "prices from <date>" banner. No key is needed. An optional keyed source may come later ([DATA_SOURCES.md](DATA_SOURCES.md), finding 1). |
| 4 | Starter themes | **The first 7, plus 3 geopolitics themes** | `critical_minerals`, `nuclear_uranium` and `shipping_routes` added to `themes/themes.yaml`, 10 in all. |
| 5 | Can the AI suggest a probability change? | **No. Evidence labels only.** | Confirms P1. The score measures the user, not the AI. |
| 6 | Neo4j `docker-compose.yml` | **Removed** | Nothing in this design needs a graph database. The file stays in git history. |
| 7 | Packaging | **`uv`** | Install becomes: install `uv` and Claude Code, clone, then `uv sync`. `uv` also installs the right Python version. |

Next open items, for after the data-source check: the minimum Python
version, the news query design (section 8, step 5), and the dashboard
template.
