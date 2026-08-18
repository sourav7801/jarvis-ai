"""Keyless, read-only market headline discovery through GDELT DOC 2.0."""

from __future__ import annotations

import threading
import time
from datetime import datetime, timedelta, timezone
import re
from email.utils import parsedate_to_datetime
from typing import Any
from urllib.parse import urlparse
from xml.etree import ElementTree

import requests


GDELT_DOC_URL = "https://api.gdeltproject.org/api/v2/doc/doc"
GOOGLE_NEWS_RSS_URL = "https://news.google.com/rss/search"
NEWS_CACHE_TTL_SECONDS = 300.0
MAX_RSS_BYTES = 2 * 1024 * 1024
_CACHE: dict[tuple[str, int, str], tuple[float, dict[str, Any]]] = {}
_CACHE_LOCK = threading.RLock()

_TIMESPAN_HOURS = {
    "1h": 2,
    "6h": 8,
    "12h": 14,
    "1d": 30,
    "3d": 84,
    "7d": 180,
    "1w": 180,
    "1m": 24 * 32,
}
_QUERY_STOP_WORDS = {
    "and", "for", "from", "india", "latest", "market", "markets", "news",
    "price", "prices", "the", "today", "update",
    # Broad-news intent words should not be mandatory title matches. They are
    # useful to the provider query, but filtering every returned title for
    # "world"/"global" can discard legitimate current headlines.
    "world", "global", "international", "headline", "headlines",
}


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_seen_date(value: Any) -> datetime | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    if re.fullmatch(r"\d{8}T\d{6}Z", raw):
        try:
            return datetime.strptime(raw, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)
        except ValueError:
            return None
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed.astimezone(timezone.utc)
    except ValueError:
        return None


def _query_terms(query: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-z0-9]+", query.casefold())
        if len(token) >= 3 and token not in _QUERY_STOP_WORDS
    }


def _rank_fresh_articles(
    articles: list[dict[str, Any]],
    query: str,
    timespan: str,
) -> tuple[list[dict[str, Any]], int]:
    cutoff = _utc_now() - timedelta(hours=_TIMESPAN_HOURS[timespan])
    terms = _query_terms(query)
    ranked: list[tuple[int, float, dict[str, Any]]] = []
    stale_filtered = 0
    for article in articles:
        published = _parse_seen_date(article.get("seen_date"))
        if published is not None and published < cutoff:
            stale_filtered += 1
            continue
        if published is None and timespan in {"1h", "6h", "12h", "1d"}:
            stale_filtered += 1
            continue
        title_terms = set(re.findall(r"[a-z0-9]+", str(article.get("title") or "").casefold()))
        relevance = len(terms.intersection(title_terms)) if terms else 0
        if terms and relevance == 0:
            continue
        enriched = dict(article)
        enriched["freshness_verified"] = published is not None
        ranked.append((relevance, published.timestamp() if published else 0.0, enriched))
    ranked.sort(key=lambda item: (item[0], item[1]), reverse=True)
    return [item[2] for item in ranked], stale_filtered


def _safe_article_url(value: Any) -> str | None:
    candidate = str(value or "").strip()
    parsed = urlparse(candidate)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return None
    return candidate


def _normalise_article(item: Any) -> dict[str, Any] | None:
    if not isinstance(item, dict):
        return None
    title = " ".join(str(item.get("title") or "").split()).strip()
    url = _safe_article_url(item.get("url"))
    if not title or not url:
        return None
    return {
        "title": title[:500],
        "url": url,
        "domain": str(item.get("domain") or urlparse(url).netloc).strip()[:200],
        "seen_date": str(item.get("seendate") or "").strip()[:40],
        "language": str(item.get("language") or "").strip()[:40],
        "source_country": str(item.get("sourcecountry") or "").strip()[:80],
        "image_url": _safe_article_url(item.get("socialimage")),
    }


def clear_news_cache() -> None:
    with _CACHE_LOCK:
        _CACHE.clear()


def _google_news_articles(
    client: Any,
    query: str,
    limit: int,
) -> list[dict[str, Any]]:
    response = client.get(
        GOOGLE_NEWS_RSS_URL,
        params={"q": query, "hl": "en-IN", "gl": "IN", "ceid": "IN:en"},
        headers={"User-Agent": "OMNI-JARVIS/0.1 read-only-market-research"},
        timeout=(3.05, 20),
    )
    response.raise_for_status()
    content = response.content
    if not content or len(content) > MAX_RSS_BYTES:
        raise ValueError("News RSS response was empty or too large.")
    root = ElementTree.fromstring(content)
    articles: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in root.findall("./channel/item"):
        title = " ".join(str(item.findtext("title") or "").split()).strip()
        url = _safe_article_url(item.findtext("link"))
        source_node = item.find("source")
        source_name = (
            " ".join(str(source_node.text or "").split()).strip()
            if source_node is not None
            else "Google News"
        )
        if not title or not url or url.casefold() in seen:
            continue
        seen.add(url.casefold())
        published = str(item.findtext("pubDate") or "").strip()
        try:
            seen_date = parsedate_to_datetime(published).astimezone(timezone.utc).isoformat()
        except (TypeError, ValueError, OverflowError):
            seen_date = published[:80]
        articles.append(
            {
                "title": title[:500],
                "url": url,
                "domain": source_name[:200],
                "seen_date": seen_date,
                "language": "English",
                "source_country": "India edition",
                "image_url": None,
            }
        )
        if len(articles) >= limit:
            break
    return articles


