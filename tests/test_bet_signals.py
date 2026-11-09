"""The crash paths of "Will the bet pay off?" (spec sections 9 and 16): the rules that read the indicators, how the
indicators set each path's state and the paths the regime, and what the morning keeps of them: the payload's bet
block, the brief's bet line, the logged state and the evidence lines."""
import datetime as dt
import json

import numpy as np
import pandas as pd
import pytest
import yaml

from whatstocks import brief, dashboard, morning, record
from whatstocks.bet import ledger, models, signals
from whatstocks.bet.ledger import Point
from whatstocks.files import Problems, load_book
from whatstocks.paths import BET_DIR, ROOT, UserDir

from conftest import DEMO_FUNDS, NEWS, TODAY, quiet_brief

DAY = dt.date(2026, 11, 7)
SLIDERS = {"gpu_life": {"default": 5}, "cost_of_capital": {"default": 8}, "deflation": {"default": "trailing"}}
REGIME = yaml.safe_load((BET_DIR / "signals.yaml").read_text("utf-8"))["regime"]


def point(series: str, entity: str, period: str, value: float | None = None, **kw) -> Point:
    return Point(series, entity, period, value, None, None, "filed", "https://x.test/1", DAY, **kw)


def book_of(*points: Point, labels=None, entities=None, sig=None, links=None) -> ledger.Ledger:
    """A ledger that holds only these points."""
    series = {}
    for p in points:
        if p.series not in series:
            label = (labels or {}).get(p.series, p.series)
            series[p.series] = ledger.Series(p.series, label, "", "", "", "", {}, {})
    for sid, s in series.items():
        s.put([p for p in points if p.series == sid])
    return ledger.Ledger(entities or {}, series, [], {"sliders": SLIDERS}, sig or {}, {}, links or {})


def read(rule: str, ind: dict, *points: Point, bet=None, prices=None, today=DAY, **kw) -> signals.Reading:
    context = signals.Context(book_of(*points, **kw), bet or {}, prices, None, today)
    return signals.RULES[rule](context, ind)


class Prices:
    def __init__(self, closes: dict[str, pd.Series]):
        self.closes = closes

    def series(self, symbol: str) -> pd.Series:
        return self.closes.get(symbol, pd.Series(dtype=float))


def keys(node):
    if isinstance(node, dict):
        for k, v in node.items():
            yield k
            yield from keys(v)
    elif isinstance(node, list):
        for v in node:
            yield from keys(v)


# ---------------------------------------------------------------- the rules


def test_reaching_a_level_counts():
    up = {"direction": "up", "amber": 300, "red": 500}
    assert [signals._state(up, x) for x in (299.9, 300, 499, 500)] == ["clear", "amber", "amber", "red"]
    down = {"direction": "down", "amber": -20, "red": -30}
    assert [signals._state(down, x) for x in (-19.9, -20, -30)] == ["clear", "amber", "red"]
    assert signals._state({"direction": "up", "amber": 1, "red": None}, 5) == "amber"


def test_periods_step_across_years():
    assert signals._shift("2026Q1", -1) == "2025Q4" and signals._shift("2025Q4", 1) == "2026Q1"
    assert signals._shift("2026-01", -1) == "2025-12" and signals._shift("2026-09", -12) == "2025-09"


def test_a_stale_print_gives_way_to_its_stand_in():
    ind = {"series": "cds", "entity": "orcl", "unit": "bp", "direction": "up", "amber": 200, "red": 400,
           "max_age_days": 30, "stand_in": {"series": "hy", "entity": "us", "unit": "pct", "amber": 4, "red": 6}}
    labels = {"hy": "High-yield spread"}
    old, spread = point("cds", "orcl", "2026-08-03", 350.0), point("hy", "us", "2026-11-05", 6.2)
    r = read("level", ind, old, spread, labels=labels)
    assert (r.value, r.state, r.as_of) == (6.2, "red", "2026-11-05")  # by the stand-in's own levels
    assert r.text == "no print in 30 days, so the high-yield spread stands in: 6.2% on 2026-11-05"
    fresh = read("level", ind, old, point("cds", "orcl", "2026-11-02", 250.0), spread, labels=labels)
    assert (fresh.value, fresh.state, fresh.text) == (250.0, None, "250bp on 2026-11-02")  # evaluate() sets the state
    assert read("level", ind, spread, labels=labels).text == "the high-yield spread: 6.2% on 2026-11-05"
    gone = read("level", ind, old, point("hy", "us", "2026-08-01", 6.2), labels=labels)
    assert gone.value is None and gone.text == "no figure in the last 30 days (the last: 350bp on 2026-08-03)"


