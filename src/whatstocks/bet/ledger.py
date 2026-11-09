"""The ledger (spec section 14): every figure the code cannot fetch, each with its source, and the settings of both
models. The shipped ledger lives in sources/bet/; the user's my/bet.yaml is merged on top of it:

    series:      add a point, or replace the shipped point with the same series, entity and period
    remove:      drop a shipped point
    parameters:  replace a parameter by id (or one company of a parameter set by company)
    sliders:     your default for a slider
    indicators:  your amber and red levels for an indicator, with your reason
    channels:    a path's whole list of channels
    view_links:  which of your views a path's changes count for or against

load() reads all of it, checks it (spec 14.3) and raises Problems with every problem found."""
from __future__ import annotations

import datetime as dt
import math
import re
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

from ..files import Problems, ThemeMap, _clean, _date, _yaml
from ..paths import BET_DIR, UserDir

FILES = ("series", "model", "signals", "events")
GRADES = ("filed", "company", "press", "estimate")
CADENCES = ("daily", "weekly", "monthly", "quarterly", "yearly", "irregular")
DATE = r"\d{4}-\d\d-\d\d"
PERIODS = {"quarter": r"\d{4}Q[1-4]", "month": r"\d{4}-(?:0[1-9]|1[0-2])", "year": r"(?:FY)?\d{4}",
           "week": DATE, "day": DATE, "point": DATE}
EXAMPLES = {"quarter": "2026Q3", "month": "2026-09", "year": "2026 or FY2027", "week": "2026-10-30",
            "day": "2026-10-30", "point": "2026-10-30"}
POINT_KEYS = ("period", "for", "value", "low", "high", "unit", "agency", "rating", "outlook", "kind", "grade",
              "source", "published", "seen", "why", "basis", "note")
SERIES_KEYS = ("label", "unit", "period", "cadence", "about", "entities", "points")
FOR_SERIES = {"capex_guide": r"(?:FY)?\d{4}", "nvda_revenue_guide": r"\d{4}Q[1-4]"}  # 'for': what a guide covers
GUIDE_WHY = ("accounting", "supply", "demand", "unstated")
BASES = ("gross", "net")
OUTLOOKS = ("positive", "stable", "negative", "developing")
EVENT_KINDS = ("distressed_exchange", "pulled_deal", "missed_payment", "bankruptcy")
SCALES = {  # best first; the scales line up notch for notch, so BBB- and Baa3 are both the lowest investment grade
    "S&P": ("AAA", "AA+", "AA", "AA-", "A+", "A", "A-", "BBB+", "BBB", "BBB-", "BB+", "BB", "BB-", "B+", "B", "B-",
            "CCC+", "CCC", "CCC-", "CC", "C", "D"),
    "Moody's": ("Aaa", "Aa1", "Aa2", "Aa3", "A1", "A2", "A3", "Baa1", "Baa2", "Baa3", "Ba1", "Ba2", "Ba3", "B1", "B2",
                "B3", "Caa1", "Caa2", "Caa3", "Ca", "C"),
}
SCALES["Fitch"] = SCALES["S&P"]
WORD_UNITS = ("rating", "event")  # their points carry words (a rating, a kind of event), not a value
PARAM_UNITS = ("pct", "pct_per_year", "years", "months", "times")
PATH_KINDS = ("crash", "adoption")
STATES = ("clear", "amber", "red")
EFFECTS = ("hurt", "help", "mixed")
STRENGTHS = ("low", "medium", "high")
TIERS = ("core", "partial")
VIEW_EFFECTS = ("for", "against")
OVERLAY_KEYS = ("series", "remove", "parameters", "sliders", "indicators", "channels", "view_links")
MINE_INDICATOR_KEYS = ("amber", "red", "why", "trigger")
FIGURE_KEYS = ("value", "low", "high", "from", "basis", "grade", "source", "published", "seen", "why", "note")
COMPANY_KEYS = ("value", "low", "high", "why")  # one company of a parameter set by company

# Indicator rules: what each reads. The ordered ones compare one reading with an amber and a red level.
ORDERED = ("level", "mean_last", "change", "yoy", "capex_growth", "capex_to_ocf", "guide_vs_actual", "guidance_cuts",
           "below_high", "payback", "streak", "falls", "tier1_share")
NEEDS = {
    "level": ("series", "entity"), "mean_last": ("series", "entity", "points"),
    "change": ("series", "entity", "points"), "yoy": ("series", "entity", "tolerance_days"),
    "capex_growth": ("groups",), "capex_to_ocf": ("entities",), "guide_vs_actual": ("series", "actual", "entity"),
    "guidance_cuts": ("series", "entities", "quarters", "counts"), "below_high": ("basket", "weeks"),
    "payback": (), "streak": ("series", "entities"), "falls": ("paying", "users"), "tier1_share": (),
    "events": ("series", "days", "amber_kinds", "red_kinds"), "ratings": ("series", "floor"), "coverage_now": (),
    "telecom_test": ("amber",), "trend": ("series", "entity", "months", "flat"),
}


@dataclass
class Point:
    series: str
    entity: str
    period: str  # 2026Q3, 2026-09, 2026, FY2027 or 2026-10-30, by the series' period
    value: float | None
    low: float | None
    high: float | None
    grade: str
    source: str
    seen: dt.date
    published: dt.date | None = None
    covers: str = ""  # 'for' in the file: the year or quarter a guidance point covers
    agency: str = ""
    rating: str = ""
    outlook: str = ""
    kind: str = ""
    why: str = ""
    basis: str = ""
    note: str = ""
    mine: bool = False  # from my/bet.yaml

    @property
    def key(self) -> tuple[str, str, str, str]:
        """What makes it one point: series, entity and period, plus what a guide covers or who rated."""
        return self.series, self.entity, self.period, self.covers or self.agency


