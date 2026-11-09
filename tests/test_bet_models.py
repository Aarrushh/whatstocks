"""Models A and B of "Will the bet pay off?" (spec sections 4 to 7): the revenue requirement of capex, what the market
values assume, how the demand tiers are netted, the projection, and the grid the page picks from."""
import datetime as dt
import json

import numpy as np
import pandas as pd
import pytest

from whatstocks import brief, morning
from whatstocks.bet import ledger, models
from whatstocks.bet.ledger import Point

from conftest import TODAY

DAY = dt.date(2026, 11, 7)  # the shipped ledger was read on this day
Q = models.INDEX


def shipped() -> ledger.Ledger:
    return ledger.load(today=DAY)


def point(series: str, entity: str, period: str, value: float, **kw) -> Point:
    return Point(series, entity, period, value, kw.pop("low", None), kw.pop("high", None), kw.pop("grade", "filed"),
                 "https://x.test/1", DAY, **kw)


class Prices:
    """Closes by symbol, as market.Prices gives them."""

    def __init__(self, closes: dict[str, pd.Series]):
        self.closes = closes

    def series(self, symbol: str) -> pd.Series:
        return self.closes.get(symbol, pd.Series(dtype=float))


def closes(before: float, now: float, first: str = "2022-06-01") -> pd.Series:
    """A close of `before` up to ChatGPT's launch (30 November 2022), and `now` after it."""
    days = pd.bdate_range(first, "2026-11-06")
    return pd.Series(np.where(days <= pd.Timestamp("2022-11-30"), before, now), index=days)


def keys(node):
    if isinstance(node, dict):
        for k, v in node.items():
            yield k
            yield from keys(v)
    elif isinstance(node, list):
        for v in node:
            yield from keys(v)


# ---------------------------------------------------------------- quarters


def test_a_fiscal_year_counts_in_the_calendar_quarters_it_ends_in():
    assert models.covered("2026") == ["2026Q1", "2026Q2", "2026Q3", "2026Q4"]
    assert models.covered("FY2027", 5) == ["2026Q3", "2026Q4", "2027Q1", "2027Q2"]  # Oracle: June to May
    assert models.covered("FY2026", 6) == ["2025Q3", "2025Q4", "2026Q1", "2026Q2"]  # Microsoft: July to June
    assert models.covered("FY2027", 1) == ["2026Q2", "2026Q3", "2026Q4", "2027Q1"]  # Nvidia: February to January


def test_the_deadline_is_when_the_2024_to_2026_fleets_are_written_off():
    names = models.QUARTERS
    d = models.deadline(5)
    assert (names[d["quarter"]], names[d["band"][0]], names[d["band"][1]], d["date"]) == (
        "2030Q4", "2029Q1", "2031Q4", "2030-12-31")
    assert names[models.deadline(3)["quarter"]] == "2028Q4"


# ---------------------------------------------------------------- Model A: capex payback


def test_a_cohort_earns_depreciation_a_return_and_its_running_costs():
    """100 placed in one quarter, 60 of it short-lived: GPUs over 5 years, buildings over 25, 8% cost of capital,
    3% running costs."""
    short, long = np.zeros(models.N), np.zeros(models.N)
    short[0], long[0] = 60.0, 40.0
    s = models.schedule(short, long, life=5, long_life=25, wacc=0.08, running=0.03)
    assert (s["depreciation"][0], s["return"][0], s["running"][0]) == pytest.approx((13.6, 8.0, 3.0))
    assert s["return"][1] == pytest.approx(0.08 * (100 - 13.6 / 4))  # 7.728: a quarter written off
    assert s["depreciation"][19] == pytest.approx(13.6)  # the GPUs' last quarter
    assert (s["depreciation"][20], s["running"][20]) == pytest.approx((1.6, 1.2))  # only the buildings are left
    assert s["return"][20] == pytest.approx(0.08 * 32)  # on the 32 not yet written off
    assert (s["depreciation"] / 4).sum() == pytest.approx(60 + 40 * models.N / 100)


