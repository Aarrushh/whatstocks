"""Fetching for "Will the bet pay off?" (spec section 15), each source with its cache in my/cache/bet/:

    FRED    adoption (all adults, and at work) and the high-yield and investment-grade spreads, at most once a day
    EDGAR   cash capex, operating cash flow, depreciation, backlog and Nvidia's revenue, from the filings, at most once
            a week, and only once settings.yaml has a sec_contact (the SEC asks every client for a name and email)
    Yahoo   shares outstanding for the public stack, at most once a week (prices come through market.Prices)

A fetched figure has the grade 'fetched' and lives in the cache, never in the ledger files. It replaces a shipped figure
with the same series, entity and period; a figure of yours in my/bet.yaml stays. 'whatstocks check' reports a gap above
1% between a fetched figure and the one it meets. A source that cannot be reached leaves its cache as it was."""
from __future__ import annotations

import datetime as dt
import io
import json
import time
import warnings
from collections import defaultdict

import pandas as pd
import requests

from ..files import ThemeMap
from ..paths import UserDir
from .ledger import Ledger, Point

FETCHED = "fetched"  # the grade of a figure the code fetched itself
FRED_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv"
FRED_PAGE = "https://fred.stlouisfed.org/series/{id}"
FRED = {  # FRED id: the ledger series and entity it fills
    "RPSGENAIUSAGESHAREALL": ("genai_adoption", "all"),
    "RPSGENAIUSAGESHAREWORK": ("genai_adoption", "work"),
    "BAMLH0A0HYM2": ("hy_spread", "us"),
    "BAMLC0A0CM": ("ig_spread", "us"),
}
EDGAR_URL = "https://data.sec.gov/api/xbrl/companyconcept/CIK{cik:010d}/{concept}.json"
EDGAR_FILING = "https://www.sec.gov/Archives/edgar/data/{cik}/{folder}/{accn}-index.htm"
EDGAR_FORMS = ("10-Q", "10-K", "10-Q/A", "10-K/A")
EDGAR_PAUSE = 0.15  # seconds between requests; the SEC allows ten a second
EDGAR_FROM = "2018Q1"  # older quarters are left in the filings
BUILDERS = ("msft", "googl", "amzn", "meta", "orcl", "crwv")
EDGAR = {  # ledger series: the XBRL concepts that report it, best first, and the companies it is read for
    "capex_cash": (("us-gaap/PaymentsToAcquirePropertyPlantAndEquipment", "us-gaap/PaymentsToAcquireProductiveAssets"),
                   BUILDERS),
    "ocf": (("us-gaap/NetCashProvidedByUsedInOperatingActivities",), BUILDERS),
    "depreciation": (("us-gaap/Depreciation",), BUILDERS),  # never with amortization: the ledger's figure leaves it out
    "backlog": (("us-gaap/RevenueRemainingPerformanceObligation",), BUILDERS),
    "nvda_revenue": (("us-gaap/Revenues", "us-gaap/RevenueFromContractWithCustomerExcludingAssessedTax"), ("nvda",)),
}
YAHOO_PAGE = "https://finance.yahoo.com/quote/{symbol}/key-statistics"
EVERY = {"fred": 1, "edgar": 7, "yahoo": 7}  # days between fetches of one item
CURRENT = 200  # days: a concept with nothing newer is one the company has stopped using
DIFFERENCE = 0.01  # a fetched figure further than this from the one it meets is reported


# ---------------------------------------------------------------- the network (tests replace these)


def fred_csv(series_id: str) -> str:
    # No User-Agent of our own: FRED stalls a request that names itself, even as a browser (seen 2026-11-07), and
    # answers requests' default at once.
    response = requests.get(FRED_URL, params={"id": series_id}, timeout=30)
    response.raise_for_status()
    return response.text


def edgar_json(cik: int, concept: str, contact: str) -> dict | None:
    """One company-concept document, or None if the company does not report the concept."""
    response = requests.get(EDGAR_URL.format(cik=cik, concept=concept), timeout=60,
                            headers={"User-Agent": f"whatstocks {contact}", "Accept-Encoding": "gzip, deflate"})
    if response.status_code == 404:
        return None
    response.raise_for_status()
    return response.json()


