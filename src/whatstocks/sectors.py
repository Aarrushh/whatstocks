"""Which sector each stock is in, and the fund that stands for that sector's average (computed in code only, P2).

The sector comes from Yahoo's company profile and is kept in the cache, so an offline run still has it. Each
sector is measured against an Xtrackers MSCI World sector fund listed in EUR on Xetra: a world average for the
sector, the same family for every sector. Real estate has no fund in that family, so it shows no average.
Funds and cash have no single sector and are left out."""
from __future__ import annotations

import json
from pathlib import Path

# Yahoo sector name -> (label, MSCI World sector fund)
SECTORS: dict[str, tuple[str, str | None]] = {
    "Technology": ("Information technology", "XDWT.DE"),
    "Communication Services": ("Communication services", "XWTS.DE"),
    "Consumer Cyclical": ("Consumer discretionary", "XDWC.DE"),
    "Consumer Defensive": ("Consumer staples", "XDWS.DE"),
    "Energy": ("Energy", "XDW0.DE"),
    "Financial Services": ("Financials", "XDWF.DE"),
    "Healthcare": ("Health care", "XDWH.DE"),
    "Industrials": ("Industrials", "XDWI.DE"),
    "Basic Materials": ("Materials", "XDWM.DE"),
    "Utilities": ("Utilities", "XDWU.DE"),
    "Real Estate": ("Real estate", None),
}


def yahoo_sector(symbol: str) -> str | None:
    import yfinance as yf

    return (yf.Ticker(symbol).info or {}).get("sector") or None


class Sectors:
    """Symbol -> Yahoo sector name, cached in cache/sectors.json. A symbol is looked up once."""

    def __init__(self, cache: Path):
        self.path = cache / "sectors.json"
        self.map: dict[str, str | None] = json.loads(self.path.read_text("utf-8")) if self.path.exists() else {}

    def refresh(self, symbols, lookup=None) -> list[str]:
        """Look up symbols not in the cache yet. Returns the ones Yahoo had no sector for."""
        lookup = lookup or yahoo_sector
        for symbol in symbols:
            if self.map.get(symbol):
                continue
            try:
                self.map[symbol] = lookup(symbol)
            except Exception:
                self.map[symbol] = None
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.map, indent=1, sort_keys=True), "utf-8")
        return sorted(s for s in symbols if not self.map.get(s))

    def of(self, symbols) -> dict[str, str]:
        """The known sectors of these symbols."""
        return {s: self.map[s] for s in symbols if self.map.get(s)}


def proxies() -> set[str]:
    return {fund for _, fund in SECTORS.values() if fund}