@dataclass
class Series:
    id: str
    label: str
    unit: str
    period: str
    cadence: str
    about: str
    entities: dict[str, dict]  # its own entities, beyond the ledger's
    points: dict[str, list[Point]]  # by entity, oldest first

    def latest(self, entity: str) -> Point | None:
        points = self.points.get(entity) or []
        return points[-1] if points else None

    def get(self, entity: str, period: str, covers: str = "") -> Point | None:
        return next((p for p in self.points.get(entity, []) if p.period == period and p.covers == covers), None)

    def put(self, points: list[Point]) -> None:
        """Add points, each replacing the point with the same key."""
        keys = {p.key for p in points}
        kept = [p for ps in self.points.values() for p in ps if p.key not in keys]
        self.points = _sort(kept + list(points))


@dataclass
class Ledger:
    entities: dict[str, dict]
    series: dict[str, Series]
    gaps: list[dict]
    model: dict  # model.yaml merged with yours: sliders, parameters, capex, valuation, demand, units, pool
    signals: dict  # signals.yaml merged with yours: paths, regime, indicators, channels, replays
    events: dict  # events.yaml: releases, unconfirmed, ai_start, analogs
    view_links: dict[str, dict[str, str]]
    removed: int = 0  # shipped points that my/bet.yaml removes

    def points(self) -> list[Point]:
        return [p for s in self.series.values() for ps in s.points.values() for p in ps]

    def default(self, slider: str):
        return self.model["sliders"][slider]["default"]

    def param(self, pid: str, entity: str | None = None) -> dict:
        """A parameter as the models use it: value, low and high, and where it comes from."""
        p = self.model["parameters"][pid]
        if "by_entity" in p:
            p = dict(p["by_entity"][entity], basis="judgment", mine=p["by_entity"][entity].get("mine", False))
        elif "from" in p:
            ref = p["from"]
            point = self.series[ref["series"]].get(ref["entity"], _text(ref["period"]))
            p = dict(p, value=point.value, low=point.low, high=point.high, grade=point.grade, source=point.source,
                     mine=p.get("mine", False) or point.mine)
        value = float(p["value"])
        low, high = p.get("low"), p.get("high")
        return {"value": value, "low": value if low is None else float(low), "high": value if high is None
                else float(high), "basis": p.get("basis") or "sourced", "grade": p.get("grade", ""),
                "source": p.get("source", ""), "why": _clean(p.get("why")), "mine": bool(p.get("mine"))}

    def summary(self) -> str:
        points = self.points()
        mine = sum(p.mine for p in points)
        signals, events = self.signals, self.events
        return (f"Ledger: {len(points)} figures in {len(self.series)} series ({mine} yours), "
                f"{len(signals['indicators'])} indicators on {len(signals['paths'])} paths, "
                f"{len(events['releases'])} open-weight releases, {len(self.gaps)} gaps to fill.")


def notch(agency: str, rating: str) -> int | None:
    """0 for AAA or Aaa, one more for each notch down; None for a rating the scale does not know."""
    scale = SCALES.get(agency, ())
    return scale.index(rating) if rating in scale else None


# ---------------------------------------------------------------- small readers


def _text(value) -> str:
    """A period or a 'for' as YAML gave it: dates and bare years come back as text."""
    if isinstance(value, dt.datetime):
        return value.date().isoformat()
    if isinstance(value, dt.date):
        return value.isoformat()
    return "" if value is None else str(value)


def _period(kind: str, value) -> str | None:
    text = _text(value)
    if kind not in PERIODS or not re.fullmatch(PERIODS[kind], text):
        return None
    if PERIODS[kind] == DATE:
        try:
            dt.date.fromisoformat(text)
        except ValueError:
            return None
    return text


def _num(value, where: str, problems: list[str]) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        problems.append(f"{where}: '{value}' is not a number")
        return None
    return float(value)


def _link(value) -> bool:
    return bool(re.fullmatch(r"https?://\S+", str(value or "")))


def _seen(raw: dict, where: str, problems: list[str], today: dt.date) -> dt.date | None:
    """The day the source was read: required, and no later than today."""
    if raw.get("seen") is None:
        problems.append(f"{where}: seen (the day the source was read) is missing")
        return None
    seen = _date(raw["seen"], f"{where} seen", problems)
    if seen and seen > today:
        problems.append(f"{where}: seen {seen} is after today")
    return seen


def _keys(raw: dict, allowed, where: str, problems: list[str]) -> None:
    unknown = sorted(str(k) for k in raw if str(k) not in allowed)
    if unknown:
        problems.append(f"{where}: unknown field{'s' if len(unknown) > 1 else ''} {', '.join(unknown)}")


# ---------------------------------------------------------------- series and points


def _series(sid: str, raw, problems: list[str]) -> Series | None:
    where = f"series.yaml {sid}"
    if not isinstance(raw, dict):
        problems.append(f"{where}: a series is a mapping with label, unit, period, cadence and points")
        return None
    _keys(raw, SERIES_KEYS, where, problems)
    missing = [k for k in ("label", "unit", "period", "cadence") if not raw.get(k)]
    if missing:
        problems.append(f"{where}: {', '.join(missing)} missing")
        return None
    if raw["period"] not in PERIODS:
        problems.append(f"{where}: period must be one of {', '.join(PERIODS)}")
        return None
    if raw["cadence"] not in CADENCES:
        problems.append(f"{where}: cadence must be one of {', '.join(CADENCES)}")
    entities = {str(k): dict(v or {}) for k, v in (raw.get("entities") or {}).items()}
    return Series(sid, _clean(raw["label"]), str(raw["unit"]), str(raw["period"]), str(raw["cadence"]),
                  _clean(raw.get("about")), entities, {})