def yahoo_shares(symbol: str) -> float | None:
    import yfinance as yf

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")  # yfinance's own pandas deprecation warnings
        shares = yf.Ticker(symbol).fast_info.get("shares")
    return float(shares) if shares else None


# ---------------------------------------------------------------- reading what came back


def _day(text) -> dt.date:
    return dt.date.fromisoformat(str(text)[:10])


def quarter_of(day: dt.date) -> str:
    return f"{day.year}Q{(day.month - 1) // 3 + 1}"


def period_of(kind: str, day: dt.date) -> str:
    """A date as a period of the given kind: the quarter, month or year it falls in, or the date itself."""
    if kind == "quarter":
        return quarter_of(day)
    if kind == "month":
        return f"{day.year}-{day.month:02d}"
    if kind == "year":
        return str(day.year)
    return day.isoformat()


def parse_fred(text: str, series_id: str) -> list[tuple[dt.date, float]]:
    """FRED's CSV: a date column, then the series. A day with no value has '.' or nothing."""
    frame = pd.read_csv(io.StringIO(text))
    if len(frame.columns) != 2 or frame.columns[1] != series_id:
        raise ValueError(f"not FRED's CSV for {series_id}")
    values = pd.to_numeric(frame[series_id], errors="coerce")
    return [(_day(day), float(v)) for day, v in zip(frame.iloc[:, 0], values) if pd.notna(v)]


def edgar_quarters(doc: dict) -> list[dict]:
    """Calendar-quarter figures from one company-concept document, oldest first, in $ billions.

    A flow (capex, cash flow, revenue) is filed as a year-to-date sum in each 10-Q, so a quarter is the step between two
    sums that start on the same day; a three-month figure, where one is filed, is used as it is. A stock (backlog) is
    read at the quarter's end. A fiscal quarter counts in the calendar quarter it ends in (Microsoft's fiscal 2027 Q1
    is 2026Q3), and where filings restate a figure, the latest filing wins."""
    facts: dict[tuple, dict] = {}
    for f in (doc.get("units") or {}).get("USD") or []:
        if f.get("form") not in EDGAR_FORMS or not {"end", "val", "filed", "accn"} <= set(f):
            continue
        key = (f.get("start"), f["end"])
        if key not in facts or f["filed"] > facts[key]["filed"]:
            facts[key] = f
    found: dict[str, tuple[float, dict]] = {}
    if facts and all(start is None for start, _ in facts):  # a stock: the latest reading in each quarter
        for (_, end), f in sorted(facts.items(), key=lambda kv: kv[0][1]):
            found[quarter_of(_day(end))] = (f["val"], f)
    else:
        sums = defaultdict(list)
        for (start, end), f in facts.items():
            if start is None:
                continue
            days = (_day(end) - _day(start)).days
            if 80 <= days <= 100:
                found.setdefault(quarter_of(_day(end)), (f["val"], f))
            if 80 <= days <= 380:
                sums[start].append(f)
        for rows in sums.values():  # year-to-date sums, each a quarter after the one before
            rows.sort(key=lambda f: f["end"])
            for before, after in zip(rows, rows[1:]):
                if 80 <= (_day(after["end"]) - _day(before["end"])).days <= 100:
                    found.setdefault(quarter_of(_day(after["end"])), (after["val"] - before["val"], after))
    return [{"period": q, "value": round(v / 1e9, 6), "end": f["end"], "filed": f["filed"], "accn": f["accn"],
             "form": f["form"]} for q, (v, f) in sorted(found.items())]


# ---------------------------------------------------------------- what the page prices


def members(theme_id: str, themes: ThemeMap) -> list[str]:
    """A theme's members, or one tier of them (ai_buildout:core)."""
    tid, _, tier = theme_id.partition(":")
    theme = themes.themes[tid]
    return list(getattr(theme, tier)) if tier else [*theme.core, *theme.partial]


