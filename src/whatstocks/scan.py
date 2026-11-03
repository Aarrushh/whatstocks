"""Conflict scans (/scan): where would a conflict reach this portfolio, next to the world index?

prepare  searches the past week's news for the conflict and writes the AI payload: themes, regions and holdings
         as percentages, plus headlines. No amounts, no URLs (P3, P4).
the AI   writes <slug>.json: the channels (themes and regions) the conflict would hurt or help and how strongly,
         and past windows that looked like it.
finish   checks that file and computes every number in code (P2): how much of the portfolio and of the world
         index each channel reaches, which holdings it reaches, and how both did in the past windows.

A scan is a map of where a conflict would reach the money, not a forecast of what will happen."""
from __future__ import annotations

import datetime as dt
import re
from collections import defaultdict
from pathlib import Path

import pandas as pd

from . import brief as briefs
from . import dashboard
from .exposure import replay, window_return
from .files import Book, Problems, ThemeMap, read_json, write_json
from .market import START, Fx, Prices
from .news import search_news
from .paths import UserDir

STRENGTH = {"low": 1 / 3, "medium": 2 / 3, "high": 1.0}
EFFECTS = ("hurt", "help", "mixed")
KINDS = ("theme", "region")
MAX_CHANNELS, MAX_ANALOGS, MAX_WATCH = 12, 4, 6
MAX_ANALOG_DAYS = 400
REGIONS_SHOWN = 30
NOT_REGIONS = {"Cash", "Cash and other", "Not looked through", "Unknown"}
SLUG = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")


def slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:60].strip("-") or "scan"


def _paths(user: UserDir, slug: str) -> dict[str, Path]:
    folder = user.out / "scans"
    return {"scan": folder / f"{slug}.json", **{k: folder / f"{slug}.{k}.json" for k in ("news", "payload", "result")}}


def _needs(user: UserDir, *names: str) -> None:
    missing = [n for n in names if not (user.out / n).exists()]
    if missing:
        raise Problems([f"{n} is missing: run 'whatstocks prepare' first" for n in missing])


def prepare(user: UserDir, conflict: str, offline: bool = False, today: dt.date | None = None) -> dict:
    from .morning import load  # here, not at the top: morning imports dashboard, which this module also uses

    today = today or dt.date.today()
    conflict = " ".join(conflict.split())
    if len(conflict) < 3:
        raise Problems(['Name the conflict in a few words, for example: whatstocks scan prepare "China blockade of Taiwan"'])
    _needs(user, "exposure.json", "payload.json", "lookthrough.json")
    book, _ = load(user)
    exposure, morning = read_json(user.out / "exposure.json"), read_json(user.out / "payload.json")
    slug = slugify(conflict)
    paths = _paths(user, slug)
    if offline:
        news = read_json(paths["news"]) if paths["news"].exists() else {"items": [], "notes": ["Offline: no news searched."]}
    else:
        now = dt.datetime.now(dt.timezone.utc)
        items, notes = search_news(conflict, now)
        news = {"query": conflict, "fetched": now.isoformat(timespec="minutes"), "items": items, "notes": notes}
        write_json(paths["news"], news)

    you, world = exposure["countries"]["you"], exposure["countries"]["world"]
    regions = sorted((c for c in set(you) | set(world) if c not in NOT_REGIONS),
                     key=lambda c: -max(you.get(c, 0.0), world.get(c, 0.0)))[:REGIONS_SHOWN]
    payload = {
        "conflict": conflict,
        "slug": slug,
        "date": today.isoformat(),
        "themes": [{k: t[k] for k in ("id", "label", "description", "your_share_pct", "world_share_pct")}
                   for t in morning["themes"]],
        "regions": [{"id": c, "your_share_pct": round(100 * you.get(c, 0.0), 1),
                     "world_share_pct": round(100 * world.get(c, 0.0), 1)} for c in regions],
        "holdings": morning["holdings"],
        "news": [{"id": n["id"], "title": n["title"], "source": n["source"], "published": n["published"]}
                 for n in news["items"]],
    }
    amounts = [h.value for h in book.holdings if h.value] + [h.quantity for h in book.holdings if h.quantity]
    leaks = briefs.payload_leaks(payload, amounts)
    if leaks:
        raise Problems([f"AI payload check failed: {leak}" for leak in leaks])
    write_json(paths["payload"], payload)
    notes = list(news.get("notes", []))
    if exposure.get("date") != today.isoformat():
        notes.append(f"Exposure numbers are from {exposure.get('date')}: run 'whatstocks prepare' for today's.")
    return {"slug": slug, "payload": payload, "path": paths["payload"], "notes": notes}


