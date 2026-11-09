"""Your reach to each crash path, next to the world index's, and the past episodes replayed (spec section 10); the
open-weight releases' effects and the analogs (spec sections 11 and 12)."""
import datetime as dt
import json

import numpy as np
import pandas as pd
import pytest

from whatstocks import brief, morning, scan
from whatstocks.bet import ledger, markets, models, reach
from whatstocks.bet.ledger import Point
from whatstocks.files import Theme, ThemeMap

from conftest import TODAY

DAY = dt.date(2026, 11, 7)
THEMES = ThemeMap({
    "ai": Theme("ai", "AI build-out", "", "SMH", core=["NVDA", "ASML"], partial=["MSFT"]),
    "hs": Theme("hs", "Hyperscalers", "", "MAGS", core=["MSFT", "GOOGL", "GOOG"], partial=[]),
}, aliases={"NVDA": ["NVD.DE"]})


def point(series: str, entity: str, period: str, value: float) -> Point:
    return Point(series, entity, period, value, None, None, "press", "https://x.test/1", DAY)


def book(points=(), units=None, entities=None, signals=None, model=None, events=None) -> ledger.Ledger:
    series = {}
    for p in points:
        if p.series not in series:
            series[p.series] = ledger.Series(p.series, p.series.replace("_", " ").capitalize(),
                                             (units or {}).get(p.series, ""), "", "", "",
                                             (entities or {}).get(p.series, {}), {})
    for sid, s in series.items():
        s.put([p for p in points if p.series == sid])
    return ledger.Ledger({}, series, [], model or {}, signals or {}, events or {}, {})


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


# ---------------------------------------------------------------- reach


def test_a_theme_tier_reaches_only_its_members():
    core, whole, partial = ({"kind": "theme", "id": i} for i in ("ai:core", "ai", "ai:partial"))
    m = scan._membership
    assert [m("NVDA", "US", c, THEMES) for c in (core, whole, partial)] == [1.0, 1.0, 0.0]
    assert [m("MSFT", "US", c, THEMES) for c in (core, whole, partial)] == [0.0, 0.5, 0.5]
    assert m("NVD.DE", "DE", core, THEMES) == 1.0  # another listing counts as its company
    assert m(None, "US", whole, THEMES) == 0.0 and m("XOM", "US", whole, THEMES) == 0.0
    assert m("NVDA", "US", {"kind": "theme", "id": "gold"}, THEMES) == 0.0


def flat_then(level: float, from_day: str, days: pd.DatetimeIndex) -> pd.Series:
    """100 until from_day, then level."""
    return pd.Series(np.where(days < pd.Timestamp(from_day), 100.0, level), index=days)


