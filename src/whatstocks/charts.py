"""Charts for the dashboard: plain HTML and inline SVG. No libraries, nothing fetched.

Charts only draw numbers the code already computed (P2). Every label goes through escape(). Hover text sits in
data-tip attributes, which the page script copies with textContent, never as HTML. Colours are CSS variables
(render.CSS), so the light and dark themes swap in one place: blue is the user, grey the world index, orange
what hurts, aqua what helps. Plots that stretch use SVG with preserveAspectRatio="none" and non-scaling
strokes; dots and most text are HTML, so they keep their shape and size at any width. The bubble map is SVG,
one small figure per group drawn at its own size, with every label placed in code so none overlaps another."""
from __future__ import annotations

import datetime as dt
import json
import math
from collections import defaultdict
from html import escape

DASH = "–"
SLOTS = 7  # categorical colours c1 to c7; anything past them folds into Other (c0)


def e(x) -> str:
    return escape(str(x), quote=True)


def pct(x, digits: int = 1, signed: bool = False) -> str:
    if x is None:
        return DASH
    return f"{x * 100:+.{digits}f}%" if signed else f"{x * 100:.{digits}f}%"


def gap(x, digits: int = 1) -> str:
    """A difference between two shares or returns, in percentage points."""
    return DASH if x is None else f"{x * 100:+.{digits}f} pts"


def move(x, digits: int = 1) -> str:
    """A signed move. The sign carries the direction; the colour only repeats it."""
    if x is None:
        return f'<span class="muted">{DASH}</span>'
    cls = "up" if x > 0 else "down" if x < 0 else ""
    return f'<span class="mv {cls}">{pct(x, digits, signed=True)}</span>'


def legend(items: list[tuple[str, str]]) -> str:
    """items: [(key classes, name)]. Names are plain text."""
    return '<div class="legend">' + "".join(f'<span><i class="key {cls}"></i>{e(name)}</span>' for cls, name in items) + "</div>"


def _ticks(lo: float, hi: float, n: int = 4) -> list[float]:
    if hi <= lo:
        return [lo]
    raw = (hi - lo) / n
    mag = 10 ** math.floor(math.log10(raw))
    step = next(m * mag for m in (1, 2, 2.5, 5, 10) if m * mag >= raw - 1e-12)
    t, out = math.ceil(lo / step - 1e-9) * step, []
    while t <= hi + 1e-9:
        out.append(round(t, 10))
        t += step
    return out


def line_chart(series: list[dict], height: int = 240, base: float = 100.0, label: str = "") -> str:
    """Lines indexed to `base` on their first day, on one axis; ticks read as the change since then.

    series: [{"name", "cls", "points": [[iso date, value], ...]}]. Hovering shows every series at the nearest date."""
    series = [s for s in series if len(s.get("points") or []) > 1]
    if not series:
        return '<p class="muted small">Not enough prices yet.</p>'
    days = sorted({p[0] for s in series for p in s["points"]})
    d0 = dt.date.fromisoformat(days[0])
    span = max((dt.date.fromisoformat(days[-1]) - d0).days, 1)
    values = [p[1] for s in series for p in s["points"]]
    lo, hi = min(values + [base]), max(values + [base])
    pad = (hi - lo) * 0.06 or 1.0
    lo, hi = lo - pad, hi + pad

    def x(day: str) -> float:
        return 100 * (dt.date.fromisoformat(day) - d0).days / span

    def y(v: float) -> float:
        return 100 * (hi - v) / (hi - lo)

    def since(v: float, digits: int = 1) -> str:
        c = v - base
        return "0%" if abs(c) < 1e-9 else f"{c:+.{digits}f}%"

    ticks = _ticks(lo, hi)
    tick_digits = 0 if all(abs(t - round(t)) < 1e-9 for t in ticks) else 1
    grid = "".join(
        f'<line class="grid{" base" if abs(t - base) < 1e-9 else ""}" x1="0" x2="100" y1="{y(t):.2f}" y2="{y(t):.2f}"/>'
        for t in ticks
    )
    paths, dots, keys = [], [], []
    for s in series:
        cls, (last_day, last) = e(s["cls"]), s["points"][-1]
        d = "M" + " L".join(f"{x(day):.2f},{y(v):.2f}" for day, v in s["points"])
        paths.append(f'<path class="ln {cls}" d="{d}"/>')
        dots.append(f'<i class="end {cls}" style="left:{x(last_day):.2f}%;top:{y(last):.2f}%"></i>')
        keys.append(f'<span><i class="key ln {cls}"></i>{e(s["name"])} <b>{e(since(last))}</b></span>')
    y_labels = "".join(f'<span style="top:{y(t):.2f}%">{e(since(t, tick_digits))}</span>' for t in ticks)
    picks = [days[round(i * (len(days) - 1) / 3)] for i in range(4)]
    x_labels = "".join(
        f'<span class="{a}" style="left:{x(day):.2f}%">{dt.date.fromisoformat(day):%b %Y}</span>'
        for day, a in zip(picks, ("l", "c", "c", "r"))
    )
    lookup = [dict(map(tuple, s["points"])) for s in series]
    data = {"b": base, "x": [round(x(day), 2) for day in days], "d": days,
            "s": [{"n": s["name"], "v": [lk.get(day) for day in days]} for s, lk in zip(series, lookup)]}
    svg = (f'<svg viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true">{grid}{"".join(paths)}</svg>')
    return (
        f'<figure class="lc" role="img" aria-label="{e(label)}"><div class="legend">{"".join(keys)}</div>'
        f'<div class="lc-box" style="height:{height}px" data-line="{e(json.dumps(data, separators=(",", ":")))}">'
        f'<div class="lc-y">{y_labels}</div><div class="lc-plot">{svg}{"".join(dots)}<i class="guide" hidden></i></div>'
        f'<div class="lc-x">{x_labels}</div></div></figure>'
    )