def test_periods_in_a_row_a_change_and_a_year_back():
    ind = {"series": "s", "entity": "e", "unit": "pct", "points": 3}
    found = [point("s", "e", q, v) for q, v in (("2026Q1", 1.0), ("2026Q2", 2.0), ("2026Q3", 6.0))]
    r = read("mean_last", ind, *found)
    assert r.value == pytest.approx(3.0) and r.text == "+3.0%, the mean of 2026Q1 to 2026Q3"
    gap = read("mean_last", ind, found[0], found[2])
    assert gap.value is None and gap.text == "needs 3 periods in a row, 2026Q1 to 2026Q3"

    months = {"series": "s", "entity": "e", "unit": "pct", "points": 12}
    r = read("change", months, point("s", "e", "2025-09", 80.0), point("s", "e", "2026-09", 100.0))
    assert r.value == pytest.approx(25.0) and r.text == "+25.0% from 2025-09 to 2026-09"
    assert read("change", months, point("s", "e", "2025-10", 80.0), point("s", "e", "2026-09", 100.0)).value is None

    yoy = {"series": "s", "entity": "e", "unit": "pct", "tolerance_days": 10}
    found = [point("s", "e", d, v) for d, v in (("2025-10-20", 90.0), ("2025-11-01", 80.0), ("2026-11-03", 100.0))]
    r = read("yoy", yoy, *found)
    assert r.value == pytest.approx(25.0) and r.text == "+25.0% from 2025-11-01 to 2026-11-03"  # the nearest
    far = read("yoy", yoy, point("s", "e", "2025-09-01", 80.0), point("s", "e", "2026-11-03", 100.0))
    assert far.value is None and "about 2025-11-03" in far.text


def test_capex_over_cash_flow_uses_the_quarters_every_company_has_filed():
    found = []
    for e, (capex, cash) in {"msft": (20.0, 40.0), "meta": (15.0, 25.0)}.items():
        for q in ("2025Q4", "2026Q1", "2026Q2", "2026Q3"):
            found += [point("capex_cash", e, q, capex), point("ocf", e, q, cash)]
    found += [point("capex_cash", "msft", "2026Q4", 50.0), point("ocf", "msft", "2026Q4", 10.0)]  # Meta not yet
    r = read("capex_to_ocf", {"entities": ["msft", "meta"]}, *found)
    assert r.value == pytest.approx(100 * 35 / 65) and r.as_of == "2026Q3"
    assert r.text == "54% over 2025Q4 to 2026Q3 (2026Q3 alone: 54%)"


def test_guides_below_the_quarter_before_count_in_a_row():
    ind = {"series": "guide", "actual": "revenue", "entity": "nvda"}
    actual = [point("revenue", "nvda", q, v) for q, v in (("2026Q1", 44.0), ("2026Q2", 47.0), ("2026Q3", 57.0))]
    guides = [point("guide", "nvda", d, v, covers=q) for d, q, v in
              (("2026-02-25", "2026Q2", 45.0), ("2026-05-28", "2026Q3", 46.0), ("2026-08-27", "2026Q4", 55.0))]
    r = read("guide_vs_actual", ind, *actual, *guides)
    assert (r.value, r.as_of) == (2, "2026-08-27")
    assert r.text == "the guide for 2026Q4 is 4% below 2026Q3's revenue, 2 quarters in a row"
    early = read("guide_vs_actual", ind, *actual[:2], *guides)  # 2026Q3's revenue is not in yet
    assert early.value is None and early.text.startswith("needs the revenue for 2026Q3 to test the guide for 2026Q4")


