import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from agents.universal_operator_agent import is_operator_request, operator
from agents.web_intelligence_agent import (
    WebIntelligenceAgent,
    _extract_query,
    _requested_limit,
    is_web_request,
)
from omni.web_research import WebDocument
from omni.agent_registry import AgentResponse, AgentStatus
from workstation import app


class FakeRetriever:
    def __init__(self, documents=None, error=None):
        self.documents = documents or {}
        self.error = error
        self.calls = []

    def fetch(self, url):
        self.calls.append(url)
        if self.error:
            raise self.error
        return self.documents[url]


class FakeBrave:
    def __init__(self, results=None, configured=True):
        self.results = results or []
        self.configured = configured
        self.calls = []

    def search(self, query, limit=8):
        self.calls.append((query, limit))
        return self.results[:limit]


class FakeWikipedia:
    def __init__(self, results=None):
        self.results = results or []
        self.calls = []

    def search(self, query, limit=6):
        self.calls.append((query, limit))
        return self.results[:limit]


class FakeFirecrawl:
    def __init__(self, results=None, error=None):
        self.results = results or []
        self.error = error
        self.calls = []

    def search(self, query, limit=8):
        self.calls.append((query, limit))
        if self.error:
            raise self.error
        return self.results[:limit]


class FakeOfficialRankings:
    def __init__(self, result=None):
        self.result = result
        self.calls = []

    def search(self, query, limit=5):
        self.calls.append((query, limit))
        return self.result


def document(url, title="Evidence", text="Verified public evidence about the requested topic."):
    return WebDocument(url, "2026-08-17T00:00:00+00:00", 200, "text/html", title, text, "a" * 64, 100)