def spark(values: list[float], label: str = "") -> str:
    """A small trend line in a quiet colour, its last point marked."""
    if len(values) < 2:
        return ""
    lo, hi = min(values), max(values)
    rng, n = (hi - lo) or 1.0, len(values) - 1

    def y(v: float) -> float:
        return 10 + 80 * (hi - v) / rng

    points = " ".join(f"{100 * i / n:.2f},{y(v):.2f}" for i, v in enumerate(values))
    return (
        f'<span class="spark" role="img" aria-label="{e(label)}"><svg viewBox="0 0 100 100" preserveAspectRatio="none" '
        f'aria-hidden="true"><polyline points="{points}"/></svg><i style="top:{y(values[-1]):.2f}%"></i></span>'
    )


def step(created: str, resolves_by: str, forecasts: list, today: str) -> str:
    """A view's probability over time, from the day it was written to its deadline. The hairline is 50%."""
    start, end = dt.date.fromisoformat(created), dt.date.fromisoformat(resolves_by)
    now = min(dt.date.fromisoformat(today), end)
    span = max((end - start).days, 1)

    def x(day: dt.date) -> float:
        return 100 * min(max((day - start).days, 0), span) / span

    def y(p: float) -> float:
        return 6 + 88 * (1 - p)

    points, calls = [], [(dt.date.fromisoformat(d), p) for d, p in forecasts]
    for i, (day, p) in enumerate(calls):
        nxt = calls[i + 1][0] if i + 1 < len(calls) else max(now, day)
        points += [(x(day), y(p)), (x(nxt), y(p))]
    path = "M" + " L".join(f"{a:.2f},{b:.2f}" for a, b in points)
    return (
        '<div class="stepc"><svg viewBox="0 0 100 100" preserveAspectRatio="none" role="img" '
        'aria-label="Your probability over time">'
        f'<line class="grid" x1="0" x2="100" y1="{y(0.5):.2f}" y2="{y(0.5):.2f}"/>'
        f'<line class="now" x1="{x(now):.2f}" x2="{x(now):.2f}" y1="0" y2="100"/>'
        f'<path class="ln you" d="{path}"/></svg><span class="stepc-l" style="top:{y(0.5):.2f}%">50%</span></div>'
        f'<div class="small muted row"><span>{e(created)}</span><span>{e(resolves_by)}</span></div>'
    )