def _point(s: Series, entity: str, raw, where: str, problems: list[str], today: dt.date, mine: bool) -> Point | None:
    if not isinstance(raw, dict):
        problems.append(f"{where}: each point is a mapping such as {{period: {EXAMPLES[s.period]}, value: 1.5, "
                        f"grade: filed, source: https://..., seen: 2026-11-07}}")
        return None
    period = _period(s.period, raw.get("period"))
    if period is None:
        problems.append(f"{where}: period '{_text(raw.get('period'))}' is not a {s.period} such as "
                        f"{EXAMPLES[s.period]}")
        return None
    where = f"{where} {period}"
    before = len(problems)
    _keys(raw, POINT_KEYS, where, problems)
    if raw.get("unit") is not None and str(raw["unit"]) != s.unit:
        problems.append(f"{where}: unit '{raw['unit']}' does not match the series ({s.unit})")
    value, low, high = (_num(raw.get(k), f"{where} {k}", problems) for k in ("value", "low", "high"))
    if s.unit in WORD_UNITS:
        if any(raw.get(k) is not None for k in ("value", "low", "high")):
            problems.append(f"{where}: a {s.unit} point has no value, low or high")
    elif raw.get("value") is None:
        problems.append(f"{where}: value is missing")
    elif value is not None:
        if low is not None and low > value:
            problems.append(f"{where}: low ({low:g}) is above the value ({value:g})")
        if high is not None and high < value:
            problems.append(f"{where}: high ({high:g}) is below the value ({value:g})")
    grade = str(raw.get("grade") or "")
    if grade not in GRADES:
        problems.append(f"{where}: grade '{grade}' is not one of {', '.join(GRADES)}")
    source = str(raw.get("source") or "")
    if not _link(source):
        problems.append(f"{where}: source must be an http(s) link")
    seen = _seen(raw, where, problems, today)
    published = _date(raw["published"], f"{where} published", problems) if raw.get("published") is not None else None
    if published and seen and published > seen:
        problems.append(f"{where}: published {published} is after seen {seen}")
    covers = _text(raw.get("for"))
    if s.id in FOR_SERIES:
        if not re.fullmatch(FOR_SERIES[s.id], covers):
            problems.append(f"{where}: 'for' must name what the guidance covers, such as "
                            f"{'2026 or FY2027' if s.id == 'capex_guide' else '2026Q4'}")
    elif covers:
        problems.append(f"{where}: 'for' is only for guidance series")
    why = _clean(raw.get("why"))
    if why and s.id == "capex_guide" and why not in GUIDE_WHY:
        problems.append(f"{where}: why must be one of {', '.join(GUIDE_WHY)}")
    basis = str(raw.get("basis") or "")
    if basis and basis not in BASES:
        problems.append(f"{where}: basis must be gross or net")
    agency, rating, outlook = (str(raw.get(k) or "") for k in ("agency", "rating", "outlook"))
    if s.unit == "rating":
        if agency not in SCALES:
            problems.append(f"{where}: agency must be one of {', '.join(SCALES)}")
        elif notch(agency, rating) is None:
            problems.append(f"{where}: '{rating}' is not on {agency}'s scale")
        if outlook not in OUTLOOKS:
            problems.append(f"{where}: outlook must be one of {', '.join(OUTLOOKS)}")
    elif agency or rating or outlook:
        problems.append(f"{where}: agency, rating and outlook are only for ratings")
    kind = str(raw.get("kind") or "")
    if s.unit == "event":
        if kind not in EVENT_KINDS:
            problems.append(f"{where}: kind must be one of {', '.join(EVENT_KINDS)}")
    elif kind:
        problems.append(f"{where}: kind is only for events")
    if len(problems) > before:
        return None
    return Point(s.id, entity, period, value, low, high, grade, source, seen, published, covers, agency, rating,
                 outlook, kind, why, basis, _clean(raw.get("note")), mine)


def _points(s: Series, raw_points, source: str, entities: dict, problems: list[str], today: dt.date,
            mine: bool) -> list[Point]:
    """One file's points for one series. No two may share a series, an entity and a period."""
    out, keys = [], set()
    if not isinstance(raw_points, dict):
        problems.append(f"{source} {s.id}: points must map each entity to a list of points")
        return out
    for entity, rows in raw_points.items():
        entity = str(entity)
        if entity not in entities and entity not in s.entities:
            problems.append(f"{source} {s.id}: unknown entity '{entity}'")
            continue
        if not isinstance(rows, list):
            problems.append(f"{source} {s.id} {entity}: points must be a list")
            continue
        for raw in rows:
            p = _point(s, entity, raw, f"{source} {s.id} {entity}", problems, today, mine)
            if p is None:
                continue
            if p.key in keys:
                problems.append(f"{source} {s.id} {entity} {p.period}: appears twice")
                continue
            keys.add(p.key)
            out.append(p)
    return out


def _sort(points: list[Point]) -> dict[str, list[Point]]:
    by_entity = defaultdict(list)
    for p in points:
        by_entity[p.entity].append(p)
    return {e: sorted(ps, key=lambda p: (p.period, p.covers, p.agency)) for e, ps in by_entity.items()}


def _guidance_whys(s: Series | None, problems: list[str]) -> None:
    """A cut in capex guidance records why: accounting and supply changes never count as retrenchment."""
    if s is None:
        return
    for entity, points in s.points.items():
        by_year = defaultdict(list)
        for p in points:
            by_year[p.covers].append(p)
        for covers, ps in by_year.items():
            for before, after in zip(ps, ps[1:]):
                if after.value < before.value and not after.why:
                    file = "bet.yaml" if after.mine else "series.yaml"
                    problems.append(f"{file} capex_guide {entity} {after.period}: a cut in {covers} guidance "
                                    f"({before.value:g} to {after.value:g}) needs a why: {', '.join(GUIDE_WHY)}")


# ---------------------------------------------------------------- my/bet.yaml on top


def _section(extra: dict, key: str, kind: type, problems: list[str]):
    """One section of my/bet.yaml, or an empty one if it is missing or the wrong shape."""
    value = extra.get(key)
    if value is None:
        return kind()
    if not isinstance(value, kind):
        problems.append(f"bet.yaml {key}: write it as a {'mapping' if kind is dict else 'list'}")
        return kind()
    return value


