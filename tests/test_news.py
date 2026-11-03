import datetime as dt

from whatstocks.files import load_themes
from whatstocks.news import fetch_news, parse_rss

RSS = b"""<?xml version="1.0"?><rss><channel>
<item><title>Oil   jumps &amp; falls</title><link>https://a.example/1</link>
  <pubDate>Tue, 03 Nov 2026 05:00:00 GMT</pubDate><source url="https://a.example">Wire A</source></item>
<item><title>Oil jumps &amp; falls</title><link>https://b.example/2</link><pubDate>Tue, 03 Nov 2026 05:30:00 GMT</pubDate></item>
<item><title>Old story</title><link>https://a.example/3</link><pubDate>Mon, 26 Oct 2026 05:00:00 GMT</pubDate></item>
<item><title>Bad link</title><link>javascript:alert(1)</link></item>
<item><title>No date</title><link>https://a.example/4</link></item>
</channel></rss>"""


class Response:
    content = RSS

    def raise_for_status(self):
        pass


def test_parse_rss_keeps_web_links_only():
    items = parse_rss(RSS)
    assert [i["title"] for i in items] == ["Oil jumps & falls", "Oil jumps & falls", "Old story", "No date"]
    assert items[0]["source"] == "Wire A"
    assert items[0]["published"] == dt.datetime(2026, 11, 3, 5, tzinfo=dt.timezone.utc)


def test_fetch_news_dedupes_and_sends_only_theme_queries():
    asked = []

    def get(url, headers, timeout):
        asked.append(url)
        if "bbci" in url:
            raise ConnectionError
        return Response()

    themes = load_themes(None, [])
    items, notes = fetch_news(themes, dt.datetime(2026, 11, 3, 8, tzinfo=dt.timezone.utc), get=get)
    assert [i["title"] for i in items] == ["Oil jumps & falls", "No date"]
    assert items[0]["url"] == "https://a.example/1" and len(items[0]["id"]) == 10
    assert "BBC Business: not fetched (ConnectionError)" in notes
    searches = [u for u in asked if "news.google.com" in u]
    assert len(searches) == len(themes.themes)
    # Only theme queries leave the machine: never a holding.
    assert not any(symbol in u for u in searches for symbol in ("NVDA", "SHEL", "INFY", "ASML"))
