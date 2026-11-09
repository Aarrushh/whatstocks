"""The two code halves of /morning around the AI step (SPEC section 8).

prepare: check files, refresh data, compute exposure, fetch news, write the AI payload.
finish:  check the AI's brief, update the evidence log, build the dashboard.

And the two code steps of /bet: bet_due lists what is due, rebuild_bet works the bet out again and redraws."""
from __future__ import annotations

import datetime as dt
import json
from collections import defaultdict
from pathlib import Path

from . import brief as briefs
from . import dashboard
from . import exposure as ex
from . import performance
from .bet import fetch as bet_fetch
from .bet import ledger as bet_ledger
from .bet import markets as bet_markets
from .bet import models as bet_models
from .bet import panels as bet_panels
from .bet import reach as bet_reach
from .bet import signals as bet_signals
from .dashboard import blind_spots  # noqa: F401  (kept importable from here)
from .files import Book, Problems, load_book, read_json, write_json
from .funds import Funds, Position, listing_country, look_through
from .market import Fx, Prices
from .news import fetch_news
from .sectors import Sectors
from .sectors import proxies as sector_funds
from .paths import UserDir


_read, _write = read_json, write_json


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


def _home_series(prices: Prices, fx: Fx, symbols, home: str) -> dict:
    """Each symbol's closes in your home currency, from the price and FX caches; a symbol without a rate is left out."""
    series = {}
    for s in symbols:
        currency = prices.currency(s)
        if currency and fx.has(currency) and fx.has(home):
            series[s] = fx.convert(prices.series(s), currency, home)
    return series


def _bet_block(user: UserDir, book: Book, ledger: bet_ledger.Ledger, prices: Prices, today: dt.date) -> dict:
    """The bet page's block (out/bet.json): the fetched figures (from the cache) take the ledger's place, then both
    models are worked out for every slider step, with the signals and the panels. Nothing in it comes from your
    holdings."""
    fetched = bet_fetch.points(user, ledger)
    differences = bet_fetch.merge(ledger, fetched)
    bet = bet_models.build(ledger, prices, today)
    bet["fetched"] = {"figures": len(fetched), "differences": differences}
    bet["signals"] = bet_signals.evaluate(ledger, bet, prices, book.themes, today)
    bet["releases"] = bet_markets.releases(ledger, prices, book.themes)
    bet["analogs"] = bet_markets.analogs(ledger, bet)
    bet["panels"] = bet_panels.build(ledger, bet, today)
    _write(user.out / "bet.json", bet)
    return bet


