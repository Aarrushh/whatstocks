"""The panels of "Will the bet pay off?" that show the ledger itself (spec 5.1, 8, 17 and 18.1):

    funnel   adoption in layers (breadth, intensity, monetization), each measure's newest figure, and the leakage
             ratios between two measures
    pillars  your four starting points, each with its indicators, the series behind it, and two rows worked out here
             from two series each (free cash flow, and depreciation's share of operating cash flow)
    grades   how much of each curve rests on filed, company, press and estimated figures, at your default settings,
             and the judgments it rests on besides
    sources  each series, its newest figure, whether a newer one is due by its cadence, and the open gaps

Nothing here sees your holdings. No key is a money key (brief.MONEY_KEYS): a figure is 'figure', never 'value'."""
from __future__ import annotations

import calendar
import datetime as dt

from .fetch import EDGAR, FRED
from .ledger import GRADES, WORD_UNITS, Ledger, Point, Series

HISTORY = 12  # figures a pillar row keeps for its sparkline
INTERVAL = {"daily": 1, "weekly": 7, "monthly": 31, "quarterly": 92, "yearly": 366}  # days from one figure to the next
LAG = {"quarter": 45, "month": 30, "year": 90, "week": 3, "day": 3, "point": 7}  # days from a period's end to its figure
NEAR = 120  # days: two figures this close count as one moment, for a leakage ratio
YEAR_BACK = (300, 430)  # days: 'a year before' is the figure nearest 365 days back, within this window
WEAKER = {"fetched": 0, "filed": 0, "company": 1, "press": 2, "estimate": 3}
# The series bet/models.py reads by name, beside the ones model.yaml names (a test keeps this in step with the code).
CURVE_SERIES = ("shares_outstanding", "market_cap", "lab_revenue", "lab_revenue_annual", "lab_runrate", "ad_revenue",
                "lab_compute", "lab_inference_cost", "paying_users")
# The judgments each curve rests on besides its figures: parameters with basis 'judgment' are listed by label.
JUDGMENTS = {"need": ("ai_share", "short_lived_share", "running_costs"),
             "demand": ("vc_funded_share", "marketplace_cut", "ad_lift_share", "usage_half_life", "usage_floor"),
             "valuation": ("exit_multiple", "stack_profit_share")}
# The rows worked out from two series, and the two (ledger.DERIVED names the same rows: a test keeps them in step).
DERIVED_FROM = {"free_cash_flow": ("ocf", "capex_cash"), "depreciation_share": ("depreciation", "ocf")}


def build(led: Ledger, bet: dict, today: dt.date) -> dict:
    """The panels, from the ledger with the fetched figures merged in, and models.build's output."""
    return {"funnel": funnel(led), "pillars": pillars(led), "grades": grades(led, bet), "sources": sources(led, today)}


# ---------------------------------------------------------------- figures and their periods


def period_end(kind: str, period: str, fiscal_end: int | None = None) -> dt.date:
    """The last day a period covers: a quarter's or a month's, a year's (a fiscal year ends in the company's
    year-end month: Oracle's FY2027 on 2027-05-31), or the day itself."""
    if kind == "quarter":
        year, n = int(period[:4]), int(period[5])
        return dt.date(year, 3 * n, calendar.monthrange(year, 3 * n)[1])
    if kind == "month":
        year, month = int(period[:4]), int(period[5:7])
        return dt.date(year, month, calendar.monthrange(year, month)[1])
    if kind == "year":
        year = int(period.removeprefix("FY"))
        month = fiscal_end if period.startswith("FY") and fiscal_end else 12
        return dt.date(year, month, calendar.monthrange(year, month)[1])
    return dt.date.fromisoformat(period)


def _end(led: Ledger, s: Series, p: Point) -> dt.date:
    return period_end(s.period, p.period, led.entities.get(p.entity, {}).get("fiscal_year_end"))


