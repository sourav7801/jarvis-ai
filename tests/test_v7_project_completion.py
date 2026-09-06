from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from omni.project_completion import snapshot as completion_snapshot
from omni.code_intelligence import analyze_file
from omni.mission_queue import MissionQueue
from omni.model_router_telemetry import ModelRouterTelemetry
from omni.trading_intelligence.champion_challenger import (
    ChampionChallenger,
    ChampionChallengerRegistry,
)
from omni.trading_intelligence.robust_validation import validate_research_result
from workstation.correlation_risk_engine import correlation_snapshot
from workstation.market_event_bus import MarketEventBus
from workstation.market_event_publishers import publish_option_chain, publish_provider_health
from scripts.jarvis_runtime_supervisor_v7 import v7_services
from omni.workspace_command_center import WORKSPACES


ROOT = Path(__file__).resolve().parents[1]


class V7ProjectCompletionTests(unittest.TestCase):
    def test_completion_audit_preserves_safety_boundary(self):
        payload = completion_snapshot()
        self.assertTrue(payload["success"])
        self.assertIn(payload["version"], {"7.0", "8.0"})
        self.assertTrue(payload["paper_only"])
        self.assertFalse(payload["live_execution"])
        self.assertFalse(payload["automatic_broker_order"])
        self.assertEqual(payload["external_actions"], "APPROVAL_GATED")

    def test_completion_audit_separates_external_blockers(self):
        payload = completion_snapshot()
        keys = {row["key"] for row in payload["external_blockers"]}
        self.assertIn("licensed_l2_data", keys)
        self.assertIn("live_broker_execution", keys)
        self.assertIn("hardware_authorization", keys)
        self.assertTrue(all(row["status"] == "BLOCKED_EXTERNAL" for row in payload["external_blockers"]))

    def test_completion_workspace_is_registered(self):
        workspaces = {item.key: item for item in WORKSPACES}
        self.assertIn("completion", workspaces)
        self.assertEqual(workspaces["completion"].port, 8799)
        self.assertEqual(workspaces["completion"].health_path, "/api/health")

    def test_code_intelligence_parses_without_executing_target(self):
        record = analyze_file(ROOT / "omni" / "project_completion.py")
        self.assertEqual(record.parse_status, "OK")
        self.assertIn("snapshot", record.functions)
        self.assertTrue(record.sha256)

    def test_resumable_mission_queue_lease_and_complete(self):
        with tempfile.TemporaryDirectory() as folder:
            queue = MissionQueue(Path(folder) / "queue.json", lease_seconds=60)
            item = queue.enqueue("Build a complete local verification packet for JARVIS V7.", priority=80)
            leased = queue.lease_next("test-worker")
            self.assertEqual(leased["queue_id"], item["queue_id"])
            self.assertEqual(leased["status"], "LEASED")
            finished = queue.complete(item["queue_id"], mission_id="mission-test", worker_id="test-worker")
            self.assertEqual(finished["status"], "SUCCEEDED")
            self.assertEqual(finished["mission_id"], "mission-test")
            self.assertFalse(queue.snapshot()["live_execution"])

    def test_model_router_telemetry_is_bounded_and_cannot_enable_cloud(self):
        with tempfile.TemporaryDirectory() as folder:
            telemetry = ModelRouterTelemetry(Path(folder) / "models.json")
            telemetry.record(
                task_type="coding",
                profile_id="local-reasoning",
                provider="ollama",
                model="test-local",
                status="SUCCEEDED",
                latency_ms=120.0,
                quality_score=0.8,
                local=True,
            )
            status = telemetry.status()
            self.assertEqual(status["event_count"], 1)
            self.assertFalse(status["privacy_policy_changed"])
            self.assertFalse(status["cloud_enabled_by_telemetry"])

    def test_robust_validation_requires_multiple_gates(self):
        values = [0.6, -0.2] * 20
        backtest = {
            "trade_log": [{"r": value} for value in values],
            "fee_bps": 2.0,
            "slippage_bps": 1.0,
        }
        report = validate_research_result(backtest, {"passed": True}, seed=7)
        self.assertTrue(report["success"])
        self.assertTrue(report["passed"])
        self.assertEqual(report["status"], "PAPER_CHALLENGER_ELIGIBLE")
        self.assertFalse(report["live_execution"])
        self.assertFalse(report["governance"]["automatic_production_promotion"])

    def test_champion_registry_remains_paper_research_only(self):
        with tempfile.TemporaryDirectory() as folder:
            registry = ChampionChallengerRegistry(Path(folder) / "registry.json")
            record = registry.register(
                symbol="BTC",
                timeframe="15m",
                regime="TRENDING",
                candidate={"name": "TEST_V7", "family": "momentum"},
                validation={"passed": True, "status": "PAPER_CHALLENGER_ELIGIBLE"},
            )
            champion = registry.nominate_paper_champion(record["record_id"])
            self.assertEqual(champion["scope"], "PAPER_RESEARCH_ONLY")
            status = registry.snapshot()
            self.assertFalse(status["live_execution"])
            self.assertFalse(status["governance"]["automatic_production_promotion"])

    def test_legacy_champion_comparator_contract_is_preserved(self):
        result = ChampionChallenger().compare(
            {"fitness": {"score": 50}},
            {"fitness": {"score": 55}},
        )
        self.assertEqual(result["decision"], "RESEARCH_CHALLENGER_WINS")
        self.assertFalse(result["production_promotion"])

    def test_correlation_engine_is_research_only(self):
        left = [100 + index for index in range(40)]
        right = [200 + index * 2 for index in range(40)]
        result = correlation_snapshot({"A": left, "B": right}, cluster_threshold=0.7)
        self.assertTrue(result["success"])
        self.assertIn(["A", "B"], result["clusters"])
        self.assertFalse(result["portfolio_limit_mutated"])
        self.assertFalse(result["live_execution"])

    def test_market_event_publishers_reject_unverified_sources(self):
        bus = MarketEventBus(capacity=20)
        with self.assertRaises(ValueError):
            publish_option_chain(
                {"provider": "TEST", "provider_symbol": "BTC", "verified": False, "data_quality": "PUBLIC_LIVE"},
                [],
                bus=bus,
            )

    def test_market_event_publishers_publish_validated_events(self):
        bus = MarketEventBus(capacity=20)
        source = {
            "provider": "TEST_PROVIDER",
            "provider_symbol": "BTC-OPTIONS",
            "verified": True,
            "success": True,
            "stale": False,
            "data_quality": "PUBLIC_LIVE",
        }
        result = publish_option_chain(source, [{"instrument": "TEST"}], expiry="2099-01-01", bus=bus)
        self.assertTrue(result["accepted"])
        self.assertEqual(bus.snapshot()["published"], 1)
        health = publish_provider_health(provider="TEST_PROVIDER", status="READY", bus=bus)
        self.assertTrue(health["accepted"])

    def test_v7_runtime_adds_completion_service_without_order_surface(self):
        services = {service.name: service for service in v7_services(ROOT)}
        self.assertIn("completion", services)
        self.assertEqual(services["completion"].port, 8799)
        source = (ROOT / "scripts" / "jarvis_runtime_supervisor_v7.py").read_text(encoding="utf-8")
        for forbidden in ("place_order(", "modify_order(", "cancel_order(", "submit_order("):
            self.assertNotIn(forbidden, source)

    def test_launcher_preserves_v7_completion_service_through_v8(self):
        source = (ROOT / "JARVIS.bat").read_text(encoding="utf-8")
        via_v7 = "-m scripts.jarvis_runtime_supervisor_v7" in source
        via_v8 = "-m scripts.jarvis_runtime_supervisor_v8" in source
        self.assertTrue(via_v7 or via_v8)
        if via_v8:
            wrapper = (ROOT / "scripts" / "jarvis_runtime_supervisor_v8.py").read_text(encoding="utf-8")
            self.assertIn("v7_services", wrapper)
            self.assertIn("scripts.jarvis_runtime_supervisor_v7", wrapper)
        v7 = (ROOT / "scripts" / "jarvis_runtime_supervisor_v7.py").read_text(encoding="utf-8")
        self.assertIn("scripts.jarvis_runtime_supervisor_v62", v7)

    def test_completion_console_has_no_broker_order_surface(self):
        source = (ROOT / "workstation" / "completion_console.py").read_text(encoding="utf-8")
        for forbidden in ("place_order(", "modify_order(", "cancel_order(", "submit_order("):
            self.assertNotIn(forbidden, source)
        self.assertIn("automatic_broker_order", source)
        self.assertIn("APPROVAL_GATED", source)


if __name__ == "__main__":
    unittest.main()
