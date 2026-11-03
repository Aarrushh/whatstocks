"""Shared test data. Every test runs offline: network calls are replaced with synthetic data."""
from __future__ import annotations

import csv
import datetime as dt
import io
import shutil
import zlib

import numpy as np
import pandas as pd
import pytest

from whatstocks import funds as funds_module
from whatstocks import market, morning
from whatstocks.paths import ROOT, UserDir

TODAY = dt.date(2026, 11, 3)
DAYS = pd.bdate_range("2023-01-02", TODAY)
DEMO_FUNDS = {"VWCE.DE"}

# A small fake MSCI ACWI file. Weights add up to 100.
ACWI_ROWS = [
    ("NVDA", "NVIDIA CORP", "Equity", 5.0, "United States", "NASDAQ"),
    ("AAPL", "APPLE INC", "Equity", 4.0, "United States", "NASDAQ"),
    ("BA", "BOEING", "Equity", 0.2, "United States", "New York Stock Exchange Inc."),
    ("ASML", "ASML HOLDING NV", "Equity", 1.0, "Netherlands", "Euronext Amsterdam"),
    ("2330", "TAIWAN SEMICONDUCTOR MANUFACTURING", "Equity", 1.0, "Taiwan", "Taiwan Stock Exchange"),
    ("SHEL", "SHELL PLC", "Equity", 0.5, "United Kingdom", "London Stock Exchange"),
    ("RHM", "RHEINMETALL AG", "Equity", 0.1, "Germany", "Xetra"),
    ("INFY", "INFOSYS", "Equity", 0.1, "India", "National Stock Exchange Of India"),
    ("XOM", "EXXON MOBIL CORP", "Equity", 0.6, "United States", "New York Stock Exchange Inc."),
    ("OTHER", "EVERYTHING ELSE", "Equity", 86.5, "United States", "NASDAQ"),
    ("USD", "USD CASH", "Cash", 1.0, "United States", "-"),
]

NEWS = [
    {"id": "aaaaaaaaaa", "title": "OPEC+ extends output cuts into 2027", "source": "Example Wire",
     "feed": "Search: Oil and gas", "url": "https://example.com/opec", "published": "2026-11-03T06:00+00:00"},
    {"id": "bbbbbbbbbb", "title": "Two hyperscalers trim 2027 capex guidance", "source": "Example Wire",
     "feed": "Search: AI build-out", "url": "https://example.com/capex", "published": "2026-11-03T05:00+00:00"},
    {"id": "cccccccccc", "title": "Gold hits a record as central banks buy", "source": "Example Wire",
     "feed": "Search: Gold", "url": "https://example.com/gold", "published": "2026-11-03T04:00+00:00"},
    {"id": "dddddddddd", "title": "<script>alert(1)</script> headline", "source": "Odd Feed",
     "feed": "Odd Feed", "url": "javascript:alert(1)", "published": None},
]


def ishares_csv(rows, as_of: str = "Nov 02, 2026") -> str:
    """rows: (ticker, name, asset class, weight %, location, exchange), in the iShares file layout."""
    out = io.StringIO()
    out.write(f'iShares Test ETF\nFund Holdings as of,"{as_of}"\nInception Date,"Mar 26, 2008"\n \n')
    # Like the real files: the header is bare, the rows are quoted.
    out.write("Ticker,Name,Sector,Asset Class,Market Value,Weight (%),Location,Exchange,Currency,Market Currency\n")
    writer = csv.writer(out, quoting=csv.QUOTE_ALL, lineterminator="\n")
    for ticker, name, asset_class, weight, location, exchange in rows:
        writer.writerow([ticker, name, "-", asset_class, "1", f"{weight:.2f}", location, exchange, "USD", "USD"])
    out.write(' \n"The content contained herein is owned or licensed by BlackRock."\n')
    return out.getvalue()


def currency_of(symbol: str) -> str:
    if symbol.endswith((".DE", ".AS")):
        return "EUR"
    if symbol.endswith(".L"):
        return "GBp"
    if symbol.endswith(".NS"):
        return "INR"
    return "USD"


def price_series(symbol: str) -> pd.Series:
    rng = np.random.default_rng(zlib.crc32(symbol.encode()))
    level = {"GBp": 2500.0, "INR": 1500.0}.get(currency_of(symbol), 100.0)
    return pd.Series(level * np.exp(np.cumsum(rng.normal(0.0003, 0.012, len(DAYS)))), index=DAYS)