def _ordered(led: Ledger, s: Series, eid: str) -> list[Point]:
    """An entity's figures that say something (a number, or a rating or an event's kind), oldest first by the day
    each period ends."""
    points = [p for p in s.points.get(eid, []) if p.value is not None or s.unit in WORD_UNITS]
    return sorted(points, key=lambda p: (_end(led, s, p), p.covers, p.agency))


def _r(x: float | None) -> float | None:
    return None if x is None else round(float(x), 4)


def _point(p: Point, unit: str) -> dict:
    out = {"figure": _r(p.value), "low": _r(p.low), "high": _r(p.high), "period": p.period, "grade": p.grade,
           "sources": [p.source] if p.source else [], "seen": p.seen.isoformat(), "mine": p.mine}
    if p.covers:
        out["covers"] = p.covers
    if unit in WORD_UNITS:
        out["word"] = f"{p.rating} ({p.agency})" if p.rating else p.kind.replace("_", " ")
    return out


def _name(led: Ledger, s: Series, eid: str) -> str:
    return (s.entities.get(eid) or {}).get("label") or led.entities.get(eid, {}).get("label") or eid


# ---------------------------------------------------------------- the funnel (spec 5.1)


def funnel(led: Ledger) -> dict:
    f = led.model.get("funnel") or {}
    return {"layers": [{"id": layer["id"], "label": layer["label"],
                        "measures": [_measure(led, m) for m in layer.get("measures") or []]}
                       for layer in f.get("layers") or []],
            "leakage": [_leakage(led, r) for r in f.get("leakage") or []]}


def _measure(led: Ledger, m: dict) -> dict:
    """A measure's newest figure, the one before it, and the one a year before, if the ledger has them."""
    s = led.series[m["series"]]
    ps = _ordered(led, s, m["entity"])
    out = {"series": s.id, "entity": m["entity"], "label": m["label"], "unit": s.unit, "now": None, "before": None,
           "year_ago": None}
    if ps:
        out["now"] = _point(ps[-1], s.unit)
        out["before"] = _point(ps[-2], s.unit) if len(ps) > 1 else None
        last, (lo, hi) = _end(led, s, ps[-1]), YEAR_BACK
        back = [p for p in ps[:-1] if lo <= (last - _end(led, s, p)).days <= hi]
        if back:
            out["year_ago"] = _point(min(back, key=lambda p: abs((last - _end(led, s, p)).days - 365)), s.unit)
    return out


def _leakage(led: Ledger, r: dict) -> dict:
    """One measure over another (paying users over weekly users), each figure of the first against the second's
    figure nearest in time, within NEAR days. The newest such pair, and the ratio of the pair before it."""
    of_s, per_s = led.series[r["of"]["series"]], led.series[r["per"]["series"]]
    pers = [p for p in _ordered(led, per_s, r["per"]["entity"]) if p.value]
    pairs = []
    for o in _ordered(led, of_s, r["of"]["entity"]):
        day = _end(led, of_s, o)
        near = [p for p in pers if abs((_end(led, per_s, p) - day).days) <= NEAR]
        if near and o.value is not None:
            pairs.append((o, min(near, key=lambda p: abs((_end(led, per_s, p) - day).days))))
    out = {"id": r["id"], "label": r["label"], "unit": of_s.unit, "ratio": None, "of": None, "per": None,
           "before": None}  # the check makes of and per share a unit
    if pairs:
        (o, p), before = pairs[-1], pairs[-2] if len(pairs) > 1 else None
        out.update(ratio=round(o.value / p.value, 6), of=_point(o, of_s.unit), per=_point(p, per_s.unit))
        if before:
            out["before"] = {"ratio": round(before[0].value / before[1].value, 6), "period": before[0].period}
    return out


# ---------------------------------------------------------------- the four pillars (spec 8)