def _merge(extra: dict, series: dict[str, Series], entities: dict, model: dict, signals: dict,
           problems: list[str], today: dt.date) -> int:
    """Merge my/bet.yaml into the shipped ledger in place. Returns how many shipped points it removed."""
    _keys(extra, OVERLAY_KEYS, "bet.yaml", problems)
    for sid, raw in _section(extra, "series", dict, problems).items():
        sid = str(sid)
        if sid not in series:
            problems.append(f"bet.yaml series: unknown series '{sid}' (sources/bet/series.yaml lists them)")
            continue
        if not isinstance(raw, dict) or set(map(str, raw)) - {"points"}:
            problems.append(f"bet.yaml series {sid}: only points can be added to a shipped series")
            continue
        s = series[sid]
        ours = _points(s, raw.get("points") or {}, "bet.yaml", entities, problems, today, mine=True)
        mine_keys = {p.key for p in ours}
        kept = [p for ps in s.points.values() for p in ps if p.key not in mine_keys]
        s.points = _sort(kept + ours)
    removed = 0
    for n, raw in enumerate(_section(extra, "remove", list, problems), start=1):
        where = f"bet.yaml remove {n}"
        if not isinstance(raw, dict) or not {"series", "entity", "period"} <= set(map(str, raw)):
            problems.append(f"{where}: name the series, entity and period of the shipped point to drop")
            continue
        _keys(raw, ("series", "entity", "period", "for", "agency"), where, problems)
        s = series.get(str(raw["series"]))
        key = (str(raw["series"]), str(raw["entity"]), _text(raw["period"]), _text(raw.get("for"))
               or str(raw.get("agency") or ""))
        found = s and next((p for p in s.points.get(key[1], []) if p.key == key and not p.mine), None)
        if not found:
            problems.append(f"{where}: no shipped point {' '.join(k for k in key if k)}")
            continue
        s.points[key[1]].remove(found)
        removed += 1
    shipped = model.get("parameters") or {}
    for pid, raw in _section(extra, "parameters", dict, problems).items():
        where = f"bet.yaml parameters.{pid}"
        if pid not in shipped:
            problems.append(f"bet.yaml parameters: unknown parameter '{pid}'")
        elif not isinstance(raw, dict):
            problems.append(f"{where}: a parameter is a mapping, such as {{value: 4, basis: judgment, why: ...}}")
        elif "by_entity" in shipped[pid]:
            by_entity = raw.get("by_entity")
            if set(map(str, raw)) != {"by_entity"} or not isinstance(by_entity, dict) or not all(
                    isinstance(one, dict) for one in by_entity.values()):
                problems.append(f"{where}: set it company by company, as by_entity: {{amzn: {{value: 60, why: ...}}}}")
                continue
            for eid, one in by_entity.items():
                _keys(one, COMPANY_KEYS, f"{where} {eid}", problems)
                shipped[pid]["by_entity"][str(eid)] = dict(one, mine=True)
        else:  # your figure replaces the shipped one; its label and unit stay
            _keys(raw, FIGURE_KEYS, where, problems)
            kept = {k: v for k, v in shipped[pid].items() if k not in FIGURE_KEYS}
            shipped[pid] = dict(kept, **{str(k): v for k, v in raw.items()}, mine=True)
    sliders = model.get("sliders") or {}
    for sid, raw in _section(extra, "sliders", dict, problems).items():
        if sid not in sliders:
            problems.append(f"bet.yaml sliders: unknown slider '{sid}'")
        elif not isinstance(raw, dict) or set(map(str, raw)) != {"default"}:
            problems.append(f"bet.yaml sliders.{sid}: only your default can be set, as default: <one of the steps>")
        else:
            sliders[sid] = dict(sliders[sid], default=raw["default"], mine=True)
    indicators = signals.get("indicators") or {}
    for iid, raw in _section(extra, "indicators", dict, problems).items():
        where = f"bet.yaml indicators.{iid}"
        if iid not in indicators:
            problems.append(f"bet.yaml indicators: unknown indicator '{iid}'")
            continue
        if not isinstance(raw, dict):
            problems.append(f"{where}: give your amber and red levels and your why")
            continue
        _keys(raw, MINE_INDICATOR_KEYS, where, problems)
        if ("amber" in raw or "red" in raw) and not _clean(raw.get("why")):
            problems.append(f"{where}: your levels need your reason (why)")
        indicators[iid] = dict(indicators[iid], **{k: v for k, v in raw.items() if k in MINE_INDICATOR_KEYS},
                               mine=True)
    channels = signals.get("channels")
    if not isinstance(channels, dict):
        channels = {}  # the check of signals.yaml reports it
    paths = signals.get("paths") or {}
    for pid, raw in _section(extra, "channels", dict, problems).items():
        pid = str(pid)
        if pid not in paths:
            problems.append(f"bet.yaml channels: unknown path '{pid}'")
        elif not isinstance(raw, list) or not all(isinstance(c, dict) for c in raw):
            problems.append(f"bet.yaml channels.{pid}: a path's channels are a list, such as "
                            f"[{{kind: theme, id: defence, effect: hurt, strength: low}}]")
        else:
            channels[pid] = [dict(c, mine=True) for c in raw]
    return removed


# ---------------------------------------------------------------- checks of the settings