def test_the_ai_share_and_the_short_lived_share_split_each_company():
    led = shipped()
    i = Q["2026Q1"]
    short, long = models.group_capex(led, {"amzn": {"2026Q1": (100.0, "filed", "filed")}}, "value")
    ai, sl = led.param("ai_share", "amzn")["value"] / 100, led.param("short_lived_share")["value"] / 100
    assert (short[i], long[i]) == pytest.approx((100 * ai * sl, 100 * ai * (1 - sl)))
    # Microsoft states its short-lived share, and that is used instead of the estimate
    stated = led.series["capex_short_lived"].get("msft", "2026Q1").value / 100
    short, long = models.group_capex(led, {"msft": {"2026Q1": (100.0, "filed", "filed")}}, "value")
    ai = led.param("ai_share", "msft")["value"] / 100
    assert (short[i], long[i]) == pytest.approx((100 * ai * stated, 100 * ai * (1 - stated)))


def test_guidance_places_the_rest_of_its_year_and_nothing_comes_after():
    led = shipped()
    led.series["capex_cash"].points["orcl"] = [point("capex_cash", "orcl", "2026Q2", 20.0),
                                                point("capex_cash", "orcl", "2026Q3", 28.5)]
    led.series["capex_guide"].points["orcl"] = [
        point("capex_guide", "orcl", "2026-06-11", 75.0, grade="company", covers="FY2027"),
        point("capex_guide", "orcl", "2026-09-09", 92.5, grade="company", covers="FY2027"),  # the latest wins
    ]
    placed = models.capex_placed(led, "orcl")
    assert placed["2026Q2"] == (20.0, "filed", "filed")  # FY2026: filed, and no guidance left for it
    for q in ("2026Q4", "2027Q1", "2027Q2"):  # Oracle's FY2027 is 2026Q3 to 2027Q2
        assert placed[q] == (pytest.approx((92.5 - 28.5) / 3), "company", "guided")
    assert max(placed) == "2027Q2"


def test_the_bet_placed_adds_up_to_each_companys_guidance():
    led = shipped()
    for eid in ("msft", "googl", "amzn", "meta", "orcl", "crwv"):
        placed = models.capex_placed(led, eid)
        guide = {}
        for p in led.series["capex_guide"].points.get(eid, []):
            if p.covers and (p.covers not in guide or p.period >= guide[p.covers].period):
                guide[p.covers] = p
        for covers, p in guide.items():
            quarters = models.covered(covers, led.entities[eid].get("fiscal_year_end"))
            filed = sum(placed[q][0] for q in quarters if q in placed and placed[q][2] == "filed")
            if filed <= p.value and any(q not in placed or placed[q][2] != "filed" for q in quarters):
                assert sum(placed[q][0] for q in quarters) == pytest.approx(p.value), (eid, covers)


# ---------------------------------------------------------------- Model A: what the market values assume


def test_the_stack_counts_for_what_it_gained_beyond_the_world_index():
    led = shipped()
    groups = led.model["valuation"]["groups"]
    for gid, members in (("chips", ["nvda"]), ("hyperscalers", ["msft"]), ("oracle_neoclouds", ["crwv"]),
                         ("labs", ["openai"])):
        groups[gid] = dict(groups[gid], members=members)
    led.series["shares_outstanding"].put([point("shares_outstanding", eid, "2026-11-07", n)
                                          for eid, n in (("nvda", 1.0), ("msft", 2.0), ("crwv", 0.5))])
    prices = Prices({"ACWI": closes(100, 150), "NVDA": closes(10, 60), "MSFT": closes(100, 120),
                     "CRWV": closes(40, 80, first="2025-03-28")})
    notes = []
    out = models.valuation(led, prices, notes)
    by = {c["id"]: c for c in out["companies"]}
    assert (by["nvda"]["market"], by["nvda"]["kept"], by["nvda"]["added"]) == (60.0, 0.75, 45.0)  # 1 - 1.5 / 6
    assert (by["msft"]["kept"], by["msft"]["added"]) == (0.0, 0.0)  # it lagged the index: it adds nothing
    assert (by["crwv"]["listed_since"], by["crwv"]["kept"], by["crwv"]["added"]) == (True, 1.0, 40.0)
    lab = led.series["lab_valuation"].latest("openai")
    assert out["groups"]["labs"] == {"label": "Labs", "on": True, "worth": lab.value,
                                     "low": lab.low or lab.value, "high": lab.high or lab.value}
    assert [out["groups"][g]["worth"] for g in ("chips", "hyperscalers", "oracle_neoclouds")] == [45.0, 0.0, 40.0]
    assert notes == []


