"""The dashboard page: one self-contained HTML file that opens offline and fetches nothing.

The page is the React app in web/, which contributors build into assets/dashboard.html with its script, styles
and fonts inlined (docs/DASHBOARD.md). This module turns what dashboard.context() gathered into the page's view
model, with every number computed here, in code (P2), and fills the template with it.

Safety: the view model goes into a JSON script tag with <, >, & and the two JavaScript line separators escaped,
so no text from a feed, a file or the AI can end the tag. The page writes every text as text, and only http(s)
addresses become links (news links are checked here as well). The template's Content-Security-Policy stops the
page from fetching or sending anything. The page shows percentages only, never amounts (P4)."""
from __future__ import annotations

import json
import math
from importlib import resources

from . import geometry
from .brief import INSIDE_SHARE
from .files import Problems

PLACEHOLDER = "/*WS_DATA*/"
VERSION = 3
NO_BRIEF = "No brief today. Run /morning in Claude Code to have your AI read the news."
QUIET = "A quiet day: nothing in the news touched your themes, holdings or views."
CENTRE = "ai_buildout"  # the ripple map puts this theme in the middle when a ripple reaches it


# ---------------------------------------------------------------- the template


def template() -> str:
    path = resources.files("whatstocks").joinpath("assets", "dashboard.html")
    if not path.is_file():
        raise Problems(["The page template is missing (src/whatstocks/assets/dashboard.html): "
                        "build it with 'npm run build' in web/."])
    return path.read_text("utf-8")


def to_json(data: dict) -> str:
    """The view model as JSON that is safe inside a script tag: nothing in it can close the tag."""
    text = json.dumps(data, ensure_ascii=False, separators=(",", ":"), default=str)
    for raw, escaped in (("<", "\\u003c"), (">", "\\u003e"), ("&", "\\u0026"), (" ", "\\u2028"),
                         (" ", "\\u2029")):
        text = text.replace(raw, escaped)
    return text


def fill(page_template: str, data: dict) -> str:
    if page_template.count(PLACEHOLDER) != 1:
        raise Problems(["The page template must hold exactly one data placeholder: rebuild it with "
                        "'npm run build' in web/."])
    return page_template.replace(PLACEHOLDER, to_json(data))


def page(ctx: dict) -> str:
    return fill(template(), view_model(ctx))


# ---------------------------------------------------------------- pieces of the view model


