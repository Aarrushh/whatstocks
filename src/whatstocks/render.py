"""The dashboard: one self-contained HTML page with no external scripts, fonts or images.

It shows percentages only, never amounts, so a screenshot of it is safe to share."""
from __future__ import annotations

import datetime as dt
from html import escape

CSS = """
:root{color-scheme:light;--bg:#fbfbfa;--card:#fff;--ink:#141413;--ink2:#55534e;--ink3:#86847d;--line:#e6e4de;
--you:#2a6fdb;--world:#b4b1a8;--for:#1a8f5e;--against:#c2452d;--unclear:#8a8780;--warn-bg:#fff4e0;--warn:#7a4f00}
@media (prefers-color-scheme:dark){:root:not([data-theme=light]){color-scheme:dark;--bg:#181817;--card:#211f1e;
--ink:#f1efe9;--ink2:#c3c0b7;--ink3:#8f8c84;--line:#36342f;--you:#5b93ec;--world:#6f6c65;--for:#3db884;
--against:#e46a50;--unclear:#9a978f;--warn-bg:#3a2e17;--warn:#f2c26b}}
:root[data-theme=dark]{color-scheme:dark;--bg:#181817;--card:#211f1e;--ink:#f1efe9;--ink2:#c3c0b7;--ink3:#8f8c84;
--line:#36342f;--you:#5b93ec;--world:#6f6c65;--for:#3db884;--against:#e46a50;--unclear:#9a978f;--warn-bg:#3a2e17;--warn:#f2c26b}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.55 system-ui,-apple-system,"Segoe UI",sans-serif}
main{max-width:1000px;margin:0 auto;padding:28px 16px 64px}
h1{font-size:26px;margin:0}
h2{font-size:19px;margin:40px 0 4px}
h2+.sub{margin-bottom:12px}
h3{font-size:15.5px;margin:0 0 6px;line-height:1.4}
.sub,.muted{color:var(--ink2)}
.small{font-size:13px}
.lead{font-size:16px}
.banner{background:var(--warn-bg);color:var(--warn);border-radius:8px;padding:9px 13px;margin:10px 0;font-size:14px}
.card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:14px 16px;margin:10px 0}
.grid{display:grid;gap:10px;grid-template-columns:repeat(auto-fit,minmax(290px,1fr))}
.grid .card{margin:0}
.chip{display:inline-block;border:1px solid var(--line);border-radius:999px;padding:0 9px;margin:2px 4px 2px 0;font-size:12.5px;color:var(--ink2);white-space:nowrap}
.chip.for{color:var(--for);border-color:var(--for)}
.chip.against{color:var(--against);border-color:var(--against)}
.chip.unclear{color:var(--unclear)}
.chip.flag{color:var(--warn);background:var(--warn-bg);border-color:transparent}
.label{font-size:12px;font-weight:600;color:var(--ink3);text-transform:uppercase;letter-spacing:.04em;margin-right:6px}
.big{font-size:30px;font-weight:650;font-variant-numeric:tabular-nums;line-height:1.1}
.row{display:flex;gap:14px;align-items:center;justify-content:space-between}
ul.effects{list-style:none;padding:0;margin:8px 0 0}
ul.effects li{margin:3px 0}
.table-wrap{overflow-x:auto;background:var(--card);border:1px solid var(--line);border-radius:10px}
table{width:100%;border-collapse:collapse;font-variant-numeric:tabular-nums}
th,td{text-align:left;padding:8px 10px;border-bottom:1px solid var(--line);vertical-align:top}
tr:last-child td{border-bottom:0}
th{font-size:12px;color:var(--ink3);font-weight:600}
td.n,th.n{text-align:right;white-space:nowrap}
.bars{min-width:120px;width:28%}
.bar{height:7px;border-radius:4px;margin:4px 0}
.bar.you{background:var(--you)}
.bar.world{background:var(--world)}
.key{font-size:13px;color:var(--ink2)}
.key i{display:inline-block;width:10px;height:10px;border-radius:2px;margin:0 5px 0 12px;vertical-align:-1px}
details summary{cursor:pointer;color:var(--ink2);font-size:12.5px}
a{color:var(--you)}
svg .line{fill:none;stroke:var(--you);stroke-width:2}
svg .mid{stroke:var(--line);stroke-dasharray:3 3}
svg .now{stroke:var(--ink3);stroke-width:1}
footer{margin-top:48px;color:var(--ink3);font-size:13px}
@media (max-width:600px){.bars{min-width:48px;width:16%}th,td{padding:7px 6px}td:first-child{min-width:118px}.big{font-size:26px}}
"""


