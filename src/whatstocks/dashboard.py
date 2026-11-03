"""Everything the page shows, gathered from the files in out/ (SPEC section 8, step 9).

morning.finish calls write() after it checks the brief; scan.finish calls it again so a new scan shows up.
Nothing here asks the AI anything: it only reads what the code and the checked brief already wrote."""
from __future__ import annotations

import datetime as dt
import json
from collections import Counter
from pathlib import Path

import pandas as pd

from . import record, render
from .brief import MUST_COVER_SHARE, text_checks
from .files import Book, Problems, read_json
from .market import Fx, Prices
from .paths import UserDir

NEWS_DAYS = 14  # the events-per-theme grid
WATCH_DAYS = 120  # view deadlines this close count as things to watch
REVIEW_SOON = 30  # so do decision reviews


def load_evidence(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text("utf-8").splitlines() if line.strip()]


def todays_brief(user: UserDir, today: dt.date) -> dict | None:
    """The brief finish checked and kept for today, if there is one."""
    path = user.out / "briefs" / f"{today.isoformat()}.json"
    return read_json(path) if path.exists() else None


def blind_spots(exposure: dict, evidence: list[dict], today: dt.date) -> list[dict]:
    """Themes busy in the news this week where the user has nothing, or under a quarter of the world's share."""
    week = [e for e in evidence if (today - dt.date.fromisoformat(e["date"])).days < 7]
    counts = Counter(tid for e in week for tid in e["themes"])
    out = []
    for tid, n in counts.items():
        row = exposure["themes"].get(tid)
        if row is None or n < record.BUSY_EVENTS:
            continue
        if row["you"] == 0 or row["you"] < row["world"] / 4:
            out.append({
                "id": tid, "label": row["label"], "events": n, "you": row["you"], "world": row["world"],
                "recent": [e["what"] for e in reversed(week) if tid in e["themes"]][:3],
            })
    return sorted(out, key=lambda r: -r["events"])


def news_heat(evidence: list[dict], theme_ids: list[str], today: dt.date, days: int = NEWS_DAYS) -> dict:
    """Events per theme per day, from the evidence log, for the last `days` days."""
    dates = [(today - dt.timedelta(days=i)).isoformat() for i in range(days - 1, -1, -1)]
    counts = {tid: Counter() for tid in theme_ids}
    for e in evidence:
        for tid in e.get("themes", []):
            if tid in counts:
                counts[tid][e["date"]] += 1
    return {"dates": dates, "rows": {tid: [counts[tid][d] for d in dates] for tid in theme_ids}}


def record_watch(book: Book, today: dt.date) -> list[dict]:
    """Dates from the user's own record: view deadlines and decision reviews coming up."""
    out = []
    for v in book.views:
        if not v.outcome and (v.resolves_by - today).days <= WATCH_DAYS:
            out.append({"date": v.resolves_by.isoformat(), "what": f"Your view {v.id} resolves", "kind": "view"})
    for d in book.decisions:
        if 0 <= (d.review_on - today).days <= REVIEW_SOON:
            out.append({"date": d.review_on.isoformat(), "what": f"Review your {d.action} of {d.symbol} ({d.date.isoformat()})",
                        "kind": "review"})
    return sorted(out, key=lambda w: w["date"])


def scans(out: Path) -> list[dict]:
    folder = out / "scans"
    found = [(read_json(p), p.stat().st_mtime) for p in folder.glob("*.result.json")] if folder.exists() else []
    # Newest first: by scan date, then by when it was finished, so "latest" means the last one run.
    found.sort(key=lambda found_at: (found_at[0]["date"], found_at[1]), reverse=True)
    return [result for result, _ in found]


def holding_rows(book: Book, exposure: dict, perf: dict, brief: dict | None) -> list[dict]:
    names = {}
    for h in book.holdings:
        names.setdefault(h.symbol, (h.name, h.kind))
    notes = {h["symbol"]: h for h in (brief or {}).get("holdings", [])}
    events = (brief or {}).get("events", [])
    details = exposure.get("holdings_detail", {})
    rows = []
    for symbol, weight in sorted(exposure["weights"].items(), key=lambda kv: -kv[1]):
        detail = details.get(symbol, {})
        name, kind = names.get(symbol, (symbol, "stock"))
        rows.append({
            "symbol": symbol, "name": name, "kind": kind, "weight": weight,
            "returns": perf.get("returns", {}).get("holdings", {}).get(symbol, {}),
            "spark": perf.get("spark", {}).get(symbol, []),
            "line": perf.get("holding_lines", {}).get(symbol, []),
            "themes": detail.get("themes", {}),
            "countries": detail.get("countries", []),
            "inside": detail.get("inside", []),
            "note": notes.get(symbol),
            "events": [i for i, e in enumerate(events) if symbol in ((e.get("touches") or {}).get("holdings") or [])],
        })
    return rows