def validate(scan, payload: dict) -> tuple[list[str], list[str]]:
    """(errors, advice) for the AI's scan file, like validate_brief for the morning brief."""
    if not isinstance(scan, dict):
        return ["the scan must be a JSON object"], []
    errors = []
    news = {n["id"] for n in payload["news"]}
    themes = {t["id"] for t in payload["themes"]}
    regions = {r["id"] for r in payload["regions"]}
    if scan.get("date") != payload["date"]:
        errors.append(f"date must be {payload['date']}")
    if not str(scan.get("summary") or "").strip():
        errors.append("'summary' is missing")

    def cites(where: str, item: dict) -> None:
        cited = item.get("news_ids") or []
        if not isinstance(cited, list):
            errors.append(f"{where}: news_ids must be a list")
            return
        if news and not cited:
            errors.append(f"{where}: cites no news_ids")
        errors.extend(f"{where}: news id '{n}' was not in the scan payload" for n in cited if n not in news)

    cites("summary", scan)
    channels = scan.get("channels")
    if not isinstance(channels, list) or not channels:
        errors.append("channels: list at least one theme or region the conflict would reach")
        channels = []
    if len(channels) > MAX_CHANNELS:
        errors.append(f"channels: at most {MAX_CHANNELS}, keep the ones that matter most")
    seen = set()
    for i, c in enumerate(channels, start=1):
        where = f"channel {i}"
        if not isinstance(c, dict):
            errors.append(f"{where}: must be an object")
            continue
        kind, cid = c.get("kind"), c.get("id")
        if kind not in KINDS:
            errors.append(f"{where}: kind must be theme or region")
        elif kind == "theme" and cid not in themes:
            errors.append(f"{where}: unknown theme '{cid}'")
        elif kind == "region" and cid not in regions:
            errors.append(f"{where}: unknown region '{cid}': use a region id from the payload")
        if (kind, cid) in seen:
            errors.append(f"{where}: '{cid}' appears twice")
        seen.add((kind, cid))
        if c.get("effect") not in EFFECTS:
            errors.append(f"{where}: effect must be hurt, help or mixed")
        if c.get("strength") not in STRENGTH:
            errors.append(f"{where}: strength must be low, medium or high")
        if not str(c.get("why") or "").strip():
            errors.append(f"{where}: 'why' is missing")

    for key, limit in (("analogs", MAX_ANALOGS), ("watch", MAX_WATCH)):
        if not isinstance(scan.get(key) or [], list):
            errors.append(f"{key} must be a list")
        elif len(scan.get(key) or []) > limit:
            errors.append(f"{key}: at most {limit}")
    for i, a in enumerate(scan.get("analogs") or [], start=1):
        where = f"analog {i}"
        if not isinstance(a, dict):
            errors.append(f"{where}: must be an object")
            continue
        errors.extend(f"{where}: '{k}' is missing" for k in ("name", "why") if not str(a.get(k) or "").strip())
        try:
            start, end = dt.date.fromisoformat(str(a.get("start"))), dt.date.fromisoformat(str(a.get("end")))
        except ValueError:
            errors.append(f"{where}: start and end must be dates like 2022-08-01")
            continue
        if start >= end:
            errors.append(f"{where}: start must be before end")
        elif (end - start).days > MAX_ANALOG_DAYS:
            errors.append(f"{where}: at most {MAX_ANALOG_DAYS} days long")
        if start.isoformat() < START:
            errors.append(f"{where}: prices start on {START}, so pick a window after that")
        if end.isoformat() >= payload["date"]:
            errors.append(f"{where}: must end before today")
    for i, w in enumerate(scan.get("watch") or [], start=1):
        if not isinstance(w, dict) or not str(w.get("what") or "").strip():
            errors.append(f"watch {i}: 'what' is missing")
        else:
            cites(f"watch {i}", w)
    links, advice = briefs.text_checks(scan)
    return errors + links, advice


def _membership(member: str | None, country: str, channel: dict, themes: ThemeMap) -> float:
    """How much of one look-through row a channel reaches: 1 for its region, the theme weight for its theme."""
    if channel["kind"] == "region":
        return 1.0 if country == channel["id"] else 0.0
    return themes.weights(member).get(channel["id"], 0.0) if member else 0.0


def reach(member: str | None, country: str, channels: list[dict], themes: ThemeMap) -> dict[str, float]:
    """The strongest hurt, help and mixed channel reaching one row (strength x membership, 0 to 1).

    Strongest, not summed: a Taiwanese chipmaker in both the 'Taiwan' and 'AI build-out' channels counts once."""
    out = dict.fromkeys(EFFECTS, 0.0)
    for c in channels:
        m = _membership(member, country, c, themes)
        if m:
            out[c["effect"]] = max(out[c["effect"]], STRENGTH[c["strength"]] * m)
    return out


def _tally(rows) -> dict[str, float]:
    """rows: (share, reach) pairs. Share reached by each effect, and that share weighted by strength."""
    t = {f"{e}_{k}": 0.0 for e in EFFECTS for k in ("share", "score")}
    for share, r in rows:
        for e in EFFECTS:
            if r[e]:
                t[f"{e}_share"] += share
                t[f"{e}_score"] += share * r[e]
    return t