def test_only_cuts_for_a_reason_that_counts_are_counted():
    ind = {"series": "guide", "entities": ["msft", "meta"], "quarters": 2, "counts": ["demand", "returns"]}
    names = {"msft": {"label": "Microsoft"}, "meta": {"label": "Meta"}}
    found = [
        point("guide", "msft", "2026-07-30", 120.0, covers="FY2027"),
        point("guide", "msft", "2026-10-29", 110.0, covers="FY2027", why="supply"),
        point("guide", "meta", "2026-04-29", 70.0, covers="2026"),
        point("guide", "meta", "2026-07-30", 72.0, covers="2026"),
        point("guide", "meta", "2026-10-29", 66.0, covers="2026", why="demand"),
    ]
    r = read("guidance_cuts", ind, *found, entities=names)
    assert r.value == 1
    assert r.text == "1 company: Meta (demand, 2026-10-29) (not counted: Microsoft 2026-10-29: supply)"
    later = read("guidance_cuts", ind, *found, entities=names, today=dt.date(2027, 6, 1))
    assert (later.value, later.text) == (0, "none that count")  # both cuts are more than two quarters old


def test_a_basket_is_equal_weight_and_counts_each_company_once(monkeypatch):
    days = pd.bdate_range("2025-11-10", "2026-11-06")
    half = len(days) // 2
    a = np.r_[np.linspace(100, 200, half), np.linspace(200, 150, len(days) - half)]
    b = np.r_[np.linspace(100, 50, half), np.linspace(50, 60, len(days) - half)]
    prices = Prices({"AAA": pd.Series(a, days), "BBB": pd.Series(b, days), "BBB.2": pd.Series(3 * b, days)})
    monkeypatch.setattr(signals, "members", lambda basket, themes: ["AAA", "BBB", "BBB.2"])
    r = read("below_high", {"basket": "ai_buildout", "weeks": 52}, prices=prices)
    assert r.value == pytest.approx(-16.0)  # (1.5 + 0.6) / 2 against (2.0 + 0.5) / 2 at the turn
    assert r.as_of == "2026-11-06"
    assert r.text == (f"-16.0% from its high on {days[half - 1].date()} (2 members, equal weight; "
                      "BBB.2 counted once with its other share class)")


def test_events_in_the_window_set_the_state_themselves():
    ind = {"series": "events", "days": 90, "amber_kinds": ["downgrade"], "red_kinds": ["default"]}
    names = {"crwv": {"label": "CoreWeave"}}
    none = read("events", ind)
    assert (none.value, none.state, none.text) == (0, "clear", "none in the last 90 days")
    old = point("events", "crwv", "2026-06-01", kind="default")  # outside the window
    downgrade = point("events", "crwv", "2026-10-01", kind="downgrade")
    amber = read("events", ind, old, downgrade, entities=names)
    assert (amber.value, amber.state, amber.text) == (1, "amber", "CoreWeave: downgrade on 2026-10-01")
    red = read("events", ind, old, downgrade, point("events", "crwv", "2026-10-15", kind="default"), entities=names)
    assert red.state == "red" and red.text == "CoreWeave: default on 2026-10-15; CoreWeave: downgrade on 2026-10-01"


def test_a_rating_at_the_floor_or_on_negative_outlook_is_amber_and_below_it_red():
    ind = {"series": "ratings", "floor": "BBB-"}
    names = {"orcl": {"label": "Oracle"}, "meta": {"label": "Meta"}, "crwv": {"label": "CoreWeave"}}

    def rated(entity: str, agency: str, rating: str, day: str, outlook: str = "stable") -> Point:
        return point("ratings", entity, day, agency=agency, rating=rating, outlook=outlook)

    found = [rated("orcl", "S&P", "BBB-", "2025-09-01"), rated("orcl", "S&P", "BBB", "2026-09-01"),
             rated("orcl", "Moody's", "Baa2", "2026-10-01", "negative"), rated("meta", "S&P", "AA-", "2026-06-01"),
             rated("meta", "Fitch", "NR", "2026-06-01")]
    r = read("ratings", ind, *found, entities=names)
    # S&P's latest action on Oracle is the upgrade to BBB; a rating the scale does not know is left out.
    assert (r.state, r.value, r.as_of) == ("amber", 1, "2026-10-01")
    assert r.text == "Oracle Baa2, negative outlook (Moody's, 2026-10-01)"
    worse = read("ratings", ind, *found, rated("crwv", "S&P", "BB-", "2026-08-01"), entities=names)
    assert worse.state == "red" and "CoreWeave BB- (S&P, 2026-08-01)" in worse.text


