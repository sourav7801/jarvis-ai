from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import patch

from agents.research_agent import ResearchAgent
from omni.conversation_turns import ConversationTurns


class ConversationTurnsV1Tests(unittest.TestCase):
    def test_why_uses_previous_turn(self):
        context = ConversationTurns()
        context.remember(
            "Can you tell me top 3 news?",
            "I couldn't retrieve current news right now.",
            "MASTER_JARVIS",
        )
        value = context.augment("Why?")
        self.assertIn("Previous user request:", value)
        self.assertIn("top 3 news", value.lower())
        self.assertIn("Current user follow-up: Why?", value)

    def test_song_selection_uses_previous_turn(self):
        context = ConversationTurns()
        context.remember(
            "Suggest Hindi songs",
            "1. Lag Jaa Gale\n2. Another song",
            "MASTER_JARVIS",
        )
        value = context.augment("Lag JA Gale.")
        self.assertIn("Lag Jaa Gale", value)
        self.assertIn("Current user follow-up: Lag JA Gale.", value)

    def test_explicit_command_is_not_augmented(self):
        context = ConversationTurns()
        context.remember("hello", "hello", "MASTER_JARVIS")
        self.assertEqual(context.augment("open notepad"), "open notepad")


class ResearchAgentV2Tests(unittest.TestCase):
    def test_top_three_limit(self):
        agent = ResearchAgent()
        self.assertEqual(
            agent.requested_limit("Can you tell me top 3 News?", 5),
            3,
        )

    def test_primary_provider_success(self):
        agent = ResearchAgent()
        payload = {
            "success": True,
            "source": "GDELT_DOC_2",
            "articles": [
                {"title": "A", "url": "https://a.example"},
                {"title": "B", "url": "https://b.example"},
                {"title": "C", "url": "https://c.example"},
            ],
        }

        with patch.object(agent, "_market_news_search", return_value=payload):
            result = agent.search_news("top 3 news", limit=3)

        self.assertTrue(result["success"])
        self.assertEqual(result["provider"], "GDELT_DOC_2")
        self.assertEqual(len(result["articles"]), 3)

    def test_web_fallback_success(self):
        agent = ResearchAgent()

        primary = {
            "success": False,
            "source": "PUBLIC_NEWS",
            "message": "temporarily unavailable",
            "articles": [],
        }

        fallback = {
            "success": True,
            "providers": ["FIRECRAWL_FREE"],
            "sources": [
                {
                    "title": "Fallback headline",
                    "url": "https://example.com/story",
                    "provider": "FIRECRAWL_FREE",
                }
            ],
            "errors": [],
        }

        with (
            patch.object(agent, "_market_news_search", return_value=primary),
            patch.object(agent, "_web_fallback", return_value=fallback),
        ):
            result = agent.search_news("latest news", limit=3)

        self.assertTrue(result["success"])
        self.assertEqual(len(result["articles"]), 1)
        self.assertIn("FIRECRAWL_FREE", result["provider"])

    def test_failure_reason_is_preserved(self):
        agent = ResearchAgent()

        with (
            patch.object(
                agent,
                "_market_news_search",
                return_value={
                    "success": False,
                    "source": "PUBLIC_NEWS",
                    "message": "HTTP 503",
                    "articles": [],
                },
            ),
            patch.object(
                agent,
                "_web_fallback",
                side_effect=RuntimeError("fallback unavailable"),
            ),
        ):
            result = agent.research("top 3 news")

        self.assertFalse(result["success"])
        self.assertIn("Reason:", result["message"])
        self.assertIn("WEB_INTELLIGENCE", result["message"])


class StartupProfilerV1Tests(unittest.TestCase):
    def test_profiler_markers(self):
        source = Path("start_jarvis_v3.py").read_text(encoding="utf-8")
        for marker in (
            'stage("main import")',
            'stage("protected core verification")',
            'stage("trading safety status")',
            'stage("workspace server import")',
            'stage("HTTP server creation")',
            'stage("CORE READY")',
        ):
            self.assertIn(marker, source)


if __name__ == "__main__":
    unittest.main()
