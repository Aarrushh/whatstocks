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


def fetch_news(themes: ThemeMap, now: dt.datetime, hours: int = 36, get=None) -> tuple[list[dict], list[str]]:
    get = get or requests.get
    config = yaml.safe_load(FEEDS_FILE.read_text("utf-8")) or {}
    cutoff = now - dt.timedelta(hours=hours)
    items, notes, seen = [], [], set()
    for name, url in targets(themes, config):
        try:
            response = get(url, headers=UA, timeout=20)
            response.raise_for_status()
            found = parse_rss(response.content)
        except Exception as e:
            notes.append(f"{name}: not fetched ({type(e).__name__})")
            continue
        kept = 0
        for it in found:
            if kept >= MAX_PER_FEED:
                break
            if it["published"] is not None and it["published"] < cutoff:
                continue
            title_key = re.sub(r"\W+", " ", it["title"].lower()).strip()
            if it["url"] in seen or title_key in seen:
                continue
            seen.update((it["url"], title_key))
            kept += 1
            items.append({
                "id": hashlib.sha1(it["url"].encode()).hexdigest()[:10],
                "title": it["title"],
                "source": it["source"] or name,
                "feed": name,
                "url": it["url"],
                "published": it["published"].isoformat(timespec="minutes") if it["published"] else None,
            })
    items.sort(key=lambda i: i["published"] or "", reverse=True)
    return items, notes
