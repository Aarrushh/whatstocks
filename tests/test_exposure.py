import numpy as np
import pandas as pd
import pytest

from whatstocks.exposure import beta, portfolio_weekly, sell_offs, theme_shares, window_return, worst_weeks
from whatstocks.files import load_themes
from whatstocks.funds import Piece

WEEKS = pd.date_range("2024-11-08", periods=104, freq="W-FRI")


def test_theme_share_matches_aliases_exchanges_and_partials():
    themes = load_themes(None, [])
    pieces = [
        Piece(("2330", "Taiwan Stock Exchange"), "TSMC", 10, "Taiwan", "TWD"),  # TSM's home line: AI core
        Piece(("BA", "London Stock Exchange"), "BAE SYSTEMS", 10, "United Kingdom", "GBP"),  # BA.L: defence core
        Piece(("BA", "New York Stock Exchange Inc."), "BOEING", 10, "United States", "USD"),  # BA: defence partial
        Piece(("MSFT", "NASDAQ"), "MICROSOFT", 10, "United States", "USD"),  # AI partial
        Piece("SHEL.L", "Shell", 10, "United Kingdom", "GBP"),  # held directly
    ]
    shares = theme_shares(pieces, themes)
    assert shares["ai_buildout"]["share"] == pytest.approx(15 / 50)
    assert shares["defence"]["share"] == pytest.approx(15 / 50)
    assert shares["oil_gas"]["share"] == pytest.approx(10 / 50)
    assert shares["gold"] == {"share": 0.0, "names": []}
    assert [m for m, _ in shares["ai_buildout"]["names"]] == ["TSM", "MSFT"]


def test_beta_recovers_a_known_slope():
    rng = np.random.default_rng(1)
    x = pd.Series(rng.normal(0, 0.02, 104), index=WEEKS)
    y = 1.5 * x + rng.normal(0, 0.002, 104)
    assert beta(y, x) == pytest.approx(1.5, abs=0.05)
    assert beta(y.iloc[:40], x.iloc[:40]) is None


def test_portfolio_weekly_leaves_out_short_histories():
    days = pd.bdate_range("2024-01-01", "2026-11-02")
    long = pd.Series(np.linspace(100, 150, len(days)), index=days)
    short = long.iloc[-100:]
    port, covered = portfolio_weekly({"A": 0.5, "B": 0.3, "CASH": 0.2}, {"A": long, "B": short}, {"CASH"})
    assert covered == pytest.approx(0.7)
    assert len(port) == 104
    assert (port > 0).all()


def test_worst_weeks_and_windows():
    proxy = pd.Series(np.linspace(-0.05, 0.05, 104), index=WEEKS)
    you = proxy * 2
    result = worst_weeks(proxy, you, pd.Series(0.0, index=WEEKS))
    assert result["proxy"] == pytest.approx(proxy.nsmallest(10).mean())
    assert result["you"] == pytest.approx(2 * result["proxy"])
    assert result["world"] == 0

    days = pd.bdate_range("2021-01-04", "2026-11-02")
    s = pd.Series(np.linspace(100, 200, len(days)), index=days)
    assert window_return(s, "2020-02-19", "2020-03-23") is None  # no prices yet
    assert window_return(s, "2022-01-03", "2022-12-30") > 0
    covid, rates, ai = sell_offs({"A": 0.8, "C": 0.2}, {"A": s}, {"C"}, s)
    assert covid["coverage"] == pytest.approx(0.2) and covid["world"] is None
    assert rates["coverage"] == pytest.approx(1.0) and rates["you"] == pytest.approx(0.8 * rates["world"])
