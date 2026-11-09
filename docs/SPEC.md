# whatstocks v1 spec (draft)

Status: 2026-11-07. v0.1 built the pipeline; v0.2 added the seven-page
dashboard (section 3) and conflict scans (section 3.5); v0.3 rebuilds the
page in React, still as one offline file ([DASHBOARD.md](DASHBOARD.md));
v0.4 adds an eighth page, "Will the bet pay off?", and `/bet` (section 3.6).
Section 12 records the owner's decisions on the first round of open
questions.

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

**Exceptions to P2.** The page itself does arithmetic in one place only, the bet page (section 3.6), and only on
numbers Python computed. Vitest tests (`web/src/lib/bet.test.ts`) check the sums, the readouts and the clock against
the figures Python computed for the demo.

- **(a) The cash clock** adds a rate × the seconds since its data date to a total Python computed.
- **(b) The switches.** The page adds up the pieces of a model that are switched on, and divides two such sums for
  its readouts (coverage now, payback by the deadline, the valuation target). To show a sum in seats or work hours,
  or what the need implies (a productivity gain, work hours, a share of the budget pool), it multiplies the sum by a
  factor Python computed for that slider step.

The regime, the paths and every indicator are computed in Python, never on the page.

## 3. What the user sees

One self-contained HTML file, `my/out/dashboard.html`, rebuilt by `/morning`
and after each `/scan`. It works offline and fetches nothing: its script,
styles and fonts are inlined, and its Content-Security-Policy blocks every
request. The page is a React app (`web/`, built into
`src/whatstocks/assets/dashboard.html`); Python computes the view model and
puts it into the page as escaped JSON, also written to `out/dashboard.json`.
The page has eight pages, a command palette, hover tips on every mark, and a
dark and a light theme. It shows your holdings as percentages only, never
your amounts. (The bet page shows public figures in dollars, such as a
company's capex or a lab's revenue; none of them is your money.) Every chart
draws numbers the code computed (P2, with the two exceptions above), and
every heat map is a real table, so its numbers are there for screen readers.
The design rules are in [DASHBOARD.md](DASHBOARD.md).

| Page | What it shows |
|---|---|
| Overview | Today's and the past year's move of today's mix next to the world index, the biggest tilt, the brief's summary with the themes that matter today and how busy each is, the top 3 events, the next things to watch, the biggest themes, and the latest scan. |
| Holdings | Each holding with its weight, its moves (1D, 1M, YTD, 1Y) and a 90-day line, sortable. Opening one shows its line against the world index over a year, the largest companies and countries inside it, the brief's note and events on it, and the state of each theme it sits in. |
| News & world | Section 3.1: the brief, a card for each theme that matters, the ripple map, things to watch on a 90-day timeline, the full events, and two heat maps (each theme proxy against the world index by week, and events per theme by day). Themes that do not matter to the user sit in a short table. |
| Exposure | Section 3.3, plus a holdings-by-themes table: the share of the portfolio each holding puts into each theme. |
| Scenarios | Section 3.5. |
| Views | Section 3.2. |
| Record | Section 3.4. |
| The bet | Section 3.6: "Will the bet pay off?" |

### 3.1 Morning brief (the News & world page)

Up to 10 events from the last 24 hours, picked because they touch the user's
themes, holdings or views. Each event answers the same four questions:

1. **What happened?** One sentence, with a source link and the source headline next to it.
2. **Where does money move?** Who pays, and who gets paid (governments, companies, consumers). This is the most important question, because money flows are what reach share prices.
3. **What does it touch?** Themes, regions, and the user's holdings (by ticker and portfolio %).
4. **Which views?** For each view it touches, the event counts as *for*, *against*, or *unclear*, with one line on why.

A quiet day is a valid result. If no view was touched, the brief says so
plainly and does not invent drama.

Around the events, the brief gives:

- **The themes that matter.** A line on the state of every theme that is 2%
  or more of the portfolio or that an open view names (the code checks this),
  plus any other theme the AI judges today's news made relevant. Each line
  says where the theme stands and why it matters to this portfolio, citing
  news ids; a quiet theme says "No news in today's feeds." The page shows
  only these themes in full, busiest first, and adds the week's blind spots.
- **Notes on holdings**, where an item is about that company or fund directly.
- **Ripples** (up to 8): an event in one theme that reaches another, such as
  energy prices into data-centre costs. The AI is asked to look hardest for
  ripples into AI build-out. The page draws them as a small network.
