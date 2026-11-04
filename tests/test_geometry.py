"""Chart geometry (geometry.py): where bubbles, labels and ripple-map nodes go. The page only draws it."""
import math

from whatstocks import geometry


def scan_points():
    points = [{"group": "hurt", "label": "AI build-out", "you": 0.33, "world": 0.16}]
    points += [{"group": "hurt", "label": f"Region {i}", "you": 0.002 * (i + 1), "world": 0.004} for i in range(10)]
    points.append({"group": "help", "label": "Defence", "you": 0.07, "world": 0.01})
    return [dict(p, index=i) for i, p in enumerate(points)]


def test_shares_are_written_the_way_the_page_writes_them():
    assert geometry.pct(0.1234) == "12.3%" and geometry.pct(None) == geometry.DASH  # web/src/lib/format.ts pct()
    assert geometry.pct(0.0002) == "<0.1%" and geometry.pct(0.0) == "0.0%" and geometry.pct(0.004, 0) == "<1%"


def test_bubble_map_never_stacks_bubbles_or_labels():
    for group in geometry.bubble_layout(scan_points()).values():
        bubbles = group["bubbles"]
        for i, a in enumerate(bubbles):  # no bubble overlaps another
            assert all(math.hypot(a["x"] - b["x"], a["y"] - b["y"]) >= a["outer"] + b["outer"] - 1e-6 for b in bubbles[i + 1:])
        boxes = [b["beside"]["box"] for b in bubbles if b["beside"]]
        for i, box in enumerate(boxes):  # no label sits on another label or on any bubble
            assert not any(geometry._overlap(box, other) for other in boxes[i + 1:])
            assert not any(geometry._box_hits(box, (b["x"], b["y"], b["outer"])) for b in bubbles)
        # every bubble is named once: inside it, beside it, or in the list under its group
        assert sum(b["inside"] or b["beside"] is not None for b in bubbles) + len(group["listed"]) == len(bubbles)


def test_bubble_groups_come_in_order_with_a_box_around_everything():
    groups = geometry.bubble_groups(scan_points())
    assert [g["effect"] for g in groups] == ["hurt", "help"]  # no group without bubbles
    hurt = groups[0]
    assert any(b["inside"] for b in hurt["bubbles"] if b["index"] == 0)  # the big bubble carries its name inside
    seen = [b["index"] for g in groups for b in g["bubbles"]]
    assert sorted(seen) == list(range(len(scan_points())))  # every point drawn once, found again by its index
    for g in groups:
        x0, y0, w, h = g["box"]
        for b in g["bubbles"]:
            reach = max(b["r"], b["ring"])
            assert x0 <= b["x"] - reach and b["x"] + reach <= x0 + w
            assert y0 <= b["y"] - reach and b["y"] + reach <= y0 + h
    assert geometry.bubble_groups([]) == []


def test_ripple_map_keeps_the_centre_label_clear_of_its_arrows():
    nodes = [{"id": i, "label": i.upper(), "weight": 1.0} for i in ("hub", "top", "right", "bottom", "left")]
    # the ring starts at the top and goes clockwise; ripples reach the centre from above and below only
    edges = [{"from": "top", "to": "hub"}, {"from": "bottom", "to": "hub"}]
    layout = geometry.network_layout(nodes, edges, center="hub")
    sides = {n["id"]: n["side"] for n in layout["nodes"]}
    assert sides["hub"] not in ("c above", "c below")
    assert sides["top"] == "c above" and sides["bottom"] == "c below" and sides["left"] == "l" and sides["right"] == "r"
    assert [n["hub"] for n in layout["nodes"]] == [True, False, False, False, False]
    assert all(e["d"].startswith("M") and " Q" in e["d"] for e in layout["edges"])
    lone = geometry.network_layout(nodes, [], center="hub")
    assert next(n for n in lone["nodes"] if n["hub"])["side"] == "c below"  # no arrows: the label sits under the node
    assert geometry.network_layout([], []) == {"w": 140, "h": 100, "nodes": [], "edges": []}


def test_ripple_map_sizes_nodes_by_share():
    nodes = [{"id": "a", "label": "A", "weight": 0.30}, {"id": "b", "label": "B", "weight": 0.0},
             {"id": "c", "label": "C", "weight": None}]
    r = {n["id"]: n["r"] for n in geometry.network_layout(nodes, [])["nodes"]}
    assert r["a"] > r["b"] == r["c"] > 0  # an empty theme still gets a small node