def _e(text) -> str:
    return escape(str(text), quote=True)


def _pct(x, digits: int = 1, signed: bool = False) -> str:
    if x is None:
        return "&ndash;"
    return f"{x * 100:+.{digits}f}%" if signed else f"{x * 100:.{digits}f}%"


def _num(x, digits: int = 2) -> str:
    return "&ndash;" if x is None else f"{x:.{digits}f}"


def _link(item: dict | None) -> str:
    if not item:
        return ""
    title = _e(item["title"])
    if str(item.get("url", "")).startswith(("http://", "https://")):
        title = f'<a href="{_e(item["url"])}" rel="noopener noreferrer">{title}</a>'
    return f'{title} <span class="muted">({_e(item.get("source", ""))})</span>'


def _header(ctx) -> str:
    banners = "".join(f'<div class="banner">{_e(b)}</div>' for b in ctx["banners"])
    return (
        f'<header><h1>whatstocks</h1><div class="sub">{_e(ctx["date"])} &middot; '
        f'shown as shares of your portfolio, valued in {_e(ctx["home"])}</div>{banners}</header>'
    )


def _brief(ctx) -> str:
    b = ctx["brief"]
    parts = ['<section><h2>Morning brief</h2><div class="sub small">Each event, read through the same four questions. '
             'Your AI wrote the words; every claim links to its source.</div>']
    if b is None:
        parts.append('<p class="muted">No brief today.</p></section>')
        return "".join(parts)
    if b.get("summary"):
        parts.append(f'<p class="lead">{_e(b["summary"])}</p>')
    if not b.get("events"):
        parts.append('<div class="card">A quiet day: nothing in the news touched your themes, holdings or views.</div>')
    for e in b.get("events", []):
        sources = "<br>".join(_link(ctx["news"].get(i)) for i in e["news_ids"])
        touches = e.get("touches") or {}
        chips = "".join(f'<span class="chip">{_e(ctx["theme_labels"].get(t, t))}</span>' for t in touches.get("themes", []))
        chips += "".join(f'<span class="chip">{_e(s)} &middot; {_pct(ctx["weights"].get(s))}</span>' for s in touches.get("holdings", []))
        effects = "".join(
            f'<li><span class="chip {_e(v["effect"])}">{_e(v["effect"])}</span><b>{_e(v["view_id"])}</b>: {_e(v.get("why", ""))}</li>'
            for v in e.get("views", [])
        )
        parts.append(
            f'<article class="card"><h3>{_e(e["what"])}</h3>'
            f'<p class="small">{sources}</p>'
            f'<p><span class="label">Money</span>{_e(e["money"])}</p>'
            f'<div><span class="label">Touches</span>{chips or "<span class=muted>nothing you hold</span>"}</div>'
            f'{f"<ul class=effects>{effects}</ul>" if effects else ""}</article>'
        )
    parts.append("</section>")
    return "".join(parts)