def test_the_revenue_the_market_values_need_at_the_deadline():
    led = shipped()
    groups = {"a": {"worth": 100.0, "low": 80.0, "high": 150.0}, "b": {"worth": 50.0, "low": 50.0, "high": 50.0}}
    out = models.targets(led, groups, life=5, wacc=0.08, today=dt.date(2026, 12, 31))  # four years to 2030-12-31
    m, s = led.param("exit_multiple"), led.param("stack_profit_share")
    grow = 1.08 ** 4
    assert out["a"]["target"] == pytest.approx(100 * grow / (m["value"] * s["value"] / 100), abs=1e-3)
    assert out["a"]["low"] == pytest.approx(80 * grow / (m["high"] * s["high"] / 100), abs=1e-3)
    assert out["a"]["high"] == pytest.approx(150 * grow / (m["low"] * s["low"] / 100), abs=1e-3)
    both = models.targets(led, {"ab": {"worth": 150.0, "low": 130.0, "high": 200.0}}, 5, 0.08, dt.date(2026, 12, 31))
    assert both["ab"]["target"] == pytest.approx(out["a"]["target"] + out["b"]["target"], abs=2e-3)  # groups add up


# ---------------------------------------------------------------- Model B: what end users pay


def test_a_labs_quarters_come_from_revenue_then_its_run_rate():
    led = shipped()
    led.series["lab_revenue"].points["openai"] = [point("lab_revenue", "openai", "2026Q1", 5.0)]
    led.series["lab_revenue_annual"].points["openai"] = [point("lab_revenue_annual", "openai", "2025", 10.0)]
    led.series["lab_runrate"].points["openai"] = [point("lab_runrate", "openai", "2025-01-01", 4.0),
                                                   point("lab_runrate", "openai", "2025-12-31", 16.0),
                                                   point("lab_runrate", "openai", "2026-06-30", 30.0)]
    out = models.lab_quarters(led, "openai")
    assert out["2026Q1"] == (5.0, "filed")  # recognized revenue first
    year = [out[f"2025Q{n}"][0] for n in range(1, 5)]
    assert sum(year) == pytest.approx(10.0) and year == sorted(year)  # the year, spread by the run-rate's shape

    def rr(day: dt.date) -> float:  # straight between 2025-12-31 (16) and 2026-06-30 (30)
        return 16 + 14 * (day - dt.date(2025, 12, 31)).days / 181

    level = (rr(dt.date(2026, 4, 1)) + rr(dt.date(2026, 5, 16)) + rr(dt.date(2026, 6, 30))) / 3
    assert out["2026Q2"][0] == pytest.approx(level / 4)  # then the run-rate: a quarter of its mean level
    assert "2026Q3" not in out and "2024Q4" not in out  # never beyond the run-rate's first or last figure


def test_tiers_1_and_4_split_lab_revenue_and_tier_5_is_only_unpaid_compute():
    led = shipped()
    la = Q["2026Q3"]
    pieces, mixes = models.demand_actuals(led, la, [])
    cs = led.param("compute_share")["value"] / 100
    vc, cut = led.param("vc_funded_share"), led.param("marketplace_cut")
    labs = led.model["demand"]["labs"]
    assert "xai" not in labs and led.model["demand"]["left_out"]["xai"]  # left out, with its reason
    revenue = {lab: models.lab_quarters(led, lab) for lab in labs}
    for q in ("2025Q3", "2026Q3"):
        i = Q[q]
        gross = 4 * sum(revenue[lab][q][0] for lab in labs if q in revenue[lab])
        assert pieces["direct"]["value"][i] + pieces["vc_funded"]["value"][i] == pytest.approx(gross)
        assert pieces["vc_funded"]["value"][i] == pytest.approx(gross * vc["value"] / 100)
        net = gross * (1 - vc["high"] / 100) - 4 * revenue["anthropic"][q][0] * cut["high"] / 100
        assert pieces["direct"]["low"][i] == pytest.approx(net)  # marketplace sales, net of the partner's cut
        unpaid = 0.0
        for lab in labs:
            p = led.series["lab_compute"].get(lab, q)
            if p is not None and q in revenue[lab]:
                unpaid += max(0.0, p.value - cs * revenue[lab][q][0]) / cs
        assert pieces["investor_compute"]["value"][i] == pytest.approx(4 * unpaid)
    for pid, arrays in pieces.items():
        assert not arrays["value"][la + 1:].any(), pid  # actuals stop at the last actual quarter
        assert (arrays["low"] <= arrays["value"]).all() and (arrays["value"] <= arrays["high"]).all(), pid
    assert set(mixes["direct"]) == set(models.GRADES) and sum(mixes["direct"].values()) == pytest.approx(1, abs=1e-3)


