"""The panels that show the ledger itself (spec 5.1, 8, 17 and 18.1): the funnel and its leakage ratios, the four
pillars with their derived rows, the grade mix of each curve at your defaults, and each series' staleness."""
import datetime as dt
import json
import re
from pathlib import Path

import pytest

from whatstocks import brief, morning
from whatstocks.bet import ledger, models, panels, signals
from whatstocks.bet.ledger import Point

from conftest import TODAY

DAY = dt.date(2026, 11, 7)


def pt(sid: str, eid: str, period: str, value: float, grade: str = "press", source: str = "https://x.test/1",
       low: float | None = None, high: float | None = None) -> Point:
    return Point(sid, eid, period, value, low, high, grade, source, DAY)


def series(sid: str, unit: str, period: str, cadence: str, points: list[Point]) -> ledger.Series:
    s = ledger.Series(sid, sid.replace("_", " ").capitalize(), unit, period, cadence, "", {}, {})
    s.put(points)
    return s


def book(*found: ledger.Series, entities=None, model=None, sig=None, events=None, gaps=None) -> ledger.Ledger:
    return ledger.Ledger(entities or {}, {s.id: s for s in found}, gaps or [], model or {}, sig or {}, events or {}, {})


def keys(node):
    if isinstance(node, dict):
        for k, v in node.items():
            yield k
            yield from keys(v)
    elif isinstance(node, list):
        for v in node:
            yield from keys(v)


# ---------------------------------------------------------------- periods


def test_period_end_dates_each_kind_of_period():
    end = panels.period_end
    assert all(end("quarter", q) == models.q_end(q) for q in models.QUARTERS)
    assert end("month", "2028-02") == dt.date(2028, 2, 29)  # a leap year
    assert end("year", "2026") == dt.date(2026, 12, 31)
    assert end("year", "FY2027", 5) == dt.date(2027, 5, 31)  # Oracle's fiscal year ends in May
    assert end("year", "FY2027") == dt.date(2027, 12, 31) and end("year", "2027", 5) == dt.date(2027, 12, 31)
    assert end("point", "2026-10-30") == end("day", "2026-10-30") == dt.date(2026, 10, 30)


# ---------------------------------------------------------------- the funnel


def test_the_funnel_gives_each_measure_its_newest_figure_the_one_before_and_one_a_year_back():
    adoption = series("genai_adoption", "pct", "quarter", "quarterly",
                      [pt("genai_adoption", "all", q, v, grade="fetched")
                       for q, v in (("2025Q2", 50.0), ("2025Q3", 54.5), ("2026Q2", 61.8), ("2026Q3", 60.8))])
    users = series("ai_users", "count_m", "point", "irregular", [pt("ai_users", "chatgpt", "2026-02-27", 900.0)])
    measures = [{"series": "genai_adoption", "entity": "all", "label": "US adults"},
                {"series": "ai_users", "entity": "chatgpt", "label": "ChatGPT weekly users"},
                {"series": "ai_users", "entity": "nobody", "label": "Not in the ledger yet"}]
    led = book(adoption, users, model={"funnel": {"layers": [{"id": "breadth", "label": "Breadth",
                                                              "measures": measures}]}})
    adults, chatgpt, nobody = panels.funnel(led)["layers"][0]["measures"]
    assert (adults["now"]["figure"], adults["now"]["period"], adults["now"]["grade"]) == (60.8, "2026Q3", "fetched")
    assert adults["before"]["period"] == "2026Q2"
    assert adults["year_ago"]["period"] == "2025Q3"  # 2025Q2 is more than 430 days back, 2026Q2 under 300
    assert adults["unit"] == "pct" and "value" not in adults["now"]
    assert chatgpt["now"]["figure"] == 900.0 and chatgpt["before"] is None and chatgpt["year_ago"] is None
    assert nobody["now"] is None