- **Things to watch** (up to 8): meetings, votes, deadlines and releases the
  news mentions, with a date only when an item gives one. The page merges
  them with the user's own view deadlines and decision reviews.

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

### 3.5 Scenarios: conflict scans (`/scan`)

The user names any conflict ("China blockade of Taiwan"). The page shows
where it would reach the money, next to the world index. It is a map, not a
forecast: it says nothing about whether the conflict happens or what prices do.

1. **Code** (`whatstocks scan prepare "<conflict>"`): one news search for the
   conflict, in the user's words, over the past week. It writes the scan
   payload: the themes and countries with the user's and the world index's
   share, the holdings as percentages with what is inside them, and the
   headlines (no URLs). The payload check of section 8, step 6 applies.
2. **AI** (`out/scans/<slug>.json`): a summary; 1 to 12 **channels**, each a
   theme or a country with `effect` (hurt, help or mixed), `strength` (low,
   medium or high: how hard it would hit revenue or costs, not its odds) and
   a one-line `why`; up to 4 **analogs**, past windows that looked like it
   (on or after 2019-12-01, at most 400 days, ended before today); up to 6
   things to watch. Claims cite news ids. The brief's link and advice checks
   apply.
3. **Code** (`whatstocks scan finish <slug>`), from the look-through rows:
   - each channel's share of the portfolio and of the world index (a theme
     counts its core members in full and partial members half, a country
     counts the companies based there);
   - the share reached by anything the conflict would hurt, help or mix, with
     **each company counted once**, at the strongest channel that reaches it,
     and that share weighted by strength (low a third, medium two thirds,
     high in full);
   - per holding, the share of it that each effect reaches;
   - today's holdings, the world index and each theme channel's proxy ETF,
     replayed over the analog windows.

The page shows these as KPI tiles, a bubble map, hurt-and-help bars per
holding, the analog replays, and the channel table. The bubble map has one
cluster each for "would hurt", "mixed" and "would help", and one bubble per
channel. A bubble's area is the user's share in that channel, and a dashed
ring is the world index's share on the same scale. Colour shows the effect
and fill strength shows the channel's strength. The code places every label
inside its bubble, beside it where it overlaps nothing, or else in a list
under the cluster, so no label lies on top of another.

### 3.6 Will the bet pay off? (the bet page, `/bet`)

AI infrastructure is built like a utility. The cash goes out now, as capex,
and comes back only as the world adopts AI and pays for it out of IT and
labour budgets. The page asks one question: is adoption on pace to earn back
the build-out before the GPUs bought in 2024 to 2026 are written off? It
fits two models on one chart.

- **Model A, the money invested.** What end users must pay for AI each year
  for the build-out to pay for itself, worked out like a utility's revenue
  requirement: depreciation, return on capital and running costs, divided by
  the compute share (the part of an end-user AI dollar that reaches the
  infrastructure). And the valuation target: what today's market values
  assume end users will pay at the deadline.
- **Model B, adoption.** What end users pay for AI, net, in five tiers by
  quality (direct, bundled price rises, ad lift, VC-funded, investor-funded
  compute), with overlapping dollars removed. After the last actual quarter it
  is projected as usage × price per unit.

The **readouts** are coverage now (actual ÷ need, over the last four
quarters), payback by the deadline (each added up from 2023 to the deadline),
and actual against the valuation target. The **deadline** is the depreciation
clock: the end of 2025 plus the GPU life.

**Controls.** Five sliders (GPU life, cost of capital, price deflation, value
capture, and the labour share of the budget pool) and a switch for every
piece of both models. Python computes every slider step for every piece,
quarterly from 2023Q1 to 2033Q4 with low and high values, so the page only
picks, adds and divides (exception (b) to P2). A units toggle shows the curves
in dollars, in paying seats or in work hours.

**Signals.** Four crash paths (capex retrenchment, equity drawdown, credit
event, price collapse) and adoption pace, each made of indicators with an
amber and a red level and the reason for each (`sources/bet/signals.yaml`).
The regime reads **Breaking** when a crash path is red, **Straining** when a
crash path is amber or adoption pace is red, and **Absorbing** otherwise.
Python works them out at your default settings, so they stay put while you
explore. Every state shows a word and a shape (● clear, ◆ amber, ▲ red,
○ no data). The page shows no probability of a crash and suggests none (P1,
P6).

**Your reach.** Each crash path has channels, as a scan does (section 3.5),
and the same code works out the share of your portfolio and of the world
index each path reaches (P5), with past sell-offs replayed on today's mix.

