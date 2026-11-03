"""Load and check the user's files. The rules are in docs/SPEC.md section 6."""
from __future__ import annotations

import csv
import datetime as dt
import json
import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from .paths import THEMES_FILE, UserDir

ACTIONS = ("buy", "add", "trim", "sell", "hold")
KINDS = ("stock", "fund", "cash")
VIEW_ID = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
MIN_VIEW_DAYS = 30


class Problems(Exception):
    """Every problem found, so the user can fix them all in one pass."""

    def __init__(self, problems: list[str]):
        super().__init__("\n".join(problems))
        self.problems = problems


def read_json(path: Path):
    try:
        return json.loads(path.read_text("utf-8"))
    except json.JSONDecodeError as e:
        raise Problems([f"{path.name} line {e.lineno}: not valid JSON ({e.msg})"]) from None


def write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=1, ensure_ascii=False, default=str), "utf-8")

@dataclass
class Settings:
    home_currency: str
    benchmark: str


@dataclass
class Holding:
    row: int
    symbol: str
    isin: str
    name: str
    quantity: float | None
    value: float | None
    currency: str
    account: str
    kind: str


@dataclass
class Forecast:
    date: dt.date
    probability: float
    note: str


@dataclass
class View:
    id: str
    statement: str
    created: dt.date
    resolves_by: dt.date
    resolution: str
    themes: dict[str, str]
    forecasts: list[Forecast]
    outcome: dict | None

    def probability_on(self, day: dt.date) -> float | None:
        """The probability in force on a day, or None before the view existed."""
        p = None
        for f in self.forecasts:
            if f.date <= day:
                p = f.probability
        return p

    @property
    def probability(self) -> float:
        return self.forecasts[-1].probability

    @property
    def result(self) -> str | None:
        return self.outcome.get("result") if self.outcome else None


@dataclass
class Decision:
    id: str
    date: dt.date
    action: str
    symbol: str
    size_pct: float | None
    views: list[str]
    reason: str
    review_on: dt.date
    corrects: str | None


@dataclass
class Theme:
    id: str
    label: str
    description: str
    proxy: str
    core: list[str]
    partial: list[str]
    notes: str = ""
    news_query: str = ""

    def weight(self, symbol: str) -> float:
        if symbol in self.core:
            return 1.0
        if symbol in self.partial:
            return 0.5
        return 0.0


@dataclass
class ThemeMap:
    themes: dict[str, Theme]
    aliases: dict[str, list[str]] = field(default_factory=dict)

    def lines(self, member: str) -> list[str]:
        """Every listing of a company: the member symbol, then its alias lines."""
        return [member, *self.aliases.get(member, [])]

    def member_of(self, symbol: str) -> str:
        """The member symbol a listing belongs to (the symbol itself if it is not an alias)."""
        for member, others in self.aliases.items():
            if symbol in others:
                return member
        return symbol

    def weights(self, symbol: str) -> dict[str, float]:
        member = self.member_of(symbol)
        return {tid: w for tid, t in self.themes.items() if (w := t.weight(member))}


@dataclass
class Book:
    """Everything the user wrote, checked."""

    dir: UserDir
    settings: Settings
    holdings: list[Holding]
    views: list[View]
    decisions: list[Decision]
    themes: ThemeMap

    def view(self, view_id: str) -> View:
        return next(v for v in self.views if v.id == view_id)


def _yaml(path: Path, problems: list[str]) -> dict:
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except FileNotFoundError:
        problems.append(f"{path.name}: file not found")
    except yaml.YAMLError as e:
        mark = getattr(e, "problem_mark", None)
        line = f" line {mark.line + 1}" if mark else ""
        problems.append(f"{path.name}{line}: not valid YAML ({getattr(e, 'problem', e)})")
    return {}


def _date(value, where: str, problems: list[str]) -> dt.date | None:
    if isinstance(value, dt.datetime):
        return value.date()
    if isinstance(value, dt.date):
        return value
    try:
        return dt.date.fromisoformat(str(value))
    except ValueError:
        problems.append(f"{where}: '{value}' is not a YYYY-MM-DD date")
        return None


def _number(text: str) -> float | None:
    text = text.replace(",", "").replace(" ", "")
    return float(text) if text else None


def _clean(text) -> str:
    return " ".join(str(text or "").split())


def load_settings(path: Path, problems: list[str]) -> Settings:
    data = _yaml(path, problems)
    home = str(data.get("home_currency", "")).upper()
    if not re.fullmatch(r"[A-Z]{3}", home):
        problems.append(f"{path.name}: home_currency must be a 3-letter code such as EUR")
    benchmark = str(data.get("benchmark") or "")
    if not benchmark:
        problems.append(f"{path.name}: benchmark is missing")
    return Settings(home, benchmark)


