"""The crash paths of "Will the bet pay off?" (spec section 9): each indicator's reading and state, each path's state,
and the regime, at your default settings. And what the morning keeps of them (spec section 16): the payload's bet
block, the last logged state in out/bet_state.json, and an evidence line each time a path or the regime changes.

Each indicator follows its rule in signals.yaml. A reading the ledger cannot give is 'no data', and it never moves a
path. Every reading is text in the indicator's own unit (percent, basis points, companies, quarters), never dollars,
so it can go to the AI as it is. Nothing here sees your holdings."""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field

import pandas as pd

from . import models
from .fetch import members
from .ledger import STATES, Ledger, Point, notch

NO_DATA = "no_data"
RANK = {s: i for i, s in enumerate(STATES)}  # clear 0, amber 1, red 2
SAME_COMPANY = 0.995  # daily returns this alike are two share classes of one company (GOOGL and GOOG)
SINGULAR = {"companies": "company", "quarters in a row": "quarter in a row", "readings in a row": "reading in a row"}


@dataclass
class Reading:
    """What a rule found: a number in the indicator's unit (None when there is none), the text for it, the period of
    the data, the ledger points it read, and the state, for the rules that set it themselves."""
    value: float | None
    text: str
    as_of: str | None = None
    points: list[Point] = field(default_factory=list)
    state: str | None = None


@dataclass
class Context:
    led: Ledger
    bet: dict  # models.build's output
    prices: object  # market.Prices, or anything with .series(symbol)
    themes: object  # files.ThemeMap
    today: dt.date


# ---------------------------------------------------------------- small readers


def _points(led: Ledger, sid: str, entity: str) -> list[Point]:
    s = led.series.get(sid)
    return [p for p in (s.points.get(entity, []) if s else []) if p.value is not None]


def _day(p: Point) -> dt.date | None:
    try:
        return dt.date.fromisoformat(p.period)
    except ValueError:
        return None


def _shift(period: str, k: int) -> str:
    """A month (2026-09) or a quarter (2026Q3), k periods later (earlier when k is negative)."""
    if "Q" in period:
        n = int(period[:4]) * 4 + int(period[5]) - 1 + k
        return f"{n // 4}Q{n % 4 + 1}"
    n = int(period[:4]) * 12 + int(period[5:7]) - 1 + k
    return f"{n // 12}-{n % 12 + 1:02d}"


def _fmt(x: float, unit: str, signed: bool = False) -> str:
    if unit in ("pct", "pct_per_year"):
        return f"{x:+.1f}%" if signed else f"{x:.1f}%"
    if unit == "bp":
        return f"{x:,.0f}bp"
    if unit == "points":
        return f"{x:+.1f} points"
    n = int(round(x))
    return f"{n} {SINGULAR.get(unit, unit) if n == 1 else unit}"


def _label(led: Ledger, eid: str) -> str:
    return led.entities.get(eid, {}).get("label", eid)


def _state(ind: dict, x: float) -> str:
    """One reading against two levels. At or past a level counts as reaching it."""
    worse = (lambda lv: x >= lv) if ind["direction"] == "up" else (lambda lv: x <= lv)
    if ind.get("red") is not None and worse(ind["red"]):
        return "red"
    if ind.get("amber") is not None and worse(ind["amber"]):
        return "amber"
    return "clear"


def _defaults(c: Context) -> tuple[int, float, str]:
    return c.led.default("gpu_life"), c.led.default("cost_of_capital"), str(c.led.default("deflation"))


