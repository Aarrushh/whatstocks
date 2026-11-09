"""Models A and B of "Will the bet pay off?" (spec sections 4 to 7), and the grid the page picks from.

Model A, the money invested:
    capex payback  what the AI capex placed must earn a year (depreciation + return on capital + running costs),
                   divided by the compute share to put it in end users' dollars (spec 4.1)
    valuation      what today's market values assume end users will pay by the deadline (spec 4.2)
Model B, adoption: what end users pay, in tiers by quality and net, then projected as usage x price per unit (spec 5)

Every rate is $B a year in end users' dollars, quarter by quarter from 2023Q1 to 2033Q4. Each step of each slider is
worked out for each piece, so the page only adds the pieces you leave on and divides two sums for a coverage ratio
(spec P2 exception b). Nothing here sees your holdings. No key is a money key (brief.MONEY_KEYS): the page's render
test forbids them."""
from __future__ import annotations

import datetime as dt

import numpy as np
import pandas as pd

from .fetch import quarter_of
from .ledger import Ledger, Point, _text

FIRST, LAST = 2023, 2033
QUARTERS = [f"{y}Q{n}" for y in range(FIRST, LAST + 1) for n in range(1, 5)]
INDEX = {q: i for i, q in enumerate(QUARTERS)}
N = len(QUARTERS)
GRADES = ("filed", "company", "press", "estimate")
VARIANTS = ("value", "low", "high")  # a parameter's value and its range, as ledger.param gives them
SECONDS_A_YEAR = 365.25 * 24 * 3600
LISTED_GRACE = 7  # days: a stock with no close this close to the start date listed after it


# ---------------------------------------------------------------- quarters and figures


def q_start(q: str) -> dt.date:
    return dt.date(int(q[:4]), 3 * int(q[5]) - 2, 1)


def q_end(q: str) -> dt.date:
    year, n = int(q[:4]), int(q[5])
    return dt.date(year, 12, 31) if n == 4 else dt.date(year, 3 * n + 1, 1) - dt.timedelta(days=1)


def q_mid(q: str) -> dt.date:
    return q_start(q) + (q_end(q) - q_start(q)) / 2


def covered(covers: str, fiscal_end: int | None = None) -> list[str]:
    """The calendar quarters a year covers. 2026 is calendar 2026. FY2027 is the four quarters ending in the company's
    fiscal year-end month of 2027, each counted in the calendar quarter it ends in (Oracle's FY2027, ending in May,
    is 2026Q3 to 2027Q2)."""
    if not covers.startswith("FY"):
        return [f"{int(covers)}Q{n}" for n in range(1, 5)]
    year, end = int(covers[2:]), fiscal_end or 12
    out = []
    for back in (9, 6, 3, 0):
        month, y = end - back, year
        if month < 1:
            month, y = month + 12, year - 1
        out.append(f"{y}Q{(month - 1) // 3 + 1}")
    return out


def grade(p: Point | None) -> str:
    """The grade a figure counts under on the page: one the code fetched is a filing or an official statistic."""
    if p is None:
        return "estimate"
    return "filed" if p.grade == "fetched" else p.grade if p.grade in GRADES else "estimate"


def _pct(p: dict) -> dict[str, float]:
    return {v: p[v] / 100 for v in VARIANTS}


def _by_year(led: Ledger, ref: dict, year: int) -> float | None:
    """A yearly figure for a year: that year's, else the latest year before it. None before the first figure: an
    earlier year is never filled in from a later one."""
    s = led.series.get(ref["series"])
    known = {int(_text(p.period)[-4:]): p.value for p in (s.points.get(ref["entity"], []) if s else [])
             if p.value is not None}
    past = [y for y in known if y <= year]
    return known[max(past)] if past else None


def last_actual(led: Ledger, today: dt.date) -> int:
    """The latest quarter every hyperscaler has filed capex for, and never the quarter today is in."""
    capex = led.model["capex"]
    ends = []
    for eid in capex["groups"].get("hyperscalers", {}).get("members", []):
        s = led.series.get(capex["basis"].get(eid, ""))
        filed = [p.period for p in (s.points.get(eid, []) if s and s.period == "quarter" else [])]
        if filed:
            ends.append(max(filed))
    cap = INDEX.get(quarter_of(today), N) - 1
    return min(INDEX.get(min(ends), cap), cap) if ends else cap


