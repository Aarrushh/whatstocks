"""The open-weight releases and the analogs of "Will the bet pay off?" (spec sections 11 and 12).

A release's market effect is the move of the AI basket and of the hyperscaler basket (the baskets the two signals
watch, each company counted once) over the three trading days from the release, less the world index's move. Its
adoption effect is the change in the usage figures below over the next 30 and 90 days, where the ledger has a figure
within ten days of both dates. Until it has, the effect stays empty: it is never guessed.

The analogs are the ledger's series for each, by years since its build-out began (or since each technology launched),
indexed to 100 at their first figure unless they are shares. AI's own capex goes beside them, by years since 2023."""
from __future__ import annotations

import datetime as dt

import pandas as pd

from ..files import ThemeMap
from .fetch import members
from .ledger import Ledger, Point, Series
from .signals import _one_per_company

MARKET_DAYS = 3  # trading days of the world index, from the release on
AFTER = (30, 90)  # days after a release, for its adoption effect
NEAR = 10  # days a figure may sit from the date it stands for
BASKETS = {"ai": "ai_basket", "hyperscalers": "hyperscaler_basket"}  # the indicators whose baskets a release moves
USAGE = (("tokens_weekly", "openrouter"), ("openrouter_token_share", "open_weight"))  # what a release may speed up
SHARES = ("pct",)  # units drawn as they are; the others are indexed to 100


def _closes(prices, symbol: str) -> pd.Series:
    s = prices.series(symbol).dropna()
    s.index = pd.DatetimeIndex(s.index)
    return s.sort_index()


def _basket(prices, symbols: list[str]) -> pd.DataFrame:
    """The members' closes, one column per company: a second share class is dropped, as in the signals."""
    closes = {s: x for s in symbols if len(x := _closes(prices, s))}
    if not closes:
        return pd.DataFrame()
    frame, _ = _one_per_company(pd.DataFrame(closes).sort_index().ffill())
    return frame


def market_effect(world: pd.Series, baskets: dict[str, pd.DataFrame], day: dt.date) -> dict:
    """From the world index's last close before the release to its close on the third trading day from the release
    on: the world's move, and each basket's equal-weight move less the world's."""
    t = pd.Timestamp(day)
    before, after = world.index[world.index < t], world.index[world.index >= t]
    if not len(before) or len(after) < MARKET_DAYS:
        return {"from": None, "to": None, "world": None, **dict.fromkeys(baskets)}
    t0, t1 = before[-1], after[MARKET_DAYS - 1]
    move = float(world[t1] / world[t0] - 1)
    out = {"from": t0.date().isoformat(), "to": t1.date().isoformat(), "world": round(move, 6)}
    for key, frame in baskets.items():
        start, end = frame[frame.index <= t0], frame[frame.index <= t1]
        moves = (end.iloc[-1] / start.iloc[-1] - 1).dropna() if len(start) else pd.Series(dtype=float)
        out[key] = round(float(moves.mean()) - move, 6) if len(moves) else None
    return out


def _date(p: Point) -> dt.date | None:
    try:
        return dt.date.fromisoformat(p.period)
    except ValueError:
        return None


def _near(points: list[Point], day: dt.date) -> Point | None:
    close = [(abs((d - day).days), p) for p in points if (d := _date(p)) and abs((d - day).days) <= NEAR]
    return min(close, key=lambda x: x[0])[1] if close else None


def _label(led: Ledger, s: Series, eid: str) -> str:
    entity = s.entities.get(eid) or led.entities.get(eid) or {}
    return f"{s.label}: {entity.get('label', eid)}"


def adoption_effect(led: Ledger, day: dt.date) -> list[dict]:
    """Each usage figure's change over the next 30 and 90 days: in points for a share, as a fraction otherwise. None
    where the ledger has no figure near the release, or none near the later date."""
    out = []
    for sid, eid in USAGE:
        s = led.series.get(sid)
        if s is None:
            continue
        found = [p for p in s.points.get(eid, []) if p.value is not None]
        start, change = _near(found, day), {}
        for days in AFTER:
            end = _near(found, day + dt.timedelta(days=days))
            if start is None or end is None or end is start:
                change[str(days)] = None
            elif s.unit in SHARES:
                change[str(days)] = round(end.value - start.value, 4)
            else:
                change[str(days)] = round(end.value / start.value - 1, 6)
        out.append({"series": sid, "entity": eid, "label": _label(led, s, eid), "unit": s.unit, "change": change})
    return out