def dumbbell(rows: list[tuple], names: tuple[str, str] = ("You", "World index")) -> str:
    """rows: [(label, you, world)] as shares on one scale. A blue dot for you, a grey one for the world index."""
    if not rows:
        return ""
    top = max([max(r[1] or 0, r[2] or 0) for r in rows] + [1e-9])
    out = []
    for label, you, world in rows:
        a, b = 100 * (you or 0) / top, 100 * (world or 0) / top
        tip = f"{label}: you {pct(you)}, world index {pct(world)} ({gap((you or 0) - (world or 0))})"
        out.append(
            f'<div class="db" tabindex="0" data-tip="{e(tip)}"><span class="db-l">{e(label)}</span>'
            f'<span class="db-t"><i class="db-c" style="left:{min(a, b):.2f}%;width:{abs(a - b):.2f}%"></i>'
            f'<i class="dot world" style="left:{b:.2f}%"></i><i class="dot you" style="left:{a:.2f}%"></i></span>'
            f'<span class="db-v"><b>{pct(you)}</b> <span class="muted">{pct(world)}</span></span></div>'
        )
    return legend([("you", names[0]), ("world", names[1])]) + f'<div class="dumbbell">{"".join(out)}</div>'


def _half_bar(v: float | None, top: float, cls: str) -> str:
    if v is None:
        return '<span class="dv-r"><span class="dv-na">no prices</span></span>'
    w = 50 * abs(v) / top
    left = 50 - w if v < 0 else 50
    side = "neg" if v < 0 else "pos"
    return f'<span class="dv-r"><i class="dv-b {cls} {side}" style="left:{left:.2f}%;width:{w:.2f}%"></i></span>'


def diverging(rows: list[tuple], names: tuple[str, str] = ("You", "World index")) -> str:
    """rows: [(label, note, you, world)] moves. Each pair of bars grows left (a fall) or right (a rise) from zero."""
    top = max([abs(v) for r in rows for v in r[2:4] if v is not None] + [1e-9])
    out = []
    for label, note, you, world in rows:
        tip = f"{label}: you {pct(you, signed=True)}, world index {pct(world, signed=True)}"
        out.append(
            f'<div class="dv" tabindex="0" data-tip="{e(tip)}"><span class="dv-l">{e(label)}<small>{e(note)}</small></span>'
            f'<span class="dv-t">{_half_bar(you, top, "you")}{_half_bar(world, top, "world")}</span>'
            f'<span class="dv-v">{move(you)}<span class="muted"> / </span>{move(world)}</span></div>'
        )
    return legend([("sw you", names[0]), ("sw world", names[1])]) + f'<div class="dvs">{"".join(out)}</div>'


def balance(rows: list[tuple]) -> str:
    """rows: [(label, note, hurt, help)] shares 0 to 1. Hurt grows left from the middle, help grows right."""
    out = []
    for label, note, hurt, help_ in rows:
        tip = f"{label}: {pct(hurt, 0)} reached by what it would hurt, {pct(help_, 0)} by what it would help"
        out.append(
            f'<div class="dv" tabindex="0" data-tip="{e(tip)}"><span class="dv-l">{e(label)}<small>{e(note)}</small></span>'
            f'<span class="dv-t">{_half_bar(-(hurt or 0), 1.0, "hurt")}{_half_bar(help_ or 0, 1.0, "help")}</span>'
            f'<span class="dv-v">{pct(hurt, 0)}<span class="muted"> / </span>{pct(help_, 0)}</span></div>'
        )
    return legend([("sw hurt", "Hurt (left)"), ("sw help", "Help (right)")]) + f'<div class="dvs">{"".join(out)}</div>'


def stacked(rows: list[tuple], top: int = SLOTS) -> str:
    """rows: [(label, {key: share})] as 100% bars. A key keeps one colour in every row; keys past `top` fold
    into Other. A share prints inside its block only when the block is wide enough for it."""
    best = defaultdict(float)
    for _, parts in rows:
        for k, v in parts.items():
            if k != "Other":
                best[k] = max(best[k], v)
    keys = [k for k, _ in sorted(best.items(), key=lambda kv: -kv[1])][:top]
    slot = {k: f"c{i + 1}" for i, k in enumerate(keys)}
    out, any_other = [], False
    for label, parts in rows:
        other = sum(v for k, v in parts.items() if k not in slot)
        any_other = any_other or other > 0
        segs = []
        for k, v, cls in [(k, parts.get(k, 0.0), slot[k]) for k in keys] + [("Other", other, "c0")]:
            if v <= 0:
                continue
            inside = f"<b>{pct(v, 0)}</b>" if v >= 0.11 else ""
            segs.append(f'<i class="seg {cls}" style="flex-grow:{v:.5f}" tabindex="0" data-tip="{e(f"{label}: {k} {pct(v)}")}">{inside}</i>')
        out.append(f'<div class="st"><span class="st-l">{e(label)}</span><span class="st-bar">{"".join(segs)}</span></div>')
    keyed = [(f"sw {slot[k]}", k) for k in keys] + ([("sw c0", "Other")] if any_other else [])
    return legend(keyed) + f'<div class="stack">{"".join(out)}</div>'