def _spark(view: dict, today: str) -> str:
    start = dt.date.fromisoformat(view["created"])
    end = dt.date.fromisoformat(view["resolves_by"])
    now = min(dt.date.fromisoformat(today), end)
    span = max((end - start).days, 1)
    w, h = 260, 46
    x = lambda d: 4 + (w - 8) * min(max((d - start).days, 0), span) / span
    y = lambda p: h - 4 - (h - 8) * p
    points = []
    forecasts = [(dt.date.fromisoformat(d), p) for d, p in view["forecasts"]]
    for i, (d, p) in enumerate(forecasts):
        nxt = forecasts[i + 1][0] if i + 1 < len(forecasts) else max(now, d)
        points += [(x(d), y(p)), (x(nxt), y(p))]
    path = "M" + " L".join(f"{a:.1f},{b:.1f}" for a, b in points)
    return (
        f'<svg viewBox="0 0 {w} {h}" width="100%" height="{h}" role="img" aria-label="Probability over time">'
        f'<line class="mid" x1="4" x2="{w - 4}" y1="{y(0.5):.1f}" y2="{y(0.5):.1f}"/>'
        f'<line class="now" x1="{x(now):.1f}" x2="{x(now):.1f}" y1="2" y2="{h - 2}"/>'
        f'<path class="line" d="{path}"/></svg>'
        f'<div class="small muted row"><span>{_e(view["created"])}</span><span>50% line dotted</span><span>{_e(view["resolves_by"])}</span></div>'
    )


def _views(ctx) -> str:
    parts = ['<section><h2>Your views</h2><div class="sub small">Your calls, in your words. '
             'The evidence counts come from the briefs; only you change a probability.</div>']
    if not ctx["views"]:
        parts.append('<p class="muted">No open views. Run /setup to write your first ones.</p></section>')
        return "".join(parts)
    parts.append('<div class="grid">')
    for v in ctx["views"]:
        ev = v["evidence"]
        week = "".join(f'<span class="chip {k}">{k} {ev["7"][k]}</span>' for k in ("for", "against", "unclear"))
        month = f'{ev["30"]["for"]} for, {ev["30"]["against"]} against, {ev["30"]["unclear"]} unclear'
        themes = "".join(
            f'<span class="chip">{_e(t["label"])} {"&uarr;" if t["direction"] == "up" else "&darr;"} '
            f'&middot; you {_pct(t["you"])} &middot; world {_pct(t["world"])}</span>'
            for t in v["themes"]
        )
        due = '<div class="banner small">Past its deadline: resolve it now.</div>' if v["due"] else ""
        parts.append(
            f'<article class="card">{due}<div class="row"><div class="big">{v["probability"] * 100:.0f}%</div>'
            f'<div class="small muted" style="text-align:right">resolves by {_e(v["resolves_by"])}<br>'
            f'{max(v["days_left"], 0)} days left</div></div>'
            f'<p>{_e(v["statement"])}</p>{_spark(v, ctx["date"])}'
            f'<p class="small">Last 7 days {week}<br><span class="muted">Last 30 days: {month}</span></p>'
            f'<div>{themes}</div><div class="small muted" style="margin-top:6px">{_e(v["id"])}</div></article>'
        )
    parts.append("</div></section>")
    return "".join(parts)


def _names(names: list) -> str:
    return ", ".join(f"{_e(m)} {_pct(s)}" for m, s in names[:10]) or "none"