def test_a_stall_is_the_longest_run_of_quarters_without_a_rise():
    ind = {"series": "use", "entities": ["all", "work"], "unit": "quarters in a row"}
    names = {"all": {"label": "All adults"}, "work": {"label": "At work"}}
    found = [point("use", "all", q, v) for q, v in
             (("2025Q4", 40.0), ("2026Q1", 42.0), ("2026Q2", 42.0), ("2026Q3", 41.5))]
    found += [point("use", "work", q, v) for q, v in (("2026Q2", 20.0), ("2026Q3", 21.0))]
    r = read("streak", ind, *found, entities=names)
    assert (r.value, r.as_of) == (2, "2026Q3")
    assert r.text == ("2 quarters in a row at zero or below "
                      "(All adults -0.5 points in 2026Q3; At work +1.0 points in 2026Q3)")
    gap = read("streak", ind, *(p for p in found if p.period != "2026Q1"), entities=names)
    assert gap.value == 1 and gap.text.startswith("1 quarter in a row")  # 2025Q4 to 2026Q2 is not in a row


def test_a_trend_is_flat_within_its_band():
    ind = {"series": "t", "entity": "e", "months": 6, "flat": 1.0}

    def trend(now: float) -> signals.Reading:
        return read("trend", ind, point("t", "e", "2026-03", 50.0), point("t", "e", "2026-09", now))

    assert [trend(v).state for v in (52.0, 50.5, 49.0, 48.5)] == ["clear", "amber", "amber", "red"]
    assert trend(48.5).text == "-1.5 points from 2026-03 to 2026-09"
    assert read("trend", ind, point("t", "e", "2026-04", 50.0), point("t", "e", "2026-09", 48.0)).value is None


def test_conversion_falls_count_readings_in_a_row():
    ind = {"paying": {"series": "paying", "entity": "chatgpt"}, "users": {"series": "users", "entity": "chatgpt"}}
    days = [("2026-02-01", 50.0, 1000.0), ("2026-06-01", 50.0, 1100.0), ("2026-10-01", 52.0, 1200.0)]
    found = [p for d, pay, use in days for p in (point("paying", "chatgpt", d, pay), point("users", "chatgpt", d, use))]
    r = read("falls", ind, *found)
    assert r.value == 2 and r.text == "4.3% on 2026-10-01, lower 2 readings in a row"
    one = read("falls", ind, *found[:2])
    assert one.value == 0 and one.text == "5.0% on 2026-02-01 (one reading so far)"


def test_the_telecom_test():
    """Red when demand shrinks, (1 + price change) x (1 + token growth) < 1; amber when prices fall this fast."""
    usage = {"growth": 2.0, "since": "2025-05", "to": "2026-05"}

    def telecom(d: float | None, g: float) -> signals.Reading:
        return read("telecom_test", {"amber": -50}, bet={"demand": {"trailing": d, "usage": dict(usage, growth=g)}})

    red = telecom(-0.8, 2.0)
    assert red.state == "red" and red.text == "-80% a year: tokens x3.0 (2025-05 to 2026-05), demand x0.6"
    assert telecom(-0.6, 5.0).state == "amber"  # demand x2.4, but prices fell 60%
    assert telecom(-0.44, 5.71).state == "clear"
    assert telecom(None, 2.0).value is None


def sums_bet(direct: float, bundled: float) -> dict:
    """Model A's need at the defaults (depreciation 60 and a return of 40 a year, 500 to the deadline) and Model B's
    demand (600 to the deadline), each with a piece switched off that must not count."""

    def a(last4: float, total: float) -> dict:
        return {"readouts": {"rate": {"last4": last4, "to_deadline": total}}}

    def b(last4: float, total: float) -> dict:
        return {"readouts": {"5": {"rate": {"last4": last4, "to_deadline": total}}}}

    return {
        "quarters": models.QUARTERS, "last_actual": models.INDEX["2026Q3"], "deadlines": {"5": {"date": "2030-12-31"}},
        "capex": {"pieces": [{"id": "h.depreciation", "part": "depreciation", "on": True},
                             {"id": "h.return", "part": "return", "on": True},
                             {"id": "n.depreciation", "part": "depreciation", "on": False}],
                  "grid": {"5|8": {"h.depreciation": a(60.0, 300.0), "h.return": a(40.0, 200.0),
                                   "n.depreciation": a(900.0, 900.0)}}},
        "demand": {"pieces": [{"id": "direct", "on": True}, {"id": "bundled", "on": True}, {"id": "free", "on": False}],
                   "grid": {"trailing": {"pieces": {"direct": b(direct, 400.0), "bundled": b(bundled, 200.0),
                                                    "free": b(900.0, 900.0)}}}},
    }