def prepare(user: UserDir, offline: bool = False, today: dt.date | None = None) -> dict:
    today = today or dt.date.today()
    book, funds = load(user)
    keep_views(book)
    # Its dates are checked against the real date, so it takes no 'today'.
    ledger = bet_ledger.load(user, views={v.id for v in book.views}, themes=book.themes)
    home = book.settings.home_currency
    prices, fx = Prices(user.cache), Fx(user.cache)
    held = sorted({h.symbol for h in book.holdings if h.kind != "cash"})
    proxies = {t.proxy for t in book.themes.themes.values()}
    stocks = sorted({h.symbol for h in book.holdings if h.kind == "stock"})
    sectors = Sectors(user.cache)
    extra = set(book.settings.compare.values()) | sector_funds()
    symbols = sorted(set(held) | proxies | {book.settings.benchmark} | {d.symbol for d in book.decisions} | extra)
    notes = []
    if not offline:
        failed = prices.refresh(sorted(set(symbols) | bet_fetch.symbols(ledger, book.themes)))
        if failed:
            notes.append(f"Prices not refreshed for {', '.join(failed)}: using cached prices where there are any.")
        unknown = sectors.refresh(stocks)
        if unknown:
            notes.append(f"No sector found for {', '.join(unknown)}: left out of the sector comparison.")
        currencies = {prices.currency(s) for s in symbols} | {h.currency for h in book.holdings if h.value is not None}
        if not fx.refresh({c for c in currencies | {home} if c}):
            notes.append("FX rates not refreshed: using cached rates.")
        notes += bet_fetch.refresh(user, ledger, book.settings.sec_contact, today)
    bet = _bet_block(user, book, ledger, prices, today)

    positions, problems = _positions(book, prices, fx)
    if problems:
        raise Problems(problems)
    total = sum(p.value for p in positions)
    weights = defaultdict(float)
    for p in positions:
        weights[p.symbol] += p.value / total
    series = _home_series(prices, fx, symbols, home)

    pieces, lt_notes = look_through(positions, funds, today, offline)
    bench_pieces, bench_notes = look_through([Position(book.settings.benchmark, "Benchmark", 1.0, "fund", "")], funds, today, offline)
    notes += lt_notes + [n for n in bench_notes if n not in lt_notes]
    exposure = ex.build(book, dict(weights), series, pieces, bench_pieces)
    index = ex.member_index(book.themes)
    look = {"you": ex.lookthrough_rows(pieces, index), "world": ex.lookthrough_rows(bench_pieces, index)}
    cash = {h.symbol for h in book.holdings if h.kind == "cash"}
    exposure.update(
        date=today.isoformat(), home_currency=home, notes=notes, stale=prices.stale(held, today),
        countries={"you": ex.country_shares(pieces), "world": ex.country_shares(bench_pieces)},
        holdings_detail=ex.holding_details(pieces, book.themes, index),
        # "Will the bet pay off?": how much of you, and of the world index, each crash path reaches (spec 10).
        crash_paths=bet_reach.crash_paths(ledger, book.themes, look, dict(weights), series, cash,
                                          book.settings.benchmark),
    )
    _write(user.out / "exposure.json", exposure)
    _write(user.out / "lookthrough.json", {"date": today.isoformat(), **look})
    _write(user.out / "performance.json", {"date": today.isoformat(), **performance.build(book, dict(weights), series, today, sectors.of(stocks))})

    news_path = user.out / "news.json"
    if offline:
        news = _read(news_path) if news_path.exists() else {"items": [], "notes": ["Offline: no news fetched."]}
    else:
        now = dt.datetime.now(dt.timezone.utc)
        items, news_notes = fetch_news(book.themes, now)
        news = {"fetched": now.isoformat(timespec="minutes"), "items": items, "notes": news_notes}
        _write(news_path, news)

    payload = briefs.build_payload(book, today, dict(weights), exposure["themes"], news["items"],
                                   details=exposure["holdings_detail"])
    payload["bet"] = bet_signals.payload_block(bet["signals"], bet_signals.baseline(_bet_state(user), today))
    amounts = [p.value for p in positions] + [h.quantity for h in book.holdings if h.quantity] + [total]
    leaks = briefs.payload_leaks(payload, amounts)
    if leaks:
        raise Problems([f"AI payload check failed: {leak}" for leak in leaks])
    _write(user.out / "payload.json", payload)
    return {"exposure": exposure, "news": news, "payload": payload, "bet": bet}


def _bet_state(user: UserDir) -> dict | None:
    """The last logged state of the regime, the paths and the indicators (spec 16), if finish has logged one."""
    path = user.out / "bet_state.json"
    return _read(path) if path.exists() else None


def update_evidence(path: Path, brief: dict | None, today: dt.date, signals: list[dict] = ()) -> list[dict]:
    """Add today's events, and the bet's signal lines, to the evidence log. A re-run on the same day replaces that
    day's entries."""
    entries = [json.loads(line) for line in path.read_text("utf-8").splitlines() if line.strip()] if path.exists() else []
    entries = [e for e in entries if e["date"] != today.isoformat()]
    for e in (brief or {}).get("events", []):
        touches = e.get("touches") or {}
        entries.append({
            "date": today.isoformat(), "what": e["what"], "news_ids": e["news_ids"],
            "themes": touches.get("themes", []), "holdings": touches.get("holdings", []), "views": e.get("views", []),
        })
    entries += signals
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(e, ensure_ascii=False) + "\n" for e in entries), "utf-8")
    return entries