def _exposure(ctx) -> str:
    x = ctx["exposure"]
    rows = sorted(x["themes"].items(), key=lambda kv: -max(kv[1]["you"], kv[1]["world"]))
    top = max([max(r["you"], r["world"]) for _, r in rows] + [1e-9])
    body = []
    for _, r in rows:
        ww = r["worst_weeks"] or {}
        body.append(
            f'<tr><td><b>{_e(r["label"])}</b><details><summary>names counted</summary><div class="small">'
            f'<b>You:</b> {_names(r["names_you"])}<br><b>World:</b> {_names(r["names_world"])}</div></details></td>'
            f'<td class="bars"><div class="bar you" style="width:{100 * r["you"] / top:.1f}%"></div>'
            f'<div class="bar world" style="width:{100 * r["world"] / top:.1f}%"></div></td>'
            f'<td class="n">{_pct(r["you"])}<br><span class="muted">{_pct(r["world"])}</span></td>'
            f'<td class="n">{_num(r["beta_you"])}<br><span class="muted">{_num(r["beta_world"])}</span></td>'
            f'<td class="n">{_pct(ww.get("you"), signed=True)}<br><span class="muted">{_pct(ww.get("world"), signed=True)}</span></td>'
            f'<td class="n muted">{_e(r["proxy"])}<br>{_pct(ww.get("proxy"), signed=True)}</td></tr>'
        )
    sells = "".join(
        f'<tr><td>{_e(s["name"])}<div class="small muted">{_e(s["start"])} to {_e(s["end"])}</div></td>'
        f'<td class="n">{_pct(s["you"], signed=True)}</td><td class="n muted">{_pct(s["world"], signed=True)}</td>'
        f'<td class="n muted">{_pct(s["coverage"], 0)}</td></tr>'
        for s in x["sell_offs"]
    )
    regions = lambda items: "".join(f'<tr><td>{_e(k)}</td><td class="n">{_pct(v)}</td></tr>' for k, v in items)
    blind = "".join(
        f'<article class="card"><h3>{_e(b["label"])}</h3><p class="small">{b["events"]} events in the news this week. '
        f'You: {_pct(b["you"])}. World index: {_pct(b["world"])}.</p>'
        f'<ul class="small">{"".join(f"<li>{_e(w)}</li>" for w in b["recent"])}</ul></article>'
        for b in ctx["blind_spots"]
    ) or '<p class="muted small">None this week.</p>'
    notes = "".join(f"<li>{_e(n)}</li>" for n in ctx["notes"])
    unresolved = x.get("unresolved") or 0
    return (
        '<section><h2>Exposure</h2><div class="sub small">Funds are broken into the companies they hold. '
        'Every number sits next to the same number for a world index fund.</div>'
        '<div class="key"><i style="background:var(--you)"></i>You<i style="background:var(--world)"></i>World index</div>'
        '<div class="table-wrap"><table><thead><tr><th>Theme</th><th></th><th class="n">Share<br>you / world</th>'
        '<th class="n">Theme beta<br>you / world</th><th class="n">Avg in proxy\'s<br>10 worst weeks</th>'
        f'<th class="n">Proxy</th></tr></thead><tbody>{"".join(body)}</tbody></table></div>'
        f'<p class="small muted">Theme beta: how much the portfolio moved per 1% move in the theme\'s proxy ETF, weekly over 2 years, '
        f'in {_e(ctx["home"])}. It covers {_pct(x["beta_coverage"], 0)} of your portfolio. Betas from calm years understate how closely '
        f'things move together in a real crash.</p>'
        f'{f"<p class=small>{_pct(unresolved)} of your portfolio is in funds that could not be looked through.</p>" if unresolved else ""}'
        '<h3 style="margin-top:22px">Past sell-offs, replayed on today\'s holdings</h3>'
        '<div class="table-wrap"><table><thead><tr><th>Window</th><th class="n">You</th><th class="n">World</th>'
        f'<th class="n">Covered</th></tr></thead><tbody>{sells}</tbody></table></div>'
        '<div class="grid" style="margin-top:22px">'
        f'<div><h3>Where your companies are listed or based</h3><div class="table-wrap"><table>{regions(x["regions"]["you"])}</table></div></div>'
        f'<div><h3>World index</h3><div class="table-wrap"><table>{regions(x["regions"]["world"])}</table></div></div></div>'
        '<h3 style="margin-top:22px">Blind spots</h3><div class="sub small">Themes busy in the news this week '
        'where you hold nothing, or under a quarter of the world index\'s share. This is where to look, not what to buy.</div>'
        f'{blind}'
        f'<details style="margin-top:16px"><summary>Data notes</summary><ul class="small">{notes or "<li>None</li>"}</ul></details>'
        '</section>'
    )


