from __future__ import annotations

import unittest

from omni.venture_evidence_engine import (
    build_research_queries,
    run_venture_evidence_program,
)
from omni.venture_research_program import build_venture_research_program


class VentureEvidenceEngineTests(unittest.TestCase):
    def setUp(self):
        self.plan = {
            "id": "venture-1",
            "idea": "movable modular homes",
            "research_program": build_venture_research_program("movable modular homes"),
        }

    def test_queries_cover_every_track_and_global_radar(self):
        queries = build_research_queries(self.plan)
        self.assertEqual(len(queries), 9)
        self.assertEqual(queries[-1]["track_id"], "OPPORTUNITY_RADAR")
        self.assertTrue(all("research" in item["query"].lower() for item in queries))

    def test_deduplicates_sources_and_labels_snippets_as_discovery_only(self):
        def research(query: str):
            return {
                "providers": ["PUBLIC_SEARCH"],
                "notice": "bounded public research",
                "sources": [
                    {
                        "url": "https://example.com/evidence",
                        "title": "Evidence",
                        "excerpt": "Retrieved evidence text",
                        "provider": "DIRECT_WEBSITE",
                        "read_status": "EXTRACTED",
                    },
                    {
                        "url": "https://example.com/lead",
                        "title": "Lead",
                        "excerpt": "Search snippet",
                        "provider": "SEARCH",
                        "read_status": "SEARCH_SNIPPET",
                    },
                ],
            }

        result = run_venture_evidence_program(self.plan, research)
        self.assertEqual(result["source_count"], 2)
        self.assertEqual(result["retrieved_text_sources"], 1)
        self.assertEqual(result["discovery_leads"], 1)
        self.assertEqual(result["covered_tracks"], 9)
        self.assertFalse(result["external_actions_executed"])
        lead = next(item for item in result["sources"] if item["url"].endswith("lead"))
        self.assertEqual(lead["evidence_grade"], "DISCOVERY_LEAD")

    def test_provider_failures_are_isolated_as_evidence_gaps(self):
        result = run_venture_evidence_program(
            self.plan,
            lambda _query: (_ for _ in ()).throw(TimeoutError("offline")),
        )
        self.assertEqual(result["status"], "DEGRADED_NO_CITABLE_EVIDENCE")
        self.assertTrue(all(item["status"] == "FAILED_SAFE" for item in result["tracks"]))


if __name__ == "__main__":
    unittest.main()