def finish(user: UserDir, no_brief: bool = False, allow_advice: bool = False, today: dt.date | None = None) -> Path:
    today = today or dt.date.today()
    book, _ = load(user)
    out = user.out
    for name in ("exposure.json", "news.json", "payload.json"):
        if not (out / name).exists():
            raise Problems([f"{name} is missing: run 'whatstocks prepare' first"])
    payload = _read(out / "payload.json")
    if payload["date"] != today.isoformat():
        raise Problems([f"payload.json is from {payload['date']}: run 'whatstocks prepare' again today"])

    brief = None
    archive = out / "briefs" / f"{today.isoformat()}.json"
    if no_brief:
        archive.unlink(missing_ok=True)  # a copy of today's brief.json, so a later redraw shows no brief either
    else:
        path = out / "brief.json"
        if not path.exists():
            raise Problems(["brief.json is missing: write it from payload.json (see .claude/skills/morning/SKILL.md), or run 'whatstocks finish --no-brief'"])
        brief = _read(path)
        errors, advice = briefs.validate_brief(brief, payload)
        if errors or (advice and not allow_advice):
            raise Problems([f"brief.json: {m}" for m in errors + advice])
        _write(archive, brief)
    # "Will the bet pay off?": a line for each path, and the regime, in a new state since the last logged one.
    lines, bet_path = [], out / "bet.json"
    if bet_path.exists():
        signals = _read(bet_path).get("signals")
        if signals and signals["date"] == today.isoformat():
            state = _bet_state(user)
            open_views = {v.id for v in book.views if not v.outcome}
            lines = bet_signals.evidence(signals, bet_signals.baseline(state, today), open_views, today)
            _write(out / "bet_state.json", bet_signals.logged(signals, state, today))
    update_evidence(out / "evidence.jsonl", brief, today, lines)
    # The dashboard adds the 'no brief' and 'let through with --allow-advice' banners from the brief itself.
    return dashboard.write(user, book, today, brief, [])


def rebuild_bet(user: UserDir, today: dt.date | None = None) -> dict:
    """'whatstocks bet', the last step of /bet (spec 17): work the bet out again from the ledger and my/bet.yaml, with
    the prices and fetched figures already in the cache (nothing is fetched), and redraw the page with today's brief
    if finish kept one. Each crash path's reach is worked out again too, since my/bet.yaml can change its channels.
    The evidence log is left to finish, so a path that moved is logged on the next morning run.

    Returns the signals before and after, for the report of what moved, and the page."""
    today = today or dt.date.today()
    for name in ("exposure.json", "lookthrough.json", "news.json"):
        if not (user.out / name).exists():
            raise Problems([f"{name} is missing: run 'whatstocks prepare' first"])
    book, _ = load(user)
    ledger = bet_ledger.load(user, views={v.id for v in book.views}, themes=book.themes)
    old = user.out / "bet.json"
    before = _read(old).get("signals") if old.exists() else None
    prices, fx = Prices(user.cache), Fx(user.cache)
    bet = _bet_block(user, book, ledger, prices, today)

    exposure, look = _read(user.out / "exposure.json"), _read(user.out / "lookthrough.json")
    series = _home_series(prices, fx, set(exposure["weights"]) | {book.settings.benchmark},
                          book.settings.home_currency)
    cash = {h.symbol for h in book.holdings if h.kind == "cash"}
    exposure["crash_paths"] = bet_reach.crash_paths(ledger, book.themes, look, exposure["weights"], series, cash,
                                                    book.settings.benchmark)
    _write(user.out / "exposure.json", exposure)
    page = dashboard.write(user, book, today, dashboard.todays_brief(user, today), [])
    return {"before": before, "after": bet["signals"], "page": page}


def bet_due(user: UserDir, today: dt.date | None = None) -> dict:
    """'whatstocks bet due', the first step of /bet (spec 17): the series with a newer figure due, and the open gaps,
    ranked as the page's Sources panel ranks them (what feeds the two curves first, then what the most indicators
    read). A figure the code fetched (in the cache) counts as the newest."""
    today = today or dt.date.today()
    book, _ = load(user)
    ledger = bet_ledger.load(user, views={v.id for v in book.views}, themes=book.themes)
    bet_fetch.merge(ledger, bet_fetch.points(user, ledger))
    found = bet_panels.sources(ledger, today)
    return {"due": [r for r in found["rows"] if r["due"]], "gaps": found["gaps"], "series": len(found["rows"]),
            "sec_contact": bool(book.settings.sec_contact)}
