"""News for the morning brief: publisher RSS feeds, plus one search feed per theme (SPEC section 9).

The code fetches every item. The AI only ever cites items by id, so it cannot introduce a source."""
from __future__ import annotations

import datetime as dt
import email.utils
import hashlib
import html
import re
import xml.etree.ElementTree as ET
from urllib.parse import quote_plus

import requests
import yaml

from .files import ThemeMap
from .paths import FEEDS_FILE

UA = {"User-Agent": "Mozilla/5.0 (compatible; whatstocks; +https://github.com/Aarrushh/whatstocks)"}
MAX_PER_FEED = 15
MAX_SEARCH = 25


def parse_rss(content: bytes) -> list[dict]:
    items = []
    for item in ET.fromstring(content).iter("item"):
        title = " ".join(html.unescape(item.findtext("title") or "").split())
        link = (item.findtext("link") or "").strip()
        if not title or not link.startswith(("http://", "https://")):
            continue
        published = None
        if item.findtext("pubDate"):
            try:
                published = email.utils.parsedate_to_datetime(item.findtext("pubDate"))
            except (TypeError, ValueError):
                pass
        if published is not None and published.tzinfo is None:
            published = published.replace(tzinfo=dt.timezone.utc)
        items.append({"title": title, "url": link, "source": (item.findtext("source") or "").strip(), "published": published})
    return items


def targets(themes: ThemeMap, config: dict) -> list[tuple[str, str]]:
    """Feeds to read: the publisher feeds, then one search per theme. Only theme queries go to the search engine."""
    out = [(f["name"], f["url"]) for f in config.get("feeds") or []]
    search = config.get("search") or {}
    if search.get("enabled") and search.get("url"):
        for theme in themes.themes.values():
            if theme.news_query:
                out.append((f"Search: {theme.label}", search["url"].format(query=quote_plus(theme.news_query))))
    return out


def _config() -> dict:
    return yaml.safe_load(FEEDS_FILE.read_text("utf-8")) or {}


def _fetch(get, url: str) -> list[dict]:
    response = get(url, headers=UA, timeout=20)
    response.raise_for_status()
    return parse_rss(response.content)


def _items(found: list[dict], name: str, cutoff: dt.datetime, seen: set, limit: int) -> list[dict]:
    """New items from one feed: recent, not seen before, at most `limit`."""
    out = []
    for it in found:
        if len(out) >= limit:
            break
        if it["published"] is not None and it["published"] < cutoff:
            continue
        title_key = re.sub(r"\W+", " ", it["title"].lower()).strip()
        if it["url"] in seen or title_key in seen:
            continue
        seen.update((it["url"], title_key))
        out.append({
            "id": hashlib.sha1(it["url"].encode()).hexdigest()[:10],
            "title": it["title"],
            "source": it["source"] or name,
            "feed": name,
            "url": it["url"],
            "published": it["published"].isoformat(timespec="minutes") if it["published"] else None,
        })
    return out


def fetch_news(themes: ThemeMap, now: dt.datetime, hours: int = 36, get=None) -> tuple[list[dict], list[str]]:
    get = get or requests.get
    cutoff = now - dt.timedelta(hours=hours)
    items, notes, seen = [], [], set()
    for name, url in targets(themes, _config()):
        try:
            found = _fetch(get, url)
        except Exception as e:
            notes.append(f"{name}: not fetched ({type(e).__name__})")
            continue
        items += _items(found, name, cutoff, seen, MAX_PER_FEED)
    items.sort(key=lambda i: i["published"] or "", reverse=True)
    return items, notes


def search_news(query: str, now: dt.datetime, days: int = 7, get=None) -> tuple[list[dict], list[str]]:
    """News for a scan: one search for the conflict, in the words the user typed. Nothing else is sent."""
    get = get or requests.get
    url = (_config().get("search") or {}).get("scan_url")
    if not url:
        return [], ["sources/feeds.yaml has no search.scan_url: no news searched."]
    try:
        found = _fetch(get, url.format(query=quote_plus(query)))
    except Exception as e:
        return [], [f"News search: not fetched ({type(e).__name__})"]
    items = _items(found, "Search", now - dt.timedelta(days=days), set(), MAX_SEARCH)
    items.sort(key=lambda i: i["published"] or "", reverse=True)
    return items, []
