"""Fund look-through: spread each fund's value over the companies it holds (SPEC 7.1)."""
from __future__ import annotations

import csv
import datetime as dt
import io
import json
import re
from dataclasses import dataclass, field
from pathlib import Path

import requests
import yaml

from .paths import FUNDS_FILE

REFRESH_DAYS = 30
STALE_DAYS = 90
MAX_DEPTH = 3
UA = {"User-Agent": "Mozilla/5.0 (compatible; whatstocks; +https://github.com/Aarrushh/whatstocks)"}

# Yahoo suffix -> (listing country, exchange names), both spelled as iShares files spell them.
# One exchange can have several names, even within one issuer (docs/DATA_SOURCES.md).
EXCHANGES = {
    "": ("United States", ["NASDAQ", "NYSE", "New York Stock Exchange Inc.", "Nyse Mkt Llc", "Cboe BZX", "Cboe BZX formerly known as BATS"]),
    "L": ("United Kingdom", ["London Stock Exchange"]),
    "DE": ("Germany", ["Xetra", "Deutsche Boerse Xetra"]),
    "PA": ("France", ["Nyse Euronext - Euronext Paris"]),
    "AS": ("Netherlands", ["Euronext Amsterdam"]),
    "BR": ("Belgium", ["Nyse Euronext - Euronext Brussels"]),
    "MI": ("Italy", ["Borsa Italiana"]),
    "MC": ("Spain", ["Bolsa De Madrid"]),
    "LS": ("Portugal", ["Nyse Euronext - Euronext Lisbon"]),
    "IR": ("Ireland", ["Irish Stock Exchange - All Market"]),
    "VI": ("Austria", ["Wiener Boerse Ag"]),
    "ST": ("Sweden", ["Nasdaq Omx Nordic"]),
    "CO": ("Denmark", ["Omx Nordic Exchange Copenhagen A/S"]),
    "HE": ("Finland", ["Nasdaq Omx Helsinki Ltd."]),
    "OL": ("Norway", ["Oslo Bors Asa"]),
    "SW": ("Switzerland", ["SIX Swiss Exchange"]),
    "HK": ("Hong Kong", ["Hong Kong Exchanges And Clearing Ltd"]),
    "T": ("Japan", ["Tokyo Stock Exchange"]),
    "SS": ("China", ["Shanghai Stock Exchange"]),
    "SZ": ("China", ["Shenzhen Stock Exchange"]),
    "KS": ("Korea (South)", ["Korea Exchange (Stock Market)"]),
    "KQ": ("Korea (South)", ["Korea Exchange (Kosdaq)"]),
    "TW": ("Taiwan", ["Taiwan Stock Exchange"]),
    "TWO": ("Taiwan", ["Gretai Securities Market"]),
    "SI": ("Singapore", ["Singapore Exchange"]),
    "AX": ("Australia", ["Asx - All Markets"]),
    "NZ": ("New Zealand", ["New Zealand Exchange Ltd"]),
    "TO": ("Canada", ["Toronto Stock Exchange"]),
    "NS": ("India", ["National Stock Exchange Of India"]),
    "BO": ("India", ["Bse Ltd"]),
    "JO": ("South Africa", ["Johannesburg Stock Exchange"]),
    "SN": ("Chile", ["Santiago Stock Exchange"]),
}
HK_NAMES = set(EXCHANGES["HK"][1])
FUND_NAME = re.compile(r"\b(ETF|UCITS)\b", re.I)


def _ticker(ticker: str, hong_kong: bool) -> str:
    t = re.sub(r"[.\s\-/]", "", ticker.upper())
    return t.lstrip("0") if hong_kong else t


def fund_keys(symbol: str) -> list[tuple[str, str]]:
    """Every (ticker, exchange) a Yahoo symbol can appear as inside a holdings file."""
    base, _, suffix = symbol.partition(".")
    ticker = _ticker(base, suffix == "HK")
    return [(ticker, name) for name in EXCHANGES.get(suffix, ("", []))[1]]