class _Refs:
    """Checks that a name in model.yaml or signals.yaml points at something that exists."""

    def __init__(self, series: dict[str, Series], entities: dict, model: dict, problems: list[str]):
        self.series, self.entities, self.model, self.problems = series, entities, model, problems

    def known_series(self, sid, where: str) -> Series | None:
        s = self.series.get(str(sid))
        if s is None:
            self.problems.append(f"{where}: unknown series '{sid}'")
        return s

    def series_entity(self, sid, entity, where: str) -> None:
        s = self.known_series(sid, where)
        if s and str(entity) not in self.entities and str(entity) not in s.entities:
            self.problems.append(f"{where}: unknown entity '{entity}' for {sid}")

    def entity(self, eid, where: str) -> None:
        if str(eid) not in self.entities:
            self.problems.append(f"{where}: unknown entity '{eid}'")

    def param(self, pid, where: str) -> None:
        if pid not in (self.model.get("parameters") or {}):
            self.problems.append(f"{where}: unknown parameter '{pid}'")

    def point(self, ref, where: str) -> None:
        if not isinstance(ref, dict) or not {"series", "entity", "period"} <= set(ref):
            self.problems.append(f"{where}: from needs series, entity and period")
            return
        s = self.known_series(ref["series"], where)
        point = s and s.get(str(ref["entity"]), _text(ref["period"]))
        if s and (point is None or point.value is None):
            self.problems.append(f"{where}: no point {ref['series']} {ref['entity']} {_text(ref['period'])} "
                                 f"with a value")

    def label(self, raw: dict, where: str, *keys: str) -> None:
        missing = [k for k in ("label", *keys) if raw.get(k) in (None, "", [])]
        if missing:
            self.problems.append(f"{where}: {', '.join(missing)} missing")

    def switch(self, raw: dict, where: str) -> None:
        """A piece the page can switch on and off. 'enabled', not 'on': YAML reads a bare on as true."""
        self.label(raw, where)
        if not isinstance(raw.get("enabled"), bool):
            self.problems.append(f"{where}: enabled (whether it starts switched on) must be true or false")
        for pid in raw.get("parameters") or []:
            self.param(pid, where)
        for sid in raw.get("series") if isinstance(raw.get("series"), list) else []:
            self.known_series(sid, where)


def _range(raw: dict, where: str, problems: list[str]) -> None:
    value, low, high = (_num(raw.get(k), f"{where} {k}", problems) for k in ("value", "low", "high"))
    if value is None:
        if raw.get("value") is None:
            problems.append(f"{where}: value is missing")
        return
    if low is not None and low > value:
        problems.append(f"{where}: low ({low:g}) is above the value ({value:g})")
    if high is not None and high < value:
        problems.append(f"{where}: high ({high:g}) is below the value ({value:g})")


def _check_parameter(pid: str, p, refs: _Refs, problems: list[str], today: dt.date) -> None:
    where = f"{'bet.yaml' if isinstance(p, dict) and p.get('mine') else 'model.yaml'} parameters.{pid}"
    if not isinstance(p, dict):
        problems.append(f"{where}: a parameter is a mapping")
        return
    refs.label(p, where, "unit")
    if p.get("unit") and p["unit"] not in PARAM_UNITS:
        problems.append(f"{where}: unit must be one of {', '.join(PARAM_UNITS)}")
    forms = [k for k in ("value", "from", "by_entity") if k in p]
    if len(forms) != 1:
        problems.append(f"{where}: give exactly one of value, from or by_entity")
        return
    if forms == ["from"]:
        refs.point(p["from"], where)
    elif forms == ["by_entity"]:
        if p.get("basis") != "judgment":
            problems.append(f"{where}: a parameter set by company is a judgment (basis: judgment)")
        for eid, one in (p["by_entity"] if isinstance(p["by_entity"], dict) else {}).items():
            one = one if isinstance(one, dict) else {}
            at = f"{'bet.yaml' if one.get('mine') else 'model.yaml'} parameters.{pid} {eid}"
            refs.entity(eid, at)
            _range(one, at, problems)
            if not _clean(one.get("why")):
                problems.append(f"{at}: a judgment needs its reason (why)")
    else:
        _range(p, where, problems)
        if p.get("basis") == "judgment":
            if not _clean(p.get("why")):
                problems.append(f"{where}: a judgment needs its reason (why)")
        elif p.get("basis") is not None:
            problems.append(f"{where}: basis is judgment, or leave it out and give the source")
        else:
            if p.get("grade") not in GRADES:
                problems.append(f"{where}: grade must be one of {', '.join(GRADES)} (or basis: judgment, with why)")
            if not _link(p.get("source")):
                problems.append(f"{where}: source must be an http(s) link (or basis: judgment, with why)")
            _seen(p, where, problems, today)


