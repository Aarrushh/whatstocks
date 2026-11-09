"""The ledger of "Will the bet pay off?" (spec section 14): the shipped files load and pass their check, and
my/bet.yaml merges on top of them, with one clear problem for each mistake."""
import datetime as dt
import shutil
import textwrap

import pytest

from whatstocks import cli, morning
from whatstocks.bet import ledger
from whatstocks.files import Problems
from whatstocks.paths import BET_DIR

LEDGER_DAY = dt.date(2026, 11, 7)  # the shipped figures were read on this day, so the check runs from it
SOURCE = 'grade: press, source: "https://x.test/1", seen: 2026-11-01'


def load(user=None, **kw) -> ledger.Ledger:
    return ledger.load(user, today=LEDGER_DAY, **kw)


def write(user, text: str) -> None:
    user.bet.write_text(textwrap.dedent(text), "utf-8")


def problems(user, text: str, **kw) -> list[str]:
    write(user, text)
    with pytest.raises(Problems) as e:
        load(user, **kw)
    return e.value.problems


def book(user):
    return morning.load(user)[0]


# ---------------------------------------------------------------- the shipped ledger


def test_the_shipped_ledger_passes_its_check():
    led = load()
    points = led.points()
    assert len(points) > 800 and len(led.series) > 60
    assert all(p.grade in ledger.GRADES and p.source.startswith(("https://", "http://")) for p in points)
    assert all(p.seen <= LEDGER_DAY and not p.mine for p in points)
    assert led.summary().startswith(f"Ledger: {len(points)} figures in {len(led.series)} series (0 yours), ")


def test_the_shipped_settings_are_the_approved_ones():
    """Spec section 22: the defaults the page opens on (decision 2), free users left out (10), the 58% bridge (12)."""
    led = load()
    sliders = ("gpu_life", "cost_of_capital", "deflation", "value_capture", "labour_share")
    assert [led.default(s) for s in sliders] == [5, 8, "trailing", 2.2, 50]
    assert led.model["demand"]["free_users"]["enabled"] is False
    assert led.model["capex"]["groups"]["consensus"]["enabled"] is False
    compute = led.param("compute_share")
    assert (compute["value"], compute["basis"], compute["grade"]) == (58, "sourced", "filed")
    assert led.param("long_life")["value"] == 25
    amzn = led.param("ai_share", "amzn")
    assert (amzn["value"], amzn["low"], amzn["high"], amzn["basis"]) == (70, 55, 85, "judgment")
    for pid, p in led.model["parameters"].items():  # a judgment gives its reason, a figure its source
        for one in [led.param(pid, e) for e in p["by_entity"]] if "by_entity" in p else [led.param(pid)]:
            assert one["why"] if one["basis"] == "judgment" else one["source"].startswith("https://"), pid
    assert [r["state"] for r in led.signals["regime"]] == ["breaking", "straining", "absorbing"]
    kinds = [p["kind"] for p in led.signals["paths"].values()]
    assert (kinds.count("crash"), kinds.count("adoption")) == (4, 1)


def test_the_shipped_channels_name_real_themes(user):
    b = book(user)
    led = load(user, views={v.id for v in b.views}, themes=b.themes)
    named = {c["id"].partition(":")[0] for channels in led.signals["channels"].values() for c in channels}
    assert named <= set(b.themes.themes) and {"hyperscalers", "ai_lessors"} <= named


def test_open_weight_releases_are_in_order_and_sourced():
    releases = load().events["releases"]
    assert [r["released"] for r in releases] == sorted(r["released"] for r in releases)
    r1 = next(r for r in releases if r["id"] == "deepseek_r1")
    assert r1["released"] == dt.date(2025, 1, 20) and r1["source"].startswith("https://")


def test_periods_and_rating_notches():
    assert ledger._period("year", 2026) == "2026" and ledger._period("year", "FY2027") == "FY2027"
    assert ledger._period("day", dt.date(2026, 10, 30)) == "2026-10-30"
    assert ledger._period("day", "2026-02-30") is None
    assert ledger._period("quarter", "2026Q5") is None and ledger._period("month", "2026-13") is None
    assert ledger.notch("S&P", "BBB-") == ledger.notch("Moody's", "Baa3") == ledger.notch("Fitch", "BBB-") == 9
    assert ledger.notch("S&P", "Baa3") is None


def test_a_switch_must_be_true_or_false(tmp_path):
    """YAML reads a bare on as true, so the switches are called enabled."""
    base = tmp_path / "bet"
    shutil.copytree(BET_DIR, base)
    model = base / "model.yaml"
    text = model.read_text("utf-8")
    assert "oracle: {label: Oracle, enabled: true" in text
    model.write_text(text.replace("oracle: {label: Oracle, enabled: true", "oracle: {label: Oracle, on: true"), "utf-8")
    with pytest.raises(Problems) as e:
        ledger.load(today=LEDGER_DAY, base=base)
    assert e.value.problems == [
        "model.yaml capex.groups.oracle: enabled (whether it starts switched on) must be true or false"]


