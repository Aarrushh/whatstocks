import copy
import json

import pytest
from conftest import DEMO_FUNDS, NEWS, TODAY, good_brief, quiet_brief, theme_notes

from whatstocks.brief import MAX_EVENTS, build_payload, payload_leaks, validate_brief
from whatstocks.files import load_book
from whatstocks.paths import ROOT, UserDir


@pytest.fixture
def book():
    return load_book(UserDir(ROOT / "demo"), DEMO_FUNDS)


@pytest.fixture
def payload(book):
    weights = {h.symbol: 1 / len(book.holdings) for h in book.holdings}
    themes = {tid: {"you": 0.1, "world": 0.05} for tid in book.themes.themes}
    return build_payload(book, TODAY, weights, themes, NEWS)


def test_payload_has_no_urls_or_amounts(payload):
    text = json.dumps(payload)
    assert "url" not in text and "example.com" not in text
    assert set(payload["holdings"][0]) == {"symbol", "name", "kind", "weight_pct", "countries", "themes"}
    assert [v["id"] for v in payload["views"]] == ["ai-capex-cut-2027", "brent-above-90-2027", "india-gdp-6-5-fy27"]
    assert payload_leaks(payload, [4321.5, 1500.0]) == []


def test_payload_marks_the_themes_to_cover(book):
    weights = {h.symbol: 1 / len(book.holdings) for h in book.holdings}
    themes = {tid: {"you": 0.0, "world": 0.05} for tid in book.themes.themes}
    themes["gold"]["you"] = 0.03
    details = {"NVDA": {"countries": [["United States", 1.0]], "themes": {"ai_buildout": 1.0, "power_grid": 0.01}}}
    payload = build_payload(book, TODAY, weights, themes, NEWS, details=details)
    rows = {t["id"]: t for t in payload["themes"]}
    assert rows["gold"]["must_cover"]  # 3% of the portfolio
    assert rows["oil_gas"]["must_cover"] and rows["oil_gas"]["open_views"] == ["brent-above-90-2027"]  # a view names it
    assert not rows["defence"]["must_cover"]
    assert rows["oil_gas"]["headlines_today"] == 1  # one headline from the theme's own search feed
    nvda = next(h for h in payload["holdings"] if h["symbol"] == "NVDA")
    assert nvda["countries"] == [["United States", 100.0]]
    assert nvda["themes"] == [["ai_buildout", 100.0]]  # power grid is under 2% of the holding


def test_payload_leak_check(payload):
    leaked = copy.deepcopy(payload)
    leaked["holdings"][0]["weight_pct"] = 4321.5
    leaked["holdings"][1]["value"] = 1500
    found = payload_leaks(leaked, [4321.5])
    assert "field 'holdings.value' is not allowed" in found
    assert "an amount (4321.5) appears in the payload" in found
    # Public text (headlines) may contain any number: the user did not write it.
    public = copy.deepcopy(payload)
    public["news"][0]["title"] = "Fund raises 4321.50 million"
    assert payload_leaks(public, [4321.5]) == []


def test_a_good_brief_passes(payload):
    assert validate_brief(good_brief(), payload) == ([], [])
    assert validate_brief(quiet_brief(), payload) == ([], [])


def test_brief_errors(payload):
    brief = good_brief()
    brief["date"] = "2026-11-02"
    event = brief["events"][0]
    event["news_ids"].append("zzzzzzzzzz")
    event["what"] = "See https://example.com for more."
    event["touches"] = {"themes": ["tulips"], "holdings": ["TSLA"]}
    event["views"] = [{"view_id": "no-such-view", "effect": "maybe", "why": ""}]
    errors, advice = validate_brief(brief, payload)
    text = "\n".join(errors)
    for part in ("date must be 2026-11-03", "news id 'zzzzzzzzzz' was not in today's payload", "contains a link",
                 "unknown theme 'tulips'", "'TSLA' is not a holding", "unknown or closed view 'no-such-view'",
                 "effect must be for, against or unclear", "needs a 'why'"):
        assert part in text
    assert advice == []
    assert validate_brief({"date": TODAY.isoformat(), "events": [], "themes": theme_notes()}, payload)[0] == [
        "no events: set quiet_day to true if nothing touched the themes, holdings or views"
    ]
    assert validate_brief([], payload)[0] == ["brief.json must be a JSON object"]


def test_every_theme_that_matters_gets_a_line(payload):
    brief = good_brief()
    brief["themes"] = [t for t in brief["themes"] if t["id"] != "gold"]
    assert validate_brief(brief, payload)[0] == [
        "themes: add 'gold' (it is 2% or more of the portfolio, or an open view names it)"
    ]
    brief["themes"] = theme_notes() + [dict(theme_notes()[0], state="")]
    errors = validate_brief(brief, payload)[0]
    assert "theme 11: theme 'ai_buildout' appears twice" in errors
    assert "theme 11: 'state' is missing" in errors


def test_ripples_holdings_and_watch_are_checked(payload):
    brief = good_brief()
    brief["ripples"] = [{"from": "oil_gas", "to": "oil_gas", "effect": "boost", "why": "", "news_ids": []}]
    brief["holdings"] = [{"symbol": "TSLA", "note": "Electric cars.", "news_ids": ["aaaaaaaaaa"]}]
    brief["watch"] = [{"what": "A vote", "when": "2026-11-01", "news_ids": []},
                      {"what": "A date", "when": "soon", "news_ids": ["aaaaaaaaaa"]}]
    text = "\n".join(validate_brief(brief, payload)[0])
    for part in ("ripple 1: 'from' and 'to' must be different themes", "ripple 1: effect must be help, hurt or unclear",
                 "ripple 1: 'why' is missing", "ripple 1: cites no news_ids", "holding 1: 'TSLA' is not a holding",
                 "watch 1: 'when' is in the past", "watch 1: cites no news_ids",
                 "watch 2: 'when' must be a date like 2026-11-30, or left out"):
        assert part in text


def test_at_most_ten_events(payload):
    brief = good_brief()
    brief["events"] = brief["events"] * 6
    assert f"events: at most {MAX_EVENTS}, keep the ones that matter most" in validate_brief(brief, payload)[0]


@pytest.mark.parametrize("text", [
    "You should sell NVDA.", "Consider buying more gold miners.", "Analysts set a price target of 200.",
    "Now looks like a good time to buy.", "We recommend trimming oil.",
])
def test_advice_is_caught(payload, text):
    brief = good_brief()
    brief["summary"] = text
    errors, advice = validate_brief(brief, payload)
    assert errors == [] and len(advice) == 1


def test_advice_is_caught_anywhere_in_the_brief(payload):
    brief = good_brief()
    brief["ripples"][0]["why"] = "Investors should buy utilities now."
    assert len(validate_brief(brief, payload)[1]) == 1


def test_plain_description_is_not_advice(payload):
    brief = good_brief()
    brief["summary"] = "Buyers of crude pay more; sellers of chips may sell less."
    assert validate_brief(brief, payload) == ([], [])
