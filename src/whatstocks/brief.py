"""What the AI gets (the payload) and the checks on what it writes back (the brief). SPEC section 8, steps 6 to 8."""
from __future__ import annotations

import datetime as dt
import json
import re

from .files import Book

EFFECTS = ("for", "against", "unclear")
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


def build_payload(book: Book, today: dt.date, weights: dict[str, float], themes: dict, news: list[dict]) -> dict:
    """Tickers, percentages, views and news headlines. Never amounts, never URLs (P3, P4)."""
    names = {}
    for h in book.holdings:
        names.setdefault(h.symbol, (h.name, h.kind))
    return {
        "date": today.isoformat(),
        "holdings": [
            {"symbol": s, "name": names[s][0], "kind": names[s][1], "weight_pct": round(100 * w, 1)}
            for s, w in sorted(weights.items(), key=lambda kv: -kv[1])
        ],
        "themes": [
            {"id": tid, "label": t.label, "description": t.description,
             "your_share_pct": round(100 * themes[tid]["you"], 1), "world_share_pct": round(100 * themes[tid]["world"], 1)}
            for tid, t in book.themes.themes.items()
        ],
        "views": [
            {"id": v.id, "statement": v.statement, "probability": v.probability,
             "resolves_by": v.resolves_by.isoformat(), "themes": v.themes}
            for v in book.views if not v.outcome
        ],
        "news": [{"id": n["id"], "title": n["title"], "source": n["source"], "published": n["published"]} for n in news],
    }


def payload_leaks(payload: dict, amounts: list[float]) -> list[str]:
    """Money fields, or the user's amounts written out anywhere except public text (headlines, statements)."""
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
    ours = json.dumps({
        "holdings": [{k: v for k, v in h.items() if k != "name"} for h in payload["holdings"]],
        "themes": [{k: v for k, v in t.items() if k not in ("label", "description")} for t in payload["themes"]],
    })
    for amount in amounts:
        if amount is None or amount < 10:
            continue
        forms = {f"{amount:.2f}", f"{amount:,.2f}"} | ({f"{amount:.0f}", f"{amount:,.0f}"} if amount >= 1000 else set())
        if amount > 100:  # JSON drops trailing zeros (4321.5); no percentage can be this large
            forms.add(f"{amount:.2f}".rstrip("0").rstrip("."))
        for form in forms:
            if re.search(rf"(?<![\d.,]){re.escape(form)}(?![\d])", ours):
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


def validate_brief(brief, payload: dict) -> tuple[list[str], list[str]]:
    """(errors, advice). Errors always block. Advice-like wording blocks unless the user lets it through."""
    if not isinstance(brief, dict):
        return ["brief.json must be a JSON object"], []
    errors, advice = [], []
    if brief.get("date") != payload["date"]:
        errors.append(f"date must be {payload['date']}")
    news_ids = {n["id"] for n in payload["news"]}
    theme_ids = {t["id"] for t in payload["themes"]}
    symbols = {h["symbol"] for h in payload["holdings"]}
    view_ids = {v["id"] for v in payload["views"]}
    events = brief.get("events")
    if not isinstance(events, list):
        return errors + ["events must be a list (empty on a quiet day)"], advice
    if not events and not brief.get("quiet_day"):
        errors.append("no events: set quiet_day to true if nothing touched the themes, holdings or views")
    for i, e in enumerate(events, start=1):
        where = f"event {i}"
        if not isinstance(e, dict):
            errors.append(f"{where}: must be an object")
            continue
        cited = e.get("news_ids") or []
        if not cited:
            errors.append(f"{where}: cites no news_ids")
        errors += [f"{where}: news id '{n}' was not in today's payload" for n in cited if n not in news_ids]
        for key in ("what", "money"):
            if not isinstance(e.get(key), str) or not e[key].strip():
                errors.append(f"{where}: '{key}' is missing")
        touches = e.get("touches") or {}
        errors += [f"{where}: unknown theme '{t}'" for t in touches.get("themes", []) if t not in theme_ids]
        errors += [f"{where}: '{s}' is not a holding" for s in touches.get("holdings", []) if s not in symbols]
        for ve in e.get("views") or []:
            if ve.get("view_id") not in view_ids:
                errors.append(f"{where}: unknown or closed view '{ve.get('view_id')}'")
            if ve.get("effect") not in EFFECTS:
                errors.append(f"{where}: effect must be for, against or unclear")
            if not str(ve.get("why") or "").strip():
                errors.append(f"{where}: each view effect needs a 'why'")
    for text in _strings(brief):
        if URL.search(text):
            errors.append(f"contains a link ('{text[:60]}'): cite news ids, never URLs")
        for pattern in ADVICE:
            if m := pattern.search(text):
                advice.append(f"advice-like wording '{m.group(0)}' in: '{text[:80]}'")
                break
    return errors, advice
