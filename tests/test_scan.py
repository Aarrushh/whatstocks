"""Conflict scans (scan.py)."""
import json

import pytest
from conftest import NEWS, TODAY, good_brief

from whatstocks import cli, morning, scan
from whatstocks.files import Problems

CONFLICT = "China blockade of Taiwan"
SLUG = "china-blockade-of-taiwan"


@pytest.fixture
def ready(user, fake_world, monkeypatch):
    """Today's numbers and brief, and a news search that returns the synthetic headlines."""
    morning.prepare(user, today=TODAY)
    (user.out / "brief.json").write_text(json.dumps(good_brief()), "utf-8")
    morning.finish(user, today=TODAY)
    monkeypatch.setattr(scan, "search_news", lambda query, now: ([dict(n) for n in NEWS[:3]], []))
    return user


def scan_file(day: str) -> dict:
    return {
        "date": day,
        "summary": "A blockade would cut the supply of chips and close a shipping lane.",
        "news_ids": ["bbbbbbbbbb"],
        "channels": [
            {"kind": "theme", "id": "ai_buildout", "effect": "hurt", "strength": "high", "why": "Most advanced chips are made there."},
            {"kind": "region", "id": "Taiwan", "effect": "hurt", "strength": "high", "why": "The blockade itself."},
            {"kind": "theme", "id": "defence", "effect": "help", "strength": "medium", "why": "Orders would rise."},
        ],
        "analogs": [{"name": "April 2024 strikes", "start": "2024-04-01", "end": "2024-04-19",
                     "why": "A short war scare with a quick recovery."}],
        "watch": [{"what": "Insurance rates for ships in the strait.", "news_ids": ["aaaaaaaaaa"]}],
    }


def test_prepare_sends_percentages_only(ready):
    found = scan.prepare(ready, f"  {CONFLICT} ", today=TODAY)
    assert found["slug"] == SLUG and found["path"].exists()
    payload = found["payload"]
    text = json.dumps(payload)
    assert "http" not in text and "example.com" not in text
    regions = {r["id"] for r in payload["regions"]}
    assert {"United States", "Taiwan"} <= regions and not {"Cash", "Unknown"} & regions
    assert [n["id"] for n in payload["news"]] == ["aaaaaaaaaa", "bbbbbbbbbb", "cccccccccc"]
    assert set(payload["holdings"][0]) == {"symbol", "name", "kind", "weight_pct", "countries", "themes"}
    with pytest.raises(Problems, match="Name the conflict"):
        scan.prepare(ready, "x", today=TODAY)


def test_the_scan_file_is_checked(ready):
    payload = scan.prepare(ready, CONFLICT, today=TODAY)["payload"]
    assert scan.validate(scan_file(TODAY.isoformat()), payload) == ([], [])
    bad = scan_file(TODAY.isoformat())
    bad["channels"][0].update(effect="crash", strength="huge")
    bad["channels"].append({"kind": "region", "id": "Atlantis", "effect": "hurt", "strength": "low", "why": "Sunk."})
    bad["analogs"] = [{"name": "Too early", "start": "2017-01-01", "end": "2017-02-01", "why": "Before the prices."},
                      {"name": "Not over", "start": "2026-10-01", "end": "2026-11-03", "why": "Still running."}]
    bad["summary"] = "You should sell chips. See https://example.com"
    errors, advice = scan.validate(bad, payload)
    text = "\n".join(errors)
    for part in ("channel 1: effect must be hurt, help or mixed", "channel 1: strength must be low, medium or high",
                 "channel 4: unknown region 'Atlantis'", "analog 1: prices start on 2018-01-01",
                 "analog 2: must end before today", "contains a link"):
        assert part in text
    assert len(advice) == 1


def test_finish_counts_each_company_once_and_draws_the_map(ready):
    scan.prepare(ready, CONFLICT, today=TODAY)
    (ready.out / "scans" / f"{SLUG}.json").write_text(json.dumps(scan_file(TODAY.isoformat())), "utf-8")
    done = scan.finish(ready, SLUG, today=TODAY)
    result = done["result"]
    channels = {c["id"]: c for c in result["channels"]}
    # In the fake world index, NVIDIA 5%, ASML 1% and TSMC 1% are AI build-out; TSMC 1% is Taiwan.
    assert channels["ai_buildout"]["world"] == pytest.approx(0.07)
    assert channels["Taiwan"]["world"] == pytest.approx(0.01)
    assert result["totals"]["world"]["hurt_share"] == pytest.approx(0.07)  # TSMC sits in both and counts once
    holdings = {h["symbol"]: h for h in result["holdings"]}
    assert holdings["NVDA"]["hurt_share"] == pytest.approx(1.0) and holdings["CASH-EUR"]["hurt_share"] == 0
    assert result["analogs"][0]["you"] is not None and result["analogs"][0]["world"] is not None
    assert [n["id"] for n in result["news"]] == ["aaaaaaaaaa", "bbbbbbbbbb"]  # only what the scan cites

    page = done["page"].read_text("utf-8")
    model = json.loads((ready.out / "dashboard.json").read_text("utf-8"))
    shown = next(s for s in model["scans"] if s["slug"] == SLUG)
    assert shown["bubbles"][0]["effect"] == "hurt" and shown["bubbles"][0]["bubbles"]  # the bubble map
    assert f'"slug":"{SLUG}"' in page
    assert "A blockade would cut the supply of chips" in page
    assert "Oil supply tightened and AI capex guidance softened." in page  # the morning brief stays on the page


def test_finish_refuses_what_it_cannot_trust(ready):
    with pytest.raises(Problems, match="is not a scan name"):
        scan.finish(ready, "../evil", today=TODAY)
    with pytest.raises(Problems, match="No scan 'iran-war'"):
        scan.finish(ready, "iran-war", today=TODAY)
    scan.prepare(ready, CONFLICT, today=TODAY)
    with pytest.raises(Problems, match="is missing"):
        scan.finish(ready, SLUG, today=TODAY)
    (ready.out / "scans" / f"{SLUG}.json").write_text(json.dumps(scan_file(TODAY.isoformat())), "utf-8")
    with pytest.raises(Problems, match="run 'scan prepare' again today"):
        scan.finish(ready, SLUG, today=TODAY.replace(day=4))


def test_cli_scan(ready, capsys):
    assert cli.main(["--dir", str(ready.path), "scan", "prepare", CONFLICT]) == 0
    assert SLUG in capsys.readouterr().out
