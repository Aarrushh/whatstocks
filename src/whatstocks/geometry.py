"""Chart geometry for the page: where the bubbles of a conflict scan go and where their labels fit, and where the
themes and arrows of the ripple map sit.

It is computed here, in code, and tested here; the React page (web/) only draws what it is given. Coordinates
are SVG units. Labels are drawn in Geist Mono, where every glyph is 0.6 em wide, so _text_width is exact for
them rather than a guess."""
from __future__ import annotations

import math

DASH = "–"


def pct(x: float | None, digits: int = 1) -> str:
    """A share as the page writes it (web/src/lib/format.ts does the same), so label widths match. A share that
    is there but rounds to nothing reads <0.1%, so it does not look empty."""
    if x is None:
        return DASH
    text = f"{x * 100:.{digits}f}"
    if x > 0 and float(text) == 0:
        return f"<{10 ** -digits:.{digits}f}%"
    return f"{text}%"


def _text_width(text: str, size: float) -> float:
    return len(text) * size * 0.6


def _box_hits(box: tuple, circle: tuple) -> bool:
    x0, y0, x1, y1 = box
    cx, cy, r = circle
    return math.hypot(cx - min(max(cx, x0), x1), cy - min(max(cy, y0), y1)) < r - 1e-6


def _overlap(a: tuple, b: tuple) -> bool:
    return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]


def bubble_layout(points: list[dict], biggest: float = 58.0) -> dict[str, dict]:
    """Where every bubble and label of a bubble map goes.

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


def bubble_groups(points: list[dict], order: tuple[str, ...] = ("hurt", "mixed", "help")) -> list[dict]:
    """bubble_layout, ready to draw: one entry per group that has bubbles, in `order`, each with the box that
    holds its bubbles and labels ([x0, y0, width, height], for the SVG viewBox). Points carry an "index" that
    the page uses to find the rest of the point (its label, effect, strength and reason)."""
    layout = bubble_layout(points) if points else {}
    out = []
    for key in order:
        group = layout.get(key)
        if not group:
            continue
        xs: list[float] = []
        ys: list[float] = []
        bubbles = []
        for b in group["bubbles"]:
            x, y, beside = b["x"], b["y"], b["beside"]
            xs += [x - b["outer"], x + b["outer"]]
            ys += [y - b["outer"], y + b["outer"]]
            if beside:
                xs += [beside["box"][0], beside["box"][2]]
                ys += [beside["box"][1], beside["box"][3]]
            bubbles.append({
                "index": b["point"]["index"], "x": round(x, 2), "y": round(y, 2), "r": round(b["r"], 2),
                "ring": round(b["ring"], 2), "inside": b["inside"],
                "beside": {"x": round(beside["x"], 2), "y": round(beside["y"], 2), "anchor": beside["anchor"]} if beside else None,
            })
        x0, y0 = min(xs) - 8, min(ys) - 4
        box = [round(x0, 2), round(y0, 2), round(max(xs) - x0 + 8, 2), round(max(ys) - y0 + 4, 2)]
        out.append({"effect": key, "box": box, "bubbles": bubbles, "listed": [p["index"] for p in group["listed"]]})
    return out


def network_layout(nodes: list[dict], edges: list[dict], center: str | None = None) -> dict:
    """The ripple map. nodes: [{"id", "label", "weight"}]; edges: [{"from", "to", ...}].

    Nodes sit on an oval in a 140 by 100 box, the centre node (if given) in the middle; a node's radius follows
    its weight. Edges are quadratic curves, bent to one side so A to B and B to A stay apart, and stop short of
    the nodes so their arrowheads show. Each label gets a side of its node ("l", "r", "c above", "c below", or
    for the centre node one of eight sides) that keeps it off the arrows."""
    if not nodes:
        return {"w": 140, "h": 100, "nodes": [], "edges": []}
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
        paths.append(f"M{sx:.2f},{sy:.2f} Q{cx:.2f},{cy:.2f} {ex:.2f},{ey:.2f}")

    def clearest() -> str:
        """The side of the centre node that its edges come in furthest from, so its label hides no arrow."""
        sides = (("c below", math.pi / 2), ("r", 0.0), ("l", math.pi), ("c above", -math.pi / 2),
                 ("dr", math.pi / 4), ("ur", -math.pi / 4), ("dl", 3 * math.pi / 4), ("ul", -3 * math.pi / 4))
        return max(sides, key=lambda s: min([abs(math.remainder(s[1] - a, 2 * math.pi)) for a in approach] + [math.pi]))[0]

    placed = []
    for n in nodes:
        x, y = pos[n["id"]]
        if n["id"] == center:
            side = clearest()
        elif abs(x - w / 2) < 6:
            side = "c " + ("above" if y < h / 2 - 5 else "below")
        else:
            side = "l" if x < w / 2 else "r"
        placed.append({"id": n["id"], "label": n["label"], "weight": n.get("weight") or 0, "x": round(x, 2),
                       "y": round(y, 2), "r": round(radius[n["id"]], 2), "hub": n["id"] == center, "side": side})
    return {"w": w, "h": h, "nodes": placed, "edges": [{"d": d} for d in paths]}