def load_holdings(path: Path, problems: list[str], funds: set[str]) -> list[Holding]:
    try:
        rows = list(csv.DictReader(path.read_text(encoding="utf-8-sig").splitlines()))
    except FileNotFoundError:
        problems.append(f"{path.name}: file not found")
        return []
    if not rows:
        problems.append(f"{path.name}: no holdings")
    holdings, seen = [], set()
    for n, r in enumerate(rows, start=2):
        where = f"{path.name} row {n}"
        get = lambda key: (r.get(key) or "").strip()
        symbol, isin, currency = get("symbol"), get("isin"), get("currency").upper()
        if not symbol:
            hint = " (finding a symbol from an ISIN is not built yet)" if isin else ""
            problems.append(f"{where}: symbol is missing{hint}")
            continue
        try:
            quantity, value = _number(get("quantity")), _number(get("value"))
        except ValueError:
            problems.append(f"{where}: quantity and value must be numbers")
            continue
        kind = get("kind").lower() or (
            "cash" if symbol.upper().startswith("CASH-") else "fund" if symbol in funds else "stock"
        )
        if kind not in KINDS:
            problems.append(f"{where}: kind must be one of {', '.join(KINDS)}")
        if quantity is None and value is None:
            problems.append(f"{where}: needs a quantity or a value")
        if kind == "cash" and value is None:
            problems.append(f"{where}: cash needs a value")
        if value is not None and not currency:
            problems.append(f"{where}: a value needs a currency")
        key = (get("account"), symbol)
        if key in seen:
            problems.append(f"{where}: {symbol} appears twice in the same account")
        seen.add(key)
        holdings.append(Holding(n, symbol, isin, get("name"), quantity, value, currency, get("account"), kind))
    return holdings


def _members(raw) -> list[str]:
    return [str(m["symbol"]) if isinstance(m, dict) else str(m) for m in raw or []]


def _theme(tid: str, raw: dict, source: str, problems: list[str]) -> Theme:
    missing = [key for key in ("label", "description", "proxy") if not raw.get(key)]
    if missing:
        problems.append(f"{source}: theme '{tid}' is missing {', '.join(missing)}")
    members = raw.get("members") or {}
    return Theme(
        tid,
        _clean(raw.get("label", tid)),
        _clean(raw.get("description")),
        str(raw.get("proxy", "")),
        _members(members.get("core")),
        _members(members.get("partial")),
        _clean(raw.get("notes")),
        _clean(raw.get("news_query")),
    )


def load_themes(overlay: Path | None, problems: list[str], base: Path = THEMES_FILE) -> ThemeMap:
    """The shipped theme map, with the user's my/themes.yaml merged on top (SPEC 6.4)."""
    shipped = _yaml(base, problems)
    aliases = {str(k): [str(x) for x in v] for k, v in (shipped.get("aliases") or {}).items()}
    themes = {tid: _theme(tid, raw or {}, base.name, problems) for tid, raw in (shipped.get("themes") or {}).items()}
    if overlay is not None and overlay.exists():
        extra = _yaml(overlay, problems)
        for member, lines in (extra.get("aliases") or {}).items():
            known = aliases.setdefault(str(member), [])
            known += [str(x) for x in lines if str(x) not in known]
        for tid, raw in (extra.get("themes") or {}).items():
            raw = raw or {}
            if tid not in themes:
                themes[tid] = _theme(tid, raw, overlay.name, problems)
                continue
            theme = themes[tid]
            members = raw.get("members") or {}
            theme.core += [m for m in _members(members.get("core")) if m not in theme.core]
            theme.partial += [m for m in _members(members.get("partial")) if m not in theme.partial]
            removed = {str(m) for m in raw.get("remove") or []}
            theme.core = [m for m in theme.core if m not in removed]
            theme.partial = [m for m in theme.partial if m not in removed]
            for key in ("label", "description", "proxy", "notes", "news_query"):
                if raw.get(key):
                    setattr(theme, key, _clean(raw[key]))
    return ThemeMap(themes, aliases)


