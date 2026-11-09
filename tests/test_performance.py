"""Price moves for the dashboard (performance.py)."""
import datetime as dt
import math

import pandas as pd
import pytest

from whatstocks import performance as perf

TODAY = dt.date(2026, 11, 3)


def series(values, end: str = "2026-11-03") -> pd.Series:
    return pd.Series(values, index=pd.bdate_range(end=end, periods=len(values)), dtype=float)


def test_change_over_each_period():
    days = pd.bdate_range("2025-10-01", "2026-11-03")
    s = pd.Series(range(100, 100 + len(days)), index=days, dtype=float)
    assert perf.change(s, TODAY, "1D") == pytest.approx(s.iloc[-1] / s.iloc[-2] - 1)
    assert perf.change(s, TODAY, "YTD") == pytest.approx(s.iloc[-1] / s[s.index <= "2025-12-31"].iloc[-1] - 1)
    assert perf.change(s.iloc[-30:], TODAY, "1Y") is None  # not enough history for a year
    assert set(perf.changes(s, TODAY)) == {name for name, _ in perf.PERIODS}
    later = pd.concat([s, pd.Series([1000.0], index=[pd.Timestamp("2026-11-04")])])
    assert perf.change(later, TODAY, "1D") == perf.change(s, TODAY, "1D")  # nothing after today counts


def test_replay_counts_cash_as_flat():
    rets, covered = perf.daily_returns({"A": 0.5, "CASH": 0.5}, {"A": series([100, 110, 121])}, {"CASH"}, TODAY)
    assert covered == pytest.approx(1.0)
    assert list(rets.round(6)) == [0.05, 0.05]  # half the money up 10% a day, half in cash
    line = perf.index_line(rets, TODAY)
    assert line[0][1] == 100.0 and line[-1][1] == pytest.approx(110.25)


def test_portfolio_line_ends_where_its_period_figures_say():
    days = pd.bdate_range("2025-06-02", "2026-11-03")
    prices = pd.Series([100 + 10 * math.sin(i / 5) + 0.1 * i for i in range(len(days))], index=days)
    morning = dt.date(2026, 11, 4)  # a Wednesday morning: the last close is Tuesday's
    rets, _ = perf.daily_returns({"A": 1.0}, {"A": prices}, set(), morning)
    line = dict(perf.index_line(rets, morning))
    level = (1 + rets).cumprod()
    last = list(line)[-1]
    assert line[min(line)] == 100.0 and last == "2026-11-03"
    for period, back in (("1M", 30), ("3M", 91), ("1Y", 365)):
        cut = (pd.Timestamp(last) - pd.Timedelta(days=back)).date().isoformat()
        base = max(d for d in line if d <= cut)  # what the page's window control starts from
        assert line[last] / line[base] - 1 == pytest.approx(perf.change(level, morning, period), abs=1e-4)


def test_a_market_holiday_carries_the_last_price():
    days = pd.bdate_range(end="2026-11-03", periods=3)
    a = pd.Series([100.0, 100.0, 100.0], index=days)
    b = pd.Series([100.0, 120.0], index=[days[0], days[2]])  # closed on the middle day
    rets, _ = perf.daily_returns({"A": 0.5, "B": 0.5}, {"A": a, "B": b}, set(), TODAY)
    assert list(rets.round(6)) == [0.0, 0.1]


def test_theme_weeks_are_the_gap_to_the_world_index():
    days = pd.bdate_range("2026-06-01", "2026-11-03")
    proxy = pd.Series([100 * 1.01 ** i for i in range(len(days))], index=days)
    world = pd.Series(100.0, index=days)
    weeks = perf.theme_weeks(proxy, world, TODAY)
    assert len(weeks) == perf.HEAT_WEEKS
    assert all(gap > 0 for _, gap in weeks)  # the proxy rose every week; the world index stood still


def test_rebased_lines_start_at_100():
    line = perf.rebased(series([50.0, 55.0, 60.0]), TODAY, 30)
    assert [v for _, v in line] == [100.0, 110.0, 120.0]
    assert perf.rebased(series([50.0]), TODAY, 30) == []


def test_weekly_line_ends_where_the_year_figure_says():
    days = pd.bdate_range("2025-09-01", "2026-11-03")  # 2026-11-03 is a Tuesday
    s = pd.Series([100 * 1.002 ** i for i in range(len(days))], index=days)
    line = perf.rebased(s, TODAY, 365, weekly=True)
    assert line[-1][0] == "2026-11-03"  # today's close on its own date, not the Friday that ends the week
    assert line[0][0] == "2025-11-03" and line[0][1] == 100.0  # the same base as the 1Y change
    assert line[-1][1] / 100 - 1 == pytest.approx(perf.change(s, TODAY, "1Y"), abs=1e-4)
    assert all(dt.date.fromisoformat(d).weekday() == 4 for d, _ in line[1:-1])  # one close a week, on Fridays


def test_sectors_compare_your_stocks_with_the_sector_fund():
    s = {"A": series([100, 110]), "B": series([100, 100]), "C": series([100, 90]),
         "XDWS.DE": series([100, 102]), "XDWT.DE": series([100, 95])}
    weights = {"A": 0.3, "B": 0.1, "C": 0.2, "FUND": 0.4}
    rows = perf.sector_rows(weights, s, {"A": "Consumer Defensive", "B": "Consumer Defensive", "C": "Technology"}, TODAY)
    staples, tech = rows  # largest share first
    assert staples["label"] == "Consumer staples" and staples["fund"] == "XDWS.DE"
    assert staples["weight"] == pytest.approx(0.4) and staples["holdings"] == ["A", "B"]
    assert staples["you"]["1D"] == pytest.approx(0.075)  # A up 10% at 3/4 of the sector, B flat
    assert staples["average"]["1D"] == pytest.approx(0.02)
    assert staples["gap"]["1D"] == pytest.approx(0.055)
    assert tech["you"]["1D"] == pytest.approx(-0.1) and tech["gap"]["1D"] == pytest.approx(-0.05)


def test_a_sector_without_a_fund_shows_no_average():
    rows = perf.sector_rows({"A": 1.0}, {"A": series([100, 105])}, {"A": "Real Estate"}, TODAY)
    assert rows[0]["fund"] is None and rows[0]["average"] == {} and rows[0]["gap"]["1D"] is None


def test_compare_lists_each_extra_index_from_settings():
    class Book:
        class settings:
            compare = {"Nasdaq-100": "EQQQ.DE", "Missing": "NOPE"}

    out = perf.compare(Book, {"EQQQ.DE": series([100, 104])}, TODAY)
    assert [c["name"] for c in out] == ["Nasdaq-100", "Missing"]
    assert out[0]["returns"]["1D"] == pytest.approx(0.04) and out[0]["line"][-1][1] == pytest.approx(104)
    assert out[1]["returns"] == {} and out[1]["line"] == []