def _decision_row(d: dict) -> str:
    size = f" &middot; {d['size_pct']:g}%" if d["size_pct"] is not None else ""
    views = "".join(f'<span class="chip">{_e(v)}</span>' for v in d["views"]) or '<span class="muted">none</span>'
    flags = "".join(f'<span class="chip flag">{_e(f)}</span>' for f in d["flags"]) or '<span class="muted small">none</span>'
    return (
        f'<tr><td class="n">{_e(d["date"])}</td><td>{_e(d["action"])} <b>{_e(d["symbol"])}</b>{size}'
        f'<div class="small muted">{_e(d["reason"])}</div></td><td>{views}</td><td>{flags}</td></tr>'
    )


def _record(ctx) -> str:
    s = ctx["scores"]
    if s["count"]:
        score = (f'<div class="row"><div class="big">{s["mean"]:.3f}</div><div class="small muted">mean Brier score over '
                 f'{s["count"]} resolved views. Lower is better; always saying 50% scores {s["coin_flip"]}.</div></div>')
        if s["luck"]:
            score += '<p class="small muted">Under 20 resolved views, the score is mostly luck.</p>'
    else:
        score = '<p class="muted">No views have resolved yet.</p>'
    parts = [
        '<section><h2>Record</h2><div class="sub small">Your calls, scored when they resolve, '
        'and your trades next to the views they cite.</div>',
        f'<div class="card">{score}</div>',
    ]
    resolved = "".join(
        f'<tr><td>{_e(v["statement"])}</td><td>{_e(v["result"])}</td><td class="n">{_num(v["brier"], 3)}</td></tr>'
        for v in s["views"]
    )
    if resolved:
        parts.append('<div class="table-wrap"><table><thead><tr><th>Resolved view</th><th>Outcome</th>'
                     f'<th class="n">Brier</th></tr></thead><tbody>{resolved}</tbody></table></div>')
    decisions = "".join(_decision_row(d) for d in reversed(ctx["decisions"]))
    parts.append(
        '<h3 style="margin-top:22px">Decisions</h3><div class="table-wrap"><table><thead><tr><th class="n">Date</th>'
        '<th>Decision</th><th>Views cited</th><th>Flags</th></tr></thead>'
        f'<tbody>{decisions or "<tr><td colspan=4 class=muted>No decisions logged yet.</td></tr>"}</tbody></table></div>'
    )
    reviews = "".join(
        f'<tr><td>{_e(r["action"])} {_e(r["symbol"])} on {_e(r["date"])}</td><td class="n">{_pct(r["since"], signed=True)}</td>'
        f'<td class="n muted">{_pct(r["world"], signed=True)}</td></tr>'
        for r in ctx["reviews"]
    )
    if reviews:
        parts.append(
            '<h3 style="margin-top:22px">What happened after</h3><div class="table-wrap"><table><thead><tr><th>Decision</th>'
            f'<th class="n">Stock since</th><th class="n">World since</th></tr></thead><tbody>{reviews}</tbody></table></div>'
            '<p class="small muted">One trade\'s outcome is mostly noise. This is a record, not a verdict.</p>'
        )
    return "".join(parts) + "</section>"


def _footer() -> str:
    return (
        "<footer>whatstocks describes your own portfolio and your own stated views. It makes no recommendations "
        "and is not financial advice. Numbers are computed in code; the brief is written by your AI from the linked sources."
        "</footer>"
    )


def page(ctx: dict) -> str:
    body = _header(ctx) + _brief(ctx) + _views(ctx) + _exposure(ctx) + _record(ctx) + _footer()
    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        f'<title>whatstocks {_e(ctx["date"])}</title><style>{CSS}</style></head>'
        f"<body><main>{body}</main></body></html>"
    )
