import datetime as dt
import json
import textwrap

import pytest
from conftest import TODAY, ishares_csv

from whatstocks.funds import Funds, Position, fund_keys, listing_country, look_through, parse_ishares

WORLD = ishares_csv([
    ("NVDA", "NVIDIA CORP", "Equity", 60, "United States", "NASDAQ"),
    ("NDIA", "ISHARES MSCI INDIA UCITS ETF", "Equity", 20, "Ireland", "London Stock Exchange"),
    ("CNYA", "ISH MSCI CHINA A ETF USD ACC", "Equity", 10, "Ireland", "London Stock Exchange"),
    ("USD", "USD CASH", "Cash", 10, "United States", "-"),
])
INDIA = ishares_csv([
    ("INFY", "INFOSYS", "Equity", 50, "India", "National Stock Exchange Of India"),
    ("RELIANCE", "RELIANCE INDUSTRIES LTD", "Equity", 50, "India", "National Stock Exchange Of India"),
])
FILES = {"https://example.com/world.csv": WORLD, "https://example.com/india.csv": INDIA}


@pytest.fixture
def registry(tmp_path):
    path = tmp_path / "funds.yaml"
    path.write_text(textwrap.dedent("""
        funds:
          WORLD:
            holdings_url: https://example.com/world.csv
          INDIA:
            holdings_url: https://example.com/india.csv
            lines: [[NDIA, London Stock Exchange]]
          WORLD.DE:
            lookthrough_with: WORLD
            label: same index
    """), "utf-8")
    return path


def test_parse_ishares():
    as_of, rows = parse_ishares(WORLD)
    assert as_of == dt.date(2026, 11, 2)
    assert [r.ticker for r in rows] == ["NVDA", "NDIA", "CNYA", "USD"]
    assert rows[0].weight == pytest.approx(0.6)
    assert parse_ishares(WORLD.replace("Nov 02, 2026", "02/Nov/2026"))[0] == dt.date(2026, 11, 2)
    assert len(parse_ishares(WORLD.replace("Ticker,Name,", '"Ticker","Name",'))[1]) == 4
    with pytest.raises(ValueError):
        parse_ishares("<html><body>Please enable JavaScript</body></html>")


def test_fund_keys_match_ticker_and_exchange():
    assert fund_keys("0700.HK") == [("700", "Hong Kong Exchanges And Clearing Ltd")]
    assert fund_keys("SAAB-B.ST") == [("SAABB", "Nasdaq Omx Nordic")]
    # BA.L is BAE Systems in London; BA is Boeing in New York. They must not meet.
    assert fund_keys("BA.L") == [("BA", "London Stock Exchange")]
    assert ("BA", "London Stock Exchange") not in fund_keys("BA")
    assert listing_country("INFY.NS") == "India" and listing_country("NVDA") == "United States"


def test_look_through_spreads_funds_and_recurses(tmp_path, registry):
    funds = Funds(tmp_path / "cache", registry=registry, fetch=FILES.__getitem__)
    positions = [Position("WORLD.DE", "World", 1000.0, "fund", "EUR"), Position("ACME", "Acme", 100.0, "stock", "USD")]
    pieces, notes = look_through(positions, funds, TODAY)
    by = {p.line: p for p in pieces}
    assert by[("NVDA", "NASDAQ")].value == pytest.approx(600)
    assert by[("INFY", "National Stock Exchange Of India")].value == pytest.approx(100)  # 1000 x 20% x 50%
    assert by[("INFY", "National Stock Exchange Of India")].via == "INDIA"
    assert by[("CNYA", "London Stock Exchange")].kind == "unresolved"
    assert by[("", "other")].value == pytest.approx(100)
    assert by["ACME"].country == "United States"
    assert sum(p.value for p in pieces) == pytest.approx(1100)
    assert "WORLD.DE: same index" in notes
    assert any("CHINA A" in n for n in notes)


def test_unknown_or_missing_funds_stay_unresolved(tmp_path, registry):
    funds = Funds(tmp_path / "cache", registry=registry, fetch=FILES.__getitem__)
    pieces, notes = look_through([Position("MYSTERY", "", 50.0, "fund", "EUR")], funds, TODAY)
    assert pieces[0].kind == "unresolved" and "MYSTERY" in notes[0]
    pieces, notes = look_through([Position("WORLD", "", 50.0, "fund", "EUR")], funds, TODAY, offline=True)
    assert pieces[0].kind == "unresolved" and "no holdings file yet" in notes[0]


def test_a_failed_refresh_keeps_the_cached_file(tmp_path, registry):
    cache = tmp_path / "cache"
    Funds(cache, registry=registry, fetch=FILES.__getitem__).holdings("WORLD", TODAY)
    meta = cache / "funds.json"
    meta.write_text(json.dumps({"WORLD": {"fetched": "2026-08-01"}}), "utf-8")

    def html(url):
        return "<html>a page, not a holdings file</html>"

    as_of, rows, _, notes = Funds(cache, registry=registry, fetch=html).holdings("WORLD", TODAY)
    assert len(rows) == 4
    assert notes == ["WORLD: holdings not refreshed (ValueError); using the cached file"]
