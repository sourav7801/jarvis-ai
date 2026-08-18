import unittest

from omni.web_research import WebDocument
from workstation import news_briefing


class FakeRetriever:
    def __init__(self, document):
        self.document = document
        self.urls = []

    def fetch(self, url):
        self.urls.append(url)
        return self.document


class NewsBriefingTests(unittest.TestCase):
    def setUp(self):
        news_briefing.clear_latest_news()
        news_briefing.remember_news(
            {
                "success": True,
                "query": "crude oil",
                "articles": [
                    {
                        "title": "Oil prices rise after supply disruption",
                        "url": "https://example.com/oil",
                        "domain": "Example Wire",
                    },
                    {
                        "title": "India reviews energy import costs",
                        "url": "https://news.google.com/rss/articles/example",
                        "domain": "Example Business",
                    },
                ],
            }
        )

    def tearDown(self):
        news_briefing.clear_latest_news()

    def test_followup_parser_resolves_ordinal(self):
        parsed = news_briefing.parse_news_followup("ok read first one what inside")
        self.assertEqual(parsed, {"index": 1, "limit": 1})

    def test_top_headline_briefing_is_bounded(self):
        result = news_briefing.build_news_briefing(limit=2)
        self.assertTrue(result["success"])
        self.assertEqual(len(result["articles"]), 2)
        self.assertIn("top 2", result["speech"])
        self.assertEqual(result["detail_level"], "HEADLINE_METADATA")

    def test_selected_direct_article_uses_bounded_extract(self):
        document = WebDocument(
            url="https://example.com/oil",
            retrieved_at="2026-08-17T00:00:00+00:00",
            status=200,
            content_type="text/html",
            title="Oil prices rise",
            text=(
                "Oil prices rose after a supply disruption affected regional shipments. "
                "Traders monitored the restoration timeline and changes in available inventory."
            ),
            checksum="abc",
            byte_count=200,
        )
        retriever = FakeRetriever(document)
        result = news_briefing.build_news_briefing(index=1, retriever=retriever)
        self.assertEqual(result["detail_level"], "ARTICLE_EXTRACT")
        self.assertIn("short extractive briefing", result["speech"])
        self.assertEqual(retriever.urls, ["https://example.com/oil"])

    def test_aggregator_result_does_not_invent_article_content(self):
        result = news_briefing.build_news_briefing(index=2)
        self.assertEqual(result["detail_level"], "HEADLINE_METADATA")
        self.assertIn("will not invent", result["speech"])


if __name__ == "__main__":
    unittest.main()