def test_a_leakage_ratio_pairs_each_figure_with_the_nearest_one_in_time():
    paying = series("paying_users", "count_m", "point", "irregular",
                    [pt("paying_users", "chatgpt", d, v) for d, v in (("2025-06-01", 20.0), ("2026-02-27", 50.0))])
    users = series("ai_users", "count_m", "point", "irregular",
                   [pt("ai_users", "chatgpt", d, v) for d, v in
                    (("2025-03-01", 400.0), ("2025-07-01", 500.0), ("2026-01-15", 800.0), ("2026-02-27", 900.0))])
    old = series("old_users", "count_m", "point", "irregular", [pt("old_users", "x", "2024-01-01", 1.0)])
    conversion = {"id": "conversion", "label": "Paying ÷ weekly users", "of": {"series": "paying_users",
                                                                              "entity": "chatgpt"},
                  "per": {"series": "ai_users", "entity": "chatgpt"}}
    too_far = {**conversion, "id": "too_far", "per": {"series": "old_users", "entity": "x"}}
    led = book(paying, users, old, model={"funnel": {"leakage": [conversion, too_far]}})
    found, none = panels.funnel(led)["leakage"]
    assert found["ratio"] == pytest.approx(50 / 900, abs=1e-6) and found["per"]["period"] == "2026-02-27"
    assert found["unit"] == "count_m"  # the page writes the pair as 50M of 900M
    assert found["before"]["period"] == "2025-06-01"
    assert found["before"]["ratio"] == pytest.approx(20 / 500)  # 2025-07-01 is nearer than 2025-03-01
    assert none["ratio"] is None and none["of"] is None and none["before"] is None  # nothing within NEAR days


def test_the_check_wants_a_leakage_ratio_of_two_measures_in_one_unit():
    led = ledger.load()
    problems = []
    leak = {"id": "mixed", "label": "Mixed", "of": {"series": "paying_users", "entity": "chatgpt"},
            "per": {"series": "genai_adoption", "entity": "all"}}
    ledger._check_funnel({"layers": [], "leakage": [leak]}, ledger._Refs(led.series, led.entities, led.model,
                                                                         problems), problems)
    assert problems == ["model.yaml funnel leakage mixed: of and per must share a unit, not count_m and pct"]


# ---------------------------------------------------------------- the pillars


def cash() -> ledger.Ledger:
    """Two companies' cash flow, capex and depreciation."""
    ocf = series("ocf", "usd_b", "quarter", "quarterly", [
        pt("ocf", "amzn", "2026Q2", 30.0, grade="filed", source="https://sec.test/ocf2"),
        pt("ocf", "amzn", "2026Q3", 35.0, grade="filed", source="https://sec.test/ocf3"),
        pt("ocf", "msft", "2026Q3", -1.0, grade="filed")])
    capex = series("capex_cash", "usd_b", "quarter", "quarterly", [
        pt("capex_cash", "amzn", "2026Q2", 40.0, grade="filed"),
        pt("capex_cash", "amzn", "2026Q3", 50.0, low=48.0, high=52.0, grade="company", source="https://ir.test/c3"),
        pt("capex_cash", "amzn", "2026Q4", 60.0, grade="company"),  # no cash flow for it yet: left out
        pt("capex_cash", "msft", "2026Q3", 20.0, grade="filed")])
    depreciation = series("depreciation", "usd_b", "quarter", "quarterly", [
        pt("depreciation", "amzn", "2026Q3", 7.0, grade="filed"), pt("depreciation", "msft", "2026Q3", 5.0)])
    return book(ocf, capex, depreciation, entities={"amzn": {"label": "Amazon"}, "msft": {"label": "Microsoft"}})


def test_a_derived_row_works_each_company_out_at_the_latest_quarter_both_have():
    amzn, msft = panels.free_cash_flow(cash())["entities"]
    assert (amzn["label"], amzn["figure"], amzn["period"]) == ("Amazon", -15.0, "2026Q3")
    assert (amzn["low"], amzn["high"]) == (-17.0, -13.0)  # capex 48 to 52
    assert amzn["grade"] == "company" and amzn["sources"] == ["https://sec.test/ocf3", "https://ir.test/c3"]
    assert amzn["history"] == [["2026Q2", -10.0], ["2026Q3", -15.0]]
    assert (msft["figure"], msft["low"], msft["high"]) == (-21.0, None, None)
    share = panels.depreciation_share(cash())
    assert share["unit"] == "pct" and [(e["label"], e["figure"]) for e in share["entities"]] == [("Amazon", 20.0)]
    # Microsoft's cash flow is below zero: depreciation has no share of it


