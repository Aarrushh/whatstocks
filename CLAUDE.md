# whatstocks: instructions for coding agents

You are helping one person make whatstocks their own. They may not be a programmer. They will ask in plain words
("add Rheinmetall to defence", "I care about Japan, add a theme", "put my views on the first page", "make it
green"). Your job is to make the change they want, in the safest place it can live, without breaking their data
or the rules below.

The product rules are in [docs/SPEC.md](docs/SPEC.md). The page's design rules are in
[web/CLAUDE.md](web/CLAUDE.md). The demo in `demo/` is a fictional user, which is safe to break and rebuild.

## 1. What is theirs and what is shipped

| Path | Whose | Notes |
|---|---|---|
| `my/` | The user's | Holdings, views, decisions, settings, theme additions, cache, output. Git ignores it. It exists on this computer only, so a lost file is gone for good. |
| `themes/themes.yaml`, `sources/*.yaml` | Shipped | The starter theme map, the funds that can be looked through, the news feeds. |
| `src/whatstocks/` | Shipped | Python: every number is computed here. |
| `web/` | Shipped | The React page, built into `src/whatstocks/assets/dashboard.html`. |
| `.claude/skills/` | Shipped | `/setup`, `/morning`, `/scan`. Agents without slash commands follow each `SKILL.md` file as written. |
| `demo/`, `tests/` | Shipped | A fictional user and the offline tests. |

## 2. Where each change goes: use the lowest level that does the job

| Level | The user asks for | Where | Risk |
|---|---|---|---|
| 1. Their data | New holdings, a view, a decision, another currency or benchmark | `my/*.yaml`, `my/holdings.csv`, through `/setup` (its "Later" section) | Low. Run `uv run whatstocks check` after. |
| 2. Their themes | Add or remove a company in a theme, rename a theme, a new theme, a different news query | `my/themes.yaml`. It is merged on top of the shipped map: it can add themes, add members, `remove:` members and replace `label`, `description`, `proxy`, `notes`, `news_query` (SPEC 6.4). | Low. Never edit `themes/themes.yaml` for one person's taste. |
| 3. Shipped settings | Another news feed, a fund to look through | `sources/feeds.yaml`, `sources/funds.yaml` | Medium. Do it on a branch. |
| 4. The page | Reorder or hide cards, a new card or chart, colours, wording | `web/`, then `npm run build` | Medium. Do it on a branch, follow `web/CLAUDE.md`, check it in a browser. |
| 5. The logic | A new figure, a new page, a new command, a change to a calculation | `src/whatstocks/`, `tests/`, maybe `web/` | Higher. Do it on a branch, add a test, run everything. |

When a request could be met at two levels, take the lower one, and say why. A new figure on the page is level 5
and then level 4: Python computes it and the page only shows it (the page never makes up a number).

## 3. Guardrails: never break these

### Their data

- **Back up before you touch `my/`.** Copy the files you will change into `my/backups/<YYYY-MM-DD>/` first, and
  tell the user where the copy is. `my/backups/` sits inside `my/`, so git ignores it too.
- **Show before you write.** Show the user each change to a file in `my/` and wait for a yes. Never delete a file in
  `my/`, and never empty `my/cache/` or `my/out/` without asking.
- **The record is append-only.** In `views.yaml`, add a new forecast with today's date; never edit or delete an
  earlier one. Views are never deleted: one that cannot be resolved gets `result: void`. In `decisions.yaml`, add
  entries and never rewrite old ones. The score only means something if the history is honest.
- **The user sets every probability.** Never suggest a number, a range or a base rate, even if asked.

### Git

- `my/` must never be committed. Before any commit, run `git status` and check that nothing under `my/` (or any
  holdings, amounts or account names) is staged. Never use `git add -A` or `git add .` without that check, and never
  add `-f` to force an ignored file in.
- **Never run `git clean -x` or `git clean -X`.** They delete ignored files, and that means the whole of `my/`.
  Plain `git clean -n` (a dry run) is the most you need.
- Never `git reset --hard`, `git checkout -- .`, `git restore .`, `git push --force` or delete a branch unless the
  user asks for that exact thing after you have told them what it throws away.
- **Work on a branch for levels 3 to 5.** `git switch -c custom/<short-name>` before the first edit, so `main` stays as
  the way back. Commit or push only when the user says so.

### The product rules (SPEC section 2)

These hold whatever the user asks. If a request would break one, say so, explain why it exists, and offer the
nearest thing that keeps it.

- **No advice.** whatstocks never tells anyone to buy or sell, and gives no price targets. Do not pass
  `--allow-advice` unless the user asks for it by name, and never remove the advice check.
- **No amounts to the AI.** The AI sees tickers and percentages only. Never weaken `brief.payload_leaks` or add
  quantities, values or account names to `payload.json` or a scan payload.
- **Read-only.** Never connect to a broker, store a broker login, or add anything that places an order.
- **The page fetches nothing.** Keep the Content-Security-Policy (`default-src 'none'`). No CDN, web font, remote
  image, analytics or API call in `web/`. New data reaches the page through Python and the view model.
- **Every fact has a source.** The brief links to a source the code fetched itself. Do not let the AI state facts
  without one.
- **Code computes, the AI writes words.** Numbers come from Python, never from the model or the page.
- **News queries stay about the theme.** A `news_query` is sent to Google News as it is: never put a holding, a
  view or an amount in it.

## 4. How to check your work

Run these before you say a change is done, and tell the user what passed and what did not:

```text
uv run whatstocks check                         # after any change in my/
uv run pytest                                   # after any change outside my/
cd web && npm run build && npm test             # after any change in web/ (commit the rebuilt dashboard.html)
uv run whatstocks --dir demo prepare            # then: uv run whatstocks --dir demo finish --no-brief
```

For a page change, open `demo/out/dashboard.html` (or `my/out/dashboard.html`) in a browser and look at it, in
dark and light, wide and phone-width (`web/CLAUDE.md`). A test that fails because the page and its sources are
out of step means you forgot `npm run build`.

If a test fails, fix the cause. Do not delete, skip or loosen a test to make it pass unless the user agrees that
the rule it guards should change.

## 5. How to work with the user

1. **Say back what you understood**, and which level from section 2 it is, in one or two plain sentences.
2. **Say what you will change** (which files) and how they can undo it.
3. **Make one change at a time.** Show it, run the checks, then move to the next.
4. **End by telling them how to see it** (`/morning`, or open the page) **and how to undo it**:
   - their data: copy the file back from `my/backups/<date>/`;
   - a branch: `git switch main` (the branch stays until they delete it);
   - one file on a branch, not yet committed: `git restore <file>`.
5. If they ask for something you think is a bad idea for them (not a rule break, just a worse design), say so once,
   briefly, then do what they want.
