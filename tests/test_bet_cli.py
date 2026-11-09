"""'whatstocks bet' and 'whatstocks bet due', the code steps of /bet (spec 17)."""
import json

import pytest
from conftest import TODAY, good_brief

from whatstocks import cli, morning
from whatstocks.bet import signals as bet_signals
from whatstocks.files import Problems

YOUR_LEVELS = """\
indicators:
  payback:
    amber: 1000
    red: 900
    why: My own levels, for the test.
"""


@pytest.fixture
def ready(user, fake_world):
    """Today's numbers, and the page with today's brief on it."""
    morning.prepare(user, today=TODAY)
    (user.out / "brief.json").write_text(json.dumps(good_brief()), "utf-8")
    morning.finish(user, today=TODAY)
    return user


def test_rebuild_works_out_your_levels_and_keeps_the_brief(ready):
    (ready.path / "bet.yaml").write_text(YOUR_LEVELS, "utf-8")
    log = (ready.out / "evidence.jsonl").read_bytes()
    done = morning.rebuild_bet(ready, today=TODAY)
    before, after = done["before"], done["after"]
    was = before["indicators"]["payback"]["state"]
    assert was != "red" and after["indicators"]["payback"]["state"] == "red" and after["indicators"]["payback"]["mine"]

    lines = bet_signals.moves(before, after)
    assert lines[0].startswith("Regime: ") and lines[1].startswith("Coverage now: ")
    assert lines[2].startswith("Payback by the deadline: ") and lines[3].startswith("Paths: ")
    assert any(line.startswith("  - Payback by the deadline: ") and line.endswith(f"red (was {was.replace('_', ' ')})")
               for line in lines)

    model = json.loads((ready.out / "dashboard.json").read_text("utf-8"))
    assert model["bet"]["signals"]["indicators"]["payback"]["state"] == "red"
    page = done["page"].read_text("utf-8")
    assert "Oil supply tightened and AI capex guidance softened." in page  # the morning brief stays on the page
    # The evidence log is untouched: finish logs a path that moved, on the next morning run.
    assert (ready.out / "evidence.jsonl").read_bytes() == log


def test_rebuild_works_out_the_reach_of_your_channels(ready):
    (ready.path / "bet.yaml").write_text(
        "channels:\n  credit_event:\n    - {kind: theme, id: defence, effect: hurt, strength: high}\n", "utf-8")
    morning.rebuild_bet(ready, today=TODAY)
    reach = json.loads((ready.out / "exposure.json").read_text("utf-8"))["crash_paths"]["credit_event"]
    assert [c["id"] for c in reach["channels"]] == ["defence"]
    assert reach["you"]["hurt_share"] > 0  # the demo holds Rheinmetall


def test_rebuild_needs_a_prepare_first(user, fake_world):
    with pytest.raises(Problems, match="run 'whatstocks prepare' first"):
        morning.rebuild_bet(user, today=TODAY)


def test_moves_with_nothing_before_says_where_things_stand(ready):
    after = json.loads((ready.out / "bet.json").read_text("utf-8"))["signals"]
    lines = bet_signals.moves(None, after)
    assert len(lines) == 4 and "(was" not in "".join(lines)
    assert bet_signals.moves(after, after)[-1] == "No indicator moved."


def test_due_ranks_what_feeds_the_curves_first(ready):
    found = morning.bet_due(ready, today=TODAY)
    assert found["series"] > len(found["due"]) > 0 and all(r["due"] for r in found["due"])
    curves = [r["feeds"]["curves"] for r in found["due"]]
    assert curves == sorted(curves, reverse=True)
    assert found["gaps"] and found["sec_contact"] is False
    named = [g for g in found["gaps"] if g["entity"]]
    assert named and all(g["name"] for g in named)


def test_cli_bet_and_bet_due(ready, capsys):
    assert cli.main(["--dir", str(ready.path), "bet", "due"]) == 0
    out = capsys.readouterr().out
    assert "series have a newer figure due" in out and "Open gaps in the ledger:" in out and out.isascii()
    assert cli.main(["--dir", str(ready.path), "bet"]) == 0
    out = capsys.readouterr().out
    assert "Regime: " in out and "Dashboard (The bet page):" in out and out.isascii()


def test_say_writes_plain_ascii(capsys):
    cli._say("Nebius – São Paulo − “quoted” … → 日")
    assert capsys.readouterr().out == 'Nebius - Sao Paulo - "quoted" ... -> ?\n'