def deadline(life: int) -> dict:
    """The depreciation clock (spec 4.3): the fleets of 2024, 2025 and 2026 are written off in 2024+L to 2026+L.
    The readouts use the end of 2025+L."""
    return {"quarter": INDEX.get(f"{2025 + life}Q4", N - 1),
            "band": [INDEX.get(f"{2024 + life}Q1", N - 1), INDEX.get(f"{2026 + life}Q4", N - 1)],
            "date": dt.date(2025 + life, 12, 31).isoformat()}


# ---------------------------------------------------------------- Model A: the capex placed


def capex_placed(led: Ledger, eid: str) -> dict[str, tuple[float, str, str]]:
    """A company's capex by quarter, on the basis it states and guides on, as (amount, grade, kind). First the
    quarters it filed; then the rest of each guided year, spread evenly over that year's quarters not yet filed.
    After its last guided quarter nothing more is placed: the curve shows what the bet already placed needs."""
    capex = led.model["capex"]
    s = led.series.get(capex["basis"].get(eid, ""))
    out: dict[str, tuple[float, str, str]] = {}
    for p in (s.points.get(eid, []) if s else []):
        if p.value is None:
            continue
        if s.period == "quarter":
            out[p.period] = (p.value, grade(p), "filed")
        elif s.period == "year":  # a lab's build for a year: spread evenly over it
            for q in covered(_text(p.period).removeprefix("FY")):
                out.setdefault(q, (p.value / 4, grade(p), "guided"))
    guide = led.series.get(capex.get("guidance", ""))
    latest: dict[str, Point] = {}
    for p in (guide.points.get(eid, []) if guide else []):
        if p.covers and p.value is not None and (p.covers not in latest or p.period >= latest[p.covers].period):
            latest[p.covers] = p
    fiscal_end = led.entities.get(eid, {}).get("fiscal_year_end")
    for covers in sorted(latest):
        p, quarters = latest[covers], covered(covers, fiscal_end)
        open_ = [q for q in quarters if q not in out]
        if open_:
            rest = max(0.0, p.value - sum(out[q][0] for q in quarters if q in out))
            for q in open_:
                out[q] = (rest / len(open_), grade(p), "guided")
    return out


def consensus_placed(led: Ledger, group: dict, placed: dict[str, dict]) -> dict[str, dict[str, tuple]]:
    """Analysts' capex for a year, beyond what each company has filed and guided for it, spread evenly over the
    year's quarters not yet placed."""
    s = led.series.get(group["series"])
    out: dict[str, dict[str, tuple]] = {}
    for eid, points in (s.points.items() if s else []):
        for p in points:
            year = _text(p.period).removeprefix("FY")
            if p.value is None or (group.get("for") and year != _text(group["for"])):
                continue
            mine, quarters = placed.get(eid, {}), covered(year)
            open_ = [q for q in quarters if q not in mine]
            rest = max(0.0, p.value - sum(mine[q][0] for q in quarters if q in mine))
            for q in open_:
                out.setdefault(eid, {})[q] = (rest / len(open_), grade(p), "consensus")
    return out


def group_capex(led: Ledger, members: dict[str, dict[str, tuple]], variant: str) -> tuple[np.ndarray, np.ndarray]:
    """A group's AI capex by quarter, short-lived and long-lived, under one variant of the parameters: the AI share
    of each company, and the short-lived share it states for a quarter (else the shipped estimate)."""
    short, long = np.zeros(N), np.zeros(N)
    stated = led.series.get(led.model["capex"].get("short_lived", ""))
    default_short = led.param("short_lived_share")[variant] / 100
    for eid, placed in members.items():
        ai = led.param("ai_share", eid)[variant] / 100
        for q, (amount, _, _) in placed.items():
            i = INDEX.get(q)
            if i is None:
                continue
            sp = stated.get(eid, q) if stated else None
            share = sp.value / 100 if sp is not None and sp.value is not None else default_short
            short[i] += amount * ai * share
            long[i] += amount * ai * (1 - share)
    return short, long


def schedule(short: np.ndarray, long: np.ndarray, life: float, long_life: float, wacc: float,
             running: float) -> dict[str, np.ndarray]:
    """What one stream of capex must earn, as rates a year by quarter, the way a regulator sets a utility's revenue
    requirement (spec 4.1). Capex placed in a quarter counts from that quarter: it depreciates straight-line
    (short-lived assets over the GPU life, long-lived over long_life), earns the cost of capital on what is not yet
    depreciated, and costs running costs on what is still in service."""
    n = len(short)
    dep, gross = np.zeros(n), np.zeros(n)
    for i in range(n):
        for amount, years in ((short[i], life), (long[i], long_life)):
            if amount:
                j = min(n, i + round(4 * years))
                dep[i:j] += amount / years
                gross[i:j] += amount
    written = np.cumsum(dep / 4) - dep / 4  # depreciation through the quarter before
    net = np.cumsum(short + long) - written
    return {"depreciation": dep, "return": wacc * net, "running": running * gross}