def test_coverage_payback_and_the_tier_1_share_count_only_the_pieces_switched_on():
    r = read("coverage_now", {}, bet=sums_bet(30.0, 20.0))
    assert r.value == pytest.approx(50.0) and r.state == "red"  # 50 against a need of 100, under depreciation's 60
    assert r.text == "50% of the need over the four quarters to 2026Q3; 83% of depreciation alone"
    assert read("coverage_now", {}, bet=sums_bet(50.0, 20.0)).state == "amber"  # 70: past depreciation, short of need
    assert read("coverage_now", {}, bet=sums_bet(80.0, 40.0)).state == "clear"
    payback = read("payback", {}, bet=sums_bet(30.0, 20.0))
    assert payback.value == pytest.approx(120.0)
    assert payback.text == "120% by 2030-12-31, projected at the trailing price change"
    assert read("tier1_share", {}, bet=sums_bet(30.0, 20.0)).value == pytest.approx(60.0)


# ---------------------------------------------------------------- paths and the regime


def level(path: str, label: str, series: str, trigger: bool) -> dict:
    """An indicator on the level rule: amber from 4%, red from 6%."""
    return {"label": label, "path": path, "rule": "level", "series": series, "entity": "x", "unit": "pct",
            "direction": "up", "amber": 4.0, "red": 6.0, "trigger": trigger, "why": "A test."}


INDICATORS = {
    "spread": level("credit_event", "High-yield spread", "spread", True),
    "cds_a": level("credit_event", "Oracle CDS", "cds_a", False),
    "cds_b": level("credit_event", "CoreWeave CDS", "cds_b", False),
    "stall": level("adoption_pace", "Adoption stall", "stall", True),
    "coverage": {"label": "Coverage now", "path": "adoption_pace", "rule": "coverage_now", "unit": "pct",
                 "direction": "down", "why": "A test."},
    "payback": {"label": "Payback by the deadline", "path": "adoption_pace", "rule": "payback", "unit": "pct",
                "direction": "down", "amber": 100.0, "red": 75.0, "why": "A test."},
}


def board(**readings: float) -> dict:
    """evaluate() on a small board. The credit path has a trigger and two CDS that turn it red only together; the
    adoption path has a trigger and the two shares, which cover the need here (120%)."""
    sig = {"paths": {"credit_event": {"label": "Credit event", "kind": "crash", "about": "",
                                      "red_when_all_red": ["cds_a", "cds_b"]},
                     "adoption_pace": {"label": "Adoption pace", "kind": "adoption", "about": ""}},
           "regime": REGIME, "indicators": INDICATORS,
           "channels": {"credit_event": [{"kind": "theme", "id": "ai_lessors:core"}, {"kind": "symbol", "id": "HYG"}]}}
    found = [point(sid, "x", "2026-11-05", v) for sid, v in readings.items()]
    led = book_of(*found, sig=sig, links={"crunch-2027": {"credit_event": "for"}})
    return signals.evaluate(led, sums_bet(80.0, 40.0), None, None, DAY)


def test_only_a_trigger_turns_its_path_red():
    s = board(spread=3.0, cds_a=7.0, cds_b=3.0, stall=1.0)
    credit = s["paths"]["credit_event"]
    assert (credit["state"], credit["drivers"]) == ("amber", ["cds_a"])  # one CDS red, and it is not a trigger
    assert credit["counts"] == {"clear": 2, "amber": 0, "red": 1, "no_data": 0}
    assert s["regime"]["state"] == "straining" and s["regime"]["because"] == ["credit_event"]
    both = board(spread=3.0, cds_a=7.0, cds_b=6.5, stall=1.0)
    assert (both["paths"]["credit_event"]["state"], both["paths"]["credit_event"]["drivers"]) == ("red", ["cds_a", "cds_b"])
    assert both["regime"]["state"] == "breaking"
    trigger = board(spread=6.0, cds_a=5.0, cds_b=3.0, stall=1.0)["paths"]["credit_event"]
    assert (trigger["state"], trigger["drivers"]) == ("red", ["spread"])