def listing_country(symbol: str) -> str:
    return EXCHANGES.get(symbol.partition(".")[2], ("Other", []))[0]


@dataclass
class Constituent:
    ticker: str
    name: str
    asset_class: str
    weight: float  # fraction of the fund
    location: str
    exchange: str
    currency: str

    @property
    def key(self) -> tuple[str, str]:
        return _ticker(self.ticker, self.exchange in HK_NAMES), self.exchange


def _parse_date(text: str) -> dt.date | None:
    for fmt in ("%b %d, %Y", "%d/%b/%Y", "%d-%b-%Y", "%Y-%m-%d"):
        try:
            return dt.datetime.strptime(text.strip(), fmt).date()
        except ValueError:
            pass
    return None


def parse_ishares(text: str) -> tuple[dt.date | None, list[Constituent]]:
    """An iShares holdings CSV: a few preamble lines, then a table from the 'Ticker,' header."""
    text = text.lstrip("﻿").replace("\r", "")
    header = re.search(r'^"?Ticker"?,', text, re.M)
    if header is None:
        raise ValueError("no 'Ticker,' header: the issuer may have changed the file format")
    start = header.start()
    found = re.search(r'Fund Holdings as of,"([^"]+)"', text[:start])
    as_of = _parse_date(found.group(1)) if found else None
    rows = []
    for r in csv.DictReader(io.StringIO(text[start:])):
        weight = (r.get("Weight (%)") or "").replace(",", "").strip()
        try:
            weight = float(weight) / 100
        except ValueError:
            continue  # disclaimer lines at the end of the file
        rows.append(Constituent(
            (r.get("Ticker") or "").strip(),
            (r.get("Name") or "").strip(),
            (r.get("Asset Class") or "").strip(),
            weight,
            (r.get("Location") or "").strip(),
            (r.get("Exchange") or "").strip(),
            (r.get("Market Currency") or r.get("Currency") or "").strip(),
        ))
    return as_of, rows


def download(url: str) -> str:
    response = requests.get(url, headers=UA, timeout=60)
    response.raise_for_status()
    return response.content.decode("utf-8-sig", errors="replace")


@dataclass
class Fund:
    symbol: str
    name: str = ""
    holdings_url: str = ""
    lookthrough_with: str = ""
    label: str = ""
    lines: list = field(default_factory=list)  # [[ticker, exchange]] as the fund appears inside other funds


class Funds:
    """The shipped fund registry (sources/funds.yaml) plus a cache of downloaded holdings files."""

    def __init__(self, cache: Path, registry: Path = FUNDS_FILE, fetch=None):
        raw = yaml.safe_load(registry.read_text("utf-8")) or {}
        self.funds = {str(s): Fund(str(s), **(spec or {})) for s, spec in (raw.get("funds") or {}).items()}
        self.dir = cache / "funds"
        self.meta_path = cache / "funds.json"
        self.meta = json.loads(self.meta_path.read_text("utf-8")) if self.meta_path.exists() else {}
        self.fetch = fetch or download

    def symbols(self) -> set[str]:
        return set(self.funds)

    def inner(self, c: Constituent) -> str | None:
        """The registry fund a constituent row stands for, if the row is itself a fund."""
        for fund in self.funds.values():
            for ticker, exchange in fund.lines:
                if exchange == c.exchange and _ticker(ticker, exchange in HK_NAMES) == c.key[0]:
                    return fund.symbol
        return None

    def holdings(self, symbol: str, today: dt.date, offline: bool = False):
        """(as_of, constituents, label, notes) for a fund, refreshing the cached file when due."""
        fund = self.funds.get(symbol)
        if fund is None:
            raise LookupError(f"{symbol}: no holdings source in sources/funds.yaml, so it is not looked through")
        label, notes = fund.label, []
        if fund.lookthrough_with:
            if fund.lookthrough_with not in self.funds:
                raise LookupError(f"{symbol}: lookthrough_with points to unknown fund {fund.lookthrough_with}")
            fund = self.funds[fund.lookthrough_with]
        path = self.dir / f"{fund.symbol}.csv"
        fetched = self.meta.get(fund.symbol, {}).get("fetched")
        due = not path.exists() or not fetched or (today - dt.date.fromisoformat(fetched)).days >= REFRESH_DAYS
        if due and not offline and fund.holdings_url:
            try:
                text = self.fetch(fund.holdings_url)
                parse_ishares(text)  # refuse to cache a page that is not a holdings file
                self.dir.mkdir(parents=True, exist_ok=True)
                path.write_text(text, "utf-8")
                self.meta[fund.symbol] = {"fetched": today.isoformat()}
                self.meta_path.write_text(json.dumps(self.meta, indent=1, sort_keys=True), "utf-8")
            except Exception as e:
                notes.append(f"{fund.symbol}: holdings not refreshed ({type(e).__name__}); using the cached file")
        if not path.exists():
            raise LookupError(f"{symbol}: no holdings file yet, so it is not looked through")
        as_of, rows = parse_ishares(path.read_text("utf-8"))
        return as_of, rows, label, notes