def stack(led: Ledger) -> dict[str, str]:
    """The public stack the valuation prices: entity id -> its Yahoo symbol. The labs are valued privately."""
    out = {}
    for g in led.model["valuation"]["groups"].values():
        if g.get("series"):
            continue
        for m in g.get("members") or []:
            if led.entities.get(m, {}).get("symbol"):
                out[m] = led.entities[m]["symbol"]
    return out


def symbols(led: Ledger, themes: ThemeMap) -> set[str]:
    """Every Yahoo symbol the page prices: the public stack, the world index, and the members of each basket."""
    out = set(stack(led).values()) | {led.model["valuation"]["world"]}
    for ind in led.signals["indicators"].values():
        if ind.get("rule") == "below_high":
            out |= set(members(ind["basket"], themes))
    return out


# ---------------------------------------------------------------- the cache


class Cache:
    """my/cache/bet/: each source's last figures, and the day each item was last fetched."""

    def __init__(self, user: UserDir):
        self.dir = user.cache / "bet"
        self.status_path = self.dir / "fetched.json"
        self.status = json.loads(self.status_path.read_text("utf-8")) if self.status_path.exists() else {}

    def last(self, source: str, item: str) -> dt.date | None:
        day = self.status.get(source, {}).get(item)
        return _day(day) if day else None

    def due(self, source: str, item: str, today: dt.date) -> bool:
        last = self.last(source, item)
        return last is None or (today - last).days >= EVERY[source]

    def save(self, source: str, item: str, name: str, text: str, today: dt.date) -> None:
        path = self.dir / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, "utf-8")
        self.status.setdefault(source, {})[item] = today.isoformat()

    def read(self, name: str) -> str | None:
        path = self.dir / name
        return path.read_text("utf-8") if path.exists() else None

    def close(self) -> None:
        self.dir.mkdir(parents=True, exist_ok=True)
        self.status_path.write_text(json.dumps(self.status, indent=1, sort_keys=True), "utf-8")


def edgar_company(cik: int, eid: str, contact: str, today: dt.date) -> dict:
    """The series EDGAR fills for one company: for each, the concept it reads and its quarters."""
    out = {}
    for sid, (concepts, entities) in EDGAR.items():
        if eid not in entities:
            continue
        best = None
        for concept in concepts:
            doc = edgar_json(cik, concept, contact)
            time.sleep(EDGAR_PAUSE)
            rows = edgar_quarters(doc) if doc else []
            if rows and (best is None or rows[-1]["end"] > best["points"][-1]["end"]):
                best = {"concept": concept, "points": rows}
            if rows and (today - _day(rows[-1]["end"])).days <= CURRENT:
                break  # the company reports it under this concept now
        if best:
            out[sid] = best
    return out


def refresh(user: UserDir, led: Ledger, contact: str = "", today: dt.date | None = None) -> list[str]:
    """Fetch every item that is due, keeping the cache where a fetch fails. Returns notes for prepare to show.
    Once FRED or EDGAR fails, the rest of that source waits for the next run rather than for more timeouts."""
    today = today or dt.date.today()
    cache, notes = Cache(user), []
    failed = []
    for sid in FRED:
        if not cache.due("fred", sid, today):
            continue
        if failed:
            failed.append(sid)
            continue
        try:
            text = fred_csv(sid)
            parse_fred(text, sid)  # refuse anything that is not the CSV
            cache.save("fred", sid, f"fred/{sid}.csv", text, today)
        except Exception:
            failed.append(sid)
    if failed:
        notes.append(f"FRED not reached for {', '.join(failed)}: using cached figures where there are any.")
    failed = []
    for symbol in sorted(set(stack(led).values())):
        if cache.due("yahoo", symbol, today):
            try:
                shares = yahoo_shares(symbol)
                if not shares or shares <= 0:
                    raise ValueError(f"no share count for {symbol}")
                cache.save("yahoo", symbol, f"yahoo/s_{symbol}.json", json.dumps({"shares": shares}), today)
            except Exception:
                failed.append(symbol)
    if failed:
        notes.append(f"Shares outstanding not refreshed for {', '.join(failed)}: using cached counts, or the ledger's "
                     f"market values.")
    if contact:
        failed = []
        for eid in sorted({e for _, entities in EDGAR.values() for e in entities}):
            cik = led.entities.get(eid, {}).get("cik")
            if not cik or not cache.due("edgar", eid, today):
                continue
            if failed:
                failed.append(led.entities[eid].get("label", eid))
                continue
            try:
                found = edgar_company(int(cik), eid, contact, today)
                cache.save("edgar", eid, f"edgar/{eid}.json", json.dumps({"cik": int(cik), "series": found}, indent=1),
                           today)
            except Exception:
                failed.append(led.entities[eid].get("label", eid))
        if failed:
            notes.append(f"SEC EDGAR not reached for {', '.join(sorted(failed))}: using cached or ledger figures.")
    cache.close()
    return notes


