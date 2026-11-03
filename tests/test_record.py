import datetime as dt
from collections import Counter

import pandas as pd
import pytest
from conftest import DEMO_FUNDS

from whatstocks.files import Decision, Forecast, View, load_book
from whatstocks.paths import ROOT, UserDir
from whatstocks.record import brier, change, decision_flags, reviews, scores

D0 = dt.date(2026, 1, 1)


def view(vid, forecasts, outcome=None, themes=None):
    return View(vid, "statement", D0, D0 + dt.timedelta(days=400), "rule", themes or {"ai_buildout": "down"},
                [Forecast(D0 + dt.timedelta(days=d), p, "") for d, p in forecasts], outcome)


def decision(action, symbol, views, day=dt.date(2026, 3, 1)):
    return Decision("x", day, action, symbol, None, views, "reason", day + dt.timedelta(days=365), None)


def test_brier_weights_each_day_by_the_probability_then_in_force():
    v = view("v", [(0, 0.2), (10, 0.6)], {"result": "yes", "date": D0 + dt.timedelta(days=20)})
    assert brier(v) == pytest.approx((10 * 0.8 ** 2 + 10 * 0.4 ** 2) / 20)
    assert brier(view("w", [(0, 0.3)], {"result": "no", "date": D0 + dt.timedelta(days=50)})) == pytest.approx(0.09)
    assert brier(view("z", [(0, 0.3)], {"result": "void", "date": D0, "note": "rule broke"})) is None


def test_scores_skip_void_and_warn_about_luck():
    views = [
        view("a", [(0, 0.3)], {"result": "no", "date": D0 + dt.timedelta(days=50)}),
        view("b", [(0, 0.3)], {"result": "void", "date": D0, "note": "n"}),
        view("c", [(0, 0.5)]),
    ]
    s = scores(views)
    assert s["count"] == 1 and s["mean"] == pytest.approx(0.09)
    assert len(s["views"]) == 2 and s["luck"]


def test_demo_decision_flags():
    book = load_book(UserDir(ROOT / "demo"), DEMO_FUNDS)
    flags = {d.id: decision_flags(d, book, {}) for d in book.decisions}
    assert flags == {
        "d-2026-09-15-nvda": ["Low-confidence view: ai-capex-cut-2027 was 30% that day"],
        "d-2026-10-01-shel-l": ["No view cited"],
        "d-2026-10-20-infy-ns": [],
    }


def test_against_your_view_busy_day_and_view_written_later():
    book = load_book(UserDir(ROOT / "demo"), DEMO_FUNDS)
    book.views.append(view("capex-crash", [(0, 0.7)]))
    busy = {"2026-03-01": Counter({"ai_buildout": 3})}
    assert decision_flags(decision("buy", "NVDA", ["capex-crash"]), book, busy) == [
        "Against your view: capex-crash implies ai_buildout down",
        "Busy news day",
    ]
    # A partial member is not flagged: the view says less about it.
    assert decision_flags(decision("buy", "MSFT", ["capex-crash"]), book, {}) == []
    early = decision("buy", "NVDA", ["capex-crash"], day=dt.date(2025, 12, 1))
    assert decision_flags(early, book, {}) == ["Cites capex-crash, which was written after this decision"]


def test_reviews_compare_with_the_world():
    book = load_book(UserDir(ROOT / "demo"), DEMO_FUNDS)
    days = pd.bdate_range("2026-09-01", "2027-10-30")
    up = pd.Series(range(100, 100 + len(days)), index=days, dtype=float)
    flat = pd.Series(100.0, index=days)
    rows = reviews(book, dt.date(2027, 10, 30), lambda s: up, flat)
    assert [r["id"] for r in rows] == ["d-2026-09-15-nvda", "d-2026-10-01-shel-l", "d-2026-10-20-infy-ns"]
    assert rows[0]["since"] > 0 and rows[0]["world"] == 0
    assert reviews(book, dt.date(2027, 1, 1), lambda s: up, flat) == []
    assert change(pd.Series(dtype=float), D0, D0) is None