def _sums(c: Context) -> dict[str, float]:
    """Model A's need and Model B's demand at your defaults, with the pieces switched on: the last four quarters'
    mean rates, and the totals to the deadline ($B, end users' dollars). Only shares of them leave this module."""
    life, wacc, deflation = _defaults(c)
    cell = c.bet["capex"]["grid"][f"{life}|{wacc}"]
    need = [p for p in c.bet["capex"]["pieces"] if p["on"]]
    step = c.bet["demand"]["grid"][deflation]["pieces"]
    tiers = [p for p in c.bet["demand"]["pieces"] if p["on"]]

    def a(read: str, part: str | None = None) -> float:
        return sum(cell[p["id"]]["readouts"]["rate"][read] for p in need if part in (None, p["part"]))

    def b(read: str, tier: str | None = None) -> float:
        return sum(step[p["id"]]["readouts"][str(life)]["rate"][read] for p in tiers if tier in (None, p["id"]))

    return {"need": a("last4"), "depreciation": a("last4", "depreciation"), "need_total": a("to_deadline"),
            "demand": b("last4"), "direct": b("last4", "direct"), "demand_total": b("to_deadline")}


# ---------------------------------------------------------------- the rules


def r_level(c: Context, ind: dict) -> Reading:
    """The latest figure. With max_age_days, an older one does not count, and the stand-in is read instead."""
    found = _points(c.led, ind["series"], ind["entity"])
    p = found[-1] if found else None
    age = ind.get("max_age_days")
    signed = ind["series"].endswith(("_qoq", "_yoy"))
    if p is not None and not (age and _day(p) and (c.today - _day(p)).days > age):
        return Reading(p.value, f"{_fmt(p.value, ind['unit'], signed)} on {p.period}", p.period, [p])
    stand = ind.get("stand_in")
    if stand:
        others = _points(c.led, stand["series"], stand["entity"])
        q = others[-1] if others else None
        if q is not None and not (age and _day(q) and (c.today - _day(q)).days > age):
            label = c.led.series[stand["series"]].label.lower()
            lead = f"no print in {age} days, so the {label} stands in: " if p is not None else f"the {label}: "
            return Reading(q.value, f"{lead}{_fmt(q.value, stand['unit'])} on {q.period}", q.period, [q],
                           state=_state({**ind, **stand}, q.value))
    if p is None:
        return Reading(None, "no figure yet")
    return Reading(None, f"no figure in the last {age} days (the last: {_fmt(p.value, ind['unit'])} on {p.period})",
                   p.period, [p])


def r_mean_last(c: Context, ind: dict) -> Reading:
    found = _points(c.led, ind["series"], ind["entity"])
    n = ind["points"]
    if not found:
        return Reading(None, "no figure yet")
    want = [_shift(found[-1].period, -k) for k in range(n - 1, -1, -1)]
    by = {p.period: p for p in found}
    if not all(w in by for w in want):
        return Reading(None, f"needs {n} periods in a row, {want[0]} to {want[-1]}", found[-1].period)
    used = [by[w] for w in want]
    mean = sum(p.value for p in used) / n
    return Reading(mean, f"{_fmt(mean, ind['unit'], True)}, the mean of {want[0]} to {want[-1]}", want[-1], used)


def r_change(c: Context, ind: dict) -> Reading:
    found = _points(c.led, ind["series"], ind["entity"])
    if not found:
        return Reading(None, "no figure yet")
    last = found[-1]
    then = next((p for p in found if p.period == _shift(last.period, -ind["points"])), None)
    if then is None or not then.value:
        return Reading(None, f"needs {_shift(last.period, -ind['points'])} to compare with {last.period}", last.period)
    x = 100 * (last.value / then.value - 1)
    return Reading(x, f"{_fmt(x, ind['unit'], True)} from {then.period} to {last.period}", last.period, [then, last])


def r_yoy(c: Context, ind: dict) -> Reading:
    found = [p for p in _points(c.led, ind["series"], ind["entity"]) if _day(p)]
    if not found:
        return Reading(None, "no figure yet")
    last = found[-1]
    target = _day(last) - dt.timedelta(days=365)
    near = [p for p in found if abs((_day(p) - target).days) <= ind["tolerance_days"]]
    if not near:
        return Reading(None, f"needs a figure from about {target.isoformat()} to compare with {last.period}",
                       last.period, [last])
    then = min(near, key=lambda p: abs((_day(p) - target).days))
    x = 100 * (last.value / then.value - 1)
    return Reading(x, f"{_fmt(x, ind['unit'], True)} from {then.period} to {last.period}", last.period, [then, last])