def test_trailing_deflation_is_demand_growth_over_token_growth():
    la = 20
    pieces = {pid: {"value": np.zeros(models.N)} for pid in "abc"}
    pieces["a"]["value"][[la - 4, la]] = (10.0, 40.0)
    pieces["b"]["value"][[la - 4, la]] = (10.0, 20.0)
    pieces["c"]["value"][la] = 99.0  # new this year: not like for like, so left out
    assert models.trailing_deflation(pieces, {"a", "b", "c"}, la, growth=2.0) == pytest.approx(0.0)
    assert models.trailing_deflation(pieces, {"a"}, la, growth=1.0) == pytest.approx(1.0)  # price per unit doubled
    assert models.trailing_deflation(pieces, {"a"}, la, growth=None) is None


def test_the_projection_is_usage_times_price_per_unit():
    la = Q["2026Q3"]
    pieces = {pid: {k: np.zeros(models.N) for k in models.VARIANTS} for pid in "ab"}
    for i in range(la - 3, la + 1):
        for k, f in (("value", 1.0), ("low", 0.5), ("high", 2.0)):
            pieces["a"][k][i], pieces["b"][k][i] = 30.0 * f, 10.0 * f
    out = models.project(pieces, la, growth=2.0, floor=0.25, half_life=1.5, deflation=-0.5)

    def total(i: int) -> float:
        return out["a"]["value"][i] + out["b"]["value"][i]

    assert total(la + 1) / total(la) == pytest.approx((3.0 * 0.5) ** 0.25)  # a quarter of a year of usage x price
    end = (models.N - 1 - la - 1) / 4  # years from the first projected quarter to the last
    assert (total(models.N - 1) / total(models.N - 2)) ** 4 == pytest.approx(
        (1 + 0.25 + 1.75 * 0.5 ** (end / 1.5)) * 0.5)  # usage growth halves towards the floor
    assert out["a"]["value"][la + 5] / out["b"]["value"][la + 5] == pytest.approx(3.0)  # each keeps its share
    assert out["a"]["high"][la + 5] / out["a"]["value"][la + 5] == pytest.approx(2.0)  # and its range
    assert out["a"]["value"][la] == pieces["a"]["value"][la]  # actuals stay
    telecom = models.project(pieces, la, growth=2.0, floor=0.25, half_life=1.5, deflation=-0.8)
    # the telecom path: price per unit falls faster than usage grows, so demand shrinks while usage climbs
    assert telecom["a"]["value"][la + 1] == pytest.approx(30.0 * (3.0 * 0.2) ** 0.25)
    assert telecom["a"]["value"][models.N - 1] < telecom["a"]["value"][la + 1] < pieces["a"]["value"][la]


# ---------------------------------------------------------------- units and the grid


def test_the_units_are_factors_worked_out_here():
    led = shipped()
    u = models.units(led)
    assert u["seats"] == pytest.approx(1000 / u["seat"]["dollars"], rel=1e-6)
    i, year = Q["2026Q1"], 2026 - models.FIRST
    labour, it = u["inputs"]["labour"][year], u["inputs"]["it"][year]
    up = led.param("hour_uplift")
    assert u["hours"]["2.2"]["rate"][i] == pytest.approx(100 / 2.2 / (labour * 1000 * up["value"] / 100), rel=1e-6)
    assert u["hours"]["2.2"]["low"][i] < u["hours"]["2.2"]["rate"][i] < u["hours"]["2.2"]["high"][i]
    assert 550 * u["hours"]["2.2"]["rate"][i] > 1  # spec 6: at 2.2% capture, $550B a year needs every work hour
    assert u["pool"]["50"][i] == pytest.approx((it + labour) * 500)
    assert u["pool"]["100"][i] == pytest.approx(labour * 1000)
    assert u["gain"]["2.2"] == pytest.approx(100 / 2.2)
    ref = led.model["pool"]["it_spending"]
    first = min(int(p.period) for p in led.series["it_spending"].points[ref["entity"]])
    assert models._by_year(led, ref, first - 1) is None  # never filled in from a later year
    assert models._by_year(led, ref, models.LAST) == led.series["it_spending"].latest(ref["entity"]).value