# ---------------------------------------------------------------- my/bet.yaml on top


def test_your_points_replace_add_and_remove(user):
    shipped = load()
    write(user, f"""\
        series:
          lab_compute_share:
            points:
              anthropic:
                - {{period: 2026Q3, value: 55, {SOURCE}}}
          genai_adoption:
            points:
              all:
                - {{period: 2026Q4, value: 62.5, {SOURCE}}}
        remove:
          - {{series: credit_rating, entity: orcl, period: 2025-07-28, agency: "Moody's"}}
        """)
    led = load(user)
    compute = led.param("compute_share")
    assert (compute["value"], compute["mine"]) == (55, True)  # the parameter follows your figure
    assert led.series["genai_adoption"].latest("all").value == 62.5
    assert [p.agency for p in led.series["credit_rating"].points["orcl"]] == ["S&P", "S&P"]
    assert led.removed == 1 and len(led.points()) == len(shipped.points())  # one replaced, one added, one removed
    assert sum(p.mine for p in led.points()) == 2 and "(2 yours)" in led.summary()


def test_each_point_is_checked(user):
    found = problems(user, """\
        series:
          lab_revenue:
            points:
              openai:
                - {period: 2024Q1, value: 9, grade: rumour, source: "https://x.test/a", seen: 2026-11-01}
                - {period: 2024Q2, value: 9, grade: press, source: x.test/b, seen: 2026-11-01}
                - {period: 2024Q3, value: 9, low: 10, grade: press, source: "https://x.test/c", seen: 2026-11-01}
                - {period: 2024-09, value: 9, grade: press, source: "https://x.test/d", seen: 2026-11-01}
                - {period: 2024Q4, value: 9, grade: press, source: "https://x.test/e", seen: 2026-12-01}
                - {period: 2023Q1, value: 9, colour: red, grade: press, source: "https://x.test/f", seen: 2026-11-01}
                - {period: 2023Q2, value: 9, grade: press, source: "https://x.test/g", seen: 2026-11-01}
                - {period: 2023Q2, value: 8, grade: press, source: "https://x.test/h", seen: 2026-11-01}
                - {period: 2023Q3, grade: press, source: "https://x.test/i", seen: 2026-11-01}
                - {period: 2023Q4, value: 9, grade: press, source: "https://x.test/j"}
                - {period: 2022Q1, value: 9, grade: press, source: "https://x.test/k", seen: 2026-11-01,
                   published: 2026-11-05}
              acme:
                - {period: 2024Q1, value: 1, grade: press, source: "https://x.test/l", seen: 2026-11-01}
          not_a_series:
            points: {}
        """)
    at = "bet.yaml lab_revenue openai"
    assert found == [
        f"{at} 2024Q1: grade 'rumour' is not one of filed, company, press, estimate",
        f"{at} 2024Q2: source must be an http(s) link",
        f"{at} 2024Q3: low (10) is above the value (9)",
        f"{at}: period '2024-09' is not a quarter such as 2026Q3",
        f"{at} 2024Q4: seen 2026-12-01 is after today",
        f"{at} 2023Q1: unknown field colour",
        f"{at} 2023Q2: appears twice",
        f"{at} 2023Q3: value is missing",
        f"{at} 2023Q4: seen (the day the source was read) is missing",
        f"{at} 2022Q1: published 2026-11-05 is after seen 2026-11-01",
        "bet.yaml lab_revenue: unknown entity 'acme'",
        "bet.yaml series: unknown series 'not_a_series' (sources/bet/series.yaml lists them)",
    ]


def test_ratings_and_events_carry_words_not_values(user):
    found = problems(user, """\
        series:
          credit_rating:
            points:
              orcl:
                - {period: 2026-11-01, agency: "S&P", rating: BBB-minus, outlook: stable, grade: company,
                   source: "https://x.test/1", seen: 2026-11-01}
                - {period: 2026-11-02, agency: Egan, rating: BBB, outlook: stable, grade: company,
                   source: "https://x.test/2", seen: 2026-11-02}
                - {period: 2026-11-03, agency: "Moody's", rating: Baa3, outlook: watch, value: 3, grade: company,
                   source: "https://x.test/3", seen: 2026-11-03}
          credit_events:
            points:
              crwv:
                - {period: 2026-11-01, kind: default, grade: press, source: "https://x.test/4", seen: 2026-11-01}
        """)
    at = "bet.yaml credit_rating orcl"
    assert found == [
        f"{at} 2026-11-01: 'BBB-minus' is not on S&P's scale",
        f"{at} 2026-11-02: agency must be one of S&P, Moody's, Fitch",
        f"{at} 2026-11-03: a rating point has no value, low or high",
        f"{at} 2026-11-03: outlook must be one of positive, stable, negative, developing",
        "bet.yaml credit_events crwv 2026-11-01: kind must be one of distressed_exchange, pulled_deal, "
        "missed_payment, bankruptcy",
    ]