def search_market_news(
    query: str,
    *,
    limit: int = 10,
    timespan: str = "3d",
    session: Any = None,
) -> dict[str, Any]:
    clean_query = " ".join(str(query or "").split()).strip()
    if not clean_query or len(clean_query) > 200:
        raise ValueError("News query must contain between 1 and 200 characters.")
    if not 1 <= int(limit) <= 50:
        raise ValueError("News limit must be between 1 and 50.")
    if timespan not in {"1h", "6h", "12h", "1d", "3d", "7d", "1w", "1m"}:
        raise ValueError("Unsupported news timespan.")

    key = (clean_query.casefold(), int(limit), timespan)
    now = time.monotonic()
    with _CACHE_LOCK:
        cached = _CACHE.get(key)
        if cached and now - cached[0] < NEWS_CACHE_TTL_SECONDS:
            return cached[1]

    client = session or requests
    gdelt_failure: Exception | None = None
    try:
        response = client.get(
            GDELT_DOC_URL,
            params={
                "query": clean_query,
                "mode": "ArtList",
                "maxrecords": min(max(int(limit) * 3, 10), 50),
                "format": "json",
                "sort": "DateDesc",
                "timespan": timespan,
            },
            headers={"User-Agent": "OMNI-JARVIS/0.1 read-only-market-research"},
            timeout=(3.05, 12),
        )
        response.raise_for_status()
        raw = response.json()
        raw_articles = raw.get("articles", []) if isinstance(raw, dict) else []
        discovered: list[dict[str, Any]] = []
        seen: set[tuple[str, str]] = set()
        for item in raw_articles:
            article = _normalise_article(item)
            if article is None:
                continue
            if article["language"] and article["language"].casefold() != "english":
                continue
            identity = (article["url"].casefold(), article["title"].casefold())
            if identity in seen:
                continue
            seen.add(identity)
            discovered.append(article)
        articles, stale_filtered = _rank_fresh_articles(
            discovered, clean_query, timespan
        )
        articles = articles[: int(limit)]
        if articles:
            payload = {
                "success": True,
                "source": "GDELT_DOC_2",
                "query": clean_query,
                "count": len(articles),
                "articles": articles,
                "retrieved_at": _utc_now().isoformat(),
                "timespan": timespan,
                "freshness_enforced": True,
                "stale_filtered": stale_filtered,
                "message": f"Fresh source headlines discovered through GDELT DOC 2.0 ({timespan} window).",
            }
        else:
            gdelt_failure = ValueError("GDELT returned no matching English headlines.")
    except (requests.RequestException, ValueError, TypeError) as error:
        gdelt_failure = error

    if gdelt_failure is not None:
        try:
            discovered = _google_news_articles(
                client, clean_query, min(max(int(limit) * 5, 10), 50)
            )
            articles, stale_filtered = _rank_fresh_articles(
                discovered, clean_query, timespan
            )
            articles = articles[: int(limit)]
            payload = {
                "success": bool(articles),
                "source": "GOOGLE_NEWS_RSS",
                "query": clean_query,
                "count": len(articles),
                "articles": articles,
                "retrieved_at": _utc_now().isoformat(),
                "timespan": timespan,
                "freshness_enforced": True,
                "stale_filtered": stale_filtered,
                "message": (
                    f"Fresh headlines discovered through the Google News RSS fallback ({timespan} window)."
                    if articles
                    else "No matching English-language headlines were found."
                ),
            }
        except (
            requests.RequestException,
            ElementTree.ParseError,
            ValueError,
            TypeError,
            AttributeError,
        ) as error:
            payload = {
                "success": False,
                "source": "PUBLIC_NEWS",
                "query": clean_query,
                "count": 0,
                "articles": [],
                "retrieved_at": _utc_now().isoformat(),
                "timespan": timespan,
                "freshness_enforced": True,
                "stale_filtered": 0,
                "message": f"Market-news retrieval is temporarily unavailable ({type(error).__name__}).",
            }

    with _CACHE_LOCK:
        _CACHE[key] = (now, payload)
    return payload
