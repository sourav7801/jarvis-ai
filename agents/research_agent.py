from __future__ import annotations

import re
import threading
import time
from typing import Any


class ResearchAgent:
    """Bounded current-news facade for Master JARVIS.

    The primary path reuses workstation.market_news, which already provides
    GDELT first, Google News RSS fallback, freshness filtering, and caching.
    Web Intelligence is the independent second fallback.
    """

    FAILURE_TTL_SECONDS = 90.0

    def __init__(self):
        self.name = "research"
        self._lock = threading.RLock()
        self._last_failure: dict[str, Any] | None = None

    @staticmethod
    def requested_limit(text: str, default: int = 5) -> int:
        value = str(text or "").lower()
        words = {
            "one": 1,
            "two": 2,
            "three": 3,
            "four": 4,
            "five": 5,
            "six": 6,
            "seven": 7,
            "eight": 8,
            "nine": 9,
            "ten": 10,
        }
        match = re.search(
            r"\b(?:top|first|show|give|tell|list)\s+(?:me\s+)?"
            r"(\d+|one|two|three|four|five|six|seven|eight|nine|ten)\b",
            value,
        )
        if not match:
            return min(max(int(default), 1), 10)
        raw = match.group(1)
        count = int(raw) if raw.isdigit() else words.get(raw, default)
        return min(max(int(count), 1), 10)

    @staticmethod
    def normalize_news_query(text: str) -> str:
        value = " ".join(str(text or "").split()).strip()
        value = re.sub(
            r"^(?:can|could|would)\s+you\s+(?:please\s+)?",
            "",
            value,
            flags=re.IGNORECASE,
        )
        value = re.sub(
            r"^(?:tell|give|show|list)\s+(?:me\s+)?",
            "",
            value,
            flags=re.IGNORECASE,
        )
        value = re.sub(
            r"^top\s+(?:\d+|one|two|three|four|five|six|seven|eight|nine|ten)\s+",
            "",
            value,
            flags=re.IGNORECASE,
        )
        value = value.strip(" ?!.,:;-")
        if value.lower() in {
            "news",
            "latest news",
            "current news",
            "today news",
            "today's news",
        }:
            return "India world technology business latest news"
        return value or "India world technology business latest news"

    def _remember_failure(self, provider: str, detail: str) -> None:
        with self._lock:
            self._last_failure = {
                "provider": str(provider),
                "detail": str(detail),
                "recorded_at": time.time(),
            }

    def last_failure(self) -> dict[str, Any] | None:
        with self._lock:
            if not self._last_failure:
                return None
            payload = dict(self._last_failure)

        if time.time() - float(payload["recorded_at"]) > self.FAILURE_TTL_SECONDS:
            return None

        return payload

    @staticmethod
    def remove_duplicates(articles):
        seen = set()
        results = []

        for article in articles or []:
            if not isinstance(article, dict):
                continue

            title = " ".join(str(article.get("title") or "").split()).strip()
            url = str(article.get("url") or "").strip()
            key = (title.casefold(), url.casefold())

            if not title or key in seen:
                continue

            seen.add(key)
            results.append(dict(article))

        return results

    @staticmethod
    def format_news(articles, limit=10):
        chosen = list(articles or [])[: min(max(int(limit), 1), 10)]

        if not chosen:
            return (
                "I couldn't retrieve current news from the public providers right now. "
                "The Research Agent ran, but no verified headline source returned usable results."
            )

        lines = ["Here are the latest headlines:", ""]

        for index, article in enumerate(chosen, start=1):
            title = str(article.get("title") or "Unknown headline")
            source = (
                article.get("source")
                or article.get("domain")
                or article.get("provider")
                or ""
            )
            lines.append(
                f"{index}. {title}"
                + (f" ({source})" if source else "")
            )

        return "\n".join(lines)

    def _market_news_search(self, query: str, limit: int) -> dict[str, Any]:
        from workstation.market_news import search_market_news

        return search_market_news(
            query,
            limit=limit,
            timespan="3d",
        )

    def _web_fallback(self, request: str, limit: int) -> dict[str, Any]:
        from agents.web_intelligence_agent import WEB_INTELLIGENCE_AGENT

        return WEB_INTELLIGENCE_AGENT.research(
            f"top {limit} latest news {request}"
        )

    @staticmethod
    def _web_articles(payload: dict[str, Any], limit: int):
        output = []

        for item in list(payload.get("sources") or [])[:limit]:
            if not isinstance(item, dict):
                continue

            output.append(
                {
                    "title": item.get("title", ""),
                    "url": item.get("url", ""),
                    "source": item.get("provider", ""),
                    "published": item.get("retrieved_at", ""),
                }
            )

        return output

    def search_news(self, query, limit=8):
        clean = self.normalize_news_query(query)
        limit = min(max(int(limit), 1), 10)

        try:
            payload = self._market_news_search(clean, limit)
            articles = self.remove_duplicates(
                payload.get("articles", [])
            )[:limit]

            if payload.get("success") and articles:
                return {
                    "success": True,
                    "provider": payload.get("source", "PUBLIC_NEWS"),
                    "articles": articles,
                    "errors": [],
                }

            self._remember_failure(
                payload.get("source", "PUBLIC_NEWS"),
                payload.get("message", "No usable headlines."),
            )

        except Exception as exc:
            self._remember_failure(
                "PUBLIC_NEWS",
                f"{type(exc).__name__}: {exc}",
            )

        try:
            fallback = self._web_fallback(clean, limit)
            articles = self.remove_duplicates(
                self._web_articles(fallback, limit)
            )

            if fallback.get("success") and articles:
                return {
                    "success": True,
                    "provider": (
                        "+".join(fallback.get("providers", []))
                        or "WEB_INTELLIGENCE"
                    ),
                    "articles": articles,
                    "errors": list(fallback.get("errors", [])),
                }

            self._remember_failure(
                "WEB_INTELLIGENCE",
                fallback.get(
                    "notice",
                    "No fallback source returned usable results.",
                ),
            )

        except Exception as exc:
            self._remember_failure(
                "WEB_INTELLIGENCE",
                f"{type(exc).__name__}: {exc}",
            )

        return {
            "success": False,
            "provider": "PUBLIC_NEWS",
            "articles": [],
            "errors": [],
        }

    def market_news(self, limit=5):
        return self.search_news(
            "India Nifty Sensex US global stock markets",
            limit=limit,
        )

    def sports_news(self, limit=5):
        return self.search_news(
            "India cricket football tennis sports",
            limit=limit,
        )

    def general_news(self, limit=5):
        return self.search_news(
            "India world technology business latest news",
            limit=limit,
        )

    def research(self, query):
        query = str(query or "").strip()

        if not query:
            return {
                "success": False,
                "type": "research",
                "articles": [],
                "message": "No research topic was provided.",
            }

        value = query.lower()
        limit = self.requested_limit(query, 5)

        if any(
            word in value
            for word in (
                "market",
                "stock",
                "stocks",
                "nifty",
                "sensex",
                "trading",
                "finance",
                "financial",
            )
        ):
            result = self.market_news(limit)
            research_type = "market"

        elif any(
            word in value
            for word in (
                "sport",
                "sports",
                "cricket",
                "football",
                "soccer",
                "tennis",
                "nba",
                "f1",
            )
        ):
            result = self.sports_news(limit)
            research_type = "sports"

        else:
            result = self.search_news(query, limit=limit)
            research_type = "general"

        articles = result.get("articles", [])
        success = bool(result.get("success") and articles)
        message = self.format_news(articles, limit)

        if not success:
            failure = self.last_failure()

            if failure:
                message += (
                    "\n\nReason: the latest provider failure was "
                    f"{failure.get('provider')}: {failure.get('detail')}"
                )

        return {
            "success": success,
            "type": research_type,
            "provider": result.get("provider"),
            "articles": articles,
            "message": message,
            "last_failure": self.last_failure(),
        }


research_agent = ResearchAgent()


def research(query):
    return research_agent.research(query)


if __name__ == "__main__":
    print(research("top 3 news").get("message"))