def strip(values: list[float | None], tips: list[str], vmax: float = 0.05) -> str:
    """One row of a diverging heat map, without labels: the theme cards' last 12 weeks."""
    cells = []
    for v, tip in zip(values, tips):
        if v is None:
            cells.append(f'<i class="hm na" data-tip="{e(tip)}"></i>')
        else:
            cells.append(f'<i class="hm {"pos" if v > 0 else "neg"}" style="--a:{min(abs(v) / vmax, 1):.2f}" data-tip="{e(tip)}"></i>')
    return f'<div class="strip" style="grid-template-columns:repeat({max(len(values), 1)},1fr)">{"".join(cells)}</div>'


def heatmap(cols: list[str], rows: list[tuple], kind: str = "diverging", col_labels: list[str] | None = None,
            fmt=gap, vmax: float | None = None) -> str:
    """rows: [(label, [value or None per column], [tip per column])].

    'diverging': blue above zero, red below, grey near zero. 'sequential': one blue, deeper is more. The same
    numbers sit in a table under it."""
    vals = [abs(v) for _, vs, _ in rows for v in vs if v is not None]
    vmax = vmax or (max(vals) if vals else 0) or 1.0
    col_labels = col_labels or cols
    picks = {0, len(cols) // 2, len(cols) - 1}
    cells = ['<span></span>'] + [
        f'<span class="hm-x{" r" if i == len(cols) - 1 and i else ""}">{e(col_labels[i]) if i in picks else ""}</span>'
        for i in range(len(cols))
    ]
    for label, vs, tips in rows:
        cells.append(f'<span class="hm-l">{e(label)}</span>')
        for v, tip in zip(vs, tips):
            if v is None:
                cells.append(f'<i class="hm na" data-tip="{e(tip)}"></i>')
                continue
            cls = "seq" if kind == "sequential" else ("pos" if v > 0 else "neg")
            cells.append(f'<i class="hm {cls}" style="--a:{min(abs(v) / vmax, 1):.2f}" data-tip="{e(tip)}"></i>')
    if kind == "sequential":
        keys = legend([("sw hm-mid", "none"), ("sw seq-lo", "some"), ("sw seq-hi", "most")])
    else:
        keys = legend([("sw neg", "below the world index"), ("sw hm-mid", "about the same"), ("sw pos", "above the world index")])
    head = "".join(f"<th class='n'>{e(c)}</th>" for c in col_labels)
    body = "".join(
        f"<tr><td>{e(label)}</td>" + "".join(f"<td class='n'>{e(fmt(v)) if v is not None else DASH}</td>" for v in vs) + "</tr>"
        for label, vs, _ in rows
    )
    return (
        f'{keys}<div class="hmap" style="grid-template-columns:minmax(96px,1.3fr) repeat({len(cols)},minmax(9px,1fr))">'
        f'{"".join(cells)}</div><details class="twin"><summary>Numbers</summary><div class="tw"><table>'
        f"<thead><tr><th></th>{head}</tr></thead><tbody>{body}</tbody></table></div></details>"
    )


def heat_table(cols: list[str], rows: list[tuple], fmt=pct, total: tuple | None = None) -> str:
    """rows: [(label, [value per column])], with the number printed in every cell and a blue tint that deepens
    with it. A table rather than a grid when the columns need their full names. total: (label, [values])."""
    vals = [v for _, vs in rows for v in vs if v]
    vmax = max(vals) if vals else 1.0

    def cell(v) -> str:
        if not v:
            return f'<td class="n hc"><span class="muted">{DASH}</span></td>'
        return f'<td class="n hc" style="--a:{0.1 + 0.45 * min(v / vmax, 1):.2f}"><span>{e(fmt(v))}</span></td>'

    head = "".join(f'<th class="n">{e(c)}</th>' for c in cols)
    body = "".join(f'<tr><th scope="row">{e(label)}</th>{"".join(cell(v) for v in vs)}</tr>' for label, vs in rows)
    foot = ""
    if total:
        cells = "".join(f'<td class="n"><b>{e(fmt(v))}</b></td>' for v in total[1])
        foot = f'<tfoot><tr><th scope="row">{e(total[0])}</th>{cells}</tr></tfoot>'
    return f'<div class="tw"><table class="ht"><thead><tr><th></th>{head}</tr></thead><tbody>{body}</tbody>{foot}</table></div>'


def _text_width(text: str, size: float) -> float:
    """A generous guess at a label's width in SVG units: enough to keep labels apart."""
    return len(text) * size * 0.6


def _box_hits(box: tuple, circle: tuple) -> bool:
    x0, y0, x1, y1 = box
    cx, cy, r = circle
    return math.hypot(cx - min(max(cx, x0), x1), cy - min(max(cy, y0), y1)) < r - 1e-6


def _overlap(a: tuple, b: tuple) -> bool:
    return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]