def test_each_path_reaches_you_and_the_world_and_replays_its_episodes():
    sig = {
        "paths": {"capex": {"label": "Capex retrenchment", "kind": "crash"},
                  "pace": {"label": "Adoption pace", "kind": "adoption"}},
        "channels": {"capex": [
            {"kind": "theme", "id": "ai:core", "effect": "hurt", "strength": "high"},
            {"kind": "theme", "id": "ai", "effect": "hurt", "strength": "medium"},
            {"kind": "theme", "id": "hs", "effect": "mixed", "strength": "medium", "why": "Cash flow rises."}]},
        "replays": [
            {"id": "dip", "label": "A dip", "start": dt.date(2024, 3, 1), "end": dt.date(2024, 3, 15), "paths": ["capex"]},
            {"id": "early", "label": "Early", "start": dt.date(2024, 1, 10), "end": dt.date(2024, 1, 19),
             "paths": ["capex", "pace"]},
        ],
    }
    # NVDA held directly (40%), and a fund (60%) holding NVDA, MSFT and an untracked rest.
    look = {"you": [["NVDA", 0.4, "NVDA", "United States"], ["FUND", 0.1, "NVDA", "United States"],
                    ["FUND", 0.2, "MSFT", "United States"], ["FUND", 0.3, None, "Japan"]],
            "world": [["ACWI", 0.05, "NVDA", "United States"], ["ACWI", 0.04, "MSFT", "United States"],
                      ["ACWI", 0.91, None, "United States"]]}
    days = pd.bdate_range("2024-01-01", "2024-06-28")
    series = {"NVDA": flat_then(80.0, "2024-03-04", days),
              "FUND": flat_then(100.0, "2024-03-04", days)[days >= "2024-02-15"],  # no prices before mid-February
              "ACWI": flat_then(95.0, "2024-03-04", days)}
    out = reach.crash_paths(book(signals=sig), THEMES, look, {"NVDA": 0.4, "FUND": 0.6}, series, set(), "ACWI")

    capex = out["capex"]
    # The strongest channel of each effect counts, not the sum: NVDA is in ai:core (high) and ai (medium).
    assert capex["you"] == pytest.approx({"hurt_share": 0.7, "hurt_score": 0.4 + 0.1 + 0.2 / 3, "help_share": 0.0,
                                          "help_score": 0.0, "mixed_share": 0.2, "mixed_score": 0.2 * 2 / 3}, abs=1e-6)
    assert capex["world"] == pytest.approx({"hurt_share": 0.09, "hurt_score": 0.05 + 0.04 / 3, "help_share": 0.0,
                                            "help_score": 0.0, "mixed_share": 0.04, "mixed_score": 0.04 * 2 / 3},
                                           abs=1e-6)
    shares = {c["id"]: (c["you"], c["world"], c["label"]) for c in capex["channels"]}
    assert shares["ai:core"] == (0.5, 0.05, "AI build-out, core members")
    assert shares["ai"] == (pytest.approx(0.6), pytest.approx(0.07), "AI build-out")  # MSFT counts half
    assert shares["hs"] == (0.2, 0.04, "Hyperscalers") and capex["channels"][2]["why"] == "Cash flow rises."
    assert [h["symbol"] for h in capex["holdings"]] == ["FUND", "NVDA"]
    fund = capex["holdings"][0]
    assert (fund["weight"], fund["hurt_share"], fund["mixed_share"]) == (
        0.6, pytest.approx(0.5, abs=1e-6), pytest.approx(1 / 3, abs=1e-6))  # of the part looked through
    assert capex["holdings"][1]["hurt_score"] == 1.0

    dip, early = capex["replays"]
    assert (dip["id"], dip["name"], dip["start"], dip["end"]) == ("dip", "A dip", "2024-03-01", "2024-03-15")
    assert (dip["you"], dip["world"], dip["coverage"]) == (pytest.approx(-0.08), pytest.approx(-0.05), 1.0)
    assert (early["you"], early["coverage"]) == (0.0, 0.4)  # the fund has no prices that early
    pace = out["pace"]
    assert pace["channels"] == [] and pace["holdings"] == [] and not any(pace["you"].values())
    assert [r["id"] for r in pace["replays"]] == ["early"]


# ---------------------------------------------------------------- open-weight releases

T0, T1 = pd.Timestamp("2025-01-21"), pd.Timestamp("2025-01-24")  # around a release on Wednesday 2025-01-22


def walk(seed: int, days: pd.DatetimeIndex, a: float, b: float) -> pd.Series:
    """A random walk that closes at a on T0 and at b on T1."""
    rng = np.random.default_rng(seed)
    w = pd.Series(np.exp(np.cumsum(rng.normal(0, 0.01, len(days)))), index=days)
    return pd.Series(np.where(days < T1, a * w / w[T0], b * w / w[T1]), index=days)


def release_prices() -> Prices:
    """GOOG is GOOGL's other share class: the same returns."""
    days = pd.bdate_range("2024-06-03", "2025-03-31")
    fixed = {"ACWI": (100, 101), "NVDA": (100, 90), "ASML": (50, 47.5), "MSFT": (100, 104), "GOOGL": (100, 96)}
    closes = {symbol: walk(seed, days, a, b) for seed, (symbol, (a, b)) in enumerate(fixed.items())}
    closes["GOOG"] = closes["GOOGL"] * 0.99
    return Prices(closes)