def pillars(led: Ledger) -> list[dict]:
    derive = {"free_cash_flow": free_cash_flow, "depreciation_share": depreciation_share}
    return [{"id": p["id"], "label": p["label"], "indicators": list(p.get("indicators") or []),
             "rows": [_row(led, led.series[sid]) for sid in p.get("series") or []],
             "derived": [derive[d](led) for d in p.get("derived") or []]}
            for p in led.signals.get("pillars") or []]


def _row(led: Ledger, s: Series) -> dict:
    """A series: each entity's newest figure, with up to HISTORY figures before it for a sparkline."""
    entities = []
    for eid in s.points:
        ps = _ordered(led, s, eid)
        if ps:
            history = [] if s.unit in WORD_UNITS else [[p.period, _r(p.value)] for p in ps[-HISTORY:]]
            entities.append({"id": eid, "label": _name(led, s, eid), **_point(ps[-1], s.unit), "history": history})
    return {"id": s.id, "label": s.label, "unit": s.unit, "about": s.about, "derived": False, "entities": entities}


def _derived(led: Ledger, did: str, label: str, unit: str, about: str, a_sid: str, b_sid: str, f) -> dict:
    """A row worked out from two quarterly series, company by company, at each quarter both have: f(a, b). Its range
    takes f at the ends of both ranges; its grade is the weaker of the two, and it keeps both sources."""
    a_s, b_s = led.series.get(a_sid), led.series.get(b_sid)
    entities = []
    for eid in (a_s.points if a_s and b_s else {}):
        a = {p.period: p for p in a_s.points.get(eid, []) if p.value is not None}
        b = {p.period: p for p in b_s.points.get(eid, []) if p.value is not None}
        common = [q for q in sorted(set(a) & set(b)) if f(a[q].value, b[q].value) is not None]
        if not common:
            continue
        x, y = a[common[-1]], b[common[-1]]
        ends = [f(i, j) for i in {x.value if x.low is None else x.low, x.value if x.high is None else x.high}
                for j in {y.value if y.low is None else y.low, y.value if y.high is None else y.high}]
        ends = [e for e in ends if e is not None]
        ranged = any(v is not None for v in (x.low, x.high, y.low, y.high))
        entities.append({
            "id": eid, "label": _name(led, a_s, eid), "figure": _r(f(x.value, y.value)),
            "low": _r(min(ends)) if ranged else None, "high": _r(max(ends)) if ranged else None,
            "period": common[-1], "grade": max((x.grade, y.grade), key=lambda g: WEAKER.get(g, 3)),
            "sources": list(dict.fromkeys(s for s in (x.source, y.source) if s)),
            "seen": min(x.seen, y.seen).isoformat(), "mine": x.mine or y.mine,
            "history": [[q, _r(f(a[q].value, b[q].value))] for q in common[-HISTORY:]]})
    return {"id": did, "label": label, "unit": unit, "about": about, "derived": True, "entities": entities}


def free_cash_flow(led: Ledger) -> dict:
    return _derived(led, "free_cash_flow", "Free cash flow", "usd_b",
                    "Operating cash flow less cash capex, in the latest quarter both are known. Below zero, the "
                    "build-out is paid for with savings, borrowing or new shares.",
                    *DERIVED_FROM["free_cash_flow"], lambda o, c: o - c)


def depreciation_share(led: Ledger) -> dict:
    return _derived(led, "depreciation_share", "Depreciation's share of operating cash flow", "pct",
                    "Depreciation over operating cash flow, in the latest quarter both are known. It rises as the "
                    "fleets bought since 2023 are written off.",
                    *DERIVED_FROM["depreciation_share"], lambda d, o: 100 * d / o if o > 0 else None)


# ---------------------------------------------------------------- grades (spec 18.1, row 4)


