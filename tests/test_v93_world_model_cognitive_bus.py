from __future__ import annotations

from datetime import datetime, timedelta, timezone
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from omni.cognitive_event_bus import CognitiveEventBus, CognitiveEventType
from omni.world_model import WorldStateGraph
from workstation.market_data_contract import MarketEventType, canonical_market_event


class CognitiveEventBusTests(unittest.TestCase):
    def test_typed_event_is_persistent_bounded_and_safe(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "events.json"
            bus = CognitiveEventBus(path, capacity=50, persist=True)
            result = bus.publish(
                CognitiveEventType.MISSION_CREATED,
                source="test",
                subject="mission-1",
                payload={"status": "READY"},
                provenance={"source": "unit-test"},
            )
            self.assertTrue(result["accepted"])
            self.assertFalse(result["live_execution"])
            self.assertFalse(result["automatic_broker_order"])
            reloaded = CognitiveEventBus(path, capacity=50, persist=True)
            snapshot = reloaded.snapshot()
            self.assertEqual(snapshot["retained"], 1)
            self.assertEqual(snapshot["events"][0]["event_type"], "MISSION_CREATED")
            self.assertEqual(snapshot["events"][0]["payload"]["status"], "READY")
            self.assertEqual(snapshot["external_actions"], "APPROVAL_GATED")

    def test_subscriber_failure_is_isolated(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            bus = CognitiveEventBus(Path(folder) / "events.json", persist=False)
            delivered = []
            bus.subscribe("good", lambda event: delivered.append(event.event_type))
            bus.subscribe("bad", lambda _event: (_ for _ in ()).throw(RuntimeError("boom")))
            result = bus.publish(
                CognitiveEventType.TEST_PASSED,
                source="tests",
                subject="suite",
                payload={"count": 12},
                provenance={"verified": True},
            )
            self.assertEqual(result["delivered"], 1)
            self.assertEqual(result["subscriber_errors"], 1)
            self.assertEqual(delivered, ["TEST_PASSED"])

    def test_capacity_is_bounded(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            bus = CognitiveEventBus(Path(folder) / "events.json", capacity=50, persist=False)
            for index in range(75):
                bus.publish(
                    CognitiveEventType.WORLD_STATE_UPDATED,
                    source="test",
                    subject=f"node-{index}",
                    payload={"index": index},
                    provenance={"test": True},
                )
            snapshot = bus.snapshot(limit=100)
            self.assertEqual(snapshot["retained"], 50)
            self.assertEqual(len(snapshot["events"]), 50)
            self.assertEqual(snapshot["published"], 75)


class WorldStateGraphTests(unittest.TestCase):
    def test_freshness_and_provenance_are_explicit(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            world = WorldStateGraph(Path(folder) / "world.json")
            old = (datetime.now(timezone.utc) - timedelta(seconds=30)).isoformat()
            world.observe(
                "service:test",
                kind="SYSTEM",
                label="Test service",
                state={"healthy": True},
                source="unit-test",
                confidence=.9,
                observed_at=old,
                stale_after_seconds=5,
                provenance={"verified_read": True},
            )
            node = world.node("service:test")
            self.assertTrue(node["stale"])
            self.assertEqual(node["freshness"], "STALE")
            self.assertEqual(node["provenance"]["verified_read"], True)
            self.assertEqual(node["confidence"], .9)

    def test_cognitive_event_updates_world_subject(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            bus = CognitiveEventBus(Path(folder) / "events.json", persist=False)
            world = WorldStateGraph(Path(folder) / "world.json")
            bus.subscribe("world", world.observe_cognitive_event)
            bus.publish(
                CognitiveEventType.SERVICE_DOWN,
                source="runtime",
                subject="completion-center",
                payload={"port": 8799},
                provenance={"health_check": True},
            )
            node = world.node("event-subject:completion-center")
            self.assertEqual(node["state"]["event_type"], "SERVICE_DOWN")
            self.assertEqual(node["state"]["payload"]["port"], 8799)
            self.assertFalse(world.snapshot()["live_execution"])

    def test_graph_edges_are_bounded_and_read_only_surface(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            world = WorldStateGraph(Path(folder) / "world.json")
            world.observe(
                "mission:1", kind="MISSION", label="Mission", state={"status": "READY"},
                source="test", provenance={"local": True},
            )
            world.observe(
                "queue:1", kind="MISSION_QUEUE", label="Queue", state={"status": "QUEUED"},
                source="test", provenance={"local": True},
            )
            world.connect("queue:1", "mission:1", "MATERIALIZES")
            snapshot = world.snapshot()
            self.assertEqual(snapshot["edge_count"], 1)
            self.assertTrue(snapshot["provenance_required"])
            self.assertTrue(snapshot["freshness_explicit"])
            self.assertFalse(snapshot["automatic_broker_order"])


class CognitiveBridgeTests(unittest.TestCase):
    def test_verified_completed_bar_bridges_without_execution_authority(self) -> None:
        from omni import cognitive_bridges

        with tempfile.TemporaryDirectory() as folder:
            bus = CognitiveEventBus(Path(folder) / "events.json", persist=False)
            source = {
                "provider": "FYERS",
                "symbol": "NSE:NIFTY50-INDEX",
                "success": True,
                "quality_flag": "BROKER_LIVE",
                "exchange_timestamp": datetime.now(timezone.utc).isoformat(),
            }
            event = canonical_market_event(
                source,
                {"open": 100.0, "high": 105.0, "low": 99.0, "close": 104.0},
                event_type=MarketEventType.BAR,
                timeframe="5m",
            )
            with patch.object(cognitive_bridges, "COGNITIVE_EVENT_BUS", bus):
                cognitive_bridges._market_to_cognitive(event)
            snapshot = bus.snapshot()
            self.assertEqual(snapshot["retained"], 1)
            row = snapshot["events"][0]
            self.assertEqual(row["event_type"], "MARKET_BAR_COMPLETED")
            self.assertTrue(row["payload"]["verified"])
            self.assertFalse(snapshot["live_execution"])

    def test_unverified_non_health_tick_is_not_promoted(self) -> None:
        from omni import cognitive_bridges

        with tempfile.TemporaryDirectory() as folder:
            bus = CognitiveEventBus(Path(folder) / "events.json", persist=False)
            source = {
                "provider": "PUBLIC_TEST",
                "symbol": "TEST",
                "verified": False,
                "quality_flag": "UNVERIFIED",
                "exchange_timestamp": datetime.now(timezone.utc).isoformat(),
            }
            event = canonical_market_event(
                source,
                {"ltp": 10.0},
                event_type=MarketEventType.QUOTE_TICK,
            )
            with patch.object(cognitive_bridges, "COGNITIVE_EVENT_BUS", bus):
                cognitive_bridges._market_to_cognitive(event)
            self.assertEqual(bus.snapshot()["retained"], 0)


class ContextFabricV93Tests(unittest.TestCase):
    def test_context_exposes_world_and_cognitive_state_without_breaking_v8_version(self) -> None:
        from omni import context_fabric

        with patch.object(context_fabric, "_world_context", return_value={"world": {"version": "9.3"}}), \
             patch.object(context_fabric, "_cognitive_context", return_value={"version": "9.3", "events": []}), \
             patch.object(context_fabric, "_memory_summary", return_value={"records": 0}), \
             patch.object(context_fabric, "_mission_summary", return_value={"mission_count": 0, "latest": None}):
            payload = context_fabric.snapshot("plan a local engineering mission", include_market_context=False)
        self.assertEqual(payload["version"], "8.0")
        self.assertEqual(payload["world_model_version"], "9.3")
        self.assertTrue(payload["world_model"]["success"])
        self.assertTrue(payload["cognitive_events"]["success"])
        self.assertTrue(payload["policy"]["state_provenance"])
        self.assertTrue(payload["policy"]["freshness_explicit"])
        self.assertFalse(payload["policy"]["live_execution"])


if __name__ == "__main__":
    unittest.main()