# ---------------------------------------------------------------- Model A: what the market values assume


def _close_on(closes: pd.Series, day: dt.date) -> float | None:
    """The close on a day, or the last before it; None if the stock had not listed by then."""
    if closes.empty:
        return None
    before = closes[closes.index <= pd.Timestamp(day)]
    if before.empty or (pd.Timestamp(day) - before.index[-1]).days > LISTED_GRACE:
        return None
    return float(before.iloc[-1])


def valuation(led: Ledger, prices, notes: list[str]) -> dict:
    """The AI value priced in (spec 4.2), group by group, in $B. A public company counts for its market value now
    times the part of its gain since the start (ChatGPT's launch) that beat the world index: market value x
    (1 - (1 + world return) / (1 + its return)). One that listed since counts whole; one that lagged the index adds
    nothing. The labs count at their latest private valuation, with its range."""
    v = led.model["valuation"]
    start = v["start"]
    world = prices.series(v["world"])
    w0, w1 = _close_on(world, start), (float(world.iloc[-1]) if len(world) else None)
    if w0 is None or w1 is None:
        notes.append(f"No prices for the world index ({v['world']}): each company counts whole.")
    shares, caps = led.series.get("shares_outstanding"), led.series.get("market_cap")
    groups, companies = {}, []
    for gid, g in v["groups"].items():
        total = {k: 0.0 for k in VARIANTS}
        if g.get("series"):  # the labs
            s = led.series.get(g["series"])
            for eid in g["members"]:
                p = s.latest(eid) if s else None
                if p is None or p.value is None:
                    notes.append(f"No valuation for {led.entities.get(eid, {}).get('label', eid)} yet: it adds nothing.")
                    continue
                for k, x in zip(VARIANTS, (p.value, p.low, p.high)):
                    total[k] += p.value if x is None else x
                companies.append({"id": eid, "group": gid, "market": p.value, "added": p.value, "kept": 1.0,
                                  "basis": "private round", "date": p.period, "grade": grade(p), "source": p.source})
        else:
            for eid in g["members"]:
                symbol = led.entities[eid]["symbol"]
                closes = prices.series(symbol)
                count = shares.latest(eid) if shares else None
                if count is not None and len(closes):
                    market, basis, source = count.value * float(closes.iloc[-1]), "shares x price", count.source
                elif caps and caps.latest(eid) is not None:
                    cap = caps.latest(eid)
                    market, basis, source = cap.value, "market value in the ledger", cap.source
                else:
                    notes.append(f"No market value for {symbol}: it adds nothing.")
                    continue
                p0 = _close_on(closes, start)
                if p0 is None or w0 is None or w1 is None:
                    kept = 1.0  # listed since the start, or no index to compare with
                else:
                    kept = max(0.0, 1 - (w1 / w0) / (float(closes.iloc[-1]) / p0))
                for k in VARIANTS:
                    total[k] += market * kept
                companies.append({"id": eid, "group": gid, "symbol": symbol, "market": round(market, 3),
                                  "added": round(market * kept, 3), "kept": round(kept, 4), "basis": basis,
                                  "listed_since": p0 is None, "source": source})
        groups[gid] = {"label": g["label"], "on": g["enabled"], "worth": round(total["value"], 3),
                       "low": round(total["low"], 3), "high": round(total["high"], 3)}
    return {"start": start.isoformat(), "world": v["world"], "groups": groups, "companies": companies}


def targets(led: Ledger, groups: dict, life: int, wacc: float, today: dt.date) -> dict:
    """R_T for each group: E_T = V x (1 + r)^(T - today) / exit multiple; R_T = E_T / stack profit share. The low end
    takes the high multiple and share, the high end the low ones. Linear in V, so the groups add up."""
    years = (dt.date(2025 + life, 12, 31) - today).days / 365.25
    grow = (1 + wacc) ** years
    m, s = led.param("exit_multiple"), _pct(led.param("stack_profit_share"))
    return {gid: {"target": round(g["worth"] * grow / (m["value"] * s["value"]), 3),
                  "low": round(g["low"] * grow / (m["high"] * s["high"]), 3),
                  "high": round(g["high"] * grow / (m["low"] * s["low"]), 3)} for gid, g in groups.items()}


# ---------------------------------------------------------------- Model B: what end users pay