def grades(led: Ledger, bet: dict) -> dict:
    """How much of each curve rests on each grade, at your default settings with the pieces switched on by default:
    each piece's mix of grades, weighted by its mean rate over the last four quarters. Python works this out once,
    so the panel says 'at your default settings' and stays put while you explore."""
    life, wacc, deflation = led.default("gpu_life"), led.default("cost_of_capital"), str(led.default("deflation"))
    cell = bet["capex"]["grid"][f"{life}|{wacc}"]
    step = bet["demand"]["grid"][deflation]["pieces"]
    need = [(p, cell[p["id"]]["readouts"]["rate"]["last4"]) for p in bet["capex"]["pieces"] if p["on"]]
    demand = [(p, step[p["id"]]["readouts"][str(life)]["rate"]["last4"]) for p in bet["demand"]["pieces"] if p["on"]]
    total = sum(w for _, w in demand)
    params = led.model["parameters"]
    return {
        "at": {"gpu_life": life, "cost_of_capital": wacc, "deflation": deflation},
        "need": _blend(need), "demand": _blend(demand),
        "tiers": [{"id": p["id"], "label": p["label"], "share": round(w / total, 4) if total else None,
                   "grades": p["grades"]} for p, w in demand],
        "judgments": {curve: [params[pid]["label"] for pid in ids if (params.get(pid) or {}).get("basis") == "judgment"]
                      for curve, ids in JUDGMENTS.items()},
    }


def _blend(rows: list[tuple[dict, float]]) -> dict[str, float]:
    total = sum(w for p, w in rows if p["grades"])
    if not total:
        return {}
    return {g: round(sum(w * p["grades"].get(g, 0.0) for p, w in rows if p["grades"]) / total, 4) for g in GRADES}


# ---------------------------------------------------------------- sources and staleness (spec 17 and 18.1, row 8)


def sources(led: Ledger, today: dt.date) -> dict:
    """Each series with its newest figure and the companies whose newer figure is due, ranked for /bet: due first,
    then what feeds the two curves, then the most indicators, then the panels. A figure is due once its period's end,
    plus the series' interval and the usual lag to publication, has passed. Irregular series are never due, nor a
    closed record that only the analogs use. The open gaps come with it, ranked the same way."""
    feeds = uses(led)
    rows = []
    for sid, s in led.series.items():
        f = feeds[sid]
        closed = f["panels"] == ["analogs"] and not (f["curves"] or f["indicators"])
        newest, due, count = None, [], 0
        for eid in s.points:
            ps = _ordered(led, s, eid)
            if not ps:
                continue
            count += len(ps)
            last = ps[-1]
            if newest is None or (_end(led, s, last), last.seen) > (_end(led, s, newest), newest.seen):
                newest = last
            if s.cadence in INTERVAL and not closed:
                expected = _end(led, s, last) + dt.timedelta(days=INTERVAL[s.cadence] + LAG.get(s.period, 0))
                if today > expected:
                    due.append({"id": eid, "label": _name(led, s, eid), "period": last.period,
                                "expected": expected.isoformat()})
        rows.append({
            "id": sid, "label": s.label, "unit": s.unit, "cadence": s.cadence, "period": s.period,
            "entities": sum(1 for eid in s.points if _ordered(led, s, eid)), "points": count,
            "newest": None if newest is None else {"entity": newest.entity, "label": _name(led, s, newest.entity),
                                                   **_point(newest, s.unit)},
            "due": sorted(due, key=lambda d: d["expected"]), "closed": closed, "fetcher": fetcher(sid), "feeds": f})
    gaps = [{"series": g.get("series"), "entity": g.get("entity"), "what": " ".join(str(g.get("what")).split()),
             "label": led.series[g["series"]].label if g.get("series") in led.series else None,
             "name": _gap_name(led, g),
             "feeds": feeds.get(g.get("series")) or {"curves": False, "indicators": [], "panels": []}}
            for g in led.gaps]
    return {"rows": sorted(rows, key=lambda r: (not r["due"], *_weight(r["feeds"]), r["label"].lower())),
            "gaps": sorted(gaps, key=lambda g: _weight(g["feeds"]))}


def _weight(f: dict) -> tuple:
    return not f["curves"], -len(f["indicators"]), not f["panels"]