def test_no_data_never_moves_a_path():
    s = board(spread=3.0)  # no CDS and no stall figures
    assert s["indicators"]["cds_a"]["state"] == "no_data" and s["indicators"]["cds_a"]["text"] == "no figure yet"
    credit = s["paths"]["credit_event"]
    assert credit["state"] == "clear" and credit["counts"]["no_data"] == 2
    assert s["paths"]["adoption_pace"]["state"] == "clear" and s["regime"]["state"] == "absorbing"
    assert credit["themes"] == ["ai_lessors"] and credit["view_links"] == {"crunch-2027": "for"}
    assert s["paths"]["adoption_pace"]["view_links"] == {}
    assert s["indicators"]["spread"]["ledger"] == ["spread/x/2026-11-05"]
    assert s["indicators"]["spread"]["sources"] == ["https://x.test/1"]
    assert s["at"] == {"gpu_life": 5, "cost_of_capital": 8, "deflation": "trailing"}


@pytest.mark.parametrize("crash, adoption, regime, because", [
    ("clear", "amber", "absorbing", []),
    ("clear", "red", "straining", ["adoption_pace"]),
    ("amber", "clear", "straining", ["credit_event"]),
    ("red", "red", "breaking", ["credit_event"]),
])
def test_the_regime_is_the_first_rule_that_holds(crash, adoption, regime, because):
    paths = {"credit_event": {"kind": "crash", "state": crash}, "adoption_pace": {"kind": "adoption", "state": adoption}}
    r = signals._regime(REGIME, paths)
    assert (r["state"], r["because"]) == (regime, because)


# ---------------------------------------------------------------- what the morning keeps


def test_the_payload_block_holds_states_and_shares_never_dollars():
    now = board(spread=4.5, cds_a=7.0, cds_b=3.0, stall=1.0)
    first = signals.payload_block(now, None)  # nothing logged yet
    assert first["regime"] == {"now": "straining", "last_logged": None} and first["changed"] is False
    assert [i["id"] for i in first["indicators_changed"]] == ["spread", "cds_a"]  # every amber or red one
    assert (first["coverage_now"], first["payback_by_deadline"], first["adoption_pace"]) == (1.2, 1.2, "clear")
    assert first["at"] == "your default settings"

    calm = signals.snapshot(board(spread=3.0, cds_a=3.0, cds_b=3.0, stall=1.0))
    block = signals.payload_block(now, calm)
    assert block["changed"] is True and block["regime"] == {"now": "straining", "last_logged": "absorbing"}
    assert block["paths"][0] == {"id": "credit_event", "label": "Credit event", "now": "amber", "last_logged": "clear"}
    assert block["indicators_changed"] == [
        {"id": "spread", "label": "High-yield spread", "path": "credit_event", "state": "amber", "was": "clear",
         "reading": "4.5% on 2026-11-05"},
        {"id": "cds_a", "label": "Oracle CDS", "path": "credit_event", "state": "red", "was": "clear",
         "reading": "7.0% on 2026-11-05"},
    ]
    same = signals.payload_block(now, signals.snapshot(board(spread=3.0, cds_a=7.0, cds_b=3.0, stall=1.0)))
    assert same["changed"] is False  # the path was amber already
    assert [i["id"] for i in same["indicators_changed"]] == ["spread"]

    text = json.dumps(block)
    assert "$" not in text and "http" not in text and not set(keys(block)) & brief.MONEY_KEYS
    assert brief.payload_leaks({"bet": block}, [4321.5]) == []