def _check_model(model: dict, refs: _Refs, problems: list[str], today: dt.date) -> None:
    for key in ("sliders", "parameters", "capex", "valuation", "demand", "units", "pool"):
        if not isinstance(model.get(key), dict):
            problems.append(f"model.yaml: {key} is missing")
            model[key] = {}
    for sid, s in model["sliders"].items():
        where = f"model.yaml sliders.{sid}"
        refs.label(s, where, "unit", "steps", "why")
        steps = s.get("steps") or []
        if s.get("default") not in steps:
            problems.append(f"{'bet.yaml' if s.get('mine') else 'model.yaml'} sliders.{sid}: default "
                            f"{s.get('default')} is not one of the steps ({', '.join(map(str, steps))})")
        if s.get("from"):
            refs.point(s["from"], where)
    for pid, p in model["parameters"].items():
        _check_parameter(pid, p, refs, problems, today)
    capex = model["capex"]
    basis = capex.get("basis") or {}
    for eid, sid in basis.items():
        refs.series_entity(sid, eid, "model.yaml capex.basis")
    for key in ("guidance", "short_lived"):
        refs.known_series(capex.get(key), f"model.yaml capex.{key}")
    for pid in capex.get("parameters") or []:
        refs.param(pid, "model.yaml capex")
    by_company = [pid for pid in capex.get("parameters") or []
                  if isinstance(model["parameters"].get(pid), dict) and "by_entity" in model["parameters"][pid]]
    for gid, g in (capex.get("groups") or {}).items():
        where = f"model.yaml capex.groups.{gid}"
        refs.switch(g, where)
        if g.get("series"):
            refs.known_series(g["series"], where)
        elif not g.get("members"):
            problems.append(f"{where}: give members (or a series)")
        for m in g.get("members") or []:
            if m not in basis:
                problems.append(f"{where}: {m} has no capex basis (capex.basis)")
            for pid in by_company:
                if m not in (model["parameters"][pid]["by_entity"] or {}):
                    problems.append(f"{where}: {m} has no {pid} (parameters.{pid}.by_entity)")
    for cid, c in (capex.get("costs") or {}).items():
        refs.switch(c, f"model.yaml capex.costs.{cid}")
    valuation = model["valuation"]
    if not isinstance(valuation.get("start"), dt.date):
        problems.append("model.yaml valuation.start: give the start date, such as 2022-11-30")
    for pid in valuation.get("parameters") or []:
        refs.param(pid, "model.yaml valuation")
    for gid, g in (valuation.get("groups") or {}).items():
        where = f"model.yaml valuation.groups.{gid}"
        refs.switch(g, where)
        if g.get("series"):
            refs.known_series(g["series"], where)
        for m in g.get("members") or []:
            refs.entity(m, where)
            if not g.get("series") and not refs.entities.get(str(m), {}).get("symbol"):
                problems.append(f"{where}: {m} needs a symbol (series.yaml entities) to be priced")
    demand = model["demand"]
    for eid in demand.get("labs") or []:
        refs.entity(eid, "model.yaml demand.labs")
    tiers = demand.get("tiers") or {}
    numbers = [t.get("tier") for t in tiers.values()]
    if sorted(numbers) != list(range(1, len(numbers) + 1)):
        problems.append("model.yaml demand.tiers: number the tiers 1, 2, 3 and on, once each")
    for tid, t in tiers.items():
        refs.switch(t, f"model.yaml demand.tiers.{tid}")
    if demand.get("free_users"):
        refs.switch(demand["free_users"], "model.yaml demand.free_users")
    usage = demand.get("usage") or {}
    refs.series_entity(usage.get("series"), usage.get("entity"), "model.yaml demand.usage")
    if usage.get("check"):
        refs.series_entity(usage["check"].get("series"), usage["check"].get("entity"), "model.yaml demand.usage")
    for pid in usage.get("parameters") or []:
        refs.param(pid, "model.yaml demand.usage")
    for uid, u in model["units"].items():
        refs.label(u, f"model.yaml units.{uid}")
        for pid in u.get("parameters") or []:
            refs.param(pid, f"model.yaml units.{uid}")
    for key, ref in model["pool"].items():
        refs.series_entity((ref or {}).get("series"), (ref or {}).get("entity"), f"model.yaml pool.{key}")
    _check_funnel(model.get("funnel"), refs, problems)


def _check_funnel(funnel, refs: _Refs, problems: list[str]) -> None:
    """The funnel (spec 5.1), if there is one: layers of measures, and leakage ratios of two measures."""
    if funnel is None:
        return
    if not isinstance(funnel, dict):
        problems.append("model.yaml funnel: give layers (each with an id, a label and measures) and leakage")
        return
    for layer in funnel.get("layers") or []:
        if not isinstance(layer, dict):
            problems.append("model.yaml funnel: each layer has an id, a label and measures")
            continue
        where = f"model.yaml funnel {layer.get('id')}"
        refs.label(layer, where, "id", "measures")
        for m in layer.get("measures") or []:
            if not isinstance(m, dict):
                problems.append(f"{where}: each measure has a series, an entity and a label")
                continue
            refs.label(m, where)
            refs.series_entity(m.get("series"), m.get("entity"), where)
    for r in funnel.get("leakage") or []:
        where = f"model.yaml funnel leakage {(r or {}).get('id')}"
        refs.label(r or {}, where, "id")
        units = []
        for side in ("of", "per"):
            ref = (r or {}).get(side)
            if not isinstance(ref, dict):
                problems.append(f"{where}: {side} needs a series and an entity")
                continue
            refs.series_entity(ref.get("series"), ref.get("entity"), where)
            units.append(getattr(refs.series.get(str(ref.get("series"))), "unit", None))
        if len(units) == 2 and None not in units and units[0] != units[1]:
            problems.append(f"{where}: of and per must share a unit, not {units[0]} and {units[1]}")


def _theme(theme_id: str, themes: ThemeMap | None, where: str, problems: list[str]) -> None:
    """A theme, or a theme tier such as ai_buildout:core."""
    tid, _, tier = str(theme_id).partition(":")
    if tier and tier not in TIERS:
        problems.append(f"{where}: '{theme_id}': a theme tier is core or partial")
    if themes is not None and tid not in themes.themes:
        problems.append(f"{where}: unknown theme '{tid}'")