def test_the_grid_holds_every_step_of_every_piece():
    led = shipped()
    out = models.build(led, Prices({}), DAY)
    assert (len(out["quarters"]), out["quarters"][0], out["quarters"][-1]) == (44, "2023Q1", "2033Q4")
    assert out["quarters"][out["last_actual"]] == "2026Q3"
    cells = {f"{life}|{wacc}" for life in (3, 4, 5, 6, 7) for wacc in (6, 8, 10, 12)}
    assert set(out["capex"]["grid"]) == set(out["valuation"]["grid"]) == cells
    pieces = [p["id"] for p in out["capex"]["pieces"]]
    assert len(pieces) == 15  # five groups x three cost parts
    for cell in out["capex"]["grid"].values():
        assert list(cell) == pieces
        for p in cell.values():
            assert len(p["rate"]) == len(p["low"]) == len(p["high"]) == 44
            assert all(lo <= r <= hi for lo, r, hi in zip(p["low"], p["rate"], p["high"]))
    assert set(out["demand"]["grid"]) == {"trailing", "-20", "-40", "-60", "-80"}
    tiers = [p["id"] for p in out["demand"]["pieces"]]
    assert tiers == ["direct", "bundled", "ad_lift", "vc_funded", "investor_compute", "free_users"]
    assert [p["on"] for p in out["demand"]["pieces"]] == [True] * 5 + [False]  # free users are off by default
    for step in out["demand"]["grid"].values():
        assert list(step["pieces"]) == tiers
        assert set(step["pieces"]["direct"]["readouts"]) == {"3", "4", "5", "6", "7"}

    # a readout is what the page would get by adding up the rates itself
    la, dl = out["last_actual"], out["deadlines"]["5"]["quarter"]
    p = out["capex"]["grid"]["5|8"]["hyperscalers.depreciation"]
    assert p["readouts"]["rate"]["last4"] == pytest.approx(sum(p["rate"][la - 3:la + 1]) / 4, abs=1e-2)
    assert p["readouts"]["rate"]["at_deadline"] == p["rate"][dl]
    assert p["readouts"]["rate"]["to_deadline"] == pytest.approx(sum(p["rate"][:dl + 1]) / 4, abs=1e-2)
    # a longer GPU life spreads depreciation thinner; a dearer cost of capital asks a bigger return
    grid = out["capex"]["grid"]
    assert grid["7|8"]["hyperscalers.depreciation"]["rate"][la] < grid["3|8"]["hyperscalers.depreciation"]["rate"][la]
    assert grid["5|12"]["hyperscalers.return"]["rate"][la] > grid["5|6"]["hyperscalers.return"]["rate"][la]
    # the page only adds and divides: nothing the build gives it is a money key
    assert not set(keys(out)) & set(brief.MONEY_KEYS)
    assert out["clock"]["from"] == "2026-01-01" and out["clock"]["date"] == "2026-09-30"
    assert out["clock"]["capex_out"] > out["clock"]["demand_in"] > 0


def test_prepare_writes_both_models(user, fake_world):
    morning.prepare(user, today=TODAY)
    bet = json.loads((user.out / "bet.json").read_text("utf-8"))
    assert {"capex", "valuation", "demand", "units", "clock", "deadlines", "notes", "fetched"} <= set(bet)
    assert bet["fetched"]["figures"] > 0 and bet["date"] == TODAY.isoformat()
    assert "No prices for the world index (ACWI): each company counts whole." in bet["notes"]  # the fakes start in 2023
    (user.out / "bet.json").unlink()
    morning.prepare(user, offline=True, today=TODAY)
    assert (user.out / "bet.json").exists()  # offline, from the cache