def runrate_points(led: Ledger, lab: str) -> list[tuple[dt.date, float, Point]]:
    s = led.series.get("lab_runrate")
    return sorted(((dt.date.fromisoformat(p.period), p.value, p) for p in (s.points.get(lab, []) if s else [])
                   if p.value is not None), key=lambda r: r[0])


def runrate_at(points: list[tuple[dt.date, float, Point]], day: dt.date) -> float | None:
    """The run-rate on a day, straight between the dated figures, never beyond the first or the last."""
    if not points or day < points[0][0] or day > points[-1][0]:
        return None
    for (d0, v0, _), (d1, v1, _) in zip(points, points[1:]):
        if d0 <= day <= d1:
            return v0 if d1 == d0 else v0 + (v1 - v0) * (day - d0).days / (d1 - d0).days
    return points[-1][1]


def lab_quarters(led: Ledger, lab: str) -> dict[str, tuple[float, str]]:
    """A lab's revenue by quarter ($B in the quarter) and the grade of what it rests on. Recognized quarterly revenue
    first. Then the rest of a recognized year, spread over its other quarters by the run-rate's shape (evenly
    without one). Then the run-rate itself: the mean of its level at the quarter's start, middle and end, a quarter
    of it, using only the dates the run-rate figures span."""
    out: dict[str, tuple[float, str]] = {}
    s = led.series.get("lab_revenue")
    for p in (s.points.get(lab, []) if s else []):
        if p.value is not None:
            out[p.period] = (p.value, grade(p))
    rr = runrate_points(led, lab)
    annual = led.series.get("lab_revenue_annual")
    for p in (annual.points.get(lab, []) if annual else []):
        quarters = covered(_text(p.period).removeprefix("FY"))
        open_ = [q for q in quarters if q not in out]
        if p.value is None or not open_:
            continue
        rest = max(0.0, p.value - sum(out[q][0] for q in quarters if q in out))
        weights = [runrate_at(rr, q_mid(q)) for q in open_]
        if any(w is None for w in weights) or not sum(weights):
            weights = [1.0] * len(open_)
        for q, w in zip(open_, weights):
            out[q] = (rest * w / sum(weights), grade(p))
    for q in QUARTERS:
        if q in out:
            continue
        levels = [x for x in (runrate_at(rr, d) for d in (q_start(q), q_mid(q), q_end(q))) if x is not None]
        if levels:
            nearest = min(rr, key=lambda r: abs((r[0] - q_mid(q)).days))[2]
            out[q] = (sum(levels) / len(levels) / 4, grade(nearest))
    return out


def _yearly(led: Ledger, sid: str, entity: str) -> dict[int, Point]:
    s = led.series.get(sid)
    return {int(_text(p.period).removeprefix("FY")): p for p in (s.points.get(entity, []) if s else [])
            if p.value is not None}


def demand_actuals(led: Ledger, la: int, notes: list[str]) -> tuple[dict, dict]:
    """Each Model B piece's actual rates ($B a year) through the last actual quarter, as value, low and high, and the
    mix of grades its dollars rest on (spec 5.2 and 5.3)."""
    d = led.model["demand"]
    cs = led.param("compute_share")["value"] / 100
    vc, cut = _pct(led.param("vc_funded_share")), _pct(led.param("marketplace_cut"))
    pieces = {pid: {k: np.zeros(N) for k in VARIANTS} for pid in [*d["tiers"], "free_users"]}
    weights: dict[str, dict[str, float]] = {pid: {} for pid in pieces}

    def weigh(pid: str, g: str, amount: float) -> None:
        weights[pid][g] = weights[pid].get(g, 0.0) + amount

    gross, marketplace = np.zeros(N), np.zeros(N)
    revenue = {}
    for lab in d["labs"]:
        revenue[lab] = lab_quarters(led, lab)
        for q, (amount, g) in revenue[lab].items():
            i = INDEX.get(q)
            if i is not None and i <= la:
                gross[i] += 4 * amount
                if lab in (d.get("marketplace_gross") or []):
                    marketplace[i] += 4 * amount
                weigh("direct", g, amount)
                weigh("vc_funded", "estimate", amount)  # carved out by a judgment
    # Tier 1 keeps what is left after the venture-funded carve-out. Its low end also takes off the cloud partners'
    # cut of the sales a lab reports gross; its high end is gross.
    pieces["direct"] = {"value": gross * (1 - vc["value"]), "low": gross * (1 - vc["high"]) - marketplace * cut["high"],
                        "high": gross * (1 - vc["low"])}
    pieces["vc_funded"] = {k: gross * vc[k] for k in VARIANTS}
    notes.append("Tier 2 (bundled) has no figures yet: the ledger has no AI-led price rise.")
    ads, lift = led.series.get("ad_revenue"), _pct(led.param("ad_lift_share"))
    for points in (ads.points.values() if ads else []):
        for p in points:
            i = INDEX.get(p.period)
            if i is not None and i <= la and p.value is not None:
                for k in VARIANTS:
                    pieces["ad_lift"][k][i] += 4 * p.value * lift[k]
                weigh("ad_lift", "estimate", p.value * lift["value"])
    compute = led.series.get("lab_compute")
    for lab in d["labs"]:
        for p in (compute.points.get(lab, []) if compute else []):
            i, rev = INDEX.get(p.period), revenue.get(lab, {}).get(p.period)
            if i is None or i > la or rev is None or p.value is None:
                continue
            # Only compute beyond what revenue pays for counts, at its end-user equivalent (spec 5.2, tier 5).
            excess = max(0.0, p.value - cs * rev[0]) / cs
            for k in VARIANTS:
                pieces["investor_compute"][k][i] += 4 * excess
            weigh("investor_compute", grade(p), excess)
    free_share = led.param("free_user_share")["value"] / 100
    for lab in d["labs"]:
        for year, p in _yearly(led, "lab_inference_cost", lab).items():
            for q in covered(str(year)):
                i = INDEX.get(q)
                if i is not None and i <= la:
                    for k in VARIANTS:
                        pieces["free_users"][k][i] += p.value * free_share / cs
                    weigh("free_users", grade(p), p.value * free_share / cs / 4)
    for arrays in pieces.values():
        arrays["low"] = np.minimum(arrays["low"], arrays["value"])
        arrays["high"] = np.maximum(arrays["high"], arrays["value"])
    return pieces, {pid: _mix(w) for pid, w in weights.items()}


