import copy
import json

import pytest
from conftest import DEMO_FUNDS, NEWS, TODAY, good_brief

from whatstocks.brief import build_payload, payload_leaks, validate_brief
from whatstocks.files import load_book
from whatstocks.paths import ROOT, UserDir


@pytest.fixture
def payload():
    book = load_book(UserDir(ROOT / "demo"), DEMO_FUNDS)
    weights = {h.symbol: 1 / len(book.holdings) for h in book.holdings}
    themes = {tid: {"you": 0.1, "world": 0.05} for tid in book.themes.themes}
    return build_payload(book, TODAY, weights, themes, NEWS)


def test_payload_has_no_urls_or_amounts(payload):
    text = json.dumps(payload)
    assert "url" not in text and "example.com" not in text
    assert set(payload["holdings"][0]) == {"symbol", "name", "kind", "weight_pct"}
    assert [v["id"] for v in payload["views"]] == ["ai-capex-cut-2027", "brent-above-90-2027", "india-gdp-6-5-fy27"]
    assert payload_leaks(payload, [4321.5, 1500.0]) == []


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
    assert validate_brief({"date": TODAY.isoformat(), "events": [], "quiet_day": True}, payload) == ([], [])


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
    assert validate_brief({"date": TODAY.isoformat(), "events": []}, payload)[0] == [
        "no events: set quiet_day to true if nothing touched the themes, holdings or views"
    ]
    assert validate_brief([], payload)[0] == ["brief.json must be a JSON object"]


@pytest.mark.parametrize("text", [
    "You should sell NVDA.", "Consider buying more gold miners.", "Analysts set a price target of 200.",
    "Now looks like a good time to buy.", "We recommend trimming oil.",
])
def test_advice_is_caught(payload, text):
    brief = good_brief()
    brief["summary"] = text
    errors, advice = validate_brief(brief, payload)
    assert errors == [] and len(advice) == 1


def test_plain_description_is_not_advice(payload):
    brief = good_brief()
    brief["summary"] = "Buyers of crude pay more; sellers of chips may sell less."
    assert validate_brief(brief, payload) == ([], [])