def fake_rates(currencies) -> pd.DataFrame:
    base = {"USD": 1.08, "GBP": 0.85, "INR": 90.0}
    return pd.DataFrame({c: base[c] for c in currencies}, index=DAYS)


THEME_IDS = ("ai_buildout", "defence", "oil_gas", "power_grid", "gold", "india", "china", "critical_minerals",
             "nuclear_uranium", "shipping_routes")
THEME_NEWS = {
    "oil_gas": ("OPEC+ kept supply tight into 2027.", "Shell sits in this theme, and so does a slice of the world index.",
                ["aaaaaaaaaa"]),
    "ai_buildout": ("Two hyperscalers trimmed their 2027 capex guidance.",
                    "NVIDIA and ASML sit in this theme, and one of your views rests on it.", ["bbbbbbbbbb"]),
    "gold": ("Central banks kept buying and gold hit a record.", "You hold almost none of it.", ["cccccccccc"]),
}


def theme_notes() -> list[dict]:
    """A line for every theme: a brief must cover each theme the user holds 2% of, or an open view names."""
    return [
        {"id": tid, "state": THEME_NEWS[tid][0], "why_it_matters": THEME_NEWS[tid][1], "news_ids": THEME_NEWS[tid][2]}
        if tid in THEME_NEWS else
        {"id": tid, "state": "No news in today's feeds.", "why_it_matters": "Part of your portfolio sits in it.", "news_ids": []}
        for tid in THEME_IDS
    ]


def quiet_brief(day: dt.date = TODAY) -> dict:
    return {"date": day.isoformat(), "events": [], "quiet_day": True,
            "themes": [dict(t, state="No news in today's feeds.", news_ids=[]) for t in theme_notes()]}


def good_brief(day: dt.date = TODAY) -> dict:
    return {
        "date": day.isoformat(),
        "summary": "Oil supply tightened and AI capex guidance softened.",
        "quiet_day": False,
        "themes": theme_notes(),
        "holdings": [{"symbol": "SHEL.L", "note": "Shell sells crude and gas, so tighter supply lifts what it is paid.",
                      "news_ids": ["aaaaaaaaaa"]}],
        "ripples": [{"from": "oil_gas", "to": "ai_buildout", "effect": "hurt",
                     "why": "Dearer energy raises what data centres pay to run.", "news_ids": ["aaaaaaaaaa"]}],
        "watch": [{"what": "OPEC+ meets again on supply.", "when": "2026-12-01", "themes": ["oil_gas"],
                   "holdings": ["SHEL.L"], "news_ids": ["aaaaaaaaaa"]}],
        "events": [
            {
                "what": "OPEC+ extended its output cuts into 2027.",
                "news_ids": ["aaaaaaaaaa"],
                "money": "Producers get a higher price on lower volumes; fuel buyers pay more.",
                "touches": {"themes": ["oil_gas"], "holdings": ["SHEL.L"]},
                "views": [{"view_id": "brent-above-90-2027", "effect": "for",
                           "why": "Less supply raises the chance of a quarter above 90 dollars."}],
            },
            {
                "what": "Two hyperscalers trimmed their 2027 capex guidance.",
                "news_ids": ["bbbbbbbbbb"],
                "money": "Chip and equipment makers may sell less; the hyperscalers keep more cash.",
                "touches": {"themes": ["ai_buildout"], "holdings": ["NVDA", "ASML.AS"]},
                "views": [{"view_id": "ai-capex-cut-2027", "effect": "for",
                           "why": "Lower guidance is a step toward lower 2027 capex."}],
            },
        ],
    }


@pytest.fixture
def user(tmp_path) -> UserDir:
    """A copy of the demo user in a temporary folder."""
    target = tmp_path / "user"
    target.mkdir()
    for name in ("settings.yaml", "holdings.csv", "views.yaml", "decisions.yaml"):
        shutil.copy(ROOT / "demo" / name, target / name)
    return UserDir(target)


@pytest.fixture
def fake_world(monkeypatch):
    """Prices, FX, fund holdings and news, all synthetic."""
    monkeypatch.setattr(market, "yahoo_closes", lambda symbols: {s: price_series(s) for s in symbols})
    monkeypatch.setattr(market, "yahoo_currency", currency_of)
    monkeypatch.setattr(market, "ecb_rates", fake_rates)
    monkeypatch.setattr(funds_module, "download", lambda url: ishares_csv(ACWI_ROWS))
    monkeypatch.setattr(morning, "fetch_news", lambda themes, now: ([dict(n) for n in NEWS], []))
