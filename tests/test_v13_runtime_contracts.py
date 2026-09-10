from __future__ import annotations

from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from omni.agent_registry import default_agent_specs
from omni.trading_intelligence.options_volatility_synthesis_v13 import OptionsVolatilitySynthesisV13
from scripts import jarvis_runtime_supervisor_v13 as runtime_v13


ROOT = Path(__file__).resolve().parents[1]


class V13RuntimeSurfaceTests(unittest.TestCase):
    def test_launcher_preserves_historical_lineage_and_runs_v13(self) -> None:
        text = (ROOT / "JARVIS_WORKSTATION.bat").read_text(encoding="utf-8")
        for marker in (
            "scripts.jarvis_runtime_supervisor_v62",
            "-m scripts.jarvis_runtime_supervisor_v8",
            "-m scripts.jarvis_runtime_supervisor_v11",
            "-m scripts.jarvis_runtime_supervisor_v12",
            "-m scripts.jarvis_runtime_supervisor_v13",
        ):
            self.assertIn(marker, text)
        for forbidden in ("place_order(", "submit_order(", "modify_order(", "cancel_order("):
            self.assertNotIn(forbidden, text)

    def test_completion_start_script_preserves_v11_v12_and_targets_v13(self) -> None:
        text = (ROOT / "start_jarvis_completion_console.py").read_text(encoding="utf-8")
        self.assertIn("completion_console_v11", text)
        self.assertIn("completion_console_v12", text)
        self.assertIn("completion_console_v13", text)
        self.assertIn("from workstation import completion_console_v13 as completion_console", text)

    def test_quant_start_installs_v13_before_contextual_paper_start(self) -> None:
        text = (ROOT / "start_jarvis_quant_terminal.py").read_text(encoding="utf-8")
        self.assertIn('os.environ["JARVIS_AUTO_PAPER_START"] = "0"', text)
        self.assertIn("install_v12_adaptive_bridges", text)
        self.assertIn("install_v13_intelligence_bridges", text)
        self.assertIn("start_v12_adaptive_paper", text)
        self.assertIn("CONTEXTUAL_EXPECTED_VALUE_NOT_STATIC_SCORE", text)
        self.assertIn("runtime.start()", text)

    def test_supervisor_service_identity_requires_v13_master_and_completion(self) -> None:
        services = {service.name: service for service in runtime_v13.v13_services(ROOT)}
        self.assertTrue(services["master"].health_url.endswith("/api/v13/paper-authority"))
        self.assertEqual(services["master"].expected_service, "JARVIS_MASTER_V13_CONTEXTUAL_BRIDGE")
        self.assertTrue(services["completion"].health_url.endswith("/api/v13/status"))
        self.assertEqual(services["completion"].expected_service, "JARVIS_ADAPTIVE_INTELLIGENCE_OPERATING_SYSTEM")

    def test_master_identity_rejects_plain_v8_without_v13_bridge(self) -> None:
        with patch.object(runtime_v13, "master_v8_surface_status", return_value={"current": True}), \
             patch.object(runtime_v13, "_json_http", return_value=(404, {})):
            status = runtime_v13.master_v13_surface_status()
        self.assertFalse(status["current"])


class V13AgentAndSafetyTests(unittest.TestCase):
    def test_v13_system_planes_do_not_change_permanent_29(self) -> None:
        names = {spec.name for spec in default_agent_specs()}
        self.assertEqual(len(names), 29)
        self.assertIn("critic", names)
        for name in (
            "contextual_decision_engine_v13",
            "contextual_outcome_memory",
            "dynamic_correlation_risk_v13",
            "decision_forensics_v13",
            "options_volatility_synthesis_v13",
            "strategy_governance_pipeline_v13",
        ):
            self.assertNotIn(name, names)

    def test_v13_completion_and_ui_have_required_surfaces_without_order_api(self) -> None:
        py = (ROOT / "workstation" / "completion_console_v13.py").read_text(encoding="utf-8")
        html = (ROOT / "workstation" / "completion_console_static" / "index.html").read_text(encoding="utf-8")
        js = (ROOT / "workstation" / "completion_console_static" / "v13_intelligence_os.js").read_text(encoding="utf-8")
        for endpoint in (
            "/api/v13/status",
            "/api/contextual-decision",
            "/api/contextual-memory",
            "/api/decision-forensics",
            "/api/portfolio-correlation",
            "/api/options-volatility",
            "/api/strategy-governance-v13",
        ):
            self.assertIn(endpoint, py + js)
        for marker in ("contextualIntelligenceNav", "decisionForensicsNav", "optionsVolatilityNav", "strategyPipelineNav"):
            self.assertIn(marker, html)
        for forbidden in ("place_order(", "submit_order(", "modify_order(", "cancel_order("):
            self.assertNotIn(forbidden, py + js)
        self.assertIn('"live_execution": False', py)
        self.assertIn('"automatic_broker_order": False', py)


class OptionsVolatilityTruthfulnessTests(unittest.TestCase):
    def test_empty_verified_history_stays_unavailable(self) -> None:
        engine = OptionsVolatilitySynthesisV13()
        with patch("omni.trading_intelligence.derivatives_history_analytics.derivatives_history_analytics.analyze", return_value={"symbol": "NIFTY", "available": False, "snapshot_count": 0, "research_only": True}):
            result = engine.history("NIFTY")
        self.assertFalse(result["available"])
        self.assertIsNone(result["iv_rank"])
        self.assertTrue(result["no_data_fabrication"])
        self.assertEqual(result["dealer_positioning"]["reason"], "NO_VERIFIED_DEALER_INVENTORY")
        self.assertFalse(result["live_execution"])


class V13SourceSafetyTests(unittest.TestCase):
    def test_new_runtime_files_do_not_expose_live_order_calls(self) -> None:
        paths = (
            "omni/trading_intelligence/contextual_decision_engine_v13.py",
            "omni/trading_intelligence/contextual_outcome_memory.py",
            "omni/trading_intelligence/decision_forensics_v13.py",
            "omni/trading_intelligence/options_volatility_synthesis_v13.py",
            "omni/trading_intelligence/strategy_governance_pipeline_v13.py",
            "workstation/dynamic_correlation_risk_v13.py",
            "workstation/adaptive_discovery_router_v13.py",
            "workstation/v13_runtime_bridges.py",
            "workstation/jarvis_os_v13_bridge.py",
            "workstation/completion_console_v13.py",
            "scripts/jarvis_runtime_supervisor_v13.py",
            "start_jarvis_master_v13.py",
        )
        text = "\n".join((ROOT / path).read_text(encoding="utf-8") for path in paths)
        for forbidden in ("place_order(", "submit_order(", "modify_order(", "cancel_order("):
            self.assertNotIn(forbidden, text)
        self.assertIn("paper_only", text)
        self.assertIn("live_execution", text)


if __name__ == "__main__":
    unittest.main()