def _mix(weights: dict[str, float]) -> dict[str, float]:
    total = sum(weights.values())
    return {g: round(weights.get(g, 0.0) / total, 4) for g in GRADES} if total else {}


def usage_growth(led: Ledger) -> dict:
    """The token index's trailing yearly growth (spec 5.4): the latest figure against the one nearest a year before
    it (300 to 430 days), annualized; and the check series' growth over whatever span it has."""
    u = led.model["demand"]["usage"]

    def points(sid: str, entity: str) -> list[tuple[dt.date, float]]:
        s = led.series.get(sid)
        return sorted((dt.date.fromisoformat(p.period), p.value) for p in (s.points.get(entity, []) if s else [])
                      if p.value)

    main = points(u["series"], u["entity"])
    out = {"series": u["series"], "entity": u["entity"], "growth": None}
    if main:
        d1, v1 = main[-1]
        before = [(d, v) for d, v in main if 300 <= (d1 - d).days <= 430]
        if before:
            d0, v0 = min(before, key=lambda r: abs((d1 - r[0]).days - 365))
            out.update(growth=round((v1 / v0) ** (365.25 / (d1 - d0).days) - 1, 4), since=d0.isoformat(),
                       to=d1.isoformat())
    check = points(u["check"]["series"], u["check"]["entity"]) if u.get("check") else []
    if len(check) > 1 and (check[-1][0] - check[0][0]).days >= 180:
        (d0, v0), (d1, v1) = check[0], check[-1]
        out["check"] = {"series": u["check"]["series"], "entity": u["check"]["entity"], "since": d0.isoformat(),
                        "to": d1.isoformat(), "growth": round((v1 / v0) ** (365.25 / (d1 - d0).days) - 1, 4)}
    return out


def trailing_deflation(pieces: dict, on: set[str], la: int, growth: float | None) -> float | None:
    """The realized change in price per unit over the last year: last year's demand growth over last year's token
    growth (spec 5.4). Like for like: only pieces with demand in both quarters count."""
    if growth is None or la < 4:
        return None
    both = [p for p in on if pieces[p]["value"][la - 4] > 0]
    now = sum(pieces[p]["value"][la] for p in both)
    then = sum(pieces[p]["value"][la - 4] for p in both)
    return (now / then) / (1 + growth) - 1 if then else None