def bubble_layout(points: list[dict], biggest: float = 58.0) -> dict[str, dict]:
    """Where every bubble and label of a bubble map goes, in SVG units.

    points: [{"group", "label", "you", "world", ...}], shares as fractions, all on one scale: a bubble's area is
    your share, its ring the world index's. Within a group, bubbles are packed outward from the middle, biggest
    first. A label goes inside its bubble when it fits, else beside it where it touches no bubble and no other
    label, else into the group's list. Returns {group: {"bubbles": [...], "listed": [point, ...]}}, each bubble
    {"x", "y", "r", "ring", "outer", "point", "inside", "beside"}, where "beside" is None or
    {"box": (x0, y0, x1, y1), "x", "y", "anchor"}."""
    top = max([p["you"] for p in points] + [p["world"] for p in points] + [1e-9])

    def radius(share: float) -> float:
        return biggest * math.sqrt(max(share, 0.0) / top)

    out: dict[str, dict] = {}
    for p in sorted(points, key=lambda p: -max(p["you"], p["world"])):
        placed = out.setdefault(p["group"], {"bubbles": [], "listed": []})["bubbles"]
        r, ring = max(radius(p["you"]), 3.0), radius(p["world"])
        outer = max(r, ring) + 3.0
        x = y = 0.0
        step = 0
        # Walk out along a spiral from the middle until the bubble overlaps none placed so far.
        while any(math.hypot(x - b["x"], y - b["y"]) < outer + b["outer"] for b in placed) and step < 20000:
            step += 1
            turn = 0.25 * step
            x, y = turn * math.cos(turn), turn * math.sin(turn)
        placed.append({"x": x, "y": y, "r": r, "ring": ring, "outer": outer, "point": p, "inside": False, "beside": None})

    for group in out.values():
        circles = [(b["x"], b["y"], b["outer"]) for b in group["bubbles"]]
        boxes: list[tuple] = []
        for b in group["bubbles"]:
            p, x, y = b["point"], b["x"], b["y"]
            if b["r"] >= 22 and _text_width(p["label"], 11) <= 2 * b["r"] - 8:
                b["inside"] = True
                continue
            w, h, gap = _text_width(f'{p["label"]} {pct(p["you"])}', 10.5), 13.0, b["outer"]
            spots = (((x + gap, y - h / 2, x + gap + w, y + h / 2), x + gap, "start"),
                     ((x - gap - w, y - h / 2, x - gap, y + h / 2), x - gap, "end"),
                     ((x - w / 2, y - gap - h, x + w / 2, y - gap), x, "middle"),
                     ((x - w / 2, y + gap, x + w / 2, y + gap + h), x, "middle"))
            for box, tx, anchor in spots:
                if not any(_box_hits(box, c) for c in circles) and not any(_overlap(box, o) for o in boxes):
                    boxes.append(box)
                    b["beside"] = {"box": box, "x": tx, "y": box[3] - 3.0, "anchor": anchor}
                    break
            else:
                group["listed"].append(p)
    return out


