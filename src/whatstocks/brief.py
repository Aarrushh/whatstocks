"""What the AI gets (the payload) and the checks on what it writes back (the brief). SPEC section 8, steps 6 to 8."""
from __future__ import annotations

import datetime as dt
import json
import re

from .files import Book

EFFECTS = ("for", "against", "unclear")
RIPPLE_EFFECTS = ("help", "hurt", "unclear")
MUST_COVER_SHARE = 0.02  # a theme this big in the portfolio always gets a line in the brief
INSIDE_SHARE = 0.02  # themes under this share of a holding are left off that holding
MAX_EVENTS, MAX_RIPPLES, MAX_WATCH = 10, 8, 8
MAX_BET_LINE = 400  # characters: the bet line is one or two sentences
MONEY_KEYS = {"quantity", "value", "amount", "total", "price", "cost"}
URL = re.compile(r"https?://|www\.", re.I)
ADVICE = [re.compile(p, re.I) for p in (
    r"\byou should\b",
    r"\bwe (?:recommend|suggest|advise)\b",
    r"\brecommend(?:s|ed)? (?:buying|selling|adding|trimming|holding)\b",
    r"\bconsider (?:buying|selling|adding|trimming|reducing|increasing|exiting)\b",
    r"\bshould (?:buy|sell|add|trim|reduce|increase|exit|avoid)\b",
    r"\b(?:good|right|bad) time to (?:buy|sell)\b",
    r"\bprice target\b",
    r"\btarget price\b",
    r"\b(?:buy|sell) the dip\b",
)]


def _pct(x: float) -> float:
    return round(100 * x, 1)


def build_payload(book: Book, today: dt.date, weights: dict[str, float], themes: dict, news: list[dict],
                  details: dict | None = None) -> dict:
    """Tickers, percentages, views and news headlines. Never amounts, never URLs (P3, P4)."""
    details = details or {}
    names = {}
    for h in book.holdings:
        names.setdefault(h.symbol, (h.name, h.kind))
    open_views = [v for v in book.views if not v.outcome]
    implied = {tid for v in open_views for tid in v.themes}

    def holding(symbol: str, weight: float) -> dict:
        inside = details.get(symbol, {})
        return {
            "symbol": symbol, "name": names[symbol][0], "kind": names[symbol][1], "weight_pct": _pct(weight),
            "countries": [[c, _pct(s)] for c, s in inside.get("countries", [])[:3]],
            "themes": [[tid, _pct(s)] for tid, s in sorted(inside.get("themes", {}).items(), key=lambda kv: -kv[1])
                       if s >= INSIDE_SHARE],
        }

    return {
        "date": today.isoformat(),
        "holdings": [holding(s, w) for s, w in sorted(weights.items(), key=lambda kv: -kv[1])],
        "themes": [
            {"id": tid, "label": t.label, "description": t.description,
             "your_share_pct": _pct(themes[tid]["you"]), "world_share_pct": _pct(themes[tid]["world"]),
             "must_cover": themes[tid]["you"] >= MUST_COVER_SHARE or tid in implied,
             "open_views": [v.id for v in open_views if tid in v.themes],
             "headlines_today": sum(1 for n in news if n.get("feed") == f"Search: {t.label}")}
            for tid, t in book.themes.themes.items()
        ],
        "views": [
            {"id": v.id, "statement": v.statement, "probability": v.probability,
             "resolves_by": v.resolves_by.isoformat(), "themes": v.themes}
            for v in open_views
        ],
        "news": [{"id": n["id"], "title": n["title"], "source": n["source"], "published": n["published"]} for n in news],
    }


def _numbers(node):
    """Every number in a payload, in place. Text is left out: headlines and names may hold any number."""
    if isinstance(node, bool) or node is None or isinstance(node, str):
        return None
    if isinstance(node, (int, float)):
        return node
    values = node.values() if isinstance(node, dict) else node
    return [x for v in values if (x := _numbers(v)) is not None]


