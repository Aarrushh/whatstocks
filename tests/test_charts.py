"""Charts (charts.py)."""
import datetime as dt
import math
import re

from whatstocks import charts


def test_labels_and_tips_are_escaped():
    html = charts.dumbbell([('<b onmouseover="x">AI</b>', 0.2, 0.1)])
    assert "<b onmouseover" not in html and "&lt;b onmouseover=&quot;x&quot;&gt;AI&lt;/b&gt;" in html
    nodes = [{"id": "a", "label": "<i>A</i>", "weight": 1.0}, {"id": "b", "label": "B", "weight": 0.0}]
    net = charts.network(nodes, [{"from": "a", "to": "b", "cls": "hurt", "tip": '"><script>alert(1)</script>'}])
    assert "<script>" not in net and "<i>A</i>" not in net and "&lt;script&gt;" in net


def test_empty_data_draws_a_note_not_a_broken_chart():
    assert "Not enough prices yet" in charts.line_chart([{"name": "You", "cls": "you", "points": []}])
    assert charts.spark([1.0]) == ""
    assert "Nothing to plot" in charts.bubble_map([], [])
    assert charts.network([], []) == ""
    assert charts.timeline([], dt.date(2026, 11, 3)) == ""


def test_line_chart_reads_as_change_since_the_start():
    html = charts.line_chart([{"name": "You", "cls": "you", "points": [["2026-01-01", 100.0], ["2026-06-01", 112.5]]}])
    assert "+12.5%" in html  # the legend gives the change over the window
    assert "&quot;b&quot;:100.0" in html  # the hover script's base


def test_stacked_folds_extra_keys_into_other():
    html = charts.stacked([("You", {f"C{i}": 0.1 for i in range(10)})], top=7)
    assert html.count('class="seg c0"') == 1 and ">Other<" in html
    assert 'class="seg c8"' not in html


def test_heat_table_prints_every_number():
    html = charts.heat_table(["AI", "Oil"], [("NVDA", [0.12, 0.0]), ("SHEL.L", [0.0, 0.05])], total=("All", [0.12, 0.05]))
    assert html.count("12.0%") == 2 and html.count("5.0%") == 2 and html.count(charts.DASH) == 2
    assert "<tfoot>" in html


def test_timeline_keeps_the_next_90_days():
    items = [{"date": "2026-11-10", "n": 1, "tip": "soon"}, {"date": "2027-06-30", "n": 2, "tip": "later"},
             {"date": "2026-10-01", "n": 3, "tip": "past"}]
    html = charts.timeline(items, dt.date(2026, 11, 3))
    assert 'data-tip="soon"' in html and "later" not in html and "past" not in html


def test_bubble_map_never_stacks_labels():
    points = [{"group": "hurt", "label": "AI build-out", "you": 0.33, "world": 0.16, "cls": "hurt s-high", "tip": "ai"}]
    points += [{"group": "hurt", "label": f"Region {i}", "you": 0.002 * (i + 1), "world": 0.004, "cls": "hurt s-low",
                "tip": f"r{i}"} for i in range(10)]
    points.append({"group": "help", "label": "<b>Defence</b>", "you": 0.07, "world": 0.01, "cls": "help s-medium", "tip": "d"})
    for group in charts.bubble_layout(points).values():
        bubbles = group["bubbles"]
        for i, a in enumerate(bubbles):  # no bubble overlaps another
            assert all(math.hypot(a["x"] - b["x"], a["y"] - b["y"]) >= a["outer"] + b["outer"] - 1e-6 for b in bubbles[i + 1:])
        boxes = [b["beside"]["box"] for b in bubbles if b["beside"]]
        for i, box in enumerate(boxes):  # no label sits on another label or on any bubble
            assert not any(charts._overlap(box, other) for other in boxes[i + 1:])
            assert not any(charts._box_hits(box, (b["x"], b["y"], b["outer"])) for b in bubbles)
        # every bubble is named once: inside it, beside it, or in the list under its group
        assert sum(b["inside"] or b["beside"] is not None for b in bubbles) + len(group["listed"]) == len(bubbles)
    html = charts.bubble_map(points, [("hurt", "Would hurt"), ("mixed", "Mixed"), ("help", "Would help")])
    assert html.count('<figure class="bm-c">') == 2  # no figure for a group with no bubbles
    assert ">AI build-out</text>" in html  # a big bubble carries its name inside
    assert "<b>Defence" not in html and "&lt;b&gt;Defence&lt;/b&gt;" in html
    assert all(f'data-tip="r{i}"' in html for i in range(10))  # every bubble keeps its hover text


def test_network_centre_label_keeps_clear_of_its_arrows():
    nodes = [{"id": i, "label": i.upper(), "weight": 1.0} for i in ("hub", "top", "right", "bottom", "left")]
    # the ring starts at the top and goes clockwise; ripples reach the centre from above and below only
    edges = [{"from": "top", "to": "hub", "cls": "hurt", "tip": "t"}, {"from": "bottom", "to": "hub", "cls": "help", "tip": "b"}]
    side = re.search(r'<span class="nl ([^"]+)"[^>]*>HUB</span>', charts.network(nodes, edges, center="hub")).group(1)
    assert side not in ("c above", "c below")
    lone = charts.network(nodes, [], center="hub")
    assert re.search(r'<span class="nl c below"[^>]*>HUB</span>', lone)  # no arrows: the label sits under the node


def test_diverging_marks_missing_prices():
    html = charts.diverging([("2020 crash", "covers 40%", None, -0.2)])
    assert "no prices" in html and "-20.0%" in html