def _check_indicator(iid: str, ind, signals: dict, refs: _Refs, themes: ThemeMap | None,
                     problems: list[str]) -> None:
    mine = isinstance(ind, dict) and ind.get("mine")
    where = f"{'bet.yaml' if mine else 'signals.yaml'} indicators.{iid}"
    if not isinstance(ind, dict):
        problems.append(f"{where}: an indicator is a mapping")
        return
    refs.label(ind, where, "path", "rule", "why")
    if ind.get("path") not in (signals.get("paths") or {}):
        problems.append(f"{where}: unknown path '{ind.get('path')}'")
    rule = ind.get("rule")
    if rule not in NEEDS:
        problems.append(f"{where}: unknown rule '{rule}'")
        return
    for key in NEEDS[rule]:
        if ind.get(key) in (None, "", []):
            problems.append(f"{where}: the {rule} rule needs {key}")
    if ind.get("series"):
        if ind.get("entity"):
            refs.series_entity(ind["series"], ind["entity"], where)
        else:
            refs.known_series(ind["series"], where)
        for eid in ind.get("entities") or []:
            if rule != "capex_to_ocf":
                refs.series_entity(ind["series"], eid, where)
    if rule == "capex_to_ocf":
        for eid in ind.get("entities") or []:
            refs.entity(eid, where)
    if ind.get("actual"):
        refs.known_series(ind["actual"], where)
    for gid in ind.get("groups") or []:
        if gid not in (refs.model.get("capex", {}).get("groups") or {}):
            problems.append(f"{where}: unknown capex group '{gid}'")
    if ind.get("basket"):
        _theme(ind["basket"], themes, where, problems)
    for key in ("paying", "users"):
        if isinstance(ind.get(key), dict):
            refs.series_entity(ind[key].get("series"), ind[key].get("entity"), f"{where} {key}")
    if "trigger" in ind and not isinstance(ind["trigger"], bool):
        problems.append(f"{where}: trigger must be true or false")
    if rule in ORDERED:
        direction = ind.get("direction")
        if direction not in ("up", "down"):
            problems.append(f"{where}: direction must be up (higher is worse) or down (lower is worse)")
        levels = [ind]
        if isinstance(ind.get("stand_in"), dict):
            stand_in = ind["stand_in"]
            refs.series_entity(stand_in.get("series"), stand_in.get("entity"), f"{where} stand_in")
            levels.append(stand_in)
        for lv in levels:
            amber, red = (_num(lv.get(k), f"{where} {k}", problems) for k in ("amber", "red"))
            if amber is None and lv.get("amber") is None:
                problems.append(f"{where}: the amber level is missing")
            if red is None and lv.get("red") is None and ind.get("trigger"):
                problems.append(f"{where}: a trigger needs a red level")
            if amber is not None and red is not None and direction in ("up", "down"):
                if (direction == "up" and not amber < red) or (direction == "down" and not amber > red):
                    word = "below" if direction == "up" else "above"
                    problems.append(f"{where}: amber ({amber:g}) must come before red ({red:g}): with direction "
                                    f"{direction}, amber sits {word} red")
    elif rule == "events":
        kinds = list(ind.get("amber_kinds") or []) + list(ind.get("red_kinds") or [])
        unknown = [k for k in kinds if k not in EVENT_KINDS]
        if unknown or len(set(kinds)) != len(kinds):
            problems.append(f"{where}: amber_kinds and red_kinds are different kinds from {', '.join(EVENT_KINDS)}")
    elif rule == "ratings":
        if notch("S&P", str(ind.get("floor"))) is None:
            problems.append(f"{where}: floor must be a rating on the S&P scale, such as BBB-")
    elif rule == "telecom_test":
        amber = _num(ind.get("amber"), f"{where} amber", problems)
        if amber is not None and amber >= 0:
            problems.append(f"{where}: amber is a fall in revenue per token, below 0")
    elif rule == "trend":
        if not (_num(ind.get("flat"), f"{where} flat", problems) or 0) > 0:
            problems.append(f"{where}: flat must be above 0")


def _check_signals(signals: dict, refs: _Refs, themes: ThemeMap | None, problems: list[str]) -> None:
    for key in ("paths", "indicators", "channels"):
        if not isinstance(signals.get(key), dict):
            problems.append(f"signals.yaml: {key} is missing")
            signals[key] = {}
    for key in ("regime", "replays"):
        if not isinstance(signals.get(key), list):
            problems.append(f"signals.yaml: {key} is missing")
            signals[key] = []
    paths, indicators = signals["paths"], signals["indicators"]
    for pid, p in paths.items():
        refs.label(p, f"signals.yaml paths.{pid}", "kind")
        if p.get("kind") not in PATH_KINDS:
            problems.append(f"signals.yaml paths.{pid}: kind must be crash or adoption")
        for iid in p.get("red_when_all_red") or []:
            if (indicators.get(iid) or {}).get("path") != pid:
                problems.append(f"signals.yaml paths.{pid}: red_when_all_red names '{iid}', not one of its "
                                f"indicators")
        if not any(isinstance(i, dict) and i.get("path") == pid for i in indicators.values()):
            problems.append(f"signals.yaml paths.{pid}: no indicator reads this path")
    if [p.get("kind") for p in paths.values()].count("adoption") != 1:
        problems.append("signals.yaml paths: exactly one path is the adoption pace (kind: adoption)")
    states = [r.get("state") for r in signals["regime"]]
    if len(set(states)) != len(states) or not states:
        problems.append("signals.yaml regime: each state once, in the order they are read")
    for n, r in enumerate(signals["regime"]):
        where = f"signals.yaml regime {r.get('state')}"
        refs.label(r, where, "state", "about")
        for key in ("crash", "adoption"):
            if key in r and r[key] not in STATES[1:]:
                problems.append(f"{where}: {key} must be amber or red")
        if n == len(states) - 1 and ("crash" in r or "adoption" in r):
            problems.append(f"{where}: the last state holds otherwise, so it has no conditions")
    for iid, ind in indicators.items():
        _check_indicator(iid, ind, signals, refs, themes, problems)
    for pid, channels in signals["channels"].items():
        if pid not in paths:
            problems.append(f"signals.yaml channels.{pid}: unknown path '{pid}'")
        for c in channels or []:
            where = f"{'bet.yaml' if isinstance(c, dict) and c.get('mine') else 'signals.yaml'} channels.{pid}"
            if not isinstance(c, dict) or c.get("kind") not in ("theme", "region") or not c.get("id"):
                problems.append(f"{where}: each channel has a kind (theme or region) and an id")
                continue
            if c["kind"] == "theme":
                _theme(c["id"], themes, where, problems)
            if c.get("effect") not in EFFECTS:
                problems.append(f"{where} {c['id']}: effect must be one of {', '.join(EFFECTS)}")
            if c.get("strength") not in STRENGTHS:
                problems.append(f"{where} {c['id']}: strength must be one of {', '.join(STRENGTHS)}")
    ids = [r.get("id") for r in signals["replays"]]
    if len(set(ids)) != len(ids):
        problems.append("signals.yaml replays: each id once")
    for r in signals["replays"]:
        where = f"signals.yaml replays {r.get('id')}"
        refs.label(r, where, "id")
        start, end = r.get("start"), r.get("end")
        if not (isinstance(start, dt.date) and isinstance(end, dt.date) and start < end):
            problems.append(f"{where}: start and end are dates, start first")
        for pid in r.get("paths") or []:
            if pid not in paths:
                problems.append(f"{where}: unknown path '{pid}'")
    _check_pillars(signals.get("pillars"), indicators, refs, problems)