def test_a_cut_in_guidance_says_why(user):
    found = problems(user, """\
        series:
          capex_guide:
            points:
              msft:
                - {period: 2026-11-05, for: 2026, value: 160, grade: company, source: "https://x.test/1",
                   seen: 2026-11-06}
                - {period: 2026-11-06, value: 150, grade: company, source: "https://x.test/2", seen: 2026-11-06}
                - {period: 2026-11-07, for: 2027, value: 150, why: tariffs, grade: company,
                   source: "https://x.test/3", seen: 2026-11-07}
        """)
    at = "bet.yaml capex_guide msft"
    assert found == [
        f"{at} 2026-11-06: 'for' must name what the guidance covers, such as 2026 or FY2027",
        f"{at} 2026-11-07: why must be one of accounting, supply, demand, unstated",
        f"{at} 2026-11-05: a cut in 2026 guidance (170 to 160) needs a why: accounting, supply, demand, unstated",
    ]
    write(user, """\
        series:
          capex_guide:
            points:
              msft:
                - {period: 2026-11-05, for: 2026, value: 160, why: demand, grade: company,
                   source: "https://x.test/1", seen: 2026-11-06}
        """)
    guide = load(user).series["capex_guide"].latest("msft")
    assert (guide.period, guide.covers, guide.value, guide.why) == ("2026-11-05", "2026", 160, "demand")
    assert guide.mine


def test_your_parameters_and_slider_defaults(user):
    write(user, """\
        parameters:
          running_costs: {value: 4, low: 3, high: 6, basis: judgment, why: "Power costs more where I look."}
          ai_share:
            by_entity:
              amzn: {value: 60, low: 50, high: 70, why: "Less of Amazon's capex is AI than the shipped guess."}
        sliders:
          gpu_life: {default: 6}
        """)
    led = load(user)
    running = led.param("running_costs")
    assert (running["value"], running["low"], running["high"], running["mine"]) == (4, 3, 6, True)
    assert led.model["parameters"]["running_costs"]["label"].startswith("Running costs")  # its label stays
    assert (led.param("ai_share", "amzn")["value"], led.param("ai_share", "amzn")["mine"]) == (60, True)
    assert (led.param("ai_share", "msft")["value"], led.param("ai_share", "msft")["mine"]) == (85, False)
    assert led.default("gpu_life") == 6


def test_your_parameters_are_checked(user):
    found = problems(user, """\
        parameters:
          nope: {value: 1}
          running_costs: {value: 4, unit: years}
          exit_multiple: {value: 18, low: 20, basis: judgment, why: "Mine."}
          ai_share:
            by_entity:
              amzn: {value: 60}
              tsla: {value: 50, why: "Not a company in the ledger."}
        sliders:
          gpu_life: {default: 9}
          cost_of_capital: {default: 8, steps: [8]}
          nope: {default: 1}
        """)
    rc = "bet.yaml parameters.running_costs"
    assert found == [
        "bet.yaml parameters: unknown parameter 'nope'",
        f"{rc}: unknown field unit",
        "bet.yaml sliders.cost_of_capital: only your default can be set, as default: <one of the steps>",
        "bet.yaml sliders: unknown slider 'nope'",
        "bet.yaml sliders.gpu_life: default 9 is not one of the steps (3, 4, 5, 6, 7)",
        f"{rc}: grade must be one of filed, company, press, estimate (or basis: judgment, with why)",
        f"{rc}: source must be an http(s) link (or basis: judgment, with why)",
        f"{rc}: seen (the day the source was read) is missing",
        "bet.yaml parameters.exit_multiple: low (20) is above the value (18)",
        "bet.yaml parameters.ai_share amzn: a judgment needs its reason (why)",
        "bet.yaml parameters.ai_share tsla: unknown entity 'tsla'",
    ]


