"""Contextual, bounded spoken briefings for the workstation news surface."""

from __future__ import annotations

import re
import threading
from typing import Any
from urllib.parse import urlsplit

from omni.web_research import GovernedWebRetriever, WebPolicy


_LATEST_LOCK = threading.RLock()
_LATEST_NEWS: dict[str, Any] = {}
_ORDINALS = {
    "first": 1,
    "one": 1,
    "second": 2,
    "two": 2,
    "third": 3,
    "three": 3,
    "fourth": 4,
    "four": 4,
    "fifth": 5,
    "five": 5,
    "sixth": 6,
    "six": 6,
    "seventh": 7,
    "seven": 7,
    "eighth": 8,
    "eight": 8,
    "ninth": 9,
    "nine": 9,
    "tenth": 10,
    "ten": 10,
}


def remember_news(payload: dict[str, Any]) -> None:
    if not payload.get("success") or not payload.get("articles"):
        return
    with _LATEST_LOCK:
        _LATEST_NEWS.clear()
        _LATEST_NEWS.update(payload)


def latest_news() -> dict[str, Any]:
    with _LATEST_LOCK:
        return {
            **_LATEST_NEWS,
            "articles": [dict(item) for item in _LATEST_NEWS.get("articles", [])],
        }


def clear_latest_news() -> None:
    with _LATEST_LOCK:
        _LATEST_NEWS.clear()


def parse_news_followup(text: str) -> dict[str, int | None] | None:
    value = " ".join(str(text or "").lower().split())
    if not any(
        marker in value
        for marker in (
            "read",
            "inside",
            "summarize",
            "summary",
            "brief this",
            "brief it",
            "what does it say",
            "what is in",
            "what's in",
        )
    ):
        return None

    for word, index in _ORDINALS.items():
        if re.search(rf"\b{word}\b", value):
            return {"index": index, "limit": 1}
    numeric = re.search(r"\b(?:item|story|headline|number)\s*(\d{1,2})\b", value)
    if numeric:
        return {"index": int(numeric.group(1)), "limit": 1}
    top = re.search(r"\btop\s+(\d{1,2})\b", value)
    if top:
        return {"index": None, "limit": min(max(int(top.group(1)), 1), 10)}
    if "all" in value:
        return {"index": None, "limit": 10}
    return {"index": None, "limit": 5}


def _meaningful_excerpt(text: str, title: str) -> str:
    cleaned = " ".join(str(text or "").split())
    if not cleaned:
        return ""
    candidates = re.split(r"(?<=[.!?])\s+", cleaned)
    selected: list[str] = []
    total = 0
    title_words = set(re.findall(r"[a-z]{4,}", title.lower()))
    for sentence in candidates:
        value = sentence.strip()
        lower = value.lower()
        if not 45 <= len(value) <= 320:
            continue
        if any(
            noise in lower
            for noise in (
                "accept cookies",
                "privacy policy",
                "all rights reserved",
                "sign in",
                "subscribe now",
                "javascript",
            )
        ):
            continue
        words = set(re.findall(r"[a-z]{4,}", lower))
        if title_words and not words.intersection(title_words) and selected:
            continue
        if total + len(value) > 600:
            break
        selected.append(value)
        total += len(value)
        if len(selected) == 3:
            break
    return " ".join(selected)


def _article_excerpt(
    article: dict[str, Any],
    retriever: GovernedWebRetriever | None,
) -> tuple[str, str]:
    url = str(article.get("url") or "")
    host = (urlsplit(url).hostname or "").lower()
    if not url or host == "news.google.com" or host.endswith(".news.google.com"):
        return "", "HEADLINE_METADATA"
    client = retriever or GovernedWebRetriever(
        WebPolicy(max_response_bytes=1_000_000, timeout_seconds=12)
    )
    try:
        document = client.fetch(url)
        return _meaningful_excerpt(document.text, str(article.get("title") or "")), "ARTICLE_EXTRACT"
    except Exception:
        return "", "HEADLINE_METADATA"


def build_news_briefing(
    *,
    index: int | None = None,
    limit: int = 5,
    retriever: GovernedWebRetriever | None = None,
) -> dict[str, Any]:
    payload = latest_news()
    articles = payload.get("articles", [])
    if not articles:
        return {
            "success": False,
            "action": "news_briefing",
            "speech": "I do not have a current headline list yet. Ask me to find the latest news first.",
            "articles": [],
        }

    if index is not None:
        if index < 1 or index > len(articles):
            return {
                "success": False,
                "action": "news_briefing",
                "speech": f"I only have {len(articles)} current headlines, so story {index} is unavailable.",
                "articles": [],
            }
        article = articles[index - 1]
        excerpt, detail_level = _article_excerpt(article, retriever)
        source = str(article.get("domain") or "the listed source")
        title = str(article.get("title") or "Untitled headline")
        if excerpt:
            speech = (
                f"Story {index}, from {source}. {title}. "
                f"Here is a short extractive briefing from the article: {excerpt} "
                "Please open the linked source to verify the full context."
            )
        else:
            speech = (
                f"Story {index}, from {source}. {title}. "
                "This public feed exposes headline metadata but not reliable article text. "
                "I will not invent what is inside; open the linked source for the full report."
            )
        return {
            "success": True,
            "action": "news_briefing",
            "mode": "selected",
            "detail_level": detail_level,
            "speech": speech,
            "articles": [article],
        }

    chosen = articles[: min(max(int(limit), 1), 10)]
    parts = [
        f"{position}. {item.get('title', 'Untitled headline')}. Source: {item.get('domain', 'unknown source')}."
        for position, item in enumerate(chosen, 1)
    ]
    speech = (
        f"Here is your top {len(chosen)} current headline briefing for "
        f"{payload.get('query', 'the market')}. "
        + " ".join(parts)
        + " These are headline summaries, not trading signals. Verify the linked reports before acting."
    )
    return {
        "success": True,
        "action": "news_briefing",
        "mode": "headlines",
        "detail_level": "HEADLINE_METADATA",
        "speech": speech,
        "articles": chosen,
    }
