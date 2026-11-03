import json

from conftest import TODAY, good_brief

from whatstocks import morning, render


def finish_with(user, brief):
    (user.out / "brief.json").write_text(json.dumps(brief), "utf-8")
    return morning.finish(user, today=TODAY).read_text("utf-8")


def test_page_escapes_text_and_links_only_web_urls(user, fake_world):
    morning.prepare(user, today=TODAY)
    brief = good_brief()
    brief["events"][0]["what"] = '<img src=x onerror="alert(1)">'
    brief["events"][0]["news_ids"] = ["dddddddddd"]  # a headline with a script tag and a javascript: link
    brief["watch"][0]["what"] = '"><script>alert(2)</script>'  # also lands in a hover tip
    page = finish_with(user, brief)
    assert "<img" not in page and "<script>alert" not in page
    assert "&lt;img src=x onerror=&quot;alert(1)&quot;&gt;" in page
    assert "&lt;script&gt;alert(1)&lt;/script&gt; headline" in page
    assert "&quot;&gt;&lt;script&gt;alert(2)&lt;/script&gt;" in page
    assert "javascript:" not in page


def test_page_is_self_contained(user, fake_world):
    morning.prepare(user, today=TODAY)
    page = morning.finish(user, no_brief=True, today=TODAY).read_text("utf-8")
    for outside in ("<script src", "<link", "@import", "url(http", " src="):
        assert outside not in page
    assert "javascript:" not in render.JS + render.HEAD_JS  # the page's own script builds no links
    assert ":root[data-theme=light]" in page  # both themes, switched in the page
    for pid, _ in render.PAGES:
        assert f'id="p-{pid}"' in page and f'href="#{pid}"' in page
    for part in ("Past sell-offs", "Blind spots", "Where each theme comes from", "No scans yet", "not financial advice"):
        assert part in page


def test_every_page_carries_the_brief(user, fake_world):
    morning.prepare(user, today=TODAY)
    page = finish_with(user, good_brief())
    assert 'id="h-NVDA"' in page and 'id="h-VWCE.DE"' in page  # one panel per holding
    assert "Largest companies inside" in page  # the fund's look-through
    assert "Shell sells crude and gas" in page  # the AI's note on a holding
    assert "Dearer energy raises what data centres pay to run." in page and 'class="net"' in page  # the ripple map
    assert "OPEC+ meets again on supply." in page and 'class="tl-d"' in page  # a dated thing to watch
    assert "Two hyperscalers trimmed their 2027 capex guidance." in page  # a theme's state
    assert "Theme proxies against the world index" in page and 'class="hm ' in page  # the 12-week heat map
    assert '<span class="n">2</span>' in page  # two events counted on the News & world tab