def project(pieces: dict, la: int, growth: float, floor: float, half_life: float, deflation: float) -> dict:
    """Demand after the last actual quarter = usage x price per unit (spec 5.4). Usage grows at the trailing rate,
    halving its excess over the floor every half-life (years); price per unit changes at the deflation rate. Each
    piece keeps its share of the last four quarters, and its range relative to its value there."""
    window = slice(max(0, la - 3), la + 1)
    totals = np.zeros(N)
    totals[la] = sum(p["value"][la] for p in pieces.values())
    for i in range(la + 1, N):
        t = (i - la - 1) / 4
        g = floor + (growth - floor) * 0.5 ** (t / half_life)
        totals[i] = totals[i - 1] * ((1 + g) * (1 + deflation)) ** 0.25
    last4 = {pid: p["value"][window].sum() for pid, p in pieces.items()}
    everything = sum(last4.values())
    out = {}
    for pid, p in pieces.items():
        share = last4[pid] / everything if everything else 0.0
        arrays = {k: p[k].copy() for k in VARIANTS}
        arrays["value"][la + 1:] = share * totals[la + 1:]
        for k in ("low", "high"):
            ratio = p[k][window].sum() / last4[pid] if last4[pid] else 1.0
            arrays[k][la + 1:] = arrays["value"][la + 1:] * ratio
        out[pid] = arrays
    return out


# ---------------------------------------------------------------- the grid


def _round(a: np.ndarray) -> list[float]:
    return [round(float(x), 3) for x in a]


def readouts(arrays: dict[str, np.ndarray], la: int, dl: int) -> dict:
    """A piece's three readouts in dollars (spec 7): the mean rate over the last four quarters, the rate at the
    deadline, and the total from 2023 to the deadline ($B: the quarters' rates over four, added up)."""
    window = slice(max(0, la - 3), la + 1)
    return {("rate" if k == "value" else k): {"last4": round(float(arrays[k][window].mean()), 3),
                                              "at_deadline": round(float(arrays[k][dl]), 3),
                                              "to_deadline": round(float(arrays[k][:dl + 1].sum() / 4), 3)}
            for k in VARIANTS}


def _cell(arrays: dict[str, np.ndarray], la: int, dl: int) -> dict:
    return {"rate": _round(arrays["value"]), "low": _round(arrays["low"]), "high": _round(arrays["high"]),
            "readouts": readouts(arrays, la, dl)}


def units(led: Ledger) -> dict:
    """The adoption units and the budget pool (spec 6), as factors by quarter that turn $B a year of end-user dollars
    into each unit, for each step of the slider it depends on. So the page multiplies a sum it already has by a
    number worked out here:
        seats  paying-seat equivalents, in millions = $B a year x seats (1000 / revenue per paying seat)
        gain   the productivity gain implied, $B a year = $B a year x gain[value capture] (100 / value capture)
        hours  the share of work hours that must use AI = $B a year x hours[value capture][quarter]
               (the gain / labour pay / the uplift of an AI-assisted hour; low takes the high uplift)
        pool   the budget pool, $B a year = pool[labour share][quarter] (IT spend x (1 - w) + labour pay x w)
    A quarter whose year has no figure, and none before it, is None. The inputs, by year in $T, are kept to show."""
    sliders, refs = led.model["sliders"], led.model["pool"]
    years = list(range(FIRST, LAST + 1))
    it = [_by_year(led, refs["it_spending"], y) for y in years]
    gdp = [_by_year(led, refs["gdp"], y) for y in years]
    share = [_by_year(led, refs["labour_share"], y) for y in years]
    labour = [None if g is None or s is None else round(g * s / 100, 3) for g, s in zip(gdp, share)]
    by_quarter = {y: i for i, y in enumerate(years)}
    it_q, labour_q = ([xs[by_quarter[int(q[:4])]] for q in QUARTERS] for xs in (it, labour))
    uplift = _pct(led.param("hour_uplift"))
    seat = seat_revenue(led)

    def pool(w: float) -> list[float | None]:
        return [None if (w < 100 and i is None) or (w > 0 and lab is None)
                else round(((i or 0.0) * (100 - w) + (lab or 0.0) * w) * 10, 3) for i, lab in zip(it_q, labour_q)]

    def hours(vc: float, up: float) -> list[float | None]:
        return [None if lab is None else round(100 / vc / (lab * 1000 * up), 9) for lab in labour_q]

    return {
        "seat": seat,
        "seats": None if seat is None else round(1000 / seat["dollars"], 6),
        "gain": {str(vc): round(100 / vc, 6) for vc in sliders["value_capture"]["steps"]},
        "hours": {str(vc): {"rate": hours(vc, uplift["value"]), "low": hours(vc, uplift["high"]),
                            "high": hours(vc, uplift["low"])} for vc in sliders["value_capture"]["steps"]},
        "pool": {str(w): pool(w) for w in sliders["labour_share"]["steps"]},
        "hour_uplift": led.param("hour_uplift")["value"],
        "inputs": {"years": years, "it": it, "labour": labour},
    }


