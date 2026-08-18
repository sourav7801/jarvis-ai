import unittest
from datetime import datetime, timezone
from unittest.mock import patch

import requests

from workstation import market_news


class FakeResponse:
    def __init__(self, payload=None, *, error=None, content=b""):
        self.payload = payload
        self.error = error
        self.content = content

    def raise_for_status(self):
        if self.error:
            raise self.error

    def json(self):
        return self.payload


class FakeSession:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return self.response


class SequenceSession:
    def __init__(self, responses):
        self.responses = list(responses)

    def get(self, _url, **_kwargs):
        return self.responses.pop(0)


class MarketNewsTests(unittest.TestCase):
    def setUp(self):
        market_news.clear_news_cache()
        self.clock = patch.object(
            market_news,
            "_utc_now",
            return_value=datetime(2026, 8, 16, 21, 0, tzinfo=timezone.utc),
        )
        self.clock.start()

    def tearDown(self):
        self.clock.stop()

    def test_gdelt_articles_are_filtered_and_normalised(self):
        session = FakeSession(
            FakeResponse(
                {
                    "articles": [
                        {
                            "title": "  Oil prices rise  ",
                            "url": "https://example.com/oil",
                            "domain": "example.com",
                            "language": "English",
                            "sourcecountry": "United Kingdom",
                            "seendate": "20260816T180000Z",
                        },
                        {
                            "title": "Not English",
                            "url": "https://example.org/other",
                            "language": "Spanish",
                        },
                        {
                            "title": "Unsafe link",
                            "url": "javascript:alert(1)",
                            "language": "English",
                        },
                    ]
                }
            )
        )

        result = market_news.search_market_news("crude oil", limit=10, session=session)

        self.assertTrue(result["success"])
        self.assertEqual(result["count"], 1)
        self.assertEqual(result["articles"][0]["title"], "Oil prices rise")
        self.assertEqual(session.calls[0][0], market_news.GDELT_DOC_URL)
        params = session.calls[0][1]["params"]
        self.assertEqual(params["query"], "crude oil")
        self.assertEqual(params["mode"], "ArtList")
        self.assertEqual(params["format"], "json")

    def test_network_failure_returns_safe_degraded_payload(self):
        session = FakeSession(
            FakeResponse({}, error=requests.ConnectionError("secret upstream detail"))
        )
        result = market_news.search_market_news("NIFTY", session=session)
        self.assertFalse(result["success"])
        self.assertEqual(result["articles"], [])
        self.assertNotIn("secret upstream detail", result["message"])

    def test_google_news_rss_is_used_when_gdelt_has_no_articles(self):
        rss = b"""<?xml version="1.0"?><rss><channel><item>
        <title>Crude oil market update - Example Wire</title>
        <link>https://news.google.com/rss/articles/example</link>
        <pubDate>Sun, 16 Aug 2026 18:00:00 GMT</pubDate>
        <source url="https://example.com">Example Wire</source>
        </item></channel></rss>"""
        session = SequenceSession(
            [FakeResponse({"articles": []}), FakeResponse(content=rss)]
        )
        result = market_news.search_market_news("crude oil", session=session)
        self.assertTrue(result["success"])
        self.assertEqual(result["source"], "GOOGLE_NEWS_RSS")
        self.assertEqual(result["count"], 1)
        self.assertEqual(result["articles"][0]["domain"], "Example Wire")

    def test_invalid_query_is_rejected(self):
        with self.assertRaises(ValueError):
            market_news.search_market_news("   ")

    def test_stale_articles_are_removed_even_if_feed_returns_them(self):
        session = FakeSession(
            FakeResponse(
                {
                    "articles": [
                        {
                            "title": "Fresh crude oil futures update",
                            "url": "https://example.com/fresh",
                            "language": "English",
                            "seendate": "20260816T180000Z",
                        },
                        {
                            "title": "Old crude oil futures report",
                            "url": "https://example.com/old",
                            "language": "English",
                            "seendate": "20260720T120000Z",
                        },
                    ]
                }
            )
        )
        result = market_news.search_market_news(
            "crude oil futures", limit=10, timespan="1d", session=session
        )
        self.assertEqual(result["count"], 1)
        self.assertEqual(result["articles"][0]["title"], "Fresh crude oil futures update")
        self.assertEqual(result["stale_filtered"], 1)
        self.assertTrue(result["freshness_enforced"])


if __name__ == "__main__":
    unittest.main()
