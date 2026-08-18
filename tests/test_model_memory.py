import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from omni.audit import AuditStore
from omni.hybrid_memory import HybridMemory, SemanticHit
from omni.model_router import (
    ModelProfile,
    ModelRequest,
    ModelRouter,
    ModelTier,
    PrivacyLevel,
)


class ModelRouterTests(unittest.TestCase):
    def profiles(self):
        return (
            ModelProfile(
                "local-small",
                "ollama",
                "small",
                ModelTier.REFLEX,
                8_000,
                500,
                True,
                frozenset({"chat"}),
            ),
            ModelProfile(
                "local-reasoning",
                "ollama",
                "reasoning",
                ModelTier.REASONING,
                32_000,
                3_000,
                True,
                frozenset({"chat", "coding"}),
            ),
            ModelProfile(
                "cloud-frontier",
                "cloud",
                "frontier",
                ModelTier.FRONTIER,
                100_000,
                2_000,
                False,
                frozenset({"chat", "coding"}),
            ),
        )

    def test_selects_lowest_capable_local_tier(self):
        with patch("omni.model_router.audit_event"):
            decision = ModelRouter(self.profiles()).route(
                ModelRequest(
                    "code",
                    minimum_tier=ModelTier.REASONING,
                    required_context_tokens=16_000,
                    required_capabilities=frozenset({"coding"}),
                )
            )
        self.assertEqual(decision.profile.id, "local-reasoning")

    def test_local_privacy_excludes_cloud(self):
        with patch("omni.model_router.audit_event"):
            decision = ModelRouter(self.profiles()).route(
                ModelRequest(
                    "large-private",
                    required_context_tokens=90_000,
                    privacy=PrivacyLevel.LOCAL_ONLY,
                )
            )
        self.assertIsNone(decision.profile)

    def test_latency_constraint_can_fail_closed(self):
        with patch("omni.model_router.audit_event"):
            decision = ModelRouter(self.profiles()).route(
                ModelRequest(
                    "fast-code",
                    minimum_tier=ModelTier.REASONING,
                    maximum_latency_ms=1_000,
                    required_capabilities=frozenset({"coding"}),
                )
            )
        self.assertIsNone(decision.profile)


class FakeSemantic:
    def __init__(self, hits):
        self.hits = hits

    def search(self, _query, _limit):
        return self.hits


class HybridMemoryTests(unittest.TestCase):
    def test_lexical_search_and_upsert(self):
        with tempfile.TemporaryDirectory() as directory:
            memory = HybridMemory(Path(directory) / "memory.sqlite3")
            record = memory.remember(
                "NIFTY research requires deterministic replay",
                tags=("trading", "research"),
                record_id="one",
            )
            self.assertEqual(memory.count(), 1)
            self.assertEqual(memory.search("deterministic replay")[0].record, record)

            memory.remember(
                "NIFTY research requires walk forward validation",
                tags=("trading",),
                record_id="one",
            )
            self.assertEqual(memory.search("replay"), [])
            self.assertEqual(memory.search("validation")[0].record.id, "one")

    def test_semantic_and_lexical_results_are_fused(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "memory.sqlite3"
            memory = HybridMemory(path)
            memory.remember("portfolio exposure limits", record_id="risk")
            memory.remember("voice interface", record_id="voice")
            fused = HybridMemory(path, FakeSemantic([SemanticHit("voice", 0.9)]))

            hits = fused.search("portfolio exposure")
            self.assertEqual({hit.record.id for hit in hits}, {"risk", "voice"})
            self.assertIsNotNone(next(hit for hit in hits if hit.record.id == "risk").lexical_rank)
            self.assertIsNotNone(next(hit for hit in hits if hit.record.id == "voice").semantic_rank)

    def test_event_search_is_structured(self):
        with tempfile.TemporaryDirectory() as directory:
            store = AuditStore(Path(directory) / "audit.sqlite3")
            store.record_event("tool", "current_time", "SUCCEEDED")
            store.record_event("router", "department", "SUCCEEDED")
            events = store.search_events("tool")
            self.assertEqual(len(events), 1)
            self.assertEqual(events[0]["name"], "current_time")


if __name__ == "__main__":
    unittest.main()