def test_your_levels(user):
    write(user, """\
        indicators:
          hy_spread: {amber: 5, red: 7, why: "I watch for a wider band than the drafted one."}
          conversion: {trigger: false}
        """)
    hy = load(user).signals["indicators"]["hy_spread"]
    assert (hy["amber"], hy["red"], hy["mine"]) == (5, 7, True) and hy["why"].startswith("I watch")
    found = problems(user, """\
        indicators:
          hy_spread: {amber: 7, red: 6, why: "Mine."}
          capex_growth: {amber: 10}
          tsmc_yoy: {colour: red}
          nope: {amber: 1, why: "Mine."}
          conversion: {trigger: true}
        """)
    assert found == [
        "bet.yaml indicators.capex_growth: your levels need your reason (why)",
        "bet.yaml indicators.tsmc_yoy: unknown field colour",
        "bet.yaml indicators: unknown indicator 'nope'",
        "bet.yaml indicators.hy_spread: amber (7) must come before red (6): with direction up, amber sits below red",
        "bet.yaml indicators.conversion: a trigger needs a red level",
    ]


def test_your_channels(user):
    themes = book(user).themes
    write(user, """\
        channels:
          credit_event:
            - {kind: theme, id: "defence:core", effect: help, strength: low, why: "Mine."}
        """)
    assert load(user, themes=themes).signals["channels"]["credit_event"] == [
        {"kind": "theme", "id": "defence:core", "effect": "help", "strength": "low", "why": "Mine.", "mine": True}]
    found = problems(user, """\
        channels:
          credit_event:
            - {kind: theme, id: not_a_theme, effect: hurt, strength: high}
            - {kind: theme, id: "defence:all", effect: hurt, strength: high}
            - {kind: theme, id: defence, effect: crush, strength: huge}
          nope: []
          price_collapse: {kind: theme}
        """, themes=themes)
    assert found == [
        "bet.yaml channels: unknown path 'nope'",
        "bet.yaml channels.price_collapse: a path's channels are a list, such as "
        "[{kind: theme, id: defence, effect: hurt, strength: low}]",
        "bet.yaml channels.credit_event: unknown theme 'not_a_theme'",
        "bet.yaml channels.credit_event: 'defence:all': a theme tier is core or partial",
        "bet.yaml channels.credit_event defence: effect must be one of hurt, help, mixed",
        "bet.yaml channels.credit_event defence: strength must be one of low, medium, high",
    ]


def test_view_links_name_your_views_and_the_paths(user):
    views = {v.id for v in book(user).views}
    write(user, "view_links:\n  ai-capex-cut-2027: {capex_retrenchment: for, adoption_pace: against}\n")
    assert load(user, views=views).view_links == {
        "ai-capex-cut-2027": {"capex_retrenchment": "for", "adoption_pace": "against"}}
    found = problems(user, """\
        view_links:
          no-such-view: {capex_retrenchment: for}
          ai-capex-cut-2027: {nope: for, credit_event: maybe}
          brent-above-90-2027: credit_event
        """, views=views)
    assert found == [
        "bet.yaml view_links.no-such-view: no view 'no-such-view' in views.yaml",
        "bet.yaml view_links.ai-capex-cut-2027: unknown path 'nope'",
        "bet.yaml view_links.ai-capex-cut-2027.credit_event: 'maybe' must be for or against",
        "bet.yaml view_links.brent-above-90-2027: map each path to for or against, such as {capex_retrenchment: for}",
    ]


def test_remove_names_a_shipped_point(user):
    found = problems(user, """\
        remove:
          - {series: lab_revenue, entity: openai, period: 1999Q1}
          - {series: lab_revenue, entity: openai}
          - {series: nope, entity: openai, period: 2026Q1}
        """)
    assert found == [
        "bet.yaml remove 1: no shipped point lab_revenue openai 1999Q1",
        "bet.yaml remove 2: name the series, entity and period of the shipped point to drop",
        "bet.yaml remove 3: no shipped point nope openai 2026Q1",
    ]


def test_a_bet_file_of_the_wrong_shape(user):
    assert problems(user, "- a list\n") == ["bet.yaml: write it as a mapping (series:, parameters:, view_links: ...)"]
    assert problems(user, "series: [1, 2]\nremove: {a: 1}\ncolours: {}\n") == [
        "bet.yaml: unknown field colours",
        "bet.yaml series: write it as a mapping",
        "bet.yaml remove: write it as a list",
    ]
    found = problems(user, "series: [\n")
    assert len(found) == 1 and found[0].startswith("bet.yaml line ") and "not valid YAML" in found[0]
    write(user, "")
    assert load(user).removed == 0


def test_check_stops_on_a_ledger_problem(user, capsys):
    write(user, "sliders: {gpu_life: {default: 9}}\n")
    assert cli.main(["--dir", str(user.path), "check"]) == 1
    out = capsys.readouterr().out
    assert "OK:" not in out and "Fix these first:" in out
    assert "  - bet.yaml sliders.gpu_life: default 9 is not one of the steps (3, 4, 5, 6, 7)" in out
