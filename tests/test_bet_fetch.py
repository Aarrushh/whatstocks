"""Fetching for "Will the bet pay off?" (spec section 15): FRED, Yahoo share counts and SEC EDGAR, each cached in
my/cache/bet/ and fetched only when due. A fetched figure takes the place of the ledger's; yours stay."""
import datetime as dt
import json

import pytest
from conftest import TODAY, fred_csv

from whatstocks import cli, morning
from whatstocks.bet import fetch, ledger
from whatstocks.files import Problems

DAY = dt.date(2026, 11, 7)  # the shipped figures were read on this day
CONTACT = "Jane Doe jane@example.com"
CAPEX = "us-gaap/PaymentsToAcquirePropertyPlantAndEquipment"
AMAZON = 1018724


def fact(end: str, val: float, start: str | None = None, filed: str = "2026-10-30", form: str = "10-Q",
         accn: str = "0001018724-26-000040") -> dict:
    f = {"end": end, "val": val, "filed": filed, "form": form, "accn": accn}
    return dict(f, start=start) if start else f


def doc(*facts: dict) -> dict:
    """A company-concept document, as data.sec.gov serves it."""
    return {"units": {"USD": list(facts)}}


AMAZON_CAPEX = {(AMAZON, CAPEX): doc(
    fact("2026-03-31", 50e9, "2026-01-01", filed="2026-04-30", accn="0001018724-26-000014"),
    fact("2026-06-30", 54.208e9, "2026-04-01", filed="2026-07-31", accn="0001018724-26-000026"),
    fact("2026-09-30", 77.259e9, "2026-07-01", filed="2026-10-30", accn="0001018724-26-000040"),
)}


class Network:
    """Stands in for FRED, Yahoo and EDGAR: answers from canned data and records every call."""

    def __init__(self, monkeypatch, edgar: dict | None = None):
        self.calls, self.down, self.edgar = [], set(), edgar or {}
        monkeypatch.setattr(fetch, "fred_csv", self.fred)
        monkeypatch.setattr(fetch, "yahoo_shares", self.shares)
        monkeypatch.setattr(fetch, "edgar_json", self.filings)
        monkeypatch.setattr(fetch, "EDGAR_PAUSE", 0)

    def _call(self, source: str, *args) -> None:
        self.calls.append((source, *args))
        if source in self.down:
            raise ConnectionError(f"{source} is down")

    def fred(self, series_id):
        self._call("fred", series_id)
        return fred_csv(series_id)

    def shares(self, symbol):
        self._call("yahoo", symbol)
        return 2.5e9

    def filings(self, cik, concept, contact):
        self._call("edgar", cik, concept, contact)
        return self.edgar.get((cik, concept))

    def count(self, source: str) -> int:
        return sum(1 for c in self.calls if c[0] == source)


def shipped(user) -> ledger.Ledger:
    return ledger.load(user, today=DAY)


# ---------------------------------------------------------------- reading what comes back


def test_fred_csv():
    text = "observation_date,BAMLH0A0HYM2\n2026-11-04,3.51\n2026-11-05,.\n2026-11-06,3.48\n"
    assert fetch.parse_fred(text, "BAMLH0A0HYM2") == [(dt.date(2026, 11, 4), 3.51), (dt.date(2026, 11, 6), 3.48)]
    for wrong in ("<html><body>Service unavailable</body></html>", "observation_date,BAMLC0A0CM\n2026-11-04,0.93\n"):
        with pytest.raises(ValueError):
            fetch.parse_fred(wrong, "BAMLH0A0HYM2")


def test_quarters_from_year_to_date_sums():
    """Microsoft's fiscal year starts in July: each 10-Q files the sum since then, and the 10-K the whole year."""
    rows = fetch.edgar_quarters(doc(
        fact("2025-09-30", 10e9, "2025-07-01", filed="2025-10-29"),
        fact("2025-12-31", 25e9, "2025-07-01", filed="2026-01-28"),
        fact("2026-03-31", 45e9, "2025-07-01", filed="2026-04-29"),
        fact("2026-06-30", 70e9, "2025-07-01", filed="2026-07-30", form="10-K"),
        fact("2026-09-30", 12e9, "2026-07-01", filed="2026-10-29"),
        fact("2026-09-30", 99e9, "2026-07-01", filed="2026-10-30", form="8-K"),  # not a filing that counts
    ))
    assert [(r["period"], r["value"]) for r in rows] == [
        ("2025Q3", 10), ("2025Q4", 15), ("2026Q1", 20), ("2026Q2", 25), ("2026Q3", 12)]
    assert (rows[3]["form"], rows[3]["filed"]) == ("10-K", "2026-07-30")  # the year less its first nine months