def seat_revenue(led: Ledger) -> dict | None:
    """Revenue per paying seat a year, for the seats unit (spec 6): OpenAI's run-rate on the latest day its paying
    consumers and business users are both counted, over those users."""
    s = led.series.get("paying_users")
    if not s:
        return None
    days = {p.period for p in s.points.get("chatgpt", [])} & {p.period for p in s.points.get("openai_business", [])}
    for day in sorted(days, reverse=True):
        rate = runrate_at(runrate_points(led, "openai"), dt.date.fromisoformat(day))
        users = s.get("chatgpt", day).value + s.get("openai_business", day).value
        if rate and users:
            return {"date": day, "dollars": round(rate * 1000 / users, 1), "users_m": users, "runrate_b": round(rate, 3)}
    return None


def build(led: Ledger, prices, today: dt.date) -> dict:
    """Both models, every slider step, every piece. The ledger has the fetched figures merged in already."""
    notes: list[str] = []
    la = last_actual(led, today)
    sliders = led.model["sliders"]
    lives, waccs = sliders["gpu_life"]["steps"], sliders["cost_of_capital"]["steps"]
    deadlines = {str(life): deadline(life) for life in lives}

    # Model A, capex payback
    capex = led.model["capex"]
    groups, costs = capex["groups"], capex["costs"]
    placed = {eid: capex_placed(led, eid) for g in groups.values() for eid in g.get("members") or []}
    for eid, rows in placed.items():
        if not rows:
            notes.append(f"No capex for {led.entities.get(eid, {}).get('label', eid)} yet: it adds nothing.")
    members = {gid: (consensus_placed(led, g, placed) if g.get("series") else {m: placed[m] for m in g["members"]})
               for gid, g in groups.items()}
    shared = led.model["parameters"]["ai_share"].get("by_entity") or {}
    for gid, ms in members.items():
        for eid in [e for e in ms if e not in shared]:
            notes.append(f"No AI share for {led.entities.get(eid, {}).get('label', eid)}: its capex in "
                         f"{groups[gid]['label']} is left out.")
            del ms[eid]
    streams = {gid: {k: group_capex(led, ms, k) for k in VARIANTS} for gid, ms in members.items()}
    cs = led.param("compute_share")["value"] / 100
    running, long_life = _pct(led.param("running_costs")), led.param("long_life")["value"]
    a_pieces = [{"id": f"{gid}.{part}", "group": gid, "part": part, "label": f"{g['label']}: {costs[part]['label']}",
                 "on": bool(g["enabled"] and costs[part]["enabled"]), "grades": _capex_mix(members[gid])}
                for gid, g in groups.items() for part in costs]
    a_grid = {}
    for life in lives:
        dl = deadlines[str(life)]["quarter"]
        for wacc in waccs:
            cell = a_grid[f"{life}|{wacc}"] = {}
            for gid, variants in streams.items():
                parts = {k: schedule(*variants[k], life, long_life, wacc / 100, running[k]) for k in VARIANTS}
                for part in costs:
                    found = [parts[k][part] / cs for k in VARIANTS]
                    cell[f"{gid}.{part}"] = _cell({"value": found[0], "low": np.minimum.reduce(found),
                                                   "high": np.maximum.reduce(found)}, la, dl)

    # Model A, the valuation
    worth = valuation(led, prices, notes)
    v_grid = {f"{life}|{wacc}": targets(led, worth["groups"], life, wacc / 100, today) for life in lives
              for wacc in waccs}

    # Model B
    demand = led.model["demand"]
    actual, mixes = demand_actuals(led, la, notes)
    on = {tid for tid, t in demand["tiers"].items() if t["enabled"]}
    usage = usage_growth(led)
    if usage["growth"] is None:
        notes.append("No year of token growth in the ledger: usage grows at its long-run rate.")
    floor = led.param("usage_floor")["value"] / 100
    half_life = led.param("usage_half_life")["value"] / 12
    growth = usage["growth"] if usage["growth"] is not None else floor
    trailing = trailing_deflation(actual, on, la, usage["growth"])
    if trailing is None:
        notes.append("No trailing price change (a year of demand and of tokens is needed): 'trailing' uses -40%.")
    b_pieces = [{"id": tid, "label": t["label"], "tier": t["tier"], "on": bool(t["enabled"]), "grades": mixes[tid]}
                for tid, t in demand["tiers"].items()]
    free = demand.get("free_users") or {}
    b_pieces.append({"id": "free_users", "label": free.get("label", "Free users"), "tier": None,
                     "on": bool(free.get("enabled")), "grades": mixes["free_users"]})
    b_grid = {}
    for step in sliders["deflation"]["steps"]:
        rate = (trailing if trailing is not None else -0.4) if step == "trailing" else float(step) / 100
        projected = project(actual, la, growth, floor, half_life, rate)
        b_grid[str(step)] = {"deflation": round(rate, 4), "pieces": {
            pid: {"rate": _round(a["value"]), "low": _round(a["low"]), "high": _round(a["high"]),
                  "readouts": {str(life): readouts(a, la, deadlines[str(life)]["quarter"]) for life in lives}}
            for pid, a in projected.items()}}

    return {
        "date": today.isoformat(), "quarters": QUARTERS, "last_actual": la, "deadlines": deadlines,
        "sliders": {sid: {"label": s["label"], "unit": s["unit"], "steps": s["steps"], "default": s["default"]}
                    for sid, s in sliders.items()},
        "compute_share": round(cs, 4),
        "capex": {"pieces": a_pieces, "grid": a_grid, "placed": _placed_summary(members),
                  "by_year": capex_by_year(streams, groups, la)},
        "valuation": {**worth, "grid": v_grid},
        "demand": {"pieces": b_pieces, "grid": b_grid, "usage": usage,
                   "trailing": None if trailing is None else round(trailing, 4),
                   "left_out": demand.get("left_out") or {}},
        "units": units(led),
        "clock": cash_clock(streams, groups, actual, on, la, today),
        "notes": notes,
    }


