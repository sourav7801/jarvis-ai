from __future__ import annotations

import unittest

from agents.research_agent import ResearchAgent
from workstation.market_news import _query_terms


class NewsQualityV11Tests(unittest.TestCase):
    def test_natural_top_world_news_query_is_normalized(self):
        self.assertEqual(
            ResearchAgent.normalize_news_query(
                "You give me Top 10 news today in the world."
            ),
            "world news",
        )

    def test_polite_top_world_news_query_is_normalized(self):
        self.assertEqual(
            ResearchAgent.normalize_news_query(
                "Can you tell me the top 3 latest world news?"
            ),
            "world news",
        )

    def test_wikipedia_is_never_presented_as_current_news(self):
        payload = {
            "sources": [
                {
                    "title": "News",
                    "url": "https://en.wikipedia.org/wiki/News",
                    "provider": "WIKIPEDIA",
                },
                {
                    "title": "Real current result",
                    "url": "https://example.com/current",
                    "provider": "CURRENT_NEWS",
                },
            ]
        }
        articles = ResearchAgent._web_articles(payload, 10)
        self.assertEqual(len(articles), 1)
        self.assertEqual(articles[0]["source"], "CURRENT_NEWS")

    def test_world_is_not_required_in_every_headline(self):
        self.assertEqual(_query_terms("world news"), set())


if __name__ == "__main__":
    unittest.main()