def test_a_three_month_figure_and_the_latest_filing_win():
    rows = fetch.edgar_quarters(doc(
        fact("2026-03-31", 44.203e9, "2026-01-01", filed="2026-04-30"),
        fact("2026-03-31", 45e9, "2026-01-01", filed="2026-05-15", form="10-Q/A"),  # restated
        fact("2026-06-30", 54.208e9, "2026-04-01", filed="2026-07-31"),
        fact("2026-06-30", 98.411e9, "2026-01-01", filed="2026-07-31"),  # six months less the restated first: 53.411
    ))
    assert [(r["period"], r["value"]) for r in rows] == [("2026Q1", 45), ("2026Q2", 54.208)]
    # Nvidia's quarters end in late January, April, July and October: each counts in the quarter it ends in.
    nvidia = fetch.edgar_quarters(doc(fact("2026-10-25", 57e9, "2026-07-27")))
    assert [(r["period"], r["value"]) for r in nvidia] == [("2026Q4", 57)]


def test_a_stock_is_read_at_each_quarter_end():
    rows = fetch.edgar_quarters(doc(
        fact("2026-03-31", 300e9, filed="2026-04-30"),
        fact("2026-06-30", 360e9, filed="2026-07-31"),
        fact("2026-06-30", 368e9, filed="2026-10-30"),  # restated in a later filing
        fact("2026-09-30", 392e9, filed="2026-10-30"),
    ))
    assert [(r["period"], r["value"]) for r in rows] == [("2026Q1", 300), ("2026Q2", 368), ("2026Q3", 392)]


# ---------------------------------------------------------------- what is fetched, and when


def test_the_page_prices_the_stack_the_world_index_and_each_basket(user):
    led = shipped(user)
    stack = fetch.stack(led)
    assert sorted(stack.values()) == ["AMD", "AMZN", "ASML", "AVGO", "CRWV", "GOOGL", "META", "MSFT", "MU", "NBIS",
                                      "NVDA", "ORCL", "TSM"]
    assert "openai" not in stack  # the labs are valued privately
    found = fetch.symbols(led, morning.load(user)[0].themes)
    assert set(stack.values()) | {"ACWI", "ASML.AS", "ANET", "VRT", "GOOG"} <= found


def test_each_source_is_fetched_only_when_due(user, monkeypatch):
    net = Network(monkeypatch)
    led = shipped(user)
    assert fetch.refresh(user, led, CONTACT, DAY) == []
    edgar = net.count("edgar")
    assert (net.count("fred"), net.count("yahoo")) == (4, 13)
    assert edgar == sum(len(concepts) * len(entities) for concepts, entities in fetch.EDGAR.values())  # none answered
    assert {c[3] for c in net.calls if c[0] == "edgar"} == {CONTACT}  # the SEC is told who is asking
    cache = user.cache / "bet"
    assert json.loads((cache / "fetched.json").read_text("utf-8"))["edgar"] == dict.fromkeys(
        ["amzn", "crwv", "googl", "meta", "msft", "nvda", "orcl"], DAY.isoformat())
    assert all((cache / name).exists() for name in ("fred/BAMLC0A0CM.csv", "yahoo/s_TSM.json", "edgar/nvda.json"))
    before = len(net.calls)
    fetch.refresh(user, led, CONTACT, DAY)
    assert len(net.calls) == before  # nothing is due again the same day
    fetch.refresh(user, led, CONTACT, DAY + dt.timedelta(days=1))
    assert len(net.calls) == before + 4  # FRED is daily
    fetch.refresh(user, led, CONTACT, DAY + dt.timedelta(days=7))
    assert len(net.calls) == before + 4 + 4 + 13 + edgar  # Yahoo and EDGAR are weekly


def test_edgar_is_off_without_a_contact(user, monkeypatch):
    net = Network(monkeypatch)
    assert fetch.refresh(user, shipped(user), "", DAY) == []
    assert net.count("edgar") == 0 and not (user.cache / "bet" / "edgar").exists()


def test_a_source_that_cannot_be_reached_keeps_its_cache(user, monkeypatch):
    net = Network(monkeypatch)
    led = shipped(user)
    fetch.refresh(user, led, CONTACT, DAY)
    path = user.cache / "bet" / "fred" / "BAMLC0A0CM.csv"
    before, calls = path.read_text("utf-8"), len(net.calls)
    net.down = {"fred", "yahoo", "edgar"}
    assert fetch.refresh(user, led, CONTACT, DAY + dt.timedelta(days=7)) == [
        "FRED not reached for RPSGENAIUSAGESHAREALL, RPSGENAIUSAGESHAREWORK, BAMLH0A0HYM2, BAMLC0A0CM: using cached "
        "figures where there are any.",
        "Shares outstanding not refreshed for AMD, AMZN, ASML, AVGO, CRWV, GOOGL, META, MSFT, MU, NBIS, NVDA, ORCL, TSM: "
        "using cached counts, or the ledger's market values.",
        "SEC EDGAR not reached for Alphabet, Amazon, CoreWeave, Meta, Microsoft, Nvidia, Oracle: using cached or ledger "
        "figures.",
    ]
    tried = [c[0] for c in net.calls[calls:]]
    assert (tried.count("fred"), tried.count("edgar"), tried.count("yahoo")) == (1, 1, 13)  # one stall is enough
    assert path.read_text("utf-8") == before
    assert fetch.Cache(user).last("fred", "BAMLC0A0CM") == DAY  # still due, so the next prepare tries again
    assert any(p.series == "ig_spread" for p in fetch.points(user, led))
    monkeypatch.setattr(fetch, "fred_csv", lambda series_id: "<html>Too many requests</html>")
    notes = fetch.refresh(user, led, "", DAY + dt.timedelta(days=8))
    assert notes[0].startswith("FRED not reached for") and path.read_text("utf-8") == before  # not FRED's CSV: refused


