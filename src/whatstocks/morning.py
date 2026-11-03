"""The two code halves of /morning around the AI step (SPEC section 8).

prepare: check files, refresh data, compute exposure, fetch news, write the AI payload.
finish:  check the AI's brief, update the evidence log, build the dashboard."""
from __future__ import annotations

import datetime as dt
import json
from collections import Counter, defaultdict
from pathlib import Path

import pandas as pd

from . import brief as briefs
from . import exposure as ex
from . import record, render
from .files import Book, Problems, load_book
from .funds import Funds, Position, listing_country, look_through
from .market import Fx, Prices
from .news import fetch_news
from .paths import UserDir


def _write(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=1, ensure_ascii=False, default=str), "utf-8")


def _read(path: Path):
    try:
        return json.loads(path.read_text("utf-8"))
    except json.JSONDecodeError as e:
        raise Problems([f"{path.name} line {e.lineno}: not valid JSON ({e.msg})"]) from None


def load(user: UserDir) -> tuple[Book, Funds]:
    funds = Funds(user.cache)
    return load_book(user, funds.symbols()), funds


def keep_views(book: Book) -> None:
    """Views can be voided, never deleted (P7)."""
    path = book.dir.out / "views_seen.json"
    seen = set(_read(path)) if path.exists() else set()
    current = {v.id for v in book.views}
    gone = sorted(seen - current)
    if gone:
        raise Problems([
            f"views.yaml: view '{v}' was deleted. Put it back and give it an outcome with result: void and a note"
            for v in gone
        ])
    _write(path, sorted(seen | current))


def _positions(book: Book, prices: Prices, fx: Fx) -> tuple[list[Position], list[str]]:
    home = book.settings.home_currency
    positions, problems = [], []
    for h in book.holdings:
        where = f"holdings.csv row {h.row} ({h.symbol})"
        if h.kind != "cash" and h.quantity is not None:
            closes, currency = prices.series(h.symbol), prices.currency(h.symbol)
            if len(closes) and currency:
                amount = h.quantity * float(closes.iloc[-1])
            elif h.value is not None:
                amount, currency = h.value, h.currency
            else:
                problems.append(f"{where}: no price found, and no value given")
                continue
        else:
            amount, currency = h.value, h.currency
        if not (fx.has(currency) and fx.has(home)):
            problems.append(f"{where}: no ECB exchange rate for {currency}")
            continue
        listing = book.themes.aliases.get(h.symbol, [h.symbol])[0]
        positions.append(Position(h.symbol, h.name, fx.latest(amount, currency, home), h.kind, currency, listing_country(listing)))
    return positions, problems


def prepare(user: UserDir, offline: bool = False, today: dt.date | None = None) -> dict:
    today = today or dt.date.today()
    book, funds = load(user)
    keep_views(book)
    home = book.settings.home_currency
    prices, fx = Prices(user.cache), Fx(user.cache)
    held = sorted({h.symbol for h in book.holdings if h.kind != "cash"})
    proxies = {t.proxy for t in book.themes.themes.values()}
    symbols = sorted(set(held) | proxies | {book.settings.benchmark} | {d.symbol for d in book.decisions})
    notes = []
    if not offline:
        failed = prices.refresh(symbols)
        if failed:
            notes.append(f"Prices not refreshed for {', '.join(failed)}: using cached prices where there are any.")
        currencies = {prices.currency(s) for s in symbols} | {h.currency for h in book.holdings if h.value is not None}
        if not fx.refresh({c for c in currencies | {home} if c}):
            notes.append("FX rates not refreshed: using cached rates.")

    positions, problems = _positions(book, prices, fx)
    if problems:
        raise Problems(problems)
    total = sum(p.value for p in positions)
    weights = defaultdict(float)
    for p in positions:
        weights[p.symbol] += p.value / total
    series = {}
    for s in symbols:
        currency = prices.currency(s)
        if currency and fx.has(currency) and fx.has(home):
            series[s] = fx.convert(prices.series(s), currency, home)

    pieces, lt_notes = look_through(positions, funds, today, offline)
    bench_pieces, bench_notes = look_through([Position(book.settings.benchmark, "Benchmark", 1.0, "fund", "")], funds, today, offline)
    notes += lt_notes + [n for n in bench_notes if n not in lt_notes]
    exposure = ex.build(book, dict(weights), series, pieces, bench_pieces)
    exposure.update(date=today.isoformat(), home_currency=home, notes=notes, stale=prices.stale(held, today))
    _write(user.out / "exposure.json", exposure)

    news_path = user.out / "news.json"
    if offline:
        news = _read(news_path) if news_path.exists() else {"items": [], "notes": ["Offline: no news fetched."]}
    else:
        now = dt.datetime.now(dt.timezone.utc)
        items, news_notes = fetch_news(book.themes, now)
        news = {"fetched": now.isoformat(timespec="minutes"), "items": items, "notes": news_notes}
        _write(news_path, news)

    payload = briefs.build_payload(book, today, dict(weights), exposure["themes"], news["items"])
    amounts = [p.value for p in positions] + [h.quantity for h in book.holdings if h.quantity] + [total]
    leaks = briefs.payload_leaks(payload, amounts)
    if leaks:
        raise Problems([f"AI payload check failed: {leak}" for leak in leaks])
    _write(user.out / "payload.json", payload)
    return {"exposure": exposure, "news": news, "payload": payload}