def payload_leaks(payload: dict, amounts: list[float]) -> list[str]:
    """Money fields, or the user's amounts among the payload's numbers."""
    found = []

    def walk(node, path):
        if isinstance(node, dict):
            for key, value in node.items():
                if key.lower() in MONEY_KEYS:
                    found.append(f"field '{path}{key}' is not allowed")
                walk(value, f"{path}{key}.")
        elif isinstance(node, list):
            for value in node:
                walk(value, path)

    walk(payload, "")
    ours = json.dumps(_numbers(payload))
    for amount in amounts:
        if amount is None or amount < 10:
            continue
        forms = {f"{amount:.2f}"} | ({f"{amount:.0f}"} if amount >= 1000 else set())
        if amount > 100:  # JSON drops trailing zeros (4321.5); no percentage can be this large
            forms.add(f"{amount:.2f}".rstrip("0").rstrip("."))
        for form in sorted(forms):
            if re.search(rf"(?<![\d.]){re.escape(form)}(?![\d])", ours):
                found.append(f"an amount ({form}) appears in the payload")
    return found


def _strings(node):
    if isinstance(node, str):
        yield node
    elif isinstance(node, dict):
        for value in node.values():
            yield from _strings(value)
    elif isinstance(node, list):
        for value in node:
            yield from _strings(value)


class _Check:
    """Collects errors for one brief against one payload."""

    def __init__(self, payload: dict):
        self.errors: list[str] = []
        self.news = {n["id"] for n in payload["news"]}
        self.themes = {t["id"] for t in payload["themes"]}
        self.symbols = {h["symbol"] for h in payload["holdings"]}

    def text(self, where: str, item: dict, key: str) -> None:
        if not isinstance(item.get(key), str) or not item[key].strip():
            self.errors.append(f"{where}: '{key}' is missing")

    def cites(self, where: str, item: dict, required: bool = True) -> None:
        cited = item.get("news_ids") or []
        if not isinstance(cited, list):
            self.errors.append(f"{where}: news_ids must be a list")
            return
        if required and not cited:
            self.errors.append(f"{where}: cites no news_ids")
        self.errors += [f"{where}: news id '{n}' was not in today's payload" for n in cited if n not in self.news]

    def known(self, where: str, themes=(), holdings=()) -> None:
        self.errors += [f"{where}: unknown theme '{t}'" for t in themes if t not in self.themes]
        self.errors += [f"{where}: '{s}' is not a holding" for s in holdings if s not in self.symbols]

    def items(self, brief: dict, key: str, limit: int | None = None) -> list[tuple[str, dict]]:
        value = brief.get(key) or []
        if not isinstance(value, list):
            self.errors.append(f"{key} must be a list")
            return []
        if limit is not None and len(value) > limit:
            self.errors.append(f"{key}: at most {limit}, keep the ones that matter most")
        out = []
        for i, item in enumerate(value, start=1):
            where = f"{key.rstrip('s')} {i}"
            if isinstance(item, dict):
                out.append((where, item))
            else:
                self.errors.append(f"{where}: must be an object")
        return out