def bubble_map(points: list[dict], groups: list[tuple[str, str]]) -> str:
    """A bubble map drawn from bubble_layout, one SVG per group, so groups wrap on a narrow screen and text keeps
    its size. points also carry "cls" (the bubble's classes) and "tip" (plain hover text). groups:
    [(group, caption)] in the order to show them; a group with no bubbles is left out."""
    if not points:
        return '<p class="muted small">Nothing to plot.</p>'
    layout = bubble_layout(points)
    figures = []
    for key, caption in groups:
        group = layout.get(key)
        if not group:
            continue
        marks, xs, ys = [], [], []
        for b in group["bubbles"]:
            p, x, y = b["point"], b["x"], b["y"]
            xs += [x - b["outer"], x + b["outer"]]
            ys += [y - b["outer"], y + b["outer"]]
            ring = f'<circle class="bm-w" cx="{x:.1f}" cy="{y:.1f}" r="{b["ring"]:.1f}"/>' if b["ring"] >= 2 else ""
            text = ""
            if b["inside"]:
                text = (f'<text class="bm-t" x="{x:.1f}" y="{y - 2:.1f}">{e(p["label"])}</text>'
                        f'<text class="bm-t v" x="{x:.1f}" y="{y + 12:.1f}">{pct(p["you"])}</text>')
            elif b["beside"]:
                spot = b["beside"]
                xs += [spot["box"][0], spot["box"][2]]
                ys += [spot["box"][1], spot["box"][3]]
                text = (f'<text class="bm-l" x="{spot["x"]:.1f}" y="{spot["y"]:.1f}" text-anchor="{spot["anchor"]}">'
                        f'{e(p["label"])} <tspan class="v">{pct(p["you"])}</tspan></text>')
            marks.append(f'<g class="bm-b {e(p["cls"])}" tabindex="0" data-tip="{e(p["tip"])}">'
                         f'<circle class="bm-y" cx="{x:.1f}" cy="{y:.1f}" r="{b["r"]:.1f}"/>{ring}{text}</g>')
        x0, y0 = min(xs) - 8, min(ys) - 4
        w, h = max(xs) - x0 + 8, max(ys) - y0 + 4
        listed = "".join(f'<li tabindex="0" data-tip="{e(p["tip"])}"><i class="{e(p["cls"])}"></i>'
                         f'{e(p["label"])} {pct(p["you"])}</li>' for p in group["listed"])
        figures.append(
            f'<figure class="bm-c"><figcaption>{e(caption)}</figcaption>'
            f'<svg viewBox="{x0:.1f} {y0:.1f} {w:.1f} {h:.1f}" width="{w:.0f}" height="{h:.0f}" role="img" '
            f'aria-label="{e(caption)}">{"".join(marks)}</svg>'
            + (f'<ul class="bm-list">{listed}</ul>' if listed else "") + "</figure>"
        )
    return f'<div class="bmap">{"".join(figures)}</div>'


