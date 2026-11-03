"""The record: view scores, decision flags and reviews (SPEC 7.5, 7.6)."""
from __future__ import annotations

import datetime as dt
from collections import Counter, defaultdict

import pandas as pd

from .files import Book, Decision, View

LUCK_BELOW = 20
BUSY_EVENTS = 3
COIN_FLIP = 0.25


def brier(view: View) -> float | None:
    """Time-weighted Brier score: each day's probability in force, against the outcome."""
    if view.result not in ("yes", "no"):
        return None
    truth = 1.0 if view.result == "yes" else 0.0
    days = max((view.outcome["date"] - view.created).days, 1)
    total = 0.0
    for i in range(days):
        p = view.probability_on(view.created + dt.timedelta(days=i))
        total += (p - truth) ** 2
    return total / days


def scores(views: list[View]) -> dict:
    rows = [
        {"id": v.id, "statement": v.statement, "result": v.result, "brier": brier(v),
         "date": v.outcome["date"].isoformat() if v.outcome.get("date") else "", "note": v.outcome.get("note", "")}
        for v in views if v.outcome
    ]
    scored = [r["brier"] for r in rows if r["brier"] is not None]
    return {
        "views": rows,
        "count": len(scored),
        "mean": sum(scored) / len(scored) if scored else None,
        "luck": len(scored) < LUCK_BELOW,
        "coin_flip": COIN_FLIP,
    }


def busy_days(evidence: list[dict]) -> dict[str, Counter]:
    """Events per theme per day, from the evidence log."""
    busy = defaultdict(Counter)
    for e in evidence:
        for tid in e.get("themes", []):
            busy[e["date"]][tid] += 1
    return busy


def _pct(p: float | None) -> str:
    return "no view yet" if p is None else f"{p:.0%}"


def decision_flags(d: Decision, book: Book, busy: dict) -> list[str]:
    """Shown next to a decision, never blocking it."""
    flags = []
    if not d.views:
        flags.append("No view cited")
    weights = book.themes.weights(d.symbol)
    core = {tid for tid, w in weights.items() if w == 1.0}
    for vid in d.views:
        view = book.view(vid)
        p = view.probability_on(d.date)
        if p is None:
            flags.append(f"Cites {vid}, which was written after this decision")
            continue
        if p < 0.5:
            flags.append(f"Low-confidence view: {vid} was {_pct(p)} that day")
            continue
        for tid, direction in view.themes.items():
            buying = d.action in ("buy", "add")
            selling = d.action in ("sell", "trim")
            if tid in core and ((direction == "down" and buying) or (direction == "up" and selling)):
                flags.append(f"Against your view: {vid} implies {tid} {direction}")
    day = busy.get(d.date.isoformat(), Counter())
    if weights and sum(day[tid] for tid in weights) >= BUSY_EVENTS:
        flags.append("Busy news day")
    return flags


def view_rows(book: Book, today: dt.date, evidence: list[dict], themes: dict) -> list[dict]:
    """The open views, with evidence counts and the exposure to the themes they imply."""
    rows = []
    for v in book.views:
        if v.outcome:
            continue
        counts = {}
        for window in (7, 30):
            c = Counter(
                ve["effect"]
                for e in evidence if (today - dt.date.fromisoformat(e["date"])).days < window
                for ve in e.get("views", []) if ve.get("view_id") == v.id
            )
            counts[str(window)] = {k: c.get(k, 0) for k in ("for", "against", "unclear")}
        rows.append({
            "id": v.id,
            "statement": v.statement,
            "probability": v.probability,
            "created": v.created.isoformat(),
            "resolves_by": v.resolves_by.isoformat(),
            "days_left": (v.resolves_by - today).days,
            "due": today > v.resolves_by,
            "forecasts": [[f.date.isoformat(), f.probability] for f in v.forecasts],
            "evidence": counts,
            "themes": [
                {"id": tid, "label": book.themes.themes[tid].label, "direction": direction,
                 "you": themes.get(tid, {}).get("you"), "world": themes.get(tid, {}).get("world")}
                for tid, direction in v.themes.items()
            ],
        })
    rows.sort(key=lambda r: (not r["due"], r["resolves_by"]))
    return rows


def change(series: pd.Series, start: dt.date, end: dt.date) -> float | None:
    if series is None or series.empty:
        return None
    s = series.dropna()
    index = pd.DatetimeIndex(s.index)
    before, upto = s[index <= pd.Timestamp(start)], s[index <= pd.Timestamp(end)]
    if before.empty or upto.empty:
        return None
    return float(upto.iloc[-1] / before.iloc[-1] - 1)


def reviews(book: Book, today: dt.date, series_of, bench: pd.Series) -> list[dict]:
    """Decisions past their review date: what the stock did since, next to the world index."""
    out = []
    for d in book.decisions:
        if d.review_on > today:
            continue
        out.append({
            "id": d.id, "symbol": d.symbol, "action": d.action, "date": d.date.isoformat(),
            "since": change(series_of(d.symbol), d.date, today), "world": change(bench, d.date, today),
        })
    return out