**Also on the page:** the adoption funnel (who uses AI, how much, who pays,
and the leakage between them); how much of each curve rests on filed or
fetched figures, company statements, the press, or estimates; the four
pillars (capex against revenue, unit economics, net expansion and budgets,
high-frequency proxies); open-weight model releases with their market and
adoption effects; historical analogs; every threshold with its reason; every
series with its newest figure and whether a newer one is due; and a cash
clock of modelled capex out and demand in since 1 January (exception (a)).

**The ledger.** Every figure the code cannot fetch, each with a source link,
the date it was read, a grade (filed, company, press or estimate) and a
low–high range where sources disagree. The shipped ledger is in
`sources/bet/` (`series.yaml`, `model.yaml`, `signals.yaml`, `events.yaml`).
Your `my/bet.yaml` is merged on top of it: your figure replaces the shipped
one with the same series, company and period, `remove:` drops a shipped
figure, and you can set your own slider defaults, your own amber and red
levels (with your reason), a path's channels, and `view_links` (which of your
views a path's changes count for or against). `whatstocks check` checks both.

**What the code fetches**, with each `prepare`: FRED's adoption survey and
credit spreads (no key) at most once a day, and shares outstanding from Yahoo
at most once a week. SEC EDGAR (capex, operating cash flow, depreciation,
backlog, Nvidia's revenue) at most once a week, and only once `settings.yaml`
has a `sec_contact:`. A fetched figure takes the place of the shipped one for
the same period (a figure of yours stays), and `whatstocks check` lists any
more than 1% from the figure it meets.

**In the morning.** When `finish` finds the regime or a path in a new state,
it appends one line per change to `evidence.jsonl` (`"source": "signal"`),
counted for or against the views linked in `view_links`. The payload's `bet`
block holds states and fractions only: no dollar figures, no links and no
money keys (P4). The brief's `bet` line is required on a day something
changed (section 8, step 8).

**`/bet`**, on request only:

1. `whatstocks bet due` lists the series with a newer figure due and the open
   gaps, the ones that move the curves first.
2. The AI researches from the top of the list, and shows each proposed figure
   with its source link, grade, date and the figure it replaces.
3. Only on your yes, it copies `my/bet.yaml` to `my/backups/<date>/` and
   writes the figures.
4. `whatstocks check`, then `whatstocks bet`, which works the bet out again
   from the cache (nothing is fetched), redraws the page and says what moved.

`/bet` never edits `sources/bet/`, never sets a probability, and never raises
a grade without a better source.

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
  sources/bet/             the bet page's shipped ledger: series, model, signals, events (section 3.6)
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
    bet.yaml               optional: the user's figures, levels and defaults for the bet page
    cache/                 prices, FX, fund holdings, news, and bet/ (FRED, EDGAR and Yahoo figures)
    out/                   exposure.json, lookthrough.json, performance.json, news.json, payload.json,
                           brief.json, briefs/<date>.json, evidence.jsonl, scans/, bet.json,
                           bet_state.json, dashboard.html
  .claude/skills/          setup, morning, scan, bet (decide and resolve are covered inside setup for now)
  src/whatstocks/          code: files, market, funds, exposure, performance, news, brief, record, scan,
                           dashboard (gathers the page's data), geometry (bubble and ripple layout),
                           render (the view model, filled into assets/dashboard.html), morning, cli,
                           and bet/ (ledger, fetch, models, signals, markets, reach, panels)
  web/                     the page: React, built by contributors with Node (DASHBOARD.md)
  tests/                   offline tests with synthetic prices, holdings files and news
```

Commands (the skills run these):

| Command | What it does |
|---|---|
| `uv run whatstocks check` | Check the files in `my/` and list stocks that are in no theme. |
| `uv run whatstocks prepare` | Steps 1 to 6 of section 8: data in, `payload.json` out. `--offline` uses the cache only. |
| `uv run whatstocks finish` | Steps 8 to 11: check `brief.json`, update the evidence log, build the page. `--no-brief` skips the brief. |
| `uv run whatstocks scan prepare "<conflict>"` | Section 3.5, step 1: search the news, write the scan payload. `--offline` reuses the last search. |
| `uv run whatstocks scan finish <slug>` | Section 3.5, step 3: check the AI's scan file, compute it, rebuild the page. |
| `uv run whatstocks bet due` | Section 3.6: the bet ledger's series with a newer figure due, and its open gaps, ranked. |
| `uv run whatstocks bet` | Section 3.6: work the bet out again from the ledger and `my/bet.yaml` with cached prices and figures (nothing fetched), rebuild the page, and say what moved. |

Every command takes `--dir <folder>` (default `my`), so `--dir demo` runs the demo user.

## 6. File formats

There are four contract files and one small settings file. All dates use
`YYYY-MM-DD`, and all files are UTF-8. The `demo/` folder holds a valid
example of each one.

### 6.0 `settings.yaml`

```yaml
home_currency: EUR        # ISO 4217 code. All values and returns are converted to this.
benchmark: IUSQ.DE        # The world fund used for every comparison (iShares MSCI ACWI).
sec_contact: Jane Doe jane@example.com   # Optional. The SEC asks every EDGAR client for a name and email;
                                         # the bet page fetches nothing from EDGAR without it (section 3.6).
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
| 2 | code | Refresh prices and FX into the cache, and the bet page's fetched figures (section 3.6). If a source fails, keep the last cached values. | Show a "prices from <date>" banner when any price is older than the last trading day. Stop only when a holding has no cached price at all. |
| 3 | code | Refresh fund holdings files when they are older than 30 days. | Flag files older than 90 days. |
| 4 | code | Compute exposure (section 7) into `exposure.json`, and the bet page (section 3.6) into `bet.json`. | Theme shares within [0, 1], and the benchmark computed too. |
| 5 | code | Fetch news into `news.json`: the publisher feeds, plus one search per theme built from its `news_query`. Each item gets a stable id (a hash of its URL). | Deduplicate by URL and title. Only theme queries go to the search engine, never holdings or views. |
| 6 | code | Build the AI payload: news items (id, title, source, time, no URL), tickers with portfolio % and the countries and themes inside each, the themes with your share and the world's (marked `must_cover` at 2% or more, or when an open view names them), and open views (statement, current probability, themes), and the bet page's states and fractions (section 3.6). Also write `performance.json` (price moves) and `lookthrough.json` (the rows a scan needs). | **Payload check**: no money fields, and none of the user's amounts or quantities written anywhere outside public text such as headlines. |
| 7 | AI | Write `brief.json`: a summary; events with `news_ids` and the four answers (`what`, `money`, `touches`, and `views` with `for`, `against` or `unclear` and a `why`); a line per theme that matters; notes on holdings; ripples between themes; things to watch (section 3.1). The format is in `.claude/skills/morning/SKILL.md`. | Checked in step 8. Blind spots are computed in code, not by the AI. |
| 8 | code | Validate the brief. | Every event, holding note, ripple and thing to watch cites at least one `news_id` from today's payload, and only known themes, holdings and open views. Every `must_cover` theme has a line. A `bet` line is there when the payload says a bet path or the regime changed, and cites only today's news ids. At most 10 events, 8 ripples and 8 things to watch; no date to watch in the past. Any URL is an error. Advice-like wording ("you should", "consider buying", price targets and others) anywhere stops the run; the `/morning` skill rewrites once, and only the user can let it through with `--allow-advice`, which adds a warning banner. The checked brief is kept in `briefs/<date>.json`. |
| 9 | code | Append today's events to `evidence.jsonl`, and a line for each bet path, or the regime, in a new state since the last logged one (section 3.6). | Earlier days are never changed. A re-run on the same day replaces that day's entries. |
| 10 | code | Render `dashboard.html` (section 3) from the files in `out/`, including any scans: the view model goes into the built template as JSON, and into `dashboard.json`. | The page works offline and its Content-Security-Policy blocks every request. The JSON is escaped so no text can close its script tag, the page writes every text as text, and only http(s) links become links. A test checks the template was built from the current `web/` sources. |
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
| Macro, for resolving views | FRED, EIA, national statistics offices | Only used when the user resolves a view. |
| The bet page's adoption survey and credit spreads | FRED's keyless CSV download (`fredgraph.csv`) | No key. Fetched at most once a day (section 3.6). |
| US company facts, for the bet page | SEC EDGAR's company-concept API | Free, but the SEC asks for a name and email in the User-Agent: off until `sec_contact:` is set. |
| Every other bet figure | The ledger in `sources/bet/`: filings, company statements, the press, estimates | Each with a source link and the date it was read ([DATA_SOURCES.md](DATA_SOURCES.md)). |

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

Settled since: Python 3.11 or later; one news search per theme, built from
its `news_query` (section 8, step 5); the dashboard (section 3), built in
v0.2 with conflict scans (section 3.5); and its rebuild in React in v0.3,
with Vite rather than Next.js and no backend ([DASHBOARD.md](DASHBOARD.md),
section 1).
