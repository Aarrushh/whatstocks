import datetime as dt

import pandas as pd
import pytest

from whatstocks.market import Fx, Prices

DAYS = pd.to_datetime(["2026-11-02", "2026-11-03"])


def test_pence_are_converted_and_a_failed_refresh_keeps_the_cache(tmp_path):
    closes = pd.Series([2500.0, 2510.0], index=DAYS)
    assert Prices(tmp_path).refresh(["SHEL.L"], closes=lambda s: {"SHEL.L": closes}, currency=lambda s: "GBp") == []
    prices = Prices(tmp_path)
    assert prices.currency("SHEL.L") == "GBP"
    assert prices.series("SHEL.L").iloc[-1] == pytest.approx(25.10)

    def broken(symbols):
        raise ConnectionError

    assert Prices(tmp_path).refresh(["SHEL.L", "NEW"], closes=broken, currency=lambda s: None) == ["SHEL.L", "NEW"]
    assert Prices(tmp_path).series("SHEL.L").iloc[-1] == pytest.approx(25.10)


def test_reserved_windows_names_are_safe(tmp_path):
    closes = pd.Series([10.0, 11.0], index=DAYS)
    Prices(tmp_path).refresh(["CON.DE"], closes=lambda s: {"CON.DE": closes}, currency=lambda s: "EUR")
    assert Prices(tmp_path).series("CON.DE").iloc[-1] == 11.0


def test_stale_prices(tmp_path):
    closes = pd.Series([10.0, 11.0], index=DAYS)
    Prices(tmp_path).refresh(["A"], closes=lambda s: {"A": closes}, currency=lambda s: "USD")
    prices = Prices(tmp_path)
    assert prices.stale(["A"], dt.date(2026, 11, 5)) == {}
    assert prices.stale(["A", "NONE"], dt.date(2026, 11, 20)) == {"A": "2026-11-03", "NONE": None}


def test_fx_conversion_by_day(tmp_path):
    rates = pd.DataFrame({"USD": [1.10, 1.00], "GBP": [0.85, 0.80]}, index=DAYS)
    fx = Fx(tmp_path)
    assert fx.refresh({"USD", "GBP", "EUR"}, rates=lambda c: rates)
    usd = pd.Series([110.0, 100.0], index=DAYS)
    assert list(fx.convert(usd, "USD", "EUR")) == pytest.approx([100.0, 100.0])
    cached = Fx(tmp_path)
    assert list(cached.convert(usd, "USD", "GBP")) == pytest.approx([85.0, 80.0])
    assert cached.latest(100.0, "USD", "EUR") == pytest.approx(100.0)
    assert cached.has("EUR") and cached.has("GBP") and not cached.has("JPY")

    def broken(currencies):
        raise ConnectionError

    assert not cached.refresh({"USD"}, rates=broken)
    assert cached.has("USD")