def validate_brief(brief, payload: dict) -> tuple[list[str], list[str]]:
    """(errors, advice). Errors always block. Advice-like wording blocks unless the user lets it through."""
    if not isinstance(brief, dict):
        return ["brief.json must be a JSON object"], []
    check = _Check(payload)
    if brief.get("date") != payload["date"]:
        check.errors.append(f"date must be {payload['date']}")
    view_ids = {v["id"] for v in payload["views"]}
    if not isinstance(brief.get("events"), list):
        return check.errors + ["events must be a list (empty on a quiet day)"], []
    if not brief["events"] and not brief.get("quiet_day"):
        check.errors.append("no events: set quiet_day to true if nothing touched the themes, holdings or views")

    for where, e in check.items(brief, "events", MAX_EVENTS):
        check.cites(where, e)
        for key in ("what", "money"):
            check.text(where, e, key)
        touches = e.get("touches") or {}
        check.known(where, touches.get("themes", []), touches.get("holdings", []))
        for ve in e.get("views") or []:
            if ve.get("view_id") not in view_ids:
                check.errors.append(f"{where}: unknown or closed view '{ve.get('view_id')}'")
            if ve.get("effect") not in EFFECTS:
                check.errors.append(f"{where}: effect must be for, against or unclear")
            if not str(ve.get("why") or "").strip():
                check.errors.append(f"{where}: each view effect needs a 'why'")

    covered = set()
    for where, t in check.items(brief, "themes"):
        tid = t.get("id")
        check.known(where, [tid])
        if tid in covered:
            check.errors.append(f"{where}: theme '{tid}' appears twice")
        covered.add(tid)
        for key in ("state", "why_it_matters"):
            check.text(where, t, key)
        check.cites(where, t, required=False)
    for t in payload["themes"]:
        if t["must_cover"] and t["id"] not in covered:
            check.errors.append(f"themes: add '{t['id']}' (it is 2% or more of the portfolio, or an open view names it)")

    noted = set()
    for where, h in check.items(brief, "holdings"):
        check.known(where, holdings=[h.get("symbol")])
        if h.get("symbol") in noted:
            check.errors.append(f"{where}: '{h.get('symbol')}' appears twice")
        noted.add(h.get("symbol"))
        check.text(where, h, "note")
        check.cites(where, h)

    for where, r in check.items(brief, "ripples", MAX_RIPPLES):
        check.known(where, [r.get("from"), r.get("to")])
        if r.get("from") == r.get("to"):
            check.errors.append(f"{where}: 'from' and 'to' must be different themes")
        if r.get("effect") not in RIPPLE_EFFECTS:
            check.errors.append(f"{where}: effect must be help, hurt or unclear")
        check.text(where, r, "why")
        check.cites(where, r)

    for where, w in check.items(brief, "watch", MAX_WATCH):
        check.text(where, w, "what")
        if w.get("when") is not None:
            try:
                if dt.date.fromisoformat(str(w["when"])).isoformat() < payload["date"]:
                    check.errors.append(f"{where}: 'when' is in the past")
            except ValueError:
                check.errors.append(f"{where}: 'when' must be a date like 2026-11-30, or left out")
        check.known(where, w.get("themes") or [], w.get("holdings") or [])
        check.cites(where, w)

    _check_bet(check, brief, payload)
    links, advice = text_checks(brief)
    return check.errors + links, advice


def _check_bet(check: _Check, brief: dict, payload: dict) -> None:
    """The line on "Will the bet pay off?" (spec 16): required when the regime or a path changed since the last
    logged state, optional otherwise. Its news ids must be today's."""
    bet = brief.get("bet")
    if bet is None:
        if (payload.get("bet") or {}).get("changed"):
            check.errors.append("bet: the regime or a crash path changed since the last brief: add bet.line, one or "
                                "two sentences on what moved, with the news_ids that explain it (if any)")
        return
    if not isinstance(bet, dict):
        check.errors.append("bet must be an object: {\"line\": \"...\", \"news_ids\": [...]}")
        return
    check.text("bet", bet, "line")
    if len(str(bet.get("line") or "")) > MAX_BET_LINE:
        check.errors.append(f"bet: the line is longer than {MAX_BET_LINE} characters: one or two sentences")
    check.cites("bet", bet, required=False)


def text_checks(node) -> tuple[list[str], list[str]]:
    """Links (errors) and advice-like wording anywhere in what the AI wrote."""
    errors, advice = [], []
    for text in _strings(node):
        if URL.search(text):
            errors.append(f"contains a link ('{text[:60]}'): cite news ids, never URLs")
        for pattern in ADVICE:
            if m := pattern.search(text):
                advice.append(f"advice-like wording '{m.group(0)}' in: '{text[:80]}'")
                break
    return errors, advice