def test_a_path_that_moves_logs_a_line_for_or_against_the_views_linked_to_it():
    calm = board(spread=3.0, cds_a=3.0, cds_b=3.0, stall=1.0)
    worse = board(spread=4.5, cds_a=3.0, cds_b=3.0, stall=1.0)
    assert signals.evidence(worse, None, {"crunch-2027"}, DAY) == []  # nothing logged yet: nothing to compare with
    assert signals.evidence(worse, signals.snapshot(worse), {"crunch-2027"}, DAY) == []  # nothing moved

    path, regime = signals.evidence(worse, signals.snapshot(calm), {"crunch-2027"}, DAY)
    assert path == {
        "date": "2026-11-07", "source": "signal",
        "what": "Credit event path: clear to amber (High-yield spread 4.5% on 2026-11-05, amber from 4.0%)",
        "ledger": ["spread/x/2026-11-05"], "sources": ["https://x.test/1"], "news_ids": [], "themes": ["ai_lessors"],
        "holdings": [], "views": [{"view_id": "crunch-2027", "effect": "for", "why": "the credit event path got worse"}],
    }
    assert regime["what"] == "Regime: absorbing to straining (credit event amber)" and regime["views"] == []

    back = signals.evidence(calm, signals.snapshot(worse), {"crunch-2027"}, DAY)
    assert back[0]["what"] == "Credit event path: amber to clear (High-yield spread 3.0% on 2026-11-05)"
    assert back[0]["views"][0]["effect"] == "against"  # a path getting better counts the other way
    assert back[1]["what"] == "Regime: straining to absorbing"
    assert signals.evidence(worse, signals.snapshot(calm), set(), DAY)[0]["views"] == []  # a closed view: nothing


def test_a_second_finish_on_the_same_day_compares_with_the_state_before_the_first():
    calm = board(spread=3.0, cds_a=3.0, cds_b=3.0, stall=1.0)
    worse = board(spread=4.5, cds_a=3.0, cds_b=3.0, stall=1.0)
    assert signals.baseline(None, DAY) is None
    yesterday = {"date": "2026-11-06", **signals.snapshot(calm), "before": None}
    assert signals.baseline(yesterday, DAY) == signals.snapshot(calm)
    first = signals.logged(worse, yesterday, DAY)
    assert first == {"date": "2026-11-07", **signals.snapshot(worse), "before": signals.snapshot(calm)}
    assert signals.baseline(first, DAY) == signals.snapshot(calm)  # a re-run today still compares with yesterday
    assert signals.logged(worse, first, DAY) == first
    assert signals.changed(worse, signals.baseline(first, DAY)) and not signals.changed(worse, None)


QUIET = {"date": TODAY.isoformat(), "events": [], "quiet_day": True}


def payload_with(changed: bool | None) -> dict:
    payload = {"date": TODAY.isoformat(), "holdings": [], "themes": [], "views": [],
               "news": [{k: n[k] for k in ("id", "title", "source", "published")} for n in NEWS]}
    if changed is not None:
        payload["bet"] = {"changed": changed}
    return payload


def test_the_brief_needs_a_bet_line_when_the_regime_or_a_path_moved():
    assert brief.validate_brief(QUIET, payload_with(False)) == ([], [])
    assert brief.validate_brief(QUIET, payload_with(None)) == ([], [])  # a payload from before the bet
    assert brief.validate_brief(QUIET, payload_with(True)) == ([
        "bet: the regime or a crash path changed since the last brief: add bet.line, one or two sentences on what "
        "moved, with the news_ids that explain it (if any)"], [])
    line = "The credit event path went from clear to amber: the high-yield spread is 4.5%."
    assert brief.validate_brief(dict(QUIET, bet={"line": line, "news_ids": ["bbbbbbbbbb"]}), payload_with(True)) == ([], [])
    assert brief.validate_brief(dict(QUIET, bet={"line": line}), payload_with(False)) == ([], [])  # allowed any day

    def check(bet) -> tuple[list[str], list[str]]:
        return brief.validate_brief(dict(QUIET, bet=bet), payload_with(True))

    assert check("The credit path moved.")[0] == ['bet must be an object: {"line": "...", "news_ids": [...]}']
    assert check({"line": " "})[0] == ["bet: 'line' is missing"]
    assert check({"line": "x" * 401})[0] == ["bet: the line is longer than 400 characters: one or two sentences"]
    assert check({"line": line, "news_ids": ["zzzzzzzzzz"]})[0] == ["bet: news id 'zzzzzzzzzz' was not in today's payload"]
    assert check({"line": "Read https://x.test for why."})[0][0].startswith("contains a link")
    assert check({"line": "You should sell the AI stocks now."})[1]  # advice-like wording