RELEASES = {"releases": [
    {"id": "one", "name": "Model One", "lab": "Lab", "released": dt.date(2025, 1, 22), "source": "https://x.test/r1",
     "press": "https://x.test/p1"},
    {"id": "early", "name": "Model Zero", "lab": "Lab", "released": dt.date(2024, 5, 1), "source": "https://x.test/r0",
     "press": "https://x.test/p0"},
]}
SIGNALS = {"indicators": {"ai_basket": {"basket": "ai:core"}, "hyperscaler_basket": {"basket": "hs"}}}


def test_a_release_moves_each_basket_less_the_world_counting_each_company_once():
    usage = [point("tokens_weekly", "openrouter", d, v)
             for d, v in (("2025-01-19", 1.0), ("2025-02-20", 1.5), ("2025-04-25", 3.0))]
    usage += [point("openrouter_token_share", "open_weight", d, v) for d, v in (("2025-01-30", 30.0), ("2025-04-20", 40.0))]
    led = book(usage, units={"tokens_weekly": "tokens_t", "openrouter_token_share": "pct"}, signals=SIGNALS,
               model={"valuation": {"world": "ACWI"}}, events=RELEASES)
    out = markets.releases(led, release_prices(), THEMES)
    one, early = out["items"]
    # The AI basket fell 7.5% (NVDA -10%, ASML -5%) while the world rose 1%. MSFT +4% and GOOGL -4%: GOOG, the same
    # company, counts once, so the hyperscalers are flat, 1% behind the world.
    assert one["market"] == {"from": "2025-01-21", "to": "2025-01-24", "world": pytest.approx(0.01),
                             "ai": pytest.approx(-0.085), "hyperscalers": pytest.approx(-0.01)}
    assert early["market"] == {"from": None, "to": None, "world": None, "ai": None, "hyperscalers": None}
    tokens, share = one["adoption"]
    assert tokens["change"] == {"30": pytest.approx(0.5), "90": pytest.approx(2.0)}  # as fractions
    assert share["change"] == {"30": None, "90": pytest.approx(10.0)}  # a share moves in points
    assert share["label"] == "Openrouter token share: open_weight" and share["unit"] == "pct"
    assert out["average"]["market"]["ai"] == {"mean": pytest.approx(-0.085), "n": 1}
    assert out["average"]["adoption"]["openrouter_token_share.open_weight"] == {
        "30": {"mean": None, "n": 0}, "90": {"mean": pytest.approx(10.0), "n": 1}}
    assert out["notes"] == ["The ledger has no token price index by date yet, so a release's effect on prices is not "
                            "measured."]
    assert (one["source"], one["press"], out["days"], out["after"]) == ("https://x.test/r1", "https://x.test/p1", 3,
                                                                         [30, 90])


def test_without_figures_near_a_release_its_adoption_effect_stays_empty():
    led = book(signals=SIGNALS, model={"valuation": {"world": "ACWI"}}, events=RELEASES)
    out = markets.releases(led, Prices({}), THEMES)
    assert all(i["adoption"] == [] for i in out["items"])  # the usage series are not in this ledger at all
    assert all(i["market"]["world"] is None for i in out["items"])
    assert out["notes"][:2] == ["No prices for the world index (ACWI): no market effects.",
                                "The ledger has no usage figure within 10 days of a release and of 30 or 90 days "
                                "later yet, so no adoption effect is measured."]


# ---------------------------------------------------------------- analogs


