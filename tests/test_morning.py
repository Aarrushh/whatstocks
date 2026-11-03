import datetime as dt
import json

import pytest
import yaml
from conftest import TODAY, good_brief

from whatstocks import cli, morning
from whatstocks.files import Problems


def write_brief(user, brief):
    (user.out / "brief.json").write_text(json.dumps(brief), "utf-8")


def test_prepare_then_finish(user, fake_world):
    result = morning.prepare(user, today=TODAY)
    payload = json.loads((user.out / "payload.json").read_text("utf-8"))
    assert "http" not in json.dumps(payload)
    weights = {h["symbol"]: h["weight_pct"] for h in payload["holdings"]}
    assert set(weights) == {"VWCE.DE", "NVDA", "ASML.AS", "RHM.DE", "SHEL.L", "INFY.NS", "CASH-EUR"}
    assert sum(weights.values()) == pytest.approx(100, abs=0.5)
    assert 5 < weights["SHEL.L"] < 20  # quoted in pence, valued in pounds

    exposure = result["exposure"]
    ai = exposure["themes"]["ai_buildout"]
    assert ai["world"] == pytest.approx(0.07)  # NVDA 5% + ASML 1% + TSMC 1% in the fake ACWI
    assert ai["you"] > ai["world"]  # NVDA and ASML held directly as well
    assert all(0 <= row["you"] <= 1 and 0 <= row["world"] <= 1 for row in exposure["themes"].values())
    assert exposure["beta_coverage"] == pytest.approx(1.0)
    assert any("approximated with MSCI ACWI" in n for n in exposure["notes"])
    assert exposure["stale"] == {}

    write_brief(user, good_brief())
    page = morning.finish(user, today=TODAY).read_text("utf-8")
    assert "Low-confidence view: ai-capex-cut-2027 was 30% that day" in page
    assert "No view cited" in page
    assert 'href="https://example.com/opec"' in page
    assert "OPEC+ extended its output cuts into 2027." in page

    evidence = (user.out / "evidence.jsonl").read_text("utf-8").splitlines()
    assert len(evidence) == 2
    morning.finish(user, today=TODAY)  # a re-run replaces today's lines
    assert (user.out / "evidence.jsonl").read_text("utf-8").splitlines() == evidence


def test_offline_prepare_uses_the_cache(user, fake_world, monkeypatch):
    morning.prepare(user, today=TODAY)
    monkeypatch.setattr(morning, "fetch_news", lambda *a: pytest.fail("offline must not fetch news"))
    result = morning.prepare(user, offline=True, today=TODAY)
    assert len(result["payload"]["news"]) == 4
    assert result["exposure"]["themes"]["ai_buildout"]["world"] == pytest.approx(0.07)


def test_deleting_a_view_is_refused(user, fake_world):
    morning.prepare(user, today=TODAY)
    data = yaml.safe_load(user.views.read_text("utf-8"))
    data["views"] = [v for v in data["views"] if v["id"] != "brent-above-90-2027"]
    user.views.write_text(yaml.safe_dump(data), "utf-8")
    with pytest.raises(Problems) as e:
        morning.prepare(user, offline=True, today=TODAY)
    assert "view 'brent-above-90-2027' was deleted" in e.value.problems[0]


def test_finish_checks_the_brief(user, fake_world):
    morning.prepare(user, today=TODAY)
    with pytest.raises(Problems, match="brief.json is missing"):
        morning.finish(user, today=TODAY)
    brief = good_brief()
    brief["summary"] = "You should sell NVDA now."
    write_brief(user, brief)
    with pytest.raises(Problems, match="advice-like wording"):
        morning.finish(user, today=TODAY)
    page = morning.finish(user, allow_advice=True, today=TODAY).read_text("utf-8")
    assert "let through with --allow-advice" in page
    with pytest.raises(Problems, match="run 'whatstocks prepare' again today"):
        morning.finish(user, today=TODAY + dt.timedelta(days=1))


def test_finish_without_a_brief(user, fake_world):
    morning.prepare(user, today=TODAY)
    page = morning.finish(user, no_brief=True, today=TODAY).read_text("utf-8")
    assert "No morning brief today" in page and "No brief today." in page


def test_blind_spots():
    exposure = {"themes": {
        "gold": {"label": "Gold", "you": 0.0, "world": 0.01},
        "oil_gas": {"label": "Oil and gas", "you": 0.04, "world": 0.04},
    }}
    evidence = [{"date": "2026-11-0%d" % d, "what": f"event {d}", "themes": ["gold", "oil_gas"]} for d in (1, 2, 3)]
    evidence.append({"date": "2026-10-20", "what": "old", "themes": ["gold"]})
    spots = morning.blind_spots(exposure, evidence, TODAY)
    assert [s["id"] for s in spots] == ["gold"]
    assert spots[0]["events"] == 3 and spots[0]["recent"] == ["event 3", "event 2", "event 1"]


def test_cli(user, capsys):
    assert cli.main(["--dir", str(user.path), "check"]) == 0
    out = capsys.readouterr().out
    assert "OK: 7 holdings, 3 open views, 3 decisions, 10 themes." in out
    assert "In no theme yet" not in out
    assert cli.main(["--dir", str(user.path / "missing"), "check"]) == 2
    user.views.write_text("views: [", "utf-8")
    assert cli.main(["--dir", str(user.path), "check"]) == 1
    assert "Fix these first:" in capsys.readouterr().out