# ---------------------------------------------------------------- into the ledger


def points(user: UserDir, led: Ledger) -> list[Point]:
    """Every fetched figure in the cache, as ledger points with the grade 'fetched'."""
    cache, out = Cache(user), []
    for fid, (sid, entity) in FRED.items():
        text, seen, s = cache.read(f"fred/{fid}.csv"), cache.last("fred", fid), led.series.get(sid)
        if text is None or seen is None or s is None:
            continue
        try:
            rows = parse_fred(text, fid)
        except ValueError:
            continue
        by_period = {period_of(s.period, day): value for day, value in rows}  # the last in a period wins
        out += [Point(sid, entity, period, value, None, None, FETCHED, FRED_PAGE.format(id=fid), seen,
                      note=f"FRED {fid}") for period, value in by_period.items()]
    if "shares_outstanding" in led.series:
        for eid, symbol in stack(led).items():
            text, seen = cache.read(f"yahoo/s_{symbol}.json"), cache.last("yahoo", symbol)
            if text and seen:
                out.append(Point("shares_outstanding", eid, seen.isoformat(), json.loads(text)["shares"] / 1e9, None,
                                 None, FETCHED, YAHOO_PAGE.format(symbol=symbol), seen, note=f"Yahoo, {symbol}"))
    for eid in sorted({e for _, entities in EDGAR.values() for e in entities}):
        text, seen = cache.read(f"edgar/{eid}.json"), cache.last("edgar", eid)
        if not text or not seen:
            continue
        doc = json.loads(text)
        for sid, found in doc["series"].items():
            if sid not in led.series:
                continue
            for row in found["points"]:
                if row["period"] < EDGAR_FROM:
                    continue
                link = EDGAR_FILING.format(cik=doc["cik"], folder=row["accn"].replace("-", ""), accn=row["accn"])
                out.append(Point(sid, eid, row["period"], row["value"], None, None, FETCHED, link, seen,
                                 published=_day(row["filed"]), note=f"{found['concept']}, {row['form']}"))
    return out


def merge(led: Ledger, fetched: list[Point]) -> list[str]:
    """Put fetched figures into the ledger, in place. Each replaces a shipped figure with the same key; a figure of
    yours stays. Returns the gaps above 1% between a fetched figure and the one it meets, for the check to report."""
    gaps, by_series = [], defaultdict(list)
    for p in fetched:
        if p.series in led.series:
            by_series[p.series].append(p)
    for sid, ps in by_series.items():
        s = led.series[sid]
        old = {p.key: p for points in s.points.values() for p in points}
        keep = []
        for p in ps:
            other = old.get(p.key)
            if other is not None and other.value and p.value is not None and abs(p.value / other.value - 1) > DIFFERENCE:
                gaps.append(f"{sid} {p.entity} {p.period}: fetched {p.value:,.4g}, "
                            f"{'yours' if other.mine else 'ledger'} {other.value:,.4g} ({p.value / other.value - 1:+.1%})")
            if other is None or not other.mine:
                keep.append(p)
        s.put(keep)
    return gaps