# ---------------------------------------------------------------- into the ledger


def test_fetched_figures_take_the_ledgers_place_and_yours_stay(user, monkeypatch):
    Network(monkeypatch, edgar=AMAZON_CAPEX)
    user.bet.write_text(
        'series:\n  genai_adoption:\n    points:\n      all:\n'
        '        - {period: 2026Q2, value: 61.8, grade: press, source: "https://x.test/1", seen: 2026-11-01}\n', "utf-8")
    led = shipped(user)
    fetch.refresh(user, led, CONTACT, DAY)
    fetched = fetch.points(user, led)
    assert {p.grade for p in fetched} == {fetch.FETCHED} and all(p.seen == DAY for p in fetched)
    gaps = fetch.merge(led, fetched)
    capex = led.series["capex_cash"]
    q1 = capex.get("amzn", "2026Q1")
    assert (q1.value, q1.grade, q1.published) == (50, "fetched", dt.date(2026, 4, 30))
    assert q1.source == "https://www.sec.gov/Archives/edgar/data/1018724/000101872426000014/0001018724-26-000014-index.htm"
    assert capex.get("amzn", "2025Q4").grade == "filed"  # a quarter EDGAR did not answer keeps the ledger's figure
    adoption = led.series["genai_adoption"]
    assert (adoption.get("all", "2026Q2").value, adoption.get("all", "2026Q2").mine) == (61.8, True)  # yours stay
    assert (adoption.latest("all").period, adoption.latest("all").value) == ("2026Q3", 60)  # a quarter the ledger lacks
    assert led.series["shares_outstanding"].latest("nvda").value == 2.5
    assert led.series["hy_spread"].latest("us").period == TODAY.isoformat()
    assert "capex_cash amzn 2026Q1: fetched 50, ledger 44.2 (+13.1%)" in gaps
    assert "genai_adoption all 2026Q2: fetched 58, yours 61.8 (-6.1%)" in gaps
    assert not [g for g in gaps if g.startswith(("capex_cash amzn 2026Q2", "capex_cash amzn 2026Q3"))]


def test_check_reports_what_was_fetched(user, monkeypatch, capsys):
    Network(monkeypatch, edgar=AMAZON_CAPEX)
    fetch.refresh(user, shipped(user), CONTACT, DAY)
    assert cli.main(["--dir", str(user.path), "check"]) == 0
    out = capsys.readouterr().out
    assert "Fetched: " in out and "  - capex_cash amzn 2026Q1: fetched 50, ledger 44.2 (+13.1%)" in out


def test_prepare_fetches_the_bet_figures_unless_offline(user, fake_world, monkeypatch):
    morning.prepare(user, today=TODAY)
    status = json.loads((user.cache / "bet" / "fetched.json").read_text("utf-8"))
    assert set(status) == {"fred", "yahoo"}  # the demo has no sec_contact, so EDGAR is off
    priced = {p.name[2:-4] for p in (user.cache / "prices").glob("p_*.csv")}
    assert {"ACWI", "CRWV", "ANET"} <= priced  # the world index, the stack and a basket
    for name in ("fred_csv", "yahoo_shares", "edgar_json"):
        monkeypatch.setattr(fetch, name, lambda *a: pytest.fail("offline fetched"))
    morning.prepare(user, offline=True, today=TODAY)


def test_sec_contact_needs_an_email(user):
    text = user.settings.read_text("utf-8").rstrip("\n")
    user.settings.write_text(text + "\nsec_contact: Jane Doe\n", "utf-8")
    with pytest.raises(Problems) as e:
        morning.load(user)
    assert e.value.problems == ["settings.yaml: sec_contact needs an email address, such as 'Jane Doe jane@example.com' "
                                "(the SEC asks for a name and email)"]
    user.settings.write_text(text + f"\nsec_contact: {CONTACT}\n", "utf-8")
    assert morning.load(user)[0].settings.sec_contact == CONTACT