def test_signal_lines_count_for_views_but_not_toward_busy_news():
    news = {"date": "2026-11-02", "what": "Two hyperscalers cut their 2027 capex", "news_ids": ["bbbbbbbbbb"],
            "themes": ["ai_buildout"], "holdings": [], "views": []}
    signal = {"date": "2026-11-02", "source": "signal", "what": "Capex retrenchment path: clear to amber",
              "news_ids": [], "themes": ["ai_buildout"], "holdings": [],
              "views": [{"view_id": "ai-capex-cut-2027", "effect": "for", "why": "the capex path got worse"}]}
    evidence = [news] + [dict(signal) for _ in range(3)]
    assert record.busy_days(evidence)["2026-11-02"]["ai_buildout"] == 1
    assert sum(dashboard.news_heat(evidence, ["ai_buildout"], TODAY)["rows"]["ai_buildout"]) == 1
    exposure = {"themes": {"ai_buildout": {"label": "AI build-out", "you": 0.0, "world": 0.07}}}
    assert dashboard.blind_spots(exposure, evidence, TODAY) == []  # one news event is not a busy week
    book = load_book(UserDir(ROOT / "demo"), DEMO_FUNDS)
    row = next(v for v in record.view_rows(book, TODAY, evidence, {}) if v["id"] == "ai-capex-cut-2027")
    assert row["evidence"]["7"]["for"] == 3


def write_brief(user, content: dict) -> None:
    (user.out / "brief.json").write_text(json.dumps(content), "utf-8")


def evidence_of(user) -> list[dict]:
    text = (user.out / "evidence.jsonl").read_text("utf-8")
    return [json.loads(line) for line in text.splitlines() if line.strip()]


def test_the_morning_logs_a_line_when_a_path_moves(user, fake_world):
    morning.prepare(user, today=TODAY)  # it checks the whole payload for leaks, the bet block included
    s = json.loads((user.out / "bet.json").read_text("utf-8"))["signals"]
    assert set(s["paths"]) == {"capex_retrenchment", "equity_drawdown", "credit_event", "price_collapse",
                               "adoption_pace"}
    block = json.loads((user.out / "payload.json").read_text("utf-8"))["bet"]
    assert block["changed"] is False and block["regime"] == {"now": s["regime"]["state"], "last_logged": None}
    text = json.dumps(block)
    assert "$" not in text and "http" not in text and not set(keys(block)) & brief.MONEY_KEYS

    write_brief(user, quiet_brief())
    morning.finish(user, today=TODAY)
    state = json.loads((user.out / "bet_state.json").read_text("utf-8"))
    assert (state["date"], state["regime"], state["before"]) == (TODAY.isoformat(), s["regime"]["state"], None)
    assert not [e for e in evidence_of(user) if record.is_signal(e)]  # nothing logged before: nothing to compare

    # Yesterday's logged state had the first path in another state.
    pid = next(iter(s["paths"]))
    was = "clear" if s["paths"][pid]["state"] == "red" else "red"
    yesterday = {**state, "date": (TODAY - dt.timedelta(days=1)).isoformat(), "paths": {**state["paths"], pid: was}}
    (user.out / "bet_state.json").write_text(json.dumps(yesterday), "utf-8")
    morning.prepare(user, offline=True, today=TODAY)
    assert json.loads((user.out / "payload.json").read_text("utf-8"))["bet"]["changed"] is True
    with pytest.raises(Problems, match="bet: the regime or a crash path changed"):
        morning.finish(user, today=TODAY)

    write_brief(user, dict(quiet_brief(), bet={"line": "One crash path is in a new state since the last brief.",
                                               "news_ids": []}))
    morning.finish(user, today=TODAY)
    lines = [e for e in evidence_of(user) if record.is_signal(e)]
    assert len(lines) == 1 and lines[0]["what"].startswith(f"{s['paths'][pid]['label']} path: {was} to ")
    assert json.loads((user.out / "bet_state.json").read_text("utf-8"))["before"]["paths"][pid] == was
    morning.finish(user, today=TODAY)  # a second finish today compares with yesterday again: still one line
    assert [e for e in evidence_of(user) if record.is_signal(e)] == lines