class WebIntelligenceAgentTests(unittest.TestCase):
    def test_web_request_detection_is_explicit(self):
        self.assertTrue(is_web_request("search the web for safe AI"))
        self.assertTrue(is_web_request("search top 2 iim india"))
        self.assertTrue(is_web_request("read https://example.com/report"))
        self.assertTrue(
            is_web_request("Can you search on LinkedIn? Rishabh Goswami SMS 2025")
        )
        self.assertTrue(is_web_request("The best song trending currently on Webber"))
        self.assertFalse(is_web_request("find files in my downloads folder"))
        self.assertEqual(_extract_query("Jarvis, search the web for safe AI"), "safe AI")
        self.assertEqual(_extract_query("search top 2 iim india"), "iim india")
        self.assertEqual(
            _extract_query("Can you search on LinkedIn? Rishabh Goswami SMS 2025"),
            "Rishabh Goswami SMS 2025 LinkedIn",
        )
        self.assertEqual(
            _extract_query("Hi Jarvis, can you search on LinkedIn? Rishabh Goswami SMS 2025"),
            "Rishabh Goswami SMS 2025 LinkedIn",
        )
        self.assertEqual(_requested_limit("search top two IIM India"), 2)

    def test_direct_public_url_is_extracted_cited_and_persisted(self):
        url = "https://example.com/report"
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / "web.json"
            agent = WebIntelligenceAgent(
                state_path=state,
                retriever=FakeRetriever({url: document(url)}),
                brave=FakeBrave(configured=False),
                wikipedia=FakeWikipedia(),
            )
            with patch("agents.web_intelligence_agent.audit_event"):
                result = agent.research(f"read this website {url}")
            self.assertTrue(result["success"])
            self.assertEqual(result["mode"], "READ_URL")
            self.assertEqual(result["sources"][0]["checksum"], "a" * 64)
            self.assertEqual(result["sources"][0]["read_status"], "EXTRACTED")
            self.assertIn(url, result["message"])

            reloaded = WebIntelligenceAgent(
                state_path=state,
                retriever=FakeRetriever(),
                brave=FakeBrave(configured=False),
                wikipedia=FakeWikipedia(),
            )
            self.assertEqual(reloaded.snapshot()["latest"]["query"], result["query"])
            self.assertEqual(
                reloaded.snapshot()["recent_results"][0]["sources"][0]["url"],
                url,
            )

    def test_brave_search_reads_top_page_and_labels_remaining_snippet(self):
        first = "https://one.example/report"
        second = "https://two.example/summary"
        brave = FakeBrave(
            [
                {"title": "One", "url": first, "excerpt": "One snippet", "provider": "BRAVE_SEARCH"},
                {"title": "Two", "url": second, "excerpt": "Two snippet", "provider": "BRAVE_SEARCH"},
            ]
        )
        retriever = FakeRetriever({first: document(first, "One"), second: document(second, "Two")})
        with tempfile.TemporaryDirectory() as directory:
            agent = WebIntelligenceAgent(
                Path(directory) / "web.json", retriever, brave, FakeWikipedia()
            )
            with patch("agents.web_intelligence_agent.audit_event"):
                result = agent.research("search the web for governed AI agents")
        self.assertTrue(result["broad_search_configured"])
        self.assertEqual(result["providers"], ["BRAVE_SEARCH"])
        self.assertEqual(len(result["sources"]), 2)
        self.assertTrue(all(item["read_status"] == "EXTRACTED" for item in result["sources"]))

    def test_keyless_mode_combines_wikipedia_and_current_news(self):
        wikipedia = FakeWikipedia(
            [{"title": "AI", "url": "https://en.wikipedia.org/wiki/AI", "excerpt": "AI overview", "provider": "WIKIPEDIA"}]
        )

        def news(_query, limit, timespan):
            self.assertEqual(timespan, "3d")
            return {
                "source": "TEST_NEWS",
                "articles": [{"title": "Latest AI", "url": "https://news.example/ai", "seen_date": "20260817T000000Z"}][:limit],
            }

        with tempfile.TemporaryDirectory() as directory:
            agent = WebIntelligenceAgent(
                Path(directory) / "web.json",
                FakeRetriever(),
                FakeBrave(configured=False),
                wikipedia,
                firecrawl=FakeFirecrawl(),
                news_search=news,
            )
            with patch("agents.web_intelligence_agent.audit_event"):
                result = agent.research("search online for latest AI updates")
        self.assertEqual(result["providers"], ["WIKIPEDIA", "CURRENT_NEWS"])
        self.assertEqual(len(result["sources"]), 2)
        self.assertFalse(result["broad_search_configured"])
        self.assertIn("fell back", result["notice"])

    def test_keyless_broad_search_honors_requested_result_count(self):
        firecrawl = FakeFirecrawl(
            [
                {"title": "One", "url": "https://one.example", "excerpt": "First", "provider": "FIRECRAWL_FREE"},
                {"title": "Two", "url": "https://two.example", "excerpt": "Second", "provider": "FIRECRAWL_FREE"},
                {"title": "Three", "url": "https://three.example", "excerpt": "Third", "provider": "FIRECRAWL_FREE"},
            ]
        )
        with tempfile.TemporaryDirectory() as directory:
            agent = WebIntelligenceAgent(
                Path(directory) / "web.json",
                FakeRetriever(error=PermissionError("snippet only")),
                FakeBrave(configured=False),
                FakeWikipedia(),
                firecrawl=firecrawl,
                official_rankings=FakeOfficialRankings(),
            )
            with patch("agents.web_intelligence_agent.audit_event"):
                result = agent.research("search top 2 governed AI agents")
        self.assertEqual(result["query"], "governed AI agents")
        self.assertEqual(result["requested_limit"], 2)
        self.assertEqual(len(result["sources"]), 2)
        self.assertEqual(result["providers"], ["FIRECRAWL_FREE"])
        self.assertEqual(firecrawl.calls, [("governed AI agents", 2)])

    def test_official_ranking_vertical_preempts_generic_search(self):
        official = FakeOfficialRankings(
            {
                "year": 2025,
                "answer": "According to NIRF 2025: 1. IIM Ahmedabad; 2. IIM Bangalore.",
                "sources": [
                    {"title": "#1 IIM Ahmedabad", "url": "https://nirf.example/1", "excerpt": "Rank 1", "provider": "NIRF_GOV_IN"},
                    {"title": "#2 IIM Bangalore", "url": "https://nirf.example/2", "excerpt": "Rank 2", "provider": "NIRF_GOV_IN"},
                ],
            }
        )
        firecrawl = FakeFirecrawl()
        with tempfile.TemporaryDirectory() as directory:
            agent = WebIntelligenceAgent(
                Path(directory) / "web.json",
                FakeRetriever(),
                FakeBrave(configured=False),
                FakeWikipedia(),
                firecrawl=firecrawl,
                official_rankings=official,
            )
            with patch("agents.web_intelligence_agent.audit_event"):
                result = agent.research("search top 2 iim india")
        self.assertEqual(result["mode"], "OFFICIAL_RANKING")
        self.assertEqual(result["requested_limit"], 2)
        self.assertEqual(result["providers"], ["NIRF_GOV_IN"])
        self.assertIn("IIM Ahmedabad", result["message"])
        self.assertEqual(firecrawl.calls, [])

    def test_blocked_or_unreadable_url_degrades_without_inventing_content(self):
        with tempfile.TemporaryDirectory() as directory:
            agent = WebIntelligenceAgent(
                Path(directory) / "web.json",
                FakeRetriever(error=PermissionError("blocked")),
                FakeBrave(configured=False),
                FakeWikipedia(),
            )
            with patch("agents.web_intelligence_agent.audit_event"):
                result = agent.research("read https://private.example/secret")
        self.assertFalse(result["success"])
        self.assertEqual(result["sources"], [])
        self.assertIn("PermissionError", result["errors"][0])
        self.assertNotIn("secret contents", result["message"].lower())

    def test_selected_profile_assessment_is_job_relevant_and_not_a_hiring_verdict(self):
        url = "https://example.com/public-profile"
        source = {
            "title": "Candidate - Strategy Consultant and MBA",
            "url": url,
            "excerpt": "Public profile claims strategy consulting and MBA experience.",
            "provider": "TEST_SEARCH",
        }
        with tempfile.TemporaryDirectory() as directory:
            agent = WebIntelligenceAgent(
                Path(directory) / "web.json",
                FakeRetriever(
                    {
                        url: document(
                            url,
                            "Candidate - Strategy Consultant and MBA",
                            "Professional profile describing strategy consulting and MBA education.",
                        )
                    }
                ),
                FakeBrave(configured=False),
                FakeWikipedia(),
            )
            with patch("agents.web_intelligence_agent.audit_event"):
                result = agent.assess_source(
                    source,
                    "analyze this first profile for my company",
                    selection_index=1,
                    origin_query="candidate linkedin",
                )
        self.assertEqual(result["mode"], "SOURCE_ASSESSMENT")
        self.assertEqual(result["assessment"]["verdict"], "ROLE_SPECIFIC_EVIDENCE_REQUIRED")
        self.assertEqual(result["assessment"]["prohibited_inferences"], "PROTECTED_TRAITS_NOT_USED")
        self.assertIn("not enough verified", result["answer"])
        self.assertEqual(result["sources"][0]["url"], url)

    def test_workstation_web_context_uses_web_agent_and_opens_web_page(self):
        research = {
            "success": True,
            "action": "open_web",
            "query": "safe AI",
            "sources": [{"title": "Evidence", "url": "https://example.com"}],
            "answer": "I found the direct answer.",
            "message": "One cited source found.",
        }
        response = AgentResponse(
            AgentStatus.SUCCEEDED,
            "web_intelligence",
            research["message"],
            "test-correlation",
            data=research,
        )
        with (
            patch.object(app.jarvis_main.AGENT_REGISTRY, "execute", return_value=response) as execute,
            patch.object(app.WEB_INTELLIGENCE_AGENT, "snapshot", return_value={"latest": research}),
            patch.object(app, "audit_event"),
        ):
            result = app.execute_command("search the web for safe AI", "web")
        self.assertEqual(result["action"], "open_web")
        self.assertEqual(result["source"], "web_intelligence")
        self.assertEqual(result["query"], "safe AI")
        self.assertEqual(result["speech"], "I found the direct answer.")
        self.assertNotIn("routed_context", result)
        self.assertEqual(execute.call_args.args[0].agent, "web_intelligence")


class UniversalOperatorTests(unittest.TestCase):
    def test_operator_request_is_explicit(self):
        self.assertTrue(is_operator_request("Operator: build this secure product"))
        self.assertTrue(is_operator_request("Handle this end-to-end and verify it"))
        self.assertFalse(is_operator_request("hello Jarvis"))

    def test_operator_has_broad_plan_and_fail_closed_contract(self):
        result = operator("Operator: build an accessible local dashboard")
        self.assertTrue(result["success"])
        self.assertEqual(result["operating_contract"]["live_trading"], "DISABLED")
        self.assertEqual(
            result["operating_contract"]["consequential_external_work"],
            "EXPLICIT_APPROVAL_REQUIRED",
        )
        self.assertEqual(len(result["deliverable"]["recommended_sequence"]), 5)


if __name__ == "__main__":
    unittest.main()