def r_capex_growth(c: Context, ind: dict) -> Reading:
    """Each company's last four filed quarters against the four before, added up. A company with fewer than eight
    filed quarters in a row is left out."""
    groups = c.led.model["capex"]["groups"]
    now = then = 0.0
    used, left, last = [], [], None
    for gid in ind["groups"]:
        for eid in groups[gid].get("members") or []:
            rows = models.capex_placed(c.led, eid)
            filed = sorted(q for q, (_, _, kind) in rows.items() if kind == "filed")
            run = [_shift(filed[-1], -k) for k in range(7, -1, -1)] if filed else []
            if not run or not set(run) <= set(filed):
                left.append(_label(c.led, eid))
                continue
            then += sum(rows[q][0] for q in run[:4])
            now += sum(rows[q][0] for q in run[4:])
            used.append(_label(c.led, eid))
            last = max(last or run[-1], run[-1])
    if not then:
        return Reading(None, "needs eight filed quarters in a row")
    x = 100 * (now / then - 1)
    text = f"{_fmt(x, 'pct', True)}, the last four filed quarters against the four before ({len(used)} companies"
    text += f"; {', '.join(left)} left out: fewer than eight filed quarters)" if left else ")"
    return Reading(x, text, last)


def r_capex_to_ocf(c: Context, ind: dict) -> Reading:
    """Cash capex over operating cash flow, over the last four quarters every company has filed both for."""
    entities = ind["entities"]
    capex = {e: {p.period: p for p in _points(c.led, "capex_cash", e)} for e in entities}
    ocf = {e: {p.period: p for p in _points(c.led, "ocf", e)} for e in entities}
    common = sorted(set.intersection(*(set(capex[e]) & set(ocf[e]) for e in entities))) if entities else []
    if len(common) < 4:
        return Reading(None, "needs four quarters of cash capex and operating cash flow for each company")
    quarters = common[-4:]
    out = sum(capex[e][q].value for e in entities for q in quarters)
    cash = sum(ocf[e][q].value for e in entities for q in quarters)
    x = 100 * out / cash
    latest = 100 * sum(capex[e][quarters[-1]].value for e in entities) / sum(ocf[e][quarters[-1]].value for e in entities)
    return Reading(x, f"{x:.0f}% over {quarters[0]} to {quarters[-1]} ({quarters[-1]} alone: {latest:.0f}%)",
                   quarters[-1])


def r_guide_vs_actual(c: Context, ind: dict) -> Reading:
    """How many of the latest guides in a row were below the revenue of the quarter before the one they guide."""
    guides = _points(c.led, ind["series"], ind["entity"])
    actual = {p.period: p for p in _points(c.led, ind["actual"], ind["entity"])}
    if not guides:
        return Reading(None, "no guidance yet")
    streak, used = 0, []
    for g in reversed(guides):
        before = actual.get(_shift(g.covers, -1))
        if before is None:
            if not used:
                return Reading(None, f"needs the revenue for {_shift(g.covers, -1)} to test the guide for {g.covers} "
                                     f"(EDGAR fetches it once sec_contact is set)", g.period, [g])
            break
        used += [g, before]
        if g.value >= before.value:
            break
        streak += 1
    g, before = used[0], used[1]
    gap = 100 * (g.value / before.value - 1)
    text = f"the guide for {g.covers} is {abs(gap):.0f}% {'below' if gap < 0 else 'above'} {before.period}'s revenue"
    if streak > 1:
        text += f", {streak} quarters in a row"
    return Reading(streak, text, g.period, used)