def test_each_pillar_carries_its_indicators_its_series_and_every_derived_row_the_check_allows():
    assert set(ledger.DERIVED) == set(panels.DERIVED_FROM)
    led = cash()
    led.signals = {"pillars": [{"id": "capex_revenue", "label": "Capex", "indicators": ["capex_to_ocf"],
                                "series": ["ocf"], "derived": list(ledger.DERIVED)}]}
    (pillar,) = panels.pillars(led)
    assert pillar["indicators"] == ["capex_to_ocf"]
    assert [d["id"] for d in pillar["derived"]] == list(ledger.DERIVED) and all(d["derived"] for d in pillar["derived"])
    (row,) = pillar["rows"]
    assert row["id"] == "ocf" and not row["derived"]
    assert [(e["id"], e["figure"], e["history"]) for e in row["entities"]] == [
        ("amzn", 35.0, [["2026Q2", 30.0], ["2026Q3", 35.0]]), ("msft", -1.0, [["2026Q3", -1.0]])]


# ---------------------------------------------------------------- grades


def test_grades_weigh_each_piece_by_its_last_four_quarters_at_your_defaults():
    led = book(model={
        "sliders": {"gpu_life": {"default": 5}, "cost_of_capital": {"default": 8}, "deflation": {"default": "trailing"}},
        "parameters": {"ai_share": {"label": "AI share of capex", "basis": "judgment"},
                       "running_costs": {"label": "Running costs", "basis": "judgment"},
                       "short_lived_share": {"label": "Short-lived share", "from": {}},
                       "exit_multiple": {"label": "Exit multiple", "basis": "judgment"}}})

    def need(last4: float) -> dict:
        return {"readouts": {"rate": {"last4": last4}}}

    def demand(last4: float) -> dict:
        return {"readouts": {"5": {"rate": {"last4": last4}}}}

    bet = {"capex": {"pieces": [{"id": "a", "on": True, "grades": {"filed": 1.0}},
                                {"id": "b", "on": True, "grades": {"press": 0.5, "estimate": 0.5}},
                                {"id": "c", "on": False, "grades": {"estimate": 1.0}}],
                     "grid": {"5|8": {"a": need(30.0), "b": need(10.0), "c": need(1000.0)}}},
           "demand": {"pieces": [{"id": "direct", "label": "Direct", "on": True, "grades": {"company": 1.0}},
                                 {"id": "bundled", "label": "Bundled", "on": True, "grades": {}},
                                 {"id": "free_users", "label": "Free users", "on": False, "grades": {"press": 1.0}}],
                      "grid": {"trailing": {"pieces": {"direct": demand(8.0), "bundled": demand(0.0),
                                                       "free_users": demand(5.0)}}}}}
    g = panels.grades(led, bet)
    assert g["at"] == {"gpu_life": 5, "cost_of_capital": 8, "deflation": "trailing"}
    assert g["need"] == {"filed": 0.75, "company": 0.0, "press": 0.125, "estimate": 0.125}  # c is off
    assert g["demand"] == {"filed": 0.0, "company": 1.0, "press": 0.0, "estimate": 0.0}
    assert [(t["id"], t["share"]) for t in g["tiers"]] == [("direct", 1.0), ("bundled", 0.0)]
    assert g["judgments"] == {"need": ["AI share of capex", "Running costs"], "demand": [],
                              "valuation": ["Exit multiple"]}


# ---------------------------------------------------------------- sources and staleness


