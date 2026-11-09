import datetime as dt
import textwrap

import pytest
from conftest import DEMO_FUNDS

from whatstocks.files import Problems, load_book, load_themes
from whatstocks.paths import ROOT, UserDir


def problems_for(user, files: dict) -> list[str]:
    for name, text in files.items():
        (user.path / name).write_text(textwrap.dedent(text).lstrip(), "utf-8")
    with pytest.raises(Problems) as e:
        load_book(user, DEMO_FUNDS)
    return e.value.problems


def test_demo_loads():
    book = load_book(UserDir(ROOT / "demo"), DEMO_FUNDS)
    assert len(book.holdings) == 7 and len(book.views) == 3 and len(book.decisions) == 3
    assert {h.symbol: h.kind for h in book.holdings}["VWCE.DE"] == "fund"
    assert {h.symbol: h.kind for h in book.holdings}["CASH-EUR"] == "cash"
    view = book.view("ai-capex-cut-2027")
    assert view.probability_on(dt.date(2026, 9, 9)) is None
    assert view.probability_on(dt.date(2026, 9, 15)) == 0.30
    assert view.probability == 0.40
    nvda = book.decisions[0]
    assert nvda.review_on == dt.date(2027, 9, 15)


def test_holdings_problems(user):
    found = problems_for(user, {"holdings.csv": """
        symbol,isin,name,quantity,value,currency,account,kind
        ,IE00BK5BQT80,No symbol,1,,,A,
        CASH-EUR,,Cash,,,,A,
        NVDA,,Nvidia,,100,,A,
        NVDA,,Nvidia,1,,,A,
        SHEL.L,,Shell,abc,,,A,
        INFY.NS,,Infosys,1,,,A,bond
    """})
    text = "\n".join(found)
    assert "holdings.csv row 2: symbol is missing (finding a symbol from an ISIN is not built yet)" in text
    assert "row 3: cash needs a value" in text
    assert "row 4: a value needs a currency" in text
    assert "row 5: NVDA appears twice in the same account" in text
    assert "row 6: quantity and value must be numbers" in text
    assert "row 7: kind must be one of stock, fund, cash" in text


def test_view_problems(user):
    found = problems_for(user, {"views.yaml": """
        views:
          - id: Bad_Id
            statement: x
            created: 2026-10-01
            resolves_by: 2026-10-15
            resolution: y
            themes: {nowhere: sideways}
            forecasts:
              - {date: 2026-10-02, probability: 1.0}
              - {date: 2026-10-03, probability: 0.5}
          - id: void-view
            statement: x
            created: 2026-10-01
            resolves_by: 2027-10-01
            resolution: y
            themes: {gold: up}
            forecasts:
              - {date: 2026-10-01, probability: 0.5}
            outcome: {result: void, date: 2026-10-20}
    """})
    text = "\n".join(found)
    assert "id must be kebab-case" in text
    assert "resolves_by must be at least 30 days after created" in text
    assert "unknown theme 'nowhere'" in text
    assert "theme 'nowhere' must be up or down" in text
    assert "probability 1.0 must be between 0.01 and 0.99" in text
    assert "the first forecast must be dated 2026-10-01" in text
    assert "a void outcome needs a note saying why" in text


def test_decision_problems(user):
    found = problems_for(user, {"decisions.yaml": """
        decisions:
          - id: d1
            date: 2026-10-01
            action: buy
            symbol: NVDA
            views: [no-such-view]
            reason: test
            corrects: d2
          - id: d2
            date: 2026-10-02
            action: hodl
            symbol: TSLA
            views: []
            reason: ""
    """})
    text = "\n".join(found)
    assert "decision d1: unknown view 'no-such-view'" in text
    assert "decision d1: corrects must point to an earlier entry" in text
    assert "decision d2: action must be one of" in text
    assert "decision d2: TSLA is not in holdings.csv" in text
    assert "decision d2: reason is missing" in text


def test_a_sold_holding_can_have_decisions(user):
    (user.path / "decisions.yaml").write_text(textwrap.dedent("""
        decisions:
          - {id: d1, date: 2026-01-05, action: buy, symbol: TSLA, views: [], reason: test}
          - {id: d2, date: 2026-06-05, action: sell, symbol: TSLA, views: [], reason: test}
    """), "utf-8")
    assert len(load_book(user, DEMO_FUNDS).decisions) == 2


def test_theme_overlay_adds_removes_and_aliases(tmp_path):
    overlay = tmp_path / "themes.yaml"
    overlay.write_text(textwrap.dedent("""
        aliases:
          RHM.DE: [RHM.F]
        themes:
          defence:
            members:
              core: [{symbol: QQ.L, reason: test}]
            remove: [BA]
          my_theme:
            label: Mine
            description: A theme of my own.
            proxy: SPY
    """), "utf-8")
    problems = []
    themes = load_themes(overlay, problems)
    assert problems == []
    assert "QQ.L" in themes.themes["defence"].core
    assert "BA" not in themes.themes["defence"].partial
    assert themes.member_of("RHM.F") == "RHM.DE"
    assert themes.weights("RHM.F") == {"defence": 1.0}
    assert themes.themes["my_theme"].label == "Mine"


def test_every_shipped_theme_has_a_news_query():
    themes = load_themes(None, [])
    assert all(t.news_query for t in themes.themes.values())


def test_settings_compare_is_optional_and_checked(tmp_path):
    from whatstocks.files import load_settings

    path = tmp_path / "settings.yaml"
    path.write_text("home_currency: EUR\nbenchmark: IUSQ.DE\n", "utf-8")
    problems = []
    assert load_settings(path, problems).compare == {} and problems == []
    path.write_text("home_currency: EUR\nbenchmark: IUSQ.DE\ncompare:\n  Nasdaq-100: EQQQ.DE\n", "utf-8")
    assert load_settings(path, problems).compare == {"Nasdaq-100": "EQQQ.DE"} and problems == []
    path.write_text("home_currency: EUR\nbenchmark: IUSQ.DE\ncompare: [EQQQ.DE]\n", "utf-8")
    load_settings(path, problems)
    assert problems and "compare" in problems[0]