def capex_by_year(streams: dict, groups: dict, la: int) -> dict:
    """AI capex placed in each calendar year by the groups switched on, $B, from the low to the high estimate of each
    company's AI share: the line the analogs draw for AI. It stops at the year of the last actual quarter (that
    year's later quarters are its guidance): a later year would hold only the guidance given so far."""
    on = [g for g in groups if groups[g]["enabled"]]
    years = [y for y in sorted({int(q[:4]) for q in QUARTERS}) if y <= int(QUARTERS[la][:4])]
    out = {}
    for k in VARIANTS:
        total = sum((streams[g][k][0] + streams[g][k][1] for g in on), np.zeros(N))
        out["mid" if k == "value" else k] = [round(float(sum(total[i] for i, q in enumerate(QUARTERS)
                                                             if q.startswith(str(y)))), 3) for y in years]
    keep = max((i + 1 for i, x in enumerate(out["mid"]) if x), default=0)
    # The last year adds guidance for its quarters after the last actual one: the page says so.
    return {"years": years[:keep], "actual_through": QUARTERS[la], **{k: xs[:keep] for k, xs in out.items()}}


def _capex_mix(members: dict[str, dict[str, tuple]]) -> dict[str, float]:
    weights: dict[str, float] = {}
    for rows in members.values():
        for amount, g, _ in rows.values():
            weights[g] = weights.get(g, 0.0) + amount
    return _mix(weights)


def _placed_summary(members: dict) -> dict:
    """What each group has placed, before the AI share ($B): filed, guided, or analysts' consensus."""
    out = {}
    for gid, ms in members.items():
        kinds: dict[str, float] = {}
        last = None
        for rows in ms.values():
            for q, (amount, _, kind) in rows.items():
                if q in INDEX:
                    kinds[kind] = round(kinds.get(kind, 0.0) + amount, 3)
                    last = q if last is None else max(last, q)
        out[gid] = {"by_kind": kinds, "last_quarter": last}
    return out


def cash_clock(streams: dict, groups: dict, demand: dict, on: set[str], la: int, today: dt.date) -> dict:
    """The cash clock (spec 13), in $B: AI capex out and end-user demand in since 1 January, at the last actual
    quarter's end, with each one's latest rate a second. The page adds rate x the seconds since that date."""
    year = today.year
    since = [i for i in range(la + 1) if QUARTERS[i].startswith(str(year))]
    capex = sum((streams[g]["value"][0] + streams[g]["value"][1] for g in groups if groups[g]["enabled"]), np.zeros(N))
    paid = sum((demand[p]["value"] for p in on), np.zeros(N))
    return {"from": dt.date(year, 1, 1).isoformat(),
            "date": max(q_end(QUARTERS[la]), dt.date(year, 1, 1)).isoformat(),
            "capex_out": round(float(sum(capex[i] for i in since)), 3),
            "demand_in": round(float(sum(paid[i] for i in since) / 4), 3),
            "capex_per_second": float(capex[la] * 4 / SECONDS_A_YEAR),
            "demand_per_second": float(paid[la] / SECONDS_A_YEAR)}