def compute(scan: dict, payload: dict, look: dict, book: Book, weights: dict[str, float],
            series: dict[str, pd.Series]) -> dict:
    themes, channels = book.themes, scan["channels"]
    reached = {
        side: [(origin, share, reach(member, country, channels, themes), member, country)
               for origin, share, member, country in look[side]]
        for side in ("you", "world")
    }
    out_channels = []
    for c in channels:
        theme = themes.themes.get(c["id"]) if c["kind"] == "theme" else None
        shares = {side: sum(share * _membership(member, country, c, themes) for _, share, _, member, country in rows)
                  for side, rows in reached.items()}
        out_channels.append({**c, "label": theme.label if theme else c["id"], "proxy": theme.proxy if theme else None,
                             "you": shares["you"], "world": shares["world"]})

    by_holding = defaultdict(list)
    for origin, share, r, _, _ in reached["you"]:
        by_holding[origin].append((share, r))
    names = {h["symbol"]: h["name"] for h in payload["holdings"]}
    weights = {h["symbol"]: h["weight_pct"] / 100 for h in payload["holdings"]}
    holdings = []
    for symbol, rows in by_holding.items():
        # A fund's holdings file can miss a sliver of it (cash, futures), so its rows can sum to a little under its
        # weight: show the real weight, and measure each share against the part that could be looked through.
        covered = sum(share for share, _ in rows)
        tally = _tally(rows)
        holdings.append({"symbol": symbol, "name": names.get(symbol, symbol), "weight": weights.get(symbol, covered),
                         **{k: v / covered if covered else 0.0 for k, v in tally.items()}})
    holdings.sort(key=lambda h: -h["weight"])

    empty = pd.Series(dtype=float)
    cash = {h.symbol for h in book.holdings if h.kind == "cash"}
    analogs = scan.get("analogs") or []
    replays = replay(weights, series, cash, series.get(book.settings.benchmark, empty),
                     [(a["name"], a["start"], a["end"]) for a in analogs])
    return {
        "channels": out_channels,
        "totals": {side: _tally([(share, r) for _, share, r, _, _ in rows]) for side, rows in reached.items()},
        "holdings": holdings,
        "analogs": [
            {**a, "you": r["you"], "world": r["world"], "coverage": r["coverage"],
             "proxies": {c["id"]: window_return(series.get(c["proxy"], empty), a["start"], a["end"])
                         for c in out_channels if c["proxy"]}}
            for a, r in zip(analogs, replays)
        ],
        "strength": STRENGTH,
    }


def finish(user: UserDir, slug: str, allow_advice: bool = False, today: dt.date | None = None) -> dict:
    from .morning import load

    today = today or dt.date.today()
    if not SLUG.fullmatch(slug or ""):
        raise Problems([f"'{slug}' is not a scan name: use the name 'scan prepare' printed"])
    paths = _paths(user, slug)
    if not paths["payload"].exists():
        raise Problems([f"No scan '{slug}': run whatstocks scan prepare \"<conflict>\" first"])
    if not paths["scan"].exists():
        raise Problems([f"{paths['scan'].name} is missing: write it from {paths['payload'].name} "
                        "(see .claude/skills/scan/SKILL.md)"])
    payload, scan = read_json(paths["payload"]), read_json(paths["scan"])
    if payload["date"] != today.isoformat():
        raise Problems([f"{paths['payload'].name} is from {payload['date']}: run 'scan prepare' again today"])
    errors, advice = validate(scan, payload)
    if errors or (advice and not allow_advice):
        raise Problems([f"{paths['scan'].name}: {m}" for m in errors + advice])

    _needs(user, "exposure.json", "lookthrough.json")
    book, _ = load(user)
    exposure, look = read_json(user.out / "exposure.json"), read_json(user.out / "lookthrough.json")
    home = book.settings.home_currency
    prices, fx = Prices(user.cache), Fx(user.cache)
    symbols = set(exposure["weights"]) | {book.settings.benchmark} | {t.proxy for t in book.themes.themes.values()}
    series = {}
    for s in symbols:
        currency = prices.currency(s)
        if currency and fx.has(currency) and fx.has(home):
            series[s] = fx.convert(prices.series(s), currency, home)

    news = read_json(paths["news"]) if paths["news"].exists() else {"items": []}
    cited = set(scan.get("news_ids") or []) | {n for w in scan.get("watch") or [] for n in w.get("news_ids") or []}
    result = compute(scan, payload, look, book, exposure["weights"], series)
    result.update(
        slug=slug, conflict=payload["conflict"], date=payload["date"], home=home, summary=scan["summary"],
        news_ids=scan.get("news_ids") or [], watch=scan.get("watch") or [], advice=bool(advice),
        news=[n for n in news["items"] if n["id"] in cited], exposure_date=exposure.get("date"),
    )
    write_json(paths["result"], result)
    page = dashboard.write(user, book, today, dashboard.todays_brief(user, today), [])
    return {"result": result, "page": page}