def test_a_figure_falls_due_by_its_cadence_and_never_for_an_irregular_or_closed_series():
    led = book(
        series("capex_cash", "usd_b", "quarter", "quarterly",
               [pt("capex_cash", "msft", "2026Q3", 1.0), pt("capex_cash", "crwv", "2026Q2", 1.0)]),
        series("ai_users", "count_m", "point", "irregular", [pt("ai_users", "x", "2020-01-01", 1.0)]),
        series("telecom_investment", "usd_b", "year", "yearly", [pt("telecom_investment", "us", "2003", 1.0)]),
        series("lab_capex", "usd_b", "year", "yearly", [pt("lab_capex", "orcl", "FY2025", 1.0)]),
        entities={"orcl": {"label": "Oracle", "fiscal_year_end": 5}}, model={"capex": {"basis": {"msft": "capex_cash"}}},
        events={"analogs": {"telecom": {"series": ["telecom_investment.us"]}}})
    # 2026Q2 ends on 2026-06-30: the next quarter's figure is expected 92 + 45 days on, by 2026-11-14
    assert {r["id"]: r for r in panels.sources(led, dt.date(2026, 11, 14))["rows"]}["capex_cash"]["due"] == []
    rows = {r["id"]: r for r in panels.sources(led, dt.date(2026, 11, 15))["rows"]}
    assert rows["capex_cash"]["due"] == [{"id": "crwv", "label": "crwv", "period": "2026Q2", "expected": "2026-11-14"}]
    assert rows["capex_cash"]["newest"]["entity"] == "msft" and rows["capex_cash"]["fetcher"] == "EDGAR"
    assert rows["ai_users"]["due"] == [] and not rows["ai_users"]["closed"]  # irregular: never due
    assert rows["telecom_investment"]["closed"] and rows["telecom_investment"]["due"] == []  # only the analogs read it
    # Oracle's FY2025 ended on 2025-05-31: the next is expected 366 + 90 days on
    assert rows["lab_capex"]["due"][0]["expected"] == "2026-08-30"


def test_sources_rank_what_is_due_first_then_what_feeds_the_curves_then_the_indicators():
    led = book(
        series("cloud_revenue", "usd_b", "quarter", "quarterly", [pt("cloud_revenue", "x", "2025Q1", 1.0)]),
        series("hy_spread", "pct", "day", "daily", [pt("hy_spread", "us", "2026-01-02", 3.0)]),
        series("lab_revenue", "usd_b", "quarter", "quarterly", [pt("lab_revenue", "openai", "2025Q1", 1.0)]),
        series("nrr", "pct", "point", "irregular", [pt("nrr", "x", "2026-01-01", 120.0)]),
        sig={"indicators": {"hy": {"rule": "level", "series": "hy_spread", "entity": "us"}},
             "pillars": [{"id": "p", "label": "P", "series": ["nrr"]}]},
        gaps=[{"series": "cloud_revenue", "what": "a"}, {"series": "lab_revenue", "what": " b\n  c "},
              {"what": "a gap with no series"}])
    out = panels.sources(led, DAY)
    assert [r["id"] for r in out["rows"]] == ["lab_revenue", "hy_spread", "cloud_revenue", "nrr"]
    assert out["rows"][0]["feeds"] == {"curves": True, "indicators": [], "panels": []}
    assert out["rows"][1]["feeds"] == {"curves": False, "indicators": ["hy"], "panels": []}
    assert out["rows"][3]["feeds"]["panels"] == ["pillars"]
    assert [g["what"] for g in out["gaps"]] == ["b c", "a", "a gap with no series"]


def test_the_curves_series_include_every_series_the_models_read_by_name():
    code = Path(models.__file__).read_text("utf-8")
    named = set(re.findall(r'series\.get\("(\w+)"\)', code)) | set(re.findall(r'_yearly\(led, "(\w+)"', code))
    assert named and named <= set(panels.CURVE_SERIES)
    code = Path(signals.__file__).read_text("utf-8")
    assert set(re.findall(r'_points\(c\.led, "(\w+)"', code)) <= set(
        panels.indicator_series({"rule": "capex_to_ocf"}, {}, {}))


# ---------------------------------------------------------------- the morning


def test_prepare_writes_the_panels(user, fake_world):
    morning.prepare(user, today=TODAY)
    bet = json.loads((user.out / "bet.json").read_text("utf-8"))
    p = bet["panels"]
    assert [layer["id"] for layer in p["funnel"]["layers"]] == ["breadth", "intensity", "monetization"]
    assert {r["id"] for r in p["funnel"]["leakage"]} == {"conversion", "work_use"}
    assert [x["id"] for x in p["pillars"]] == ["capex_revenue", "unit_economics", "expansion", "proxies"]
    every = [i for x in p["pillars"] for i in x["indicators"]]
    assert sorted(every) == sorted(bet["signals"]["indicators"])  # each indicator in exactly one pillar
    assert p["grades"]["at"] == bet["signals"]["at"]
    assert sum(t["share"] for t in p["grades"]["tiers"]) == pytest.approx(1, abs=1e-3)
    assert len(p["sources"]["rows"]) == len(ledger.load().series) and p["sources"]["gaps"]
    assert not set(keys(p)) & brief.MONEY_KEYS