def _mean(xs) -> dict:
    found = [x for x in xs if x is not None]
    return {"mean": round(sum(found) / len(found), 6) if found else None, "n": len(found)}


def releases(led: Ledger, prices, themes: ThemeMap) -> dict:
    """Each open-weight release with its market and adoption effects, and the mean of each effect over the releases
    that have it, so the idea that each release knocks the market a little and speeds adoption is checked."""
    indicators = led.signals["indicators"]
    baskets = {key: _basket(prices, members(indicators[iid]["basket"], themes))
               for key, iid in BASKETS.items() if iid in indicators}
    world = _closes(prices, led.model["valuation"]["world"])
    items = []
    for r in led.events["releases"]:
        day = r["released"] if isinstance(r["released"], dt.date) else dt.date.fromisoformat(str(r["released"]))
        items.append({"id": r["id"], "name": r["name"], "lab": r["lab"], "released": day.isoformat(),
                      "source": r["source"], "press": r["press"], "market": market_effect(world, baskets, day),
                      "adoption": adoption_effect(led, day)})
    rows = items[0]["adoption"] if items else []
    average = {
        "market": {key: _mean(i["market"][key] for i in items) for key in [*baskets, "world"]},
        "adoption": {f"{u['series']}.{u['entity']}": {str(d): _mean(i["adoption"][j]["change"][str(d)] for i in items)
                                                      for d in AFTER} for j, u in enumerate(rows)},
    }
    notes = []
    if world.empty:
        notes.append(f"No prices for the world index ({led.model['valuation']['world']}): no market effects.")
    if not any(m["n"] for by in average["adoption"].values() for m in by.values()):
        notes.append(f"The ledger has no usage figure within {NEAR} days of a release and of {AFTER[0]} or "
                     f"{AFTER[1]} days later yet, so no adoption effect is measured.")
    notes.append("The ledger has no token price index by date yet, so a release's effect on prices is not measured.")
    return {"days": MARKET_DAYS, "after": list(AFTER), "items": items, "average": average, "notes": notes}


def _years(period: str, start: int) -> float | None:
    """Years from the start of `start` to a period: a year counts from its own start, a day as a part of a year."""
    if len(period) == 4 and period.isdigit():
        return float(int(period) - start)
    try:
        day = dt.date.fromisoformat(period)
    except ValueError:
        return None
    return round((day - dt.date(start, 1, 1)).days / 365.25, 3)


def analogs(led: Ledger, bet: dict) -> dict:
    """Each analog's lines by years since its start (or each technology's launch), and AI's capex by years since
    events.yaml's ai_start, indexed to its first year's mid estimate."""
    ai_start = led.events["ai_start"]
    items = {}
    for aid, a in (led.events.get("analogs") or {}).items():
        lines = []
        for ref in a.get("series") or []:
            sid, _, eid = str(ref).partition(".")
            s = led.series.get(sid)
            if s is None:
                continue
            entity = {**led.entities.get(eid, {}), **s.entities.get(eid, {})}
            start = entity.get("launch") if a.get("by") == "launch" else a.get("start")
            found = [(x, p) for p in s.points.get(eid, []) if p.value is not None and start is not None
                     and (x := _years(p.period, start)) is not None]
            base = found[0][1].value if found and s.unit not in SHARES else None
            lines.append({"id": ref, "label": entity.get("label", eid), "series": s.label, "unit": s.unit,
                          "indexed": bool(base), "start": start,
                          "points": [[x, round(100 * p.value / base, 3) if base else p.value] for x, p in found],
                          "sources": sorted({p.source for _, p in found if p.source})})
        items[aid] = {"label": a["label"], "shows": a["shows"], "by": a.get("by", "build-out"),
                      "start": a.get("start"), "lines": lines}
    cap = bet["capex"]["by_year"]
    base = next((m for m in cap.get("mid", []) if m), None)
    ai = [[y - ai_start, *(round(100 * x / base, 3) for x in (m, lo, hi))]
          for y, m, lo, hi in zip(cap.get("years", []), cap.get("mid", []), cap.get("low", []), cap.get("high", []))
          if base and y >= ai_start]
    return {"ai_start": ai_start, "items": items,
            "ai_capex": {"label": "AI capex placed (mid, low, high)", "indexed": bool(base), "points": ai,
                         "actual_through": cap.get("actual_through")}}
