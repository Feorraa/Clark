from __future__ import annotations

import calendar
import html
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from urllib.parse import urlencode

import feedparser
import httpx


TAG_RE = re.compile(r"<[^>]+>")
WHITESPACE_RE = re.compile(r"\s+")


@dataclass(frozen=True)
class Article:
    topic: str
    title: str
    url: str
    source: str
    published_at: datetime | None
    summary: str


def _clean(value: str | None) -> str:
    if not value:
        return ""
    without_tags = TAG_RE.sub(" ", value)
    return WHITESPACE_RE.sub(" ", html.unescape(without_tags)).strip()


def _published_at(entry: dict) -> datetime | None:
    parsed = entry.get("published_parsed") or entry.get("updated_parsed")
    if not parsed:
        return None
    return datetime.fromtimestamp(calendar.timegm(parsed), timezone.utc)


def _source(entry: dict) -> str:
    source = entry.get("source") or {}
    if isinstance(source, dict):
        title = source.get("title")
        if title:
            return _clean(title)
    return _clean(entry.get("author")) or "Unknown source"


def google_news_rss_url(
    topic: str,
    *,
    lookback_days: int,
    language: str,
    country: str,
    ceid: str,
) -> str:
    query = f"{topic} when:{lookback_days}d"
    params = {
        "q": query,
        "hl": language,
        "gl": country,
        "ceid": ceid,
    }
    return f"https://news.google.com/rss/search?{urlencode(params)}"


async def fetch_topic_news(
    client: httpx.AsyncClient,
    topic: str,
    *,
    lookback_days: int,
    language: str,
    country: str,
    ceid: str,
    limit: int,
) -> list[Article]:
    url = google_news_rss_url(
        topic,
        lookback_days=lookback_days,
        language=language,
        country=country,
        ceid=ceid,
    )
    response = await client.get(url)
    response.raise_for_status()

    feed = feedparser.parse(response.text)
    articles: list[Article] = []
    seen: set[str] = set()

    for entry in feed.entries:
        title = _clean(entry.get("title"))
        link = entry.get("link", "").strip()
        if not title or not link:
            continue

        source = _source(entry)
        key = f"{title.lower()}::{source.lower()}"
        if key in seen:
            continue

        seen.add(key)
        articles.append(
            Article(
                topic=topic,
                title=title,
                url=link,
                source=source,
                published_at=_published_at(entry),
                summary=_clean(entry.get("summary")),
            )
        )

        if len(articles) >= limit:
            break

    return articles


async def fetch_all_topics(
    topics: tuple[str, ...],
    *,
    lookback_days: int,
    language: str,
    country: str,
    ceid: str,
    limit: int,
) -> dict[str, list[Article]]:
    headers = {
        "User-Agent": "daily-news-discord-agent/0.1 (+https://cloud.google.com/run)"
    }
    timeout = httpx.Timeout(20.0, connect=10.0)
    async with httpx.AsyncClient(headers=headers, timeout=timeout) as client:
        results: dict[str, list[Article]] = {}
        for topic in topics:
            results[topic] = await fetch_topic_news(
                client,
                topic,
                lookback_days=lookback_days,
                language=language,
                country=country,
                ceid=ceid,
                limit=limit,
            )
        return results