def _gap_name(led: Ledger, g: dict) -> str | None:
    """The company or item a gap is about, by name (Nebius, not nbis)."""
    eid = g.get("entity")
    if not eid:
        return None
    s = led.series.get(g.get("series"))
    return _name(led, s, str(eid)) if s else led.entities.get(eid, {}).get("label") or str(eid)


def fetcher(sid: str) -> str | None:
    """The code that fills a series from the source itself, if any (bet/fetch.py)."""
    if any(sid == s for s, _ in FRED.values()):
        return "FRED"
    if sid in EDGAR:
        return "EDGAR"
    return "Yahoo" if sid == "shares_outstanding" else None


def uses(led: Ledger) -> dict[str, dict]:
    """What each series feeds: the two curves, which indicators, and which panels (funnel, pillars, analogs)."""
    out = {sid: {"curves": False, "indicators": [], "panels": []} for sid in led.series}

    def panel(sid, name: str) -> None:
        if sid in out and name not in out[sid]["panels"]:
            out[sid]["panels"].append(name)

    for sid in curve_series(led):
        if sid in out:
            out[sid]["curves"] = True
    capex = led.model.get("capex") or {}
    for iid, ind in (led.signals.get("indicators") or {}).items():
        for sid in indicator_series(ind, capex.get("basis") or {}, capex.get("groups") or {}):
            if sid in out and iid not in out[sid]["indicators"]:
                out[sid]["indicators"].append(iid)
    f = led.model.get("funnel") or {}
    for layer in f.get("layers") or []:
        for m in layer.get("measures") or []:
            panel(m["series"], "funnel")
    for r in f.get("leakage") or []:
        panel(r["of"]["series"], "funnel")
        panel(r["per"]["series"], "funnel")
    for p in led.signals.get("pillars") or []:
        for sid in [*(p.get("series") or []), *(s for d in p.get("derived") or [] for s in DERIVED_FROM[d])]:
            panel(sid, "pillars")
    for a in (led.events.get("analogs") or {}).values():
        for ref in a.get("series") or []:
            panel(str(ref).partition(".")[0], "analogs")
    return out


def curve_series(led: Ledger) -> set[str]:
    """The series Model A and Model B read: the ones bet/models.py names, and the ones model.yaml points at."""
    m = led.model
    capex, valuation = m.get("capex") or {}, m.get("valuation") or {}
    usage = (m.get("demand") or {}).get("usage") or {}
    out = set(CURVE_SERIES) | set((capex.get("basis") or {}).values())
    out |= {capex.get("guidance"), capex.get("short_lived"), usage.get("series"), (usage.get("check") or {}).get("series")}
    for g in [*(capex.get("groups") or {}).values(), *(valuation.get("groups") or {}).values()]:
        out |= set(g["series"]) if isinstance(g.get("series"), list) else {g.get("series")}
    for p in [*(m.get("parameters") or {}).values(), *(m.get("sliders") or {}).values()]:
        if isinstance(p.get("from"), dict):
            out.add(p["from"].get("series"))
    out |= {(ref or {}).get("series") for ref in (m.get("pool") or {}).values()}
    return {s for s in out if isinstance(s, str) and s}


def indicator_series(ind: dict, basis: dict, groups: dict) -> list[str]:
    """The series an indicator reads, from its settings in signals.yaml: its series, the actual a guide meets, the
    two measures of a ratio, a stand-in, and the capex and cash flow the capex rules read."""
    out = [ind.get("series"), ind.get("actual"), *(v.get("series") for v in ind.values() if isinstance(v, dict))]
    if ind.get("rule") == "capex_to_ocf":
        out += ["capex_cash", "ocf"]
    if ind.get("rule") == "capex_growth":
        out += [basis.get(eid) for gid in ind.get("groups") or [] for eid in (groups.get(gid) or {}).get("members") or []]
    return [s for s in dict.fromkeys(out) if isinstance(s, str) and s]
