"""Prices from Yahoo (via yfinance) and FX from the ECB, with the local cache as the backup (SPEC decision 3)."""
from __future__ import annotations

import datetime as dt
import io
import json
import warnings
from pathlib import Path

import pandas as pd
import requests

START = "2019-12-01"
STALE_AFTER_DAYS = 4
# Quotes in a sub-unit, converted to the main unit on the way into the cache.
SUBUNITS = {"GBp": ("GBP", 100.0), "GBX": ("GBP", 100.0), "ZAc": ("ZAR", 100.0), "ILA": ("ILS", 100.0)}
ECB_URL = "https://data-api.ecb.europa.eu/service/data/EXR/D.{codes}.EUR.SP00.A"


def yahoo_closes(symbols: list[str]) -> dict[str, pd.Series]:
    """Daily adjusted closes since START. Symbols Yahoo has nothing for are left out."""
    import yfinance as yf

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")  # yfinance's own pandas deprecation warnings
        frame = yf.download(symbols, start=START, auto_adjust=True, group_by="ticker", threads=True, progress=False)
    closes = {}
    for symbol in symbols:
        try:
            close = frame[symbol]["Close"] if isinstance(frame.columns, pd.MultiIndex) else frame["Close"]
        except KeyError:
            continue
        close = close.dropna().astype(float)
        index = pd.DatetimeIndex(close.index)
        close.index = (index.tz_localize(None) if index.tz is not None else index).normalize()
        if len(close):
            closes[symbol] = close
    return closes


def yahoo_currency(symbol: str) -> str | None:
    import yfinance as yf

    return yf.Ticker(symbol).fast_info.get("currency")


def ecb_rates(currencies: list[str]) -> pd.DataFrame:
    """Units of each currency per 1 EUR, one column per currency."""
    response = requests.get(
        ECB_URL.format(codes="+".join(currencies)),
        params={"format": "csvdata", "startPeriod": START},
        timeout=60,
    )
    response.raise_for_status()
    rows = pd.read_csv(io.StringIO(response.text))
    table = rows.pivot(index="TIME_PERIOD", columns="CURRENCY", values="OBS_VALUE")
    table.index = pd.DatetimeIndex(table.index)
    return table.sort_index()


class Prices:
    """Daily closes per symbol, in the listing's main currency unit."""

    def __init__(self, cache: Path):
        self.dir = cache / "prices"
        self.meta_path = cache / "prices.json"
        self.meta = json.loads(self.meta_path.read_text("utf-8")) if self.meta_path.exists() else {}

    def _path(self, symbol: str) -> Path:
        # The prefix keeps names like CON.DE clear of reserved Windows file names.
        return self.dir / f"p_{symbol}.csv"

    def series(self, symbol: str) -> pd.Series:
        path = self._path(symbol)
        if not path.exists():
            return pd.Series(dtype=float)
        frame = pd.read_csv(path, index_col=0, parse_dates=True)
        return frame.iloc[:, 0].astype(float)

    def currency(self, symbol: str) -> str | None:
        return self.meta.get(symbol, {}).get("currency")

    def refresh(self, symbols, closes=None, currency=None) -> list[str]:
        """Re-download full histories. Returns the symbols that failed; their cached prices stay."""
        closes, currency = closes or yahoo_closes, currency or yahoo_currency
        symbols = list(symbols)
        try:
            fresh = closes(sorted(symbols))
        except Exception:
            fresh = {}
        failed, today = [], dt.date.today().isoformat()
        for symbol in symbols:
            quote = self.meta.get(symbol, {}).get("quote_currency")
            if quote is None:
                try:
                    quote = currency(symbol)
                except Exception:
                    quote = None
            if symbol not in fresh or not quote:
                failed.append(symbol)
                continue
            main, divisor = SUBUNITS.get(quote, (quote.upper(), 1.0))
            self.dir.mkdir(parents=True, exist_ok=True)
            (fresh[symbol] / divisor).rename("close").to_csv(self._path(symbol), index_label="date")
            self.meta[symbol] = {"currency": main, "quote_currency": quote, "fetched": today}
        self.meta_path.parent.mkdir(parents=True, exist_ok=True)
        self.meta_path.write_text(json.dumps(self.meta, indent=1, sort_keys=True), "utf-8")
        return failed

    def stale(self, symbols, today: dt.date) -> dict[str, str | None]:
        """Symbols whose last cached close is older than STALE_AFTER_DAYS (None if there is none)."""
        out = {}
        for symbol in symbols:
            s = self.series(symbol)
            last = s.index[-1].date() if len(s) else None
            if last is None or (today - last).days > STALE_AFTER_DAYS:
                out[symbol] = last.isoformat() if last else None
        return out


class Fx:
    """ECB reference rates, stored as units of each currency per 1 EUR."""

    def __init__(self, cache: Path):
        self.path = cache / "fx.csv"
        self.table = pd.read_csv(self.path, index_col=0, parse_dates=True) if self.path.exists() else pd.DataFrame()

    def refresh(self, currencies, rates=None) -> bool:
        wanted = sorted({c for c in currencies if c and c != "EUR"})
        if not wanted:
            return True
        try:
            table = (rates or ecb_rates)(wanted)
        except Exception:
            return False
        self.table = table
        self.path.parent.mkdir(parents=True, exist_ok=True)
        table.to_csv(self.path, index_label="date")
        return True

    def has(self, currency: str) -> bool:
        return currency == "EUR" or currency in self.table.columns

    def _per_eur(self, currency: str, index: pd.DatetimeIndex) -> pd.Series:
        if currency == "EUR":
            return pd.Series(1.0, index=index)
        rates = self.table[currency].dropna()
        return rates.reindex(rates.index.union(index)).ffill().bfill().reindex(index)

    def convert(self, series: pd.Series, currency: str, home: str) -> pd.Series:
        """A price series in `currency`, re-expressed in `home` at each day's rate."""
        if currency == home or series.empty:
            return series
        index = pd.DatetimeIndex(series.index)
        return series / self._per_eur(currency, index).to_numpy() * self._per_eur(home, index).to_numpy()

    def latest(self, amount: float, currency: str, home: str) -> float:
        if currency == home:
            return amount
        last = lambda c: 1.0 if c == "EUR" else float(self.table[c].dropna().iloc[-1])
        return amount / last(currency) * last(home)