def context(user: UserDir, book: Book, today: dt.date, brief: dict | None, banners: list[str]) -> dict:
    out = user.out
    for name in ("exposure.json", "news.json"):
        if not (out / name).exists():
            raise Problems([f"{name} is missing: run 'whatstocks prepare' first"])
    exposure, news = read_json(out / "exposure.json"), read_json(out / "news.json")
    perf = read_json(out / "performance.json") if (out / "performance.json").exists() else {}
    banners = list(banners)
    # Worked out from the brief itself, so a later redraw (after a scan) shows them too.
    if brief is None:
        banners.insert(0, "No morning brief today: this page shows the numbers only.")
    elif text_checks(brief)[1]:
        banners.insert(0, "Parts of this brief read like advice. They were let through with --allow-advice: "
                          "treat them with care.")
    if exposure.get("date") != today.isoformat():
        banners.append(f"The numbers are from {exposure.get('date')}: run 'whatstocks prepare' for today's.")
    if exposure.get("stale"):
        banners.append("Prices from an earlier day for: " + ", ".join(f"{s} ({d or 'none'})" for s, d in exposure["stale"].items()))

    evidence = load_evidence(out / "evidence.jsonl")
    busy = record.busy_days(evidence)
    home = book.settings.home_currency
    prices, fx = Prices(user.cache), Fx(user.cache)

    def series_of(symbol: str) -> pd.Series:
        currency = prices.currency(symbol)
        if not currency or not (fx.has(currency) and fx.has(home)):
            return pd.Series(dtype=float)
        return fx.convert(prices.series(symbol), currency, home)

    themes = book.themes.themes
    open_views = [v for v in book.views if not v.outcome]
    implied = {tid for v in open_views for tid in v.themes}
    heat = Counter(tid for e in (brief or {}).get("events", []) for tid in (e.get("touches") or {}).get("themes", []))
    views = record.view_rows(book, today, evidence, exposure["themes"])
    for v in views:
        v["today"] = [
            {"what": e["what"], "effect": ve["effect"], "why": ve.get("why", ""), "news_ids": e["news_ids"]}
            for e in (brief or {}).get("events", []) for ve in e.get("views") or [] if ve.get("view_id") == v["id"]
        ]
    return {
        "date": today.isoformat(),
        "home": home,
        "benchmark": book.settings.benchmark,
        "banners": banners,
        "notes": exposure.get("notes", []) + news.get("notes", []),
        "brief": brief,
        "news": {n["id"]: n for n in news["items"]},
        "theme_labels": {tid: t.label for tid, t in themes.items()},
        "theme_proxies": {tid: t.proxy for tid, t in themes.items()},
        "must_cover": [tid for tid, row in exposure["themes"].items() if row["you"] >= MUST_COVER_SHARE or tid in implied],
        "heat": dict(heat),
        "news_heat": news_heat(evidence, list(themes), today),
        "weights": exposure["weights"],
        "holdings": holding_rows(book, exposure, perf, brief),
        "perf": perf,
        "exposure": exposure,
        "views": views,
        "blind_spots": blind_spots(exposure, evidence, today),
        "scores": record.scores(book.views),
        "decisions": [
            {"id": d.id, "date": d.date.isoformat(), "action": d.action, "symbol": d.symbol, "size_pct": d.size_pct,
             "views": d.views, "reason": d.reason, "review_on": d.review_on.isoformat(),
             "flags": record.decision_flags(d, book, busy)}
            for d in book.decisions
        ],
        "reviews": record.reviews(book, today, series_of, series_of(book.settings.benchmark)),
        "record_watch": record_watch(book, today),
        "scans": scans(out),
    }


def write(user: UserDir, book: Book, today: dt.date, brief: dict | None, banners: list[str]) -> Path:
    path = user.out / "dashboard.html"
    path.write_text(render.page(context(user, book, today, brief, banners)), "utf-8")
    return path