def r_guidance_cuts(c: Context, ind: dict) -> Reading:
    """Companies that cut a full-year guide in the last two quarters for a reason that counts."""
    since = c.today - dt.timedelta(days=round(365.25 / 4 * ind["quarters"]))
    counted, other, used = {}, [], []
    for eid in ind["entities"]:
        by_year: dict[str, list[Point]] = {}
        for p in _points(c.led, ind["series"], eid):
            by_year.setdefault(p.covers, []).append(p)
        for found in by_year.values():
            for before, after in zip(found, found[1:]):
                if after.value >= before.value or not _day(after) or _day(after) < since:
                    continue
                why = after.why or "unstated"
                if why in ind["counts"]:
                    counted.setdefault(_label(c.led, eid), []).append(f"{why}, {after.period}")
                    used.append(after)
                else:
                    other.append(f"{_label(c.led, eid)} {after.period}: {why}")
    n = len(counted)
    text = "; ".join(f"{name} ({', '.join(cuts)})" for name, cuts in counted.items()) or "none that count"
    if other:
        text += f" (not counted: {'; '.join(other)})"
    return Reading(n, f"{_fmt(n, 'companies')}: {text}" if n else text, since.isoformat(), used)


def _one_per_company(frame: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    """Drops a second share class of a company already in the basket: its daily returns are the same."""
    kept, dropped = [], []
    returns = frame.pct_change(fill_method=None)
    for symbol in frame.columns:
        if any(returns[symbol].corr(returns[k]) >= SAME_COMPANY for k in kept):
            dropped.append(symbol)
        else:
            kept.append(symbol)
    return frame[kept], dropped


def r_below_high(c: Context, ind: dict) -> Reading:
    """An equal-weight basket of a theme's members, bought a year ago, against its high since then."""
    closes = {s: c.prices.series(s) for s in members(ind["basket"], c.themes)}
    closes = {s: x for s, x in closes.items() if len(x)}
    if not closes:
        return Reading(None, "no prices yet")
    end = max(x.index[-1] for x in closes.values())
    start = end - pd.Timedelta(weeks=ind["weeks"])
    frame = pd.DataFrame(closes).sort_index().ffill()
    frame = frame[frame.index >= start].dropna(axis=1, how="any")
    if len(frame) < 2 or frame.empty:
        return Reading(None, "no prices for the last year")
    frame, dropped = _one_per_company(frame)
    basket = (frame / frame.iloc[0]).mean(axis=1)
    x = 100 * (basket.iloc[-1] / basket.max() - 1)
    high = basket.idxmax().date().isoformat()
    text = f"{_fmt(x, 'pct', True)} from its high on {high} ({len(frame.columns)} members, equal weight"
    text += f"; {', '.join(dropped)} counted once with its other share class)" if dropped else ")"
    return Reading(x, text, end.date().isoformat())


def r_events(c: Context, ind: dict) -> Reading:
    since = c.today - dt.timedelta(days=ind["days"])
    s = c.led.series.get(ind["series"])
    found = [p for ps in (s.points.values() if s else []) for p in ps if _day(p) and _day(p) >= since]
    red = [p for p in found if p.kind in ind["red_kinds"]]
    amber = [p for p in found if p.kind in ind["amber_kinds"]]
    if not red + amber:
        return Reading(0, f"none in the last {ind['days']} days", state="clear")
    text = "; ".join(f"{_label(c.led, p.entity)}: {p.kind.replace('_', ' ')} on {p.period}" for p in red + amber)
    return Reading(len(red + amber), text, max(p.period for p in red + amber), red + amber,
                   state="red" if red else "amber")


def r_ratings(c: Context, ind: dict) -> Reading:
    """Each agency's latest action on each borrower. At the floor or on negative outlook is amber; below it is red."""
    floor = notch("S&P", ind["floor"])
    s = c.led.series.get(ind["series"])
    if s is None or not s.points:
        return Reading(None, "no ratings yet")
    worst, notes, used = "clear", [], []
    for eid, found in s.points.items():
        latest: dict[str, Point] = {}
        for p in found:
            latest[p.agency] = p  # oldest first, so the last action wins
        for agency, p in sorted(latest.items()):
            n = notch(agency, p.rating)
            if n is None:
                continue
            state = "red" if n > floor else "amber" if n == floor or p.outlook == "negative" else "clear"
            if state != "clear":
                outlook = f", {p.outlook} outlook" if p.outlook == "negative" else ""
                notes.append(f"{_label(c.led, eid)} {p.rating}{outlook} ({agency}, {p.period})")
                used.append(p)
                worst = max(worst, state, key=RANK.get)
    text = "; ".join(notes) or f"every borrower above {ind['floor']}, none on negative outlook"
    return Reading(len(notes), text, max((p.period for p in used), default=None), used, state=worst)


def r_telecom_test(c: Context, ind: dict) -> Reading:
    """Realized revenue per token over the last year (Model B's trailing price change) against token growth."""
    demand = c.bet["demand"]
    d, g = demand["trailing"], demand["usage"]["growth"]
    if d is None or g is None:
        return Reading(None, "needs a year of demand and of tokens")
    x = 100 * d
    grew = (1 + d) * (1 + g)
    state = "red" if grew < 1 else "amber" if x <= ind["amber"] else "clear"
    usage = demand["usage"]
    text = f"{x:+.0f}% a year: tokens x{1 + g:.1f} ({usage['since']} to {usage['to']}), demand x{grew:.1f}"
    return Reading(x, text, usage["to"], state=state)


def r_coverage_now(c: Context, ind: dict) -> Reading:
    s = _sums(c)
    if not s["need"]:
        return Reading(None, "no need yet: no capex placed")
    x = 100 * s["demand"] / s["need"]
    of_dep = 100 * s["demand"] / s["depreciation"] if s["depreciation"] else None
    state = "red" if of_dep is not None and of_dep < 100 else "amber" if x < 100 else "clear"
    la = c.bet["quarters"][c.bet["last_actual"]]
    text = f"{x:.0f}% of the need over the four quarters to {la}"
    if of_dep is not None:
        text += f"; {of_dep:.0f}% of depreciation alone"
    return Reading(x, text, la, state=state)


def r_payback(c: Context, ind: dict) -> Reading:
    s = _sums(c)
    if not s["need_total"]:
        return Reading(None, "no need yet: no capex placed")
    x = 100 * s["demand_total"] / s["need_total"]
    life, _, deflation = _defaults(c)
    when = c.bet["deadlines"][str(life)]["date"]
    price = "the trailing price change" if deflation == "trailing" else f"prices {float(deflation):+g}% a year"
    return Reading(x, f"{x:.0f}% by {when}, projected at {price}", c.bet["quarters"][c.bet["last_actual"]])


def r_tier1_share(c: Context, ind: dict) -> Reading:
    s = _sums(c)
    if not s["demand"]:
        return Reading(None, "no demand yet")
    x = 100 * s["direct"] / s["demand"]
    la = c.bet["quarters"][c.bet["last_actual"]]
    return Reading(x, f"{x:.0f}% of net demand over the four quarters to {la}", la)


def r_streak(c: Context, ind: dict) -> Reading:
    """Quarters in a row at zero or below, for each entity; the longest run counts."""
    worst, parts, used, last = 0, [], [], None
    for eid in ind["entities"]:
        found = _points(c.led, ind["series"], eid)
        run = 0
        for before, after in zip(reversed(found[:-1]), reversed(found)):
            if _shift(before.period, 1) != after.period or after.value > before.value:
                break
            run += 1
        if len(found) > 1 and _shift(found[-2].period, 1) == found[-1].period:
            label = c.led.series[ind["series"]].entities.get(eid, {}).get("label") or _label(c.led, eid)
            parts.append(f"{label} {found[-1].value - found[-2].value:+.1f} points in {found[-1].period}")
            used += found[-2:]
            last = max(last or found[-1].period, found[-1].period)
        worst = max(worst, run)
    if not parts:
        return Reading(None, "needs two quarters in a row")
    return Reading(worst, f"{_fmt(worst, ind['unit'])} at zero or below ({'; '.join(parts)})", last, used)


def r_trend(c: Context, ind: dict) -> Reading:
    found = _points(c.led, ind["series"], ind["entity"])
    if not found:
        return Reading(None, "no figure yet")
    last = found[-1]
    target = _shift(last.period, -ind["months"])
    then = next((p for p in found if p.period == target), None)
    if then is None:
        return Reading(None, f"needs {target} to compare with {last.period}", last.period, [last])
    x = last.value - then.value
    state = "red" if x < -ind["flat"] else "amber" if abs(x) <= ind["flat"] else "clear"
    return Reading(x, f"{_fmt(x, 'points')} from {target} to {last.period}", last.period, [then, last], state=state)


def r_falls(c: Context, ind: dict) -> Reading:
    """Conversion (paying over users) on each day both are counted; how many readings in a row it fell."""
    paying = {p.period: p for p in _points(c.led, ind["paying"]["series"], ind["paying"]["entity"])}
    users = {p.period: p for p in _points(c.led, ind["users"]["series"], ind["users"]["entity"])}
    days = sorted(set(paying) & set(users))
    if not days:
        return Reading(None, "needs paying users and users counted on the same day")
    rates = [paying[d].value / users[d].value for d in days]
    falls = 0
    for before, after in zip(reversed(rates[:-1]), reversed(rates)):
        if after >= before:
            break
        falls += 1
    text = f"{100 * rates[-1]:.1f}% on {days[-1]}"
    text += f", lower {_fmt(falls, 'readings in a row')}" if falls else (
        " (one reading so far)" if len(days) == 1 else f", not lower than on {days[-2]}")
    return Reading(falls, text, days[-1], [paying[days[-1]], users[days[-1]]])


RULES = {
    "level": r_level, "mean_last": r_mean_last, "change": r_change, "yoy": r_yoy, "capex_growth": r_capex_growth,
    "capex_to_ocf": r_capex_to_ocf, "guide_vs_actual": r_guide_vs_actual, "guidance_cuts": r_guidance_cuts,
    "below_high": r_below_high, "events": r_events, "ratings": r_ratings, "telecom_test": r_telecom_test,
    "coverage_now": r_coverage_now, "payback": r_payback, "tier1_share": r_tier1_share, "streak": r_streak,
    "trend": r_trend, "falls": r_falls,
}


# ---------------------------------------------------------------- paths and the regime


def evaluate(led: Ledger, bet: dict, prices, themes, today: dt.date) -> dict:
    """Every indicator, path and the regime, at your default settings, so they stay put while you explore."""
    c = Context(led, bet, prices, themes, today)
    signals = led.signals
    indicators = {}
    for iid, ind in signals["indicators"].items():
        r = RULES[ind["rule"]](c, ind)
        if r.state is None:
            r.state = NO_DATA if r.value is None else _state(ind, r.value)
        indicators[iid] = {
            "id": iid, "label": ind["label"], "path": ind["path"], "rule": ind["rule"],
            "trigger": bool(ind.get("trigger")), "state": r.state,
            "reading": None if r.value is None else round(float(r.value), 4), "unit": ind.get("unit", ""),
            "text": r.text, "as_of": r.as_of, "amber": ind.get("amber"), "red": ind.get("red"),
            "direction": ind.get("direction"), "why": " ".join(str(ind["why"]).split()), "mine": bool(ind.get("mine")),
            "ledger": [f"{p.series}/{p.entity}/{p.period}" for p in r.points],
            "sources": sorted({p.source for p in r.points if p.source}),
        }
    paths = {}
    for pid, p in signals["paths"].items():
        mine = [i for i in indicators.values() if i["path"] == pid]
        all_red = p.get("red_when_all_red") or []
        red = any(i["trigger"] and i["state"] == "red" for i in mine) or (
            bool(all_red) and all(indicators[i]["state"] == "red" for i in all_red))
        state = "red" if red else "amber" if any(i["state"] in ("amber", "red") for i in mine) else "clear"
        drivers = [i["id"] for i in sorted(mine, key=lambda i: not i["trigger"])
                   if state != "clear" and i["state"] in (("red",) if state == "red" else ("amber", "red"))]
        paths[pid] = {
            "id": pid, "label": p["label"], "kind": p["kind"], "about": p["about"], "state": state,
            "drivers": drivers, "counts": {s: sum(i["state"] == s for i in mine) for s in (*STATES, NO_DATA)},
            "themes": sorted({ch["id"].partition(":")[0] for ch in signals["channels"].get(pid, [])
                              if ch.get("kind") == "theme"}),
            "view_links": {v: links[pid] for v, links in (led.view_links or {}).items() if pid in links},
        }
    life, wacc, deflation = _defaults(c)
    return {"date": today.isoformat(), "indicators": indicators, "paths": paths,
            "regime": _regime(signals["regime"], paths),
            "at": {"gpu_life": life, "cost_of_capital": wacc, "deflation": deflation}}


def _regime(rules: list[dict], paths: dict) -> dict:
    """The first rule that holds: a crash path at or past its 'crash' level, or the adoption path at or past its
    'adoption' level. A rule with neither always holds."""
    for rule in rules:
        tests = [[pid for pid, p in paths.items() if p["kind"] == kind and RANK[p["state"]] >= RANK[rule[kind]]]
                 for kind in ("crash", "adoption") if rule.get(kind)]
        because = [pid for found in tests for pid in found]
        if not tests or because:
            return {"state": rule["state"], "label": rule["label"], "about": rule["about"], "because": because}
    return {"state": "absorbing", "label": "Absorbing", "about": "", "because": []}


# ---------------------------------------------------------------- what the morning keeps


def snapshot(signals: dict) -> dict:
    return {"regime": signals["regime"]["state"], "paths": {pid: p["state"] for pid, p in signals["paths"].items()},
            "indicators": {iid: i["state"] for iid, i in signals["indicators"].items()}}


def baseline(state: dict | None, today: dt.date) -> dict | None:
    """The last logged state to compare with. A second run on the same day compares with the state before it."""
    if not state:
        return None
    if state.get("date") == today.isoformat():
        return state.get("before")
    return {k: state[k] for k in ("regime", "paths", "indicators")}


def logged(signals: dict, state: dict | None, today: dt.date) -> dict:
    """What out/bet_state.json holds after today's finish."""
    return {"date": today.isoformat(), **snapshot(signals), "before": baseline(state, today)}


def changed(signals: dict, base: dict | None) -> bool:
    """Whether the regime or a path is in a new state since the last logged one."""
    if base is None:
        return False
    now = snapshot(signals)
    return now["regime"] != base["regime"] or any(now["paths"][p] != base["paths"].get(p) for p in now["paths"])


def payload_block(signals: dict, base: dict | None) -> dict:
    """The payload's bet block (spec 16): states, two shares as fractions, and the indicators that changed, as text.
    No dollar figures, no links, no money keys."""
    indicators = signals["indicators"].values()
    was = (base or {}).get("indicators", {})
    moved = [i for i in indicators if (i["state"] != was.get(i["id"]) if base else i["state"] in ("amber", "red"))]

    def share(rule: str) -> float | None:
        i = next((i for i in indicators if i["rule"] == rule), None)
        return None if i is None or i["reading"] is None else round(i["reading"] / 100, 3)

    return {
        "regime": {"now": signals["regime"]["state"], "last_logged": (base or {}).get("regime")},
        "paths": [{"id": pid, "label": p["label"], "now": p["state"],
                   "last_logged": (base or {}).get("paths", {}).get(pid)} for pid, p in signals["paths"].items()],
        "adoption_pace": next((p["state"] for p in signals["paths"].values() if p["kind"] == "adoption"), None),
        "coverage_now": share("coverage_now"),
        "payback_by_deadline": share("payback"),
        "changed": changed(signals, base),
        "indicators_changed": [{"id": i["id"], "label": i["label"], "path": i["path"], "state": i["state"],
                                "was": was.get(i["id"]), "reading": i["text"]} for i in moved],
        "at": "your default settings",
    }


def evidence(signals: dict, base: dict | None, open_views: set[str], today: dt.date) -> list[dict]:
    """One line for each path, and for the regime, in a new state since the last logged one (spec 16). A path
    getting worse counts for a view linked to it with 'for', and against it when it gets better."""
    if base is None:
        return []
    lines, indicators = [], signals["indicators"]
    flip = {"for": "against", "against": "for"}
    for pid, p in signals["paths"].items():
        was = base["paths"].get(pid)
        if was is None or was == p["state"]:
            continue
        worse = RANK[p["state"]] > RANK[was]
        if worse:
            shown = [indicators[i] for i in p["drivers"]]
            detail = "; ".join(f"{i['label']} {i['text']}, {i['state']} from {_level(i)}" for i in shown)
        else:
            shown = [i for i in indicators.values() if i["path"] == pid and i["state"] in STATES
                     and RANK[i["state"]] < RANK.get(base["indicators"].get(i["id"]), 0)]
            detail = "; ".join(f"{i['label']} {i['text']}" for i in shown) or f"no indicator {was} any more"
        lines.append({
            "date": today.isoformat(), "source": "signal",
            "what": f"{p['label']} path: {was} to {p['state']} ({detail})",
            "ledger": [r for i in shown for r in i["ledger"]],
            "sources": sorted({s for i in shown for s in i["sources"]}),
            "news_ids": [], "themes": p["themes"], "holdings": [],
            "views": [{"view_id": v, "effect": e if worse else flip[e],
                       "why": f"the {p['label'].lower()} path got {'worse' if worse else 'better'}"}
                      for v, e in sorted(p["view_links"].items()) if v in open_views],
        })
    if base["regime"] != signals["regime"]["state"]:
        r = signals["regime"]
        because = ", ".join(f"{signals['paths'][pid]['label'].lower()} {signals['paths'][pid]['state']}"
                            for pid in r["because"])
        lines.append({"date": today.isoformat(), "source": "signal",
                      "what": f"Regime: {base['regime']} to {r['state']}" + (f" ({because})" if because else ""),
                      "ledger": [], "sources": [], "news_ids": [], "themes": [], "holdings": [], "views": []})
    return lines


def _level(i: dict) -> str:
    level = i["red"] if i["state"] == "red" else i["amber"]
    return "its rule" if level is None else _fmt(float(level), i["unit"], i["unit"] == "pct" and level < 0)


def moves(before: dict | None, after: dict) -> list[str]:
    """What 'whatstocks bet' reports after it works the bet out again (spec 17), in Python's numbers: the regime,
    coverage now, payback by the deadline and the paths, each with what it was, then every indicator whose state or
    reading moved. With nothing before, where things stand."""
    old = (before or {}).get("indicators", {})

    def was(then: str | None, now: str) -> str:
        return f" (was {then})" if then is not None and then != now else ""

    def reading(i: dict | None) -> str | None:
        if i is None:
            return None
        return "no data" if i["reading"] is None else _fmt(i["reading"], i["unit"])

    def word(state: str | None) -> str | None:
        return None if state is None else state.replace("_", " ")

    regime = after["regime"]["label"]
    lines = [f"Regime: {regime}{was(before and before['regime']['label'], regime)}."]
    for rule, name in (("coverage_now", "Coverage now"), ("payback", "Payback by the deadline")):
        i = next((i for i in after["indicators"].values() if i["rule"] == rule), None)
        if i is not None:
            lines.append(f"{name}: {reading(i)}{was(reading(old.get(i['id'])), reading(i))}.")
    then = (before or {}).get("paths", {})
    lines.append("Paths: " + "; ".join(f"{p['label'].lower()} {p['state']}"
                                       f"{was(then.get(pid, {}).get('state'), p['state'])}"
                                       for pid, p in after["paths"].items()) + ".")
    if before is None:
        return lines
    moved = [i for iid, i in after["indicators"].items()
             if iid in old and (i["state"] != old[iid]["state"] or reading(i) != reading(old[iid]))]
    lines.append(f"Indicators that moved ({len(moved)}):" if moved else "No indicator moved.")
    for i in moved:
        o = old[i["id"]]
        lines.append(f"  - {i['label']}: {reading(i)}{was(reading(o), reading(i))}, "
                     f"{word(i['state'])}{was(word(o['state']), word(i['state']))}")
    return lines