def update_evidence(path: Path, brief: dict | None, today: dt.date) -> list[dict]:
    """Add today's events to the evidence log. A re-run on the same day replaces that day's entries."""
    entries = [json.loads(line) for line in path.read_text("utf-8").splitlines() if line.strip()] if path.exists() else []
    entries = [e for e in entries if e["date"] != today.isoformat()]
    for e in (brief or {}).get("events", []):
        touches = e.get("touches") or {}
        entries.append({
            "date": today.isoformat(), "what": e["what"], "news_ids": e["news_ids"],
            "themes": touches.get("themes", []), "holdings": touches.get("holdings", []), "views": e.get("views", []),
        })
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(e, ensure_ascii=False) + "\n" for e in entries), "utf-8")
    return entries


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


def finish(user: UserDir, no_brief: bool = False, allow_advice: bool = False, today: dt.date | None = None) -> Path:
    today = today or dt.date.today()
    book, _ = load(user)
    out = user.out
    for name in ("exposure.json", "news.json", "payload.json"):
        if not (out / name).exists():
            raise Problems([f"{name} is missing: run 'whatstocks prepare' first"])
    exposure, news, payload = (_read(out / n) for n in ("exposure.json", "news.json", "payload.json"))
    if payload["date"] != today.isoformat():
        raise Problems([f"payload.json is from {payload['date']}: run 'whatstocks prepare' again today"])

    banners, brief = [], None
    if no_brief:
        banners.append("No morning brief today: this page shows the numbers only.")
    else:
        path = out / "brief.json"
        if not path.exists():
            raise Problems(["brief.json is missing: write it from payload.json (see .claude/skills/morning/SKILL.md), or run 'whatstocks finish --no-brief'"])
        brief = _read(path)
        errors, advice = briefs.validate_brief(brief, payload)
        if errors or (advice and not allow_advice):
            raise Problems([f"brief.json: {m}" for m in errors + advice])
        if advice:
            banners.append("Parts of this brief read like advice. They were let through with --allow-advice: treat them with care.")
    if exposure.get("stale"):
        banners.append("Prices from an earlier day for: " + ", ".join(f"{s} ({d or 'none'})" for s, d in exposure["stale"].items()))

    evidence = update_evidence(out / "evidence.jsonl", brief, today)
    busy = record.busy_days(evidence)
    home = book.settings.home_currency
    prices, fx = Prices(user.cache), Fx(user.cache)

    def series_of(symbol: str) -> pd.Series:
        currency = prices.currency(symbol)
        if not currency or not (fx.has(currency) and fx.has(home)):
            return pd.Series(dtype=float)
        return fx.convert(prices.series(symbol), currency, home)

    ctx = {
        "date": today.isoformat(),
        "home": home,
        "banners": banners,
        "notes": exposure.get("notes", []) + news.get("notes", []),
        "brief": brief,
        "news": {n["id"]: n for n in news["items"]},
        "theme_labels": {tid: t.label for tid, t in book.themes.themes.items()},
        "weights": exposure["weights"],
        "views": record.view_rows(book, today, evidence, exposure["themes"]),
        "exposure": exposure,
        "blind_spots": blind_spots(exposure, evidence, today),
        "scores": record.scores(book.views),
        "decisions": [
            {"id": d.id, "date": d.date.isoformat(), "action": d.action, "symbol": d.symbol, "size_pct": d.size_pct,
             "views": d.views, "reason": d.reason, "review_on": d.review_on.isoformat(),
             "flags": record.decision_flags(d, book, busy)}
            for d in book.decisions
        ],
        "reviews": record.reviews(book, today, series_of, series_of(book.settings.benchmark)),
    }
    path = out / "dashboard.html"
    path.write_text(render.page(ctx), "utf-8")
    return path