def network(nodes: list[dict], edges: list[dict], center: str | None = None, uid: str = "net") -> str:
    """Ripples between themes. nodes: [{"id", "label", "weight"}]; edges: [{"from", "to", "cls", "tip"}].

    Nodes sit on an oval, the centre node (if given) in the middle; a node's size follows weight. Edges are
    curved arrows, bent to one side so A to B and B to A stay apart."""
    if not nodes:
        return ""
    w, h = 140.0, 100.0
    ring = [n for n in nodes if n["id"] != center]
    pos = {}
    for i, n in enumerate(ring):
        angle = -math.pi / 2 + 2 * math.pi * i / max(len(ring), 1)
        pos[n["id"]] = (w / 2 + 44 * math.cos(angle), h / 2 + 35 * math.sin(angle))
    if center in {n["id"] for n in nodes}:
        pos[center] = (w / 2, h / 2)
    wmax = max([n.get("weight") or 0 for n in nodes] + [1e-9])
    radius = {n["id"]: 2.2 + 3.4 * math.sqrt((n.get("weight") or 0) / wmax) for n in nodes}

    def toward(px: float, py: float, qx: float, qy: float, r: float) -> tuple[float, float]:
        d = math.hypot(qx - px, qy - py) or 1.0
        return px + (qx - px) * r / d, py + (qy - py) * r / d

    paths = []
    approach = []  # the directions, from the centre node, of the edges that touch it
    for edge in edges:
        (x1, y1), (x2, y2) = pos[edge["from"]], pos[edge["to"]]
        cx, cy = (x1 + x2) / 2 - (y2 - y1) * 0.16, (y1 + y2) / 2 + (x2 - x1) * 0.16
        if center in (edge["from"], edge["to"]):
            approach.append(math.atan2(cy - pos[center][1], cx - pos[center][0]))
        sx, sy = toward(x1, y1, cx, cy, radius[edge["from"]] + 1.0)
        ex, ey = toward(x2, y2, cx, cy, radius[edge["to"]] + 1.6)
        d = f"M{sx:.2f},{sy:.2f} Q{cx:.2f},{cy:.2f} {ex:.2f},{ey:.2f}"
        cls = e(edge["cls"])
        paths.append(f'<path class="edge {cls}" d="{d}" marker-end="url(#{uid}-{cls})"/>'
                     f'<path class="hit" d="{d}" data-tip="{e(edge["tip"])}"/>')
    markers = "".join(
        f'<marker id="{uid}-{c}" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="3.6" markerHeight="3.6" '
        f'markerUnits="userSpaceOnUse" orient="auto"><path class="ah {c}" d="M0,1 L9,5 L0,9 z"/></marker>'
        for c in ("hurt", "help", "unclear")
    )
    def clearest() -> str:
        """The side of the centre node that its edges come in furthest from, so its label hides no arrow."""
        sides = (("c below", math.pi / 2), ("r", 0.0), ("l", math.pi), ("c above", -math.pi / 2),
                 ("dr", math.pi / 4), ("ur", -math.pi / 4), ("dl", 3 * math.pi / 4), ("ul", -3 * math.pi / 4))
        return max(sides, key=lambda s: min([abs(math.remainder(s[1] - a, 2 * math.pi)) for a in approach] + [math.pi]))[0]

    circles, labels = [], []
    for n in nodes:
        x, y = pos[n["id"]]
        hub = " hub" if n["id"] == center else ""
        circles.append(f'<circle class="node{hub}" cx="{x:.2f}" cy="{y:.2f}" r="{radius[n["id"]]:.2f}"/>')
        if n["id"] == center:
            side = clearest()
        elif abs(x - w / 2) < 6:
            side = "c " + ("above" if y < h / 2 - 5 else "below")
        else:
            side = "l" if x < w / 2 else "r"
        # --r is the node's radius in SVG units; the page's CSS turns it into an offset that grows with the chart.
        labels.append(f'<span class="nl {side}" style="left:{100 * x / w:.2f}%;top:{100 * y / h:.2f}%;'
                      f'--r:{radius[n["id"]]:.2f}">{e(n["label"])}</span>')
    return (
        f'<div class="net"><svg viewBox="0 0 {w:.0f} {h:.0f}" role="img" aria-label="Ripples between themes">'
        f'<defs>{markers}</defs>{"".join(paths)}{"".join(circles)}</svg>{"".join(labels)}</div>'
        + legend([("ln hurt", "hurts"), ("ln help", "helps"), ("ln unclear", "unclear")])
    )


def timeline(items: list[dict], today: dt.date, days: int = 90) -> str:
    """items: [{"date": iso, "n": number, "tip"}] on one axis from today. The list under it carries the words."""
    shown = [i for i in items if i.get("date") and 0 <= (dt.date.fromisoformat(i["date"]) - today).days <= days]
    if not shown:
        return ""
    stack: dict[int, int] = defaultdict(int)
    dots = []
    for i in shown:
        at = 100 * (dt.date.fromisoformat(i["date"]) - today).days / days
        level = stack[round(at / 3)]
        stack[round(at / 3)] += 1
        dots.append(f'<span class="tl-d" tabindex="0" data-tip="{e(i["tip"])}" '
                    f'style="left:{at:.2f}%;top:{30 - 22 * min(level, 2)}px">{e(i["n"])}</span>')
    ticks = "".join(
        f'<span class="tl-t{" l" if k == 0 else " r" if k == days else ""}" style="left:{100 * k / days:.2f}%">'
        f'{"today" if k == 0 else (today + dt.timedelta(days=k)).strftime("%d %b")}</span>'
        for k in range(0, days + 1, 30)
    )
    return f'<div class="tl">{"".join(dots)}{ticks}</div>'