DERIVED = ("free_cash_flow", "depreciation_share")  # pillar rows worked out from two series (bet/panels.py)


def _check_pillars(pillars, indicators: dict, refs: _Refs, problems: list[str]) -> None:
    """The four pillars (spec 8), if there are any: each names indicators, series and derived rows that exist."""
    if pillars is None:
        return
    if not isinstance(pillars, list):
        problems.append("signals.yaml pillars: a list of panels, each with an id, a label, indicators and series")
        return
    for p in pillars:
        if not isinstance(p, dict):
            problems.append("signals.yaml pillars: each pillar has an id, a label, indicators and series")
            continue
        where = f"signals.yaml pillars {p.get('id')}"
        refs.label(p, where, "id")
        for iid in p.get("indicators") or []:
            if iid not in indicators:
                problems.append(f"{where}: unknown indicator '{iid}'")
        for sid in p.get("series") or []:
            refs.known_series(sid, where)
        for d in p.get("derived") or []:
            if d not in DERIVED:
                problems.append(f"{where}: unknown derived row '{d}' (one of {', '.join(DERIVED)})")


def _check_events(events: dict, refs: _Refs, problems: list[str], today: dt.date) -> None:
    if not isinstance(events.get("releases"), list):
        problems.append("events.yaml: releases is missing")
        events["releases"] = []
    ids = [r.get("id") for r in events["releases"]]
    if len(set(ids)) != len(ids):
        problems.append("events.yaml releases: each id once")
    for r in events["releases"]:
        where = f"events.yaml releases {r.get('id')}"
        refs.label({**r, "label": r.get("name")}, where, "id", "lab")
        released = _date(r.get("released"), f"{where} released", problems)
        _date(r.get("announced"), f"{where} announced", problems)
        if released and released > today:
            problems.append(f"{where}: released {released} is after today")
        for key in ("source", "press"):
            if not _link(r.get(key)):
                problems.append(f"{where}: {key} must be an http(s) link")
        _seen(r, where, problems, today)
    if not isinstance(events.get("ai_start"), int):
        problems.append("events.yaml: ai_start is missing (the AI build-out's first year)")
    for aid, a in (events.get("analogs") or {}).items():
        where = f"events.yaml analogs.{aid}"
        refs.label(a, where, "shows")
        if not isinstance(a.get("start"), int) and a.get("by") != "launch":
            problems.append(f"{where}: give the year its build-out began (start), or by: launch")
        for ref in a.get("series") or []:
            sid, _, eid = str(ref).partition(".")
            refs.series_entity(sid, eid, where)


def _check_view_links(links, paths: dict, views: set[str] | None, problems: list[str]) -> None:
    if not isinstance(links, dict):
        problems.append("bet.yaml view_links: map each view id to its paths, such as "
                        "ai-capex-cut-2027: {capex_retrenchment: for}")
        return
    for vid, by_path in links.items():
        where = f"bet.yaml view_links.{vid}"
        if views is not None and vid not in views:
            problems.append(f"{where}: no view '{vid}' in views.yaml")
        if not isinstance(by_path, dict):
            problems.append(f"{where}: map each path to for or against, such as {{capex_retrenchment: for}}")
            continue
        for pid, effect in by_path.items():
            if pid not in paths:
                problems.append(f"{where}: unknown path '{pid}'")
            if effect not in VIEW_EFFECTS:
                problems.append(f"{where}.{pid}: '{effect}' must be for or against")


# ---------------------------------------------------------------- loading


def load(user: UserDir | None = None, today: dt.date | None = None, views: set[str] | None = None,
         themes: ThemeMap | None = None, base: Path = BET_DIR) -> Ledger:
    """The shipped ledger with the user's my/bet.yaml merged on top, checked.

    views and themes, when given, are the ids that view_links and channels may name."""
    today = today or dt.date.today()
    problems: list[str] = []
    shipped = {name: _yaml(base / f"{name}.yaml", problems) for name in FILES}
    entities = {str(k): dict(v or {}) for k, v in (shipped["series"].get("entities") or {}).items()}
    series: dict[str, Series] = {}
    for sid, raw in (shipped["series"].get("series") or {}).items():
        s = _series(str(sid), raw, problems)
        if s is not None:
            s.points = _sort(_points(s, raw.get("points") or {}, "series.yaml", entities, problems, today, False))
            series[s.id] = s
    model, signals, events = shipped["model"], shipped["signals"], shipped["events"]
    removed, view_links = 0, {}
    if user is not None and user.bet.exists():
        extra = _yaml(user.bet, problems)
        if isinstance(extra, dict):
            removed = _merge(extra, series, entities, model, signals, problems, today)
            view_links = extra.get("view_links") or {}
        else:
            problems.append("bet.yaml: write it as a mapping (series:, parameters:, view_links: ...)")
    refs = _Refs(series, entities, model, problems)
    gaps = shipped["series"].get("gaps") or []
    for g in gaps:
        if g.get("series"):
            refs.known_series(g["series"], "series.yaml gaps")
        if not _clean(g.get("what")):
            problems.append("series.yaml gaps: each gap says what is missing (what)")
    _guidance_whys(series.get("capex_guide"), problems)
    _check_model(model, refs, problems, today)
    _check_signals(signals, refs, themes, problems)
    _check_events(events, refs, problems, today)
    _check_view_links(view_links, signals.get("paths") or {}, views, problems)
    if problems:
        raise Problems(problems)
    return Ledger(entities, series, gaps, model, signals, events, view_links, removed)