def _finite(x):
    """JSON has no NaN or infinity: a number the code could not compute goes to the page as null."""
    if isinstance(x, float):
        return x if math.isfinite(x) else None
    if isinstance(x, dict):
        return {str(k): _finite(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [_finite(v) for v in x]
    return x


def _web_url(url) -> str | None:
    url = str(url or "")
    return url if url.startswith(("http://", "https://")) else None


def _news_item(item: dict) -> dict:
    source = str(item.get("source", ""))
    title = str(item.get("title", ""))
    if source and title.endswith(" - " + source):  # Google News adds the source to the title; the page shows it anyway
        title = title[: -len(" - " + source)]
    return {"title": title, "source": source, "url": _web_url(item.get("url"))}


def _cited(brief: dict) -> list[str]:
    """Every news id the brief cites. Only those headlines go into the page."""
    ids: list[str] = []
    for key in ("events", "themes", "holdings", "ripples", "watch"):
        for entry in brief.get(key) or []:
            ids += entry.get("news_ids") or []
    return list(dict.fromkeys(ids))


def _lead(ctx: dict) -> dict:
    brief = ctx["brief"]
    if brief is None:
        return {"kind": "none", "text": NO_BRIEF}
    if brief.get("summary"):
        return {"kind": "summary", "text": brief["summary"]}
    return {"kind": "quiet", "text": QUIET}


def _matter(ctx: dict) -> list[str]:
    """The themes that matter to this user today: 2% or more of the portfolio or named by an open view (the code's
    floor), any theme the AI chose to cover, and this week's blind spots. Busiest first, then the biggest."""
    covered = [t["id"] for t in (ctx["brief"] or {}).get("themes", [])]
    blind = [b["id"] for b in ctx["blind_spots"]]
    themes = ctx["exposure"]["themes"]
    ids = [t for t in dict.fromkeys(ctx["must_cover"] + covered + blind) if t in themes]
    return sorted(ids, key=lambda t: (-ctx["heat"].get(t, 0), -themes[t]["you"]))


def _watch_items(ctx: dict) -> list[dict]:
    """What the brief says to watch, and the dates from the user's own record, numbered in date order."""
    items = [{"date": w.get("when"), "what": w["what"], "news_ids": w.get("news_ids") or [],
              "themes": w.get("themes") or [], "holdings": w.get("holdings") or [], "record": False}
             for w in (ctx["brief"] or {}).get("watch", [])]
    items += [{"date": w["date"], "what": w["what"], "news_ids": [], "themes": [], "holdings": [], "record": True}
              for w in ctx["record_watch"]]
    items.sort(key=lambda w: (w["date"] is None, w["date"] or ""))
    for n, w in enumerate(items, start=1):
        w["n"] = n
    return items


def _themes(ctx: dict) -> dict:
    """Every theme: shares, betas, its proxy's moves, today's brief entry and the open views that name it."""
    entries = {t["id"]: t for t in (ctx["brief"] or {}).get("themes", [])}
    blind = {b["id"] for b in ctx["blind_spots"]}
    perf = ctx["perf"]
    out = {}
    for tid, row in ctx["exposure"]["themes"].items():
        proxy = ctx["theme_proxies"].get(tid) or row.get("proxy") or ""
        entry = entries.get(tid)
        out[tid] = {
            "id": tid, "label": row["label"], "proxy": proxy, "you": row["you"], "world": row["world"],
            "names_you": row.get("names_you", []), "names_world": row.get("names_world", []),
            "beta_you": row.get("beta_you"), "beta_world": row.get("beta_world"),
            "worst_weeks": row.get("worst_weeks") or {},
            "heat": ctx["heat"].get(tid, 0),
            "proxy_returns": perf.get("proxies", {}).get(proxy, {}),
            "weeks": perf.get("theme_weeks", {}).get(tid, []),
            "blind": tid in blind,
            "brief": ({"state": entry["state"], "why_it_matters": entry.get("why_it_matters", ""),
                       "news_ids": entry.get("news_ids") or []} if entry else None),
            "views": [{"id": v["id"], "probability": v["probability"]}
                      for v in ctx["views"] if any(t["id"] == tid for t in v["themes"])],
        }
    return out


def _holdings(ctx: dict) -> list[dict]:
    rows = []
    for h in ctx["holdings"]:
        top = sorted(((t, s) for t, s in h["themes"].items() if s >= INSIDE_SHARE), key=lambda kv: -kv[1])
        rows.append({**h, "top_themes": [[t, s] for t, s in top]})
    return rows


def _proxy_heat(ctx: dict) -> dict:
    """Each theme proxy's weekly return minus the world index's, over the weeks performance.py kept."""
    weeks_by = ctx["perf"].get("theme_weeks", {})
    themes = ctx["exposure"]["themes"]
    cols = sorted({w[0] for rows in weeks_by.values() for w in rows})
    rows = []
    for t in sorted(themes, key=lambda t: -themes[t]["you"]):
        by_week = {w[0]: w[1] for w in weeks_by.get(t, [])}
        rows.append({"id": t, "label": themes[t]["label"], "proxy": ctx["theme_proxies"].get(t, ""),
                     "cells": [by_week.get(c) for c in cols]})
    return {"cols": cols, "rows": rows}


def _news_heat(ctx: dict) -> dict:
    heat = ctx["news_heat"]
    rows = [{"id": t, "label": ctx["theme_labels"].get(t, t), "counts": counts}
            for t, counts in heat["rows"].items() if any(counts)]
    return {"dates": heat["dates"], "rows": rows}


def _exposure(ctx: dict) -> dict:
    x = ctx["exposure"]
    themes = x["themes"]
    held = [h for h in ctx["holdings"] if h["themes"]]
    cols = [t for t in sorted(themes, key=lambda t: -themes[t]["you"]) if themes[t]["you"] > 0]
    matrix = {
        "cols": cols,
        "rows": [{"symbol": h["symbol"], "cells": [h["weight"] * h["themes"].get(t, 0.0) for t in cols]} for h in held],
        "total": [themes[t]["you"] for t in cols],
    }
    countries = x.get("countries") or {"you": dict(x["regions"]["you"]), "world": dict(x["regions"]["world"])}
    return {
        "beta_coverage": x.get("beta_coverage"), "unresolved": x.get("unresolved") or 0.0,
        "sell_offs": x.get("sell_offs", []), "countries": countries,
        "currencies": [list(c) for c in x.get("currencies", {}).get("you", [])], "matrix": matrix,
    }


def _ripples(ctx: dict) -> dict | None:
    ripples = (ctx["brief"] or {}).get("ripples", [])
    if not ripples:
        return None
    themes = ctx["exposure"]["themes"]
    ids = list(dict.fromkeys([r["from"] for r in ripples] + [r["to"] for r in ripples]))
    nodes = [{"id": t, "label": ctx["theme_labels"].get(t, t), "weight": themes.get(t, {}).get("you", 0)} for t in ids]
    layout = geometry.network_layout(nodes, ripples, center=CENTRE if CENTRE in ids else None)
    for edge, r in zip(layout["edges"], ripples):
        edge.update({"from": r["from"], "to": r["to"], "effect": r["effect"], "why": r.get("why", ""),
                     "news_ids": r.get("news_ids") or []})
    return layout


def _scan(s: dict) -> dict:
    channels = s["channels"]
    points = [{"group": c["effect"], "label": c["label"], "you": c["you"], "world": c["world"], "index": i}
              for i, c in enumerate(channels)]
    return {
        "slug": s["slug"], "conflict": s["conflict"], "date": s["date"],
        "exposure_date": s.get("exposure_date") or s["date"], "summary": s.get("summary", ""),
        "news_ids": s.get("news_ids") or [], "advice": bool(s.get("advice")), "totals": s["totals"],
        "channels": channels, "holdings": [h for h in s["holdings"] if h["weight"] > 0],
        "analogs": s.get("analogs") or [], "watch": s.get("watch") or [],
        "news": {n["id"]: _news_item(n) for n in s.get("news", [])},
        "bubbles": geometry.bubble_groups(points),
        "proxy_channels": [c["id"] for c in channels if c.get("proxy")],
    }


def view_model(ctx: dict) -> dict:
    """Everything the page shows. Numbers are computed here or earlier in code; texts stay plain text."""
    brief = ctx["brief"] or {}
    perf = ctx["perf"]
    themes = _themes(ctx)
    matter = _matter(ctx)
    by_you = sorted(themes, key=lambda t: -themes[t]["you"])
    return _finite({
        "version": VERSION,
        "date": ctx["date"], "home": ctx["home"], "benchmark": ctx["benchmark"],
        "banners": ctx["banners"], "notes": ctx["notes"],
        "lead": _lead(ctx), "has_brief": ctx["brief"] is not None,
        "events": brief.get("events", []),
        "news": {i: _news_item(ctx["news"][i]) for i in _cited(brief) if i in ctx["news"]},
        "theme_labels": ctx["theme_labels"],
        "themes": themes,
        "theme_order": sorted(themes, key=lambda t: -max(themes[t]["you"], themes[t]["world"])),
        "matter": matter,
        "others": [t for t in by_you if t not in matter],
        "blind_spots": ctx["blind_spots"],
        "news_heat": _news_heat(ctx),
        "proxy_heat": _proxy_heat(ctx),
        "holdings": _holdings(ctx),
        "performance": {"returns": perf.get("returns", {}), "coverage": perf.get("coverage"),
                        "lines": perf.get("lines", {}), "world_weekly": perf.get("world_weekly", []),
                        "compare": perf.get("compare", []), "sectors": perf.get("sectors", [])},
        "exposure": _exposure(ctx),
        "views": ctx["views"], "scores": ctx["scores"], "decisions": ctx["decisions"], "reviews": ctx["reviews"],
        "watch": _watch_items(ctx),
        "ripples": _ripples(ctx),
        "scans": [_scan(s) for s in ctx["scans"]],
    })