def load_views(path: Path, problems: list[str], themes: ThemeMap) -> list[View]:
    data = _yaml(path, problems)
    views, ids = [], set()
    for n, raw in enumerate(data.get("views") or [], start=1):
        vid = str(raw.get("id", ""))
        where = f"{path.name} view {vid or n}"
        if not VIEW_ID.match(vid):
            problems.append(f"{where}: id must be kebab-case, like ai-capex-cut-2027")
        if vid in ids:
            problems.append(f"{where}: id is used twice")
        ids.add(vid)
        for key in ("statement", "resolution"):
            if not _clean(raw.get(key)):
                problems.append(f"{where}: {key} is missing")
        created = _date(raw.get("created"), f"{where} created", problems)
        resolves_by = _date(raw.get("resolves_by"), f"{where} resolves_by", problems)
        if created and resolves_by and (resolves_by - created).days < MIN_VIEW_DAYS:
            problems.append(f"{where}: resolves_by must be at least {MIN_VIEW_DAYS} days after created")
        view_themes = {str(k): v for k, v in (raw.get("themes") or {}).items()}
        if not view_themes:
            problems.append(f"{where}: must imply up or down for at least one theme")
        for tid, direction in view_themes.items():
            if tid not in themes.themes:
                problems.append(f"{where}: unknown theme '{tid}'")
            if direction not in ("up", "down"):
                problems.append(f"{where}: theme '{tid}' must be up or down")
        forecasts = []
        for f in raw.get("forecasts") or []:
            day = _date(f.get("date"), f"{where} forecast", problems)
            p = f.get("probability")
            if isinstance(p, bool) or not isinstance(p, (int, float)) or not 0.01 <= p <= 0.99:
                problems.append(f"{where}: probability {p} must be between 0.01 and 0.99")
                continue
            if day:
                forecasts.append(Forecast(day, float(p), _clean(f.get("note"))))
        if not forecasts:
            problems.append(f"{where}: needs at least one forecast")
            continue
        if created and forecasts[0].date != created:
            problems.append(f"{where}: the first forecast must be dated {created}, the created date")
        if any(a.date >= b.date for a, b in zip(forecasts, forecasts[1:])):
            problems.append(f"{where}: forecast dates must strictly increase")
        outcome = raw.get("outcome") or None
        if outcome:
            result = outcome.get("result")
            if result not in ("yes", "no", "void"):
                problems.append(f"{where}: outcome result must be yes, no or void")
            day = _date(outcome.get("date"), f"{where} outcome date", problems)
            if day and created and day < created:
                problems.append(f"{where}: outcome date is before the view was created")
            if result == "void" and not outcome.get("note"):
                problems.append(f"{where}: a void outcome needs a note saying why")
            if result in ("yes", "no") and not outcome.get("source"):
                problems.append(f"{where}: an outcome needs a source link")
            outcome = {**outcome, "date": day}
        if created and resolves_by:
            views.append(View(
                vid, _clean(raw.get("statement")), created, resolves_by, _clean(raw.get("resolution")),
                view_themes, forecasts, outcome,
            ))
    return views


def load_decisions(path: Path, problems: list[str], views: list[View], holdings: list[Holding]) -> list[Decision]:
    if not path.exists():
        return []
    raws = _yaml(path, problems).get("decisions") or []
    view_ids = {v.id for v in views}
    held = {h.symbol for h in holdings}
    decisions: list[Decision] = []
    for n, raw in enumerate(raws, start=1):
        did = str(raw.get("id") or "")
        where = f"{path.name} decision {did or n}"
        earlier = {d.id for d in decisions}
        if not did:
            problems.append(f"{where}: id is missing")
        elif did in earlier:
            problems.append(f"{where}: id is used twice")
        day = _date(raw.get("date"), f"{where} date", problems)
        action = raw.get("action")
        if action not in ACTIONS:
            problems.append(f"{where}: action must be one of {', '.join(ACTIONS)}")
        symbol = str(raw.get("symbol") or "")
        sold_later = any(r.get("symbol") == symbol and r.get("action") == "sell" for r in raws[n:])
        if symbol not in held and action != "sell" and not sold_later:
            problems.append(f"{where}: {symbol or 'symbol'} is not in holdings.csv")
        cited = [str(v) for v in raw.get("views") or []]
        for vid in cited:
            if vid not in view_ids:
                problems.append(f"{where}: unknown view '{vid}'")
        size = raw.get("size_pct")
        if size is not None and (isinstance(size, bool) or not isinstance(size, (int, float))):
            problems.append(f"{where}: size_pct must be a number")
            size = None
        if not _clean(raw.get("reason")):
            problems.append(f"{where}: reason is missing")
        review_on = _date(raw["review_on"], f"{where} review_on", problems) if raw.get("review_on") else None
        corrects = raw.get("corrects")
        if corrects and corrects not in earlier:
            problems.append(f"{where}: corrects must point to an earlier entry")
        if day:
            decisions.append(Decision(
                did, day, str(action), symbol, size, cited, _clean(raw.get("reason")),
                review_on or day + dt.timedelta(days=365), corrects or None,
            ))
    return decisions


def load_book(user: UserDir, funds: set[str] = frozenset()) -> Book:
    """Load every file, collect every problem, and raise them together."""
    problems: list[str] = []
    settings = load_settings(user.settings, problems)
    themes = load_themes(user.themes, problems)
    holdings = load_holdings(user.holdings, problems, funds)
    views = load_views(user.views, problems, themes)
    decisions = load_decisions(user.decisions, problems, views, holdings)
    if problems:
        raise Problems(problems)
    return Book(user, settings, holdings, views, decisions, themes)
