import json

from conftest import TODAY, good_brief

from whatstocks import morning


def test_page_escapes_text_and_links_only_web_urls(user, fake_world):
    morning.prepare(user, today=TODAY)
    brief = good_brief()
    brief["events"][0]["what"] = '<img src=x onerror="alert(1)">'
    brief["events"][0]["news_ids"] = ["dddddddddd"]  # a headline with a script tag and a javascript: link
    (user.out / "brief.json").write_text(json.dumps(brief), "utf-8")
    page = morning.finish(user, today=TODAY).read_text("utf-8")
    assert "<img" not in page and "<script>" not in page
    assert "&lt;img src=x onerror=&quot;alert(1)&quot;&gt;" in page
    assert "&lt;script&gt;alert(1)&lt;/script&gt; headline" in page
    assert "javascript:" not in page


def test_page_is_self_contained(user, fake_world):
    morning.prepare(user, today=TODAY)
    page = morning.finish(user, no_brief=True, today=TODAY).read_text("utf-8")
    assert "<script" not in page and "<link" not in page and "@import" not in page
    assert "prefers-color-scheme:dark" in page
    for section in ("Your views", "Exposure", "Past sell-offs", "Blind spots", "Record", "not financial advice"):
        assert section in page
