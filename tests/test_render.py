"""The dashboard page: render.py's view model, and the template built from web/ (docs/DASHBOARD.md)."""
import hashlib
import json
import os
import re
from pathlib import Path

import pytest
from conftest import TODAY, good_brief

from whatstocks import morning, render
from whatstocks.files import Problems

WEB = Path(__file__).resolve().parents[1] / "web"
DATA = re.compile(r'<script id="ws-data" type="application/json">(.*?)</script>', re.S)


def finish_with(user, brief):
    (user.out / "brief.json").write_text(json.dumps(brief), "utf-8")
    return morning.finish(user, today=TODAY).read_text("utf-8")


def embedded(page: str) -> tuple[str, dict]:
    """The view model the page carries, as the raw text in its script tag and as data."""
    blocks = DATA.findall(page)
    assert len(blocks) == 1
    return blocks[0], json.loads(blocks[0])


def keys(data) -> set[str]:
    if isinstance(data, dict):
        return set(data) | {k for v in data.values() for k in keys(v)}
    if isinstance(data, list):
        return {k for v in data for k in keys(v)}
    return set()


def test_page_escapes_text_and_links_only_web_urls(user, fake_world):
    morning.prepare(user, today=TODAY)
    brief = good_brief()
    brief["events"][0]["what"] = '<img src=x onerror="alert(1)">'
    brief["events"][0]["news_ids"] = ["dddddddddd"]  # a headline with a script tag and a javascript: link
    brief["watch"][0]["what"] = '"><script>alert(2)</script>'
    page = finish_with(user, brief)
    raw, model = embedded(page)
    assert "<img" not in page and "<script>alert" not in page
    assert "<" not in raw and ">" not in raw  # nothing in the data can close its script tag
    assert "javascript:" not in raw  # a link that is not http(s) never reaches the page
    # The texts arrive exactly as written; the page shows them as text.
    assert model["events"][0]["what"] == '<img src=x onerror="alert(1)">'
    assert model["watch"][0]["what"] == '"><script>alert(2)</script>'
    assert model["news"]["dddddddddd"] == {"title": "<script>alert(1)</script> headline", "source": "Odd Feed", "url": None}


def test_json_for_the_page_cannot_close_its_tag():
    text = render.to_json({"a": "</script><!--", "b": "x y ", "c": "&amp;"})
    assert not any(ch in text for ch in "<>&  ")
    assert json.loads(text) == {"a": "</script><!--", "b": "x y ", "c": "&amp;"}
    assert render.to_json(render._finite({"x": float("nan"), "y": [float("inf"), 1.5]})) == '{"x":null,"y":[null,1.5]}'


def test_fill_needs_exactly_one_placeholder():
    assert render.fill("<p>/*WS_DATA*/</p>", {"a": 1}) == '<p>{"a":1}</p>'
    for broken in ("<p></p>", "/*WS_DATA*//*WS_DATA*/"):
        with pytest.raises(Problems, match="exactly one data placeholder"):
            render.fill(broken, {})


def test_page_is_self_contained_and_shows_shares_only(user, fake_world):
    morning.prepare(user, today=TODAY)
    page = morning.finish(user, no_brief=True, today=TODAY).read_text("utf-8")
    for outside in ("<script src", "<link ", "@import", "url(http"):
        assert outside not in page
    assert "default-src 'none'" in page  # the Content-Security-Policy: the page fetches and sends nothing
    assert render.PLACEHOLDER not in page
    _, model = embedded(page)
    assert model == json.loads((user.out / "dashboard.json").read_text("utf-8"))  # the same data, readable alone
    assert model["version"] == render.VERSION and model["lead"] == {"kind": "none", "text": render.NO_BRIEF}
    # Percentages only (P4): no quantities, amounts, accounts or ISINs from holdings.csv.
    assert not keys(model) & {"quantity", "value", "amount", "account", "isin"}
    assert "Broker A" not in page and "IE00BK5BQT80" not in page


def test_every_page_gets_the_brief(user, fake_world):
    morning.prepare(user, today=TODAY)
    _, model = embedded(finish_with(user, good_brief()))
    assert model["has_brief"] and model["lead"]["kind"] == "summary" and len(model["events"]) == 2
    holdings = {h["symbol"]: h for h in model["holdings"]}
    assert {"NVDA", "VWCE.DE", "CASH-EUR"} <= set(holdings)
    assert holdings["VWCE.DE"]["inside"]  # the fund's look-through: its largest companies
    assert holdings["SHEL.L"]["note"]["note"].startswith("Shell sells crude and gas")
    assert holdings["SHEL.L"]["events"] == [0]  # the events that touch it, by index
    edges = model["ripples"]["edges"]
    assert edges[0]["why"] == "Dearer energy raises what data centres pay to run." and edges[0]["d"].startswith("M")
    hub = next(n for n in model["ripples"]["nodes"] if n["hub"])
    assert hub["id"] == render.CENTRE
    watch = model["watch"][0]
    assert watch["what"] == "OPEC+ meets again on supply." and watch["date"] == "2026-12-01" and watch["n"] == 1
    assert model["themes"]["ai_buildout"]["brief"]["state"]
    assert model["proxy_heat"]["cols"] and len(model["proxy_heat"]["rows"]) == len(model["themes"])
    assert set(model["news"]) == {"aaaaaaaaaa", "bbbbbbbbbb", "cccccccccc"}  # only what the brief cites, not dddddddddd


def source_hash() -> str:
    """The hash web/scripts/ship.mjs stamps into the template, worked out the same way."""
    paths = []
    for name in ("index.html", "package.json", "package-lock.json", "vite.config.ts", "src"):
        full = WEB / name
        if full.is_dir():
            for folder, _, names in os.walk(full):
                paths += [(Path(folder) / n).relative_to(WEB).as_posix() for n in names]
        else:
            paths.append(name)
    digest = hashlib.sha256()
    for path in sorted(paths):
        digest.update((path + "\n").encode("utf-8"))
        digest.update(((WEB / path).read_bytes().decode("utf-8").replace("\r", "") + "\n").encode("utf-8"))
    return digest.hexdigest()


@pytest.mark.skipif(not (WEB / "src").is_dir(), reason="the web sources are not here (an installed package)")
def test_template_was_built_from_the_current_web_sources():
    stamp = re.search(r'<meta name="ws-source" content="([0-9a-f]{64})"', render.template())
    assert stamp, "the template has no source stamp: build it with 'npm run build' in web/"
    assert stamp.group(1) == source_hash(), "web/ changed since the template was built: run 'npm run build' in web/"