@dataclass
class Position:
    """One holding, valued in the home currency."""

    symbol: str
    name: str
    value: float
    kind: str
    currency: str
    country: str = ""


@dataclass
class Piece:
    """One slice of the portfolio after look-through."""

    line: str | tuple[str, str]  # Yahoo symbol if held directly, (ticker, exchange) inside a fund
    name: str
    value: float
    country: str
    currency: str
    via: str = ""  # the fund it came through
    kind: str = "stock"  # stock | cash | other | unresolved
    origin: str = ""  # the holding it belongs to


def look_through(positions: list[Position], funds: Funds, today: dt.date, offline: bool = False):
    """(pieces, notes): direct holdings as they are, funds broken into what they hold."""
    pieces, notes = [], []
    for p in positions:
        if p.kind == "cash":
            found = [Piece(p.symbol, p.name or "Cash", p.value, "Cash", p.currency, kind="cash")]
        elif p.kind == "fund":
            found = _expand(p.symbol, p.value, funds, today, offline, notes, depth=1)
        else:
            found = [Piece(p.symbol, p.name or p.symbol, p.value, p.country or listing_country(p.symbol), p.currency)]
        for piece in found:
            piece.origin = p.symbol
        pieces += found
    return pieces, notes


def _expand(symbol, value, funds, today, offline, notes, depth) -> list[Piece]:
    try:
        as_of, rows, label, fetch_notes = funds.holdings(symbol, today, offline)
    except LookupError as e:
        notes.append(str(e))
        return [Piece(symbol, symbol, value, "Not looked through", "", kind="unresolved")]
    notes += fetch_notes
    if label:
        notes.append(f"{symbol}: {label}")
    if as_of and (today - as_of).days > STALE_DAYS:
        notes.append(f"{symbol}: holdings file dated {as_of}, more than {STALE_DAYS} days old")
    pieces, other, hidden = [], 0.0, []
    for c in rows:
        v = value * c.weight
        if c.asset_class != "Equity":
            other += v
            continue
        inner = funds.inner(c)
        if inner and depth < MAX_DEPTH:
            pieces += _expand(inner, v, funds, today, offline, notes, depth + 1)
        elif FUND_NAME.search(c.name):
            pieces.append(Piece(c.key, c.name, v, c.location, c.currency, via=symbol, kind="unresolved"))
            hidden.append(f"{c.name} ({c.weight:.1%})")
        else:
            pieces.append(Piece(c.key, c.name, v, c.location, c.currency, via=symbol))
    if other:
        pieces.append(Piece(("", "other"), "Cash and other", other, "Cash and other", "", via=symbol, kind="other"))
    if hidden:
        notes.append(f"{symbol}: held through other funds that are not looked through: {', '.join(hidden)}")
    return pieces