def test_analogs_count_years_from_their_start_and_index_levels_to_100():
    found = [point("telecom_investment", "equipment", y, v) for y, v in (("1996", 70.0), ("1997", 80.0), ("1998", 87.5))]
    found += [point("tech_adoption", "pc", "1984", 20.0)]
    events = {"ai_start": 2023, "analogs": {
        "telecom": {"label": "Telecom", "start": 1996, "shows": "A crash.", "series": ["telecom_investment.equipment"]},
        "s_curves": {"label": "S-curves", "by": "launch", "shows": "Speed.", "series": ["tech_adoption.pc"]},
        "cloud": {"label": "Cloud", "start": 2010, "shows": "A payoff.", "series": []},
    }}
    led = book(found, units={"telecom_investment": "usd_b", "tech_adoption": "pct"}, events=events,
               entities={"telecom_investment": {"equipment": {"label": "Equipment"}},
                         "tech_adoption": {"pc": {"label": "Personal computer", "launch": 1981}}})
    bet = {"capex": {"by_year": {"years": [2023, 2024], "actual_through": "2024Q2", "mid": [100.0, 150.0],
                                 "low": [80.0, 120.0], "high": [120.0, 180.0]}}}
    out = markets.analogs(led, bet)
    telecom = out["items"]["telecom"]["lines"][0]
    assert (telecom["label"], telecom["indexed"], telecom["start"]) == ("Equipment", True, 1996)
    assert telecom["points"] == [[0.0, 100.0], [1.0, 114.286], [2.0, 125.0]]
    pc = out["items"]["s_curves"]["lines"][0]
    assert (pc["points"], pc["indexed"], pc["start"]) == ([[3.0, 20.0]], False, 1981)  # a share, by years since launch
    assert out["items"]["cloud"]["lines"] == []
    assert out["ai_capex"]["points"] == [[0, 100.0, 80.0, 120.0], [1, 150.0, 120.0, 180.0]]
    assert out["ai_capex"]["actual_through"] == "2024Q2"  # the page says the last year adds guidance


def test_ai_capex_by_year_stops_at_the_last_actual_year_and_counts_the_groups_switched_on():
    def stream(**by_quarter: float) -> tuple:
        short = np.zeros(models.N)
        for q, x in by_quarter.items():
            short[models.INDEX[q.replace("_", "")]] = x
        return short, np.zeros(models.N)

    on = stream(_2023Q1=10.0, _2023Q3=5.0, _2024Q1=7.0, _2025Q1=100.0)  # 2025 is guidance: past the last actual
    streams = {"a": {k: on for k in models.VARIANTS}, "b": {k: stream(_2023Q1=1000.0) for k in models.VARIANTS}}
    out = models.capex_by_year(streams, {"a": {"enabled": True}, "b": {"enabled": False}}, models.INDEX["2024Q2"])
    assert out == {"years": [2023, 2024], "actual_through": "2024Q2", "mid": [15.0, 7.0], "low": [15.0, 7.0],
                   "high": [15.0, 7.0]}


# ---------------------------------------------------------------- the morning


def test_prepare_writes_the_reach_of_each_path_and_the_markets(user, fake_world):
    morning.prepare(user, today=TODAY)
    paths = json.loads((user.out / "exposure.json").read_text("utf-8"))["crash_paths"]
    assert set(paths) == {"capex_retrenchment", "equity_drawdown", "credit_event", "price_collapse", "adoption_pace"}
    assert [r["id"] for r in paths["credit_event"]["replays"]] == ["covid", "rate_shock_2022"]
    capex = paths["capex_retrenchment"]
    assert capex["channels"][0]["label"] == "AI build-out, core members"
    assert 0 < capex["you"]["hurt_share"] <= 1 and 0 < capex["world"]["hurt_share"] <= 1
    assert {"NVDA", "ASML.AS"} <= {h["symbol"] for h in capex["holdings"]}
    assert not set(keys(paths)) & brief.MONEY_KEYS
    look = json.loads((user.out / "lookthrough.json").read_text("utf-8"))
    assert set(look) == {"date", "you", "world"} and look["you"]

    bet = json.loads((user.out / "bet.json").read_text("utf-8"))
    assert len(bet["releases"]["items"]) == 15 and any(i["market"]["world"] is not None for i in bet["releases"]["items"])
    assert set(bet["analogs"]["items"]) == {"telecom", "electrification", "cloud", "s_curves"}
    assert bet["capex"]["by_year"]["years"][-1] <= int(bet["quarters"][bet["last_actual"]][:4])
