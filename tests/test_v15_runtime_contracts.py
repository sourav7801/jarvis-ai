from __future__ import annotations

import inspect
from pathlib import Path
import unittest

from scripts import jarvis_runtime_supervisor_v15 as runtime_v15
from workstation.quant_terminal_v15_bridge import QuantTerminalV15Handler


ROOT = Path(__file__).resolve().parents[1]


class V15RuntimeContracts(unittest.TestCase):
    def test_quant_launcher_installs_v15_before_paper_workers(self):
        text = (ROOT / "start_jarvis_quant_terminal.py").read_text(encoding="utf-8")
        self.assertIn('os.environ["JARVIS_AUTO_PAPER_START"] = "0"', text)
        for marker in (
            "install_v14_execution_bridges",
            "install_v141_risk_geometry_bridges",
            "install_v15_reasoning_bridges",
            "install_v15_quant_http_bridge",
            "CONTEXTUAL_EXPECTED_VALUE_NOT_STATIC_SCORE",
            "CONTEXTUAL_EXPECTED_VALUE_NOT_STATIC_SCORE",
            "install_v15_reasoning_bridges",
        ):
            self.assertIn(marker, text)
        self.assertLess(text.index("install_v15_reasoning_bridges()"), text.index("runtime.start()"))
        self.assertLess(text.index("install_v15_quant_http_bridge()"), text.index("server.serve_forever("))

    def test_completion_launcher_preserves_lineage_and_targets_v15(self):
        text = (ROOT / "start_jarvis_completion_console.py").read_text(encoding="utf-8")
        for marker in (
            "completion_console_v11", "completion_console_v12", "completion_console_v13",
            "completion_console_v14", "completion_console_v141", "completion_console_v15",
        ):
            self.assertIn(marker, text)
        self.assertIn("from workstation import completion_console_v15 as completion_console", text)

    def test_main_launcher_prevents_duplicate_supervisor_and_runs_v15(self):
        text = (ROOT / "JARVIS_WORKSTATION.bat").read_text(encoding="utf-8")
        for marker in (
            "scripts.jarvis_runtime_supervisor_v62",
            "-m scripts.jarvis_runtime_supervisor_v8",
            "-m scripts.jarvis_runtime_supervisor_v11",
            "-m scripts.jarvis_runtime_supervisor_v12",
            "-m scripts.jarvis_runtime_supervisor_v13",
            "-m scripts.jarvis_runtime_supervisor_v14",
            "-m scripts.jarvis_runtime_supervisor_v141",
            "-m scripts.jarvis_runtime_supervisor_v15",
            "/api/v15/paper-authority",
            "already running",
        ):
            self.assertIn(marker, text)
        for forbidden in ("place_order(", "submit_order(", "modify_order(", "cancel_order("):
            self.assertNotIn(forbidden, text)

    def test_v15_service_identities(self):
        services = {service.name: service for service in runtime_v15.v15_services(ROOT)}
        self.assertTrue(services["master"].health_url.endswith("/api/v15/paper-authority"))
        self.assertEqual(services["master"].expected_service, "JARVIS_MASTER_V15_AUTONOMOUS_MARKET_REASONING_BRIDGE")
        self.assertTrue(services["quant"].health_url.endswith("/api/v15/status"))
        self.assertEqual(services["quant"].expected_service, "JARVIS_QUANT_V15_AUTONOMOUS_MARKET_REASONING")
        self.assertTrue(services["completion"].health_url.endswith("/api/v15/status"))
        self.assertEqual(services["completion"].expected_service, "JARVIS_AUTONOMOUS_MARKET_REASONING_OS")

    def test_quant_bridge_exposes_reasoning_belief_position_review_forensics(self):
        source = inspect.getsource(QuantTerminalV15Handler.do_GET)
        for endpoint in (
            "/api/v15/reasoning-trace",
            "/api/v15/market-beliefs",
            "/api/v15/position-intelligence",
            "/api/v15/causal-trade-review",
            "/api/v15/execution-forensics",
            "/api/v15/status",
        ):
            self.assertIn(endpoint, source)
        for forbidden in ("place_order(", "submit_order(", "modify_order(", "cancel_order("):
            self.assertNotIn(forbidden, source)

    def test_completion_v15_surfaces_and_ui_exist(self):
        py = (ROOT / "workstation" / "completion_console_v15.py").read_text(encoding="utf-8")
        html = (ROOT / "workstation" / "completion_console_static" / "index.html").read_text(encoding="utf-8")
        js = (ROOT / "workstation" / "completion_console_static" / "v15_market_reasoning.js").read_text(encoding="utf-8")
        self.assertIn("marketReasoningV15Nav", html + js)
        self.assertIn("v15_market_reasoning.js", html)
        self.assertIn("JARVIS V15", html)
        self.assertIn("/api/v15/status", py)
        self.assertIn("/api/v15/reasoning-trace", py)
        for forbidden in ("place_order(", "submit_order(", "modify_order(", "cancel_order("):
            self.assertNotIn(forbidden, py + js)

    def test_quant_v15_ui_is_loaded_after_v141_compatibility_asset(self):
        html = (ROOT / "workstation" / "quant_terminal_v2_static" / "index.html").read_text(encoding="utf-8")
        js = (ROOT / "workstation" / "quant_terminal_v2_static" / "v15_market_reasoning_runtime.js").read_text(encoding="utf-8")
        self.assertIn("v141_risk_geometry_runtime.js", html)
        self.assertIn("v15_market_reasoning_runtime.js", html)
        self.assertLess(html.index("v141_risk_geometry_runtime.js"), html.index("v15_market_reasoning_runtime.js"))
        for marker in ("MARKET BELIEF", "DOMINANT HYPOTHESIS", "PORTFOLIO UTILITY", "LEGACY SCORE · OBSERVATION", "LIVE BROKER"):
            self.assertIn(marker, js)

    def test_v15_sources_have_no_live_broker_order_surface(self):
        paths = (
            "omni/trading_intelligence/market_reasoning_v15.py",
            "omni/trading_intelligence/autonomous_decision_engine_v15.py",
            "omni/trading_intelligence/causal_trade_review_v15.py",
            "workstation/market_belief_store_v15.py",
            "workstation/position_intelligence_v15.py",
            "workstation/execution_forensics_v15.py",
            "workstation/v15_runtime_bridges.py",
            "workstation/quant_terminal_v15_bridge.py",
            "workstation/completion_console_v15.py",
            "workstation/jarvis_os_v15_bridge.py",
            "scripts/runtime_supervisor_safety_v15.py",
            "scripts/jarvis_runtime_supervisor_v15.py",
            "start_jarvis_master_v15.py",
        )
        text = "\n".join((ROOT / path).read_text(encoding="utf-8") for path in paths)
        for forbidden in ("place_order(", "submit_order(", "modify_order(", "cancel_order("):
            self.assertNotIn(forbidden, text)
        self.assertIn("paper_only", text)
        self.assertIn("live_execution", text)
        self.assertIn("automatic_broker_order", text)

    def test_supervisor_snapshot_race_fix_is_present(self):
        text = (ROOT / "scripts" / "runtime_supervisor_safety_v15.py").read_text(encoding="utf-8")
        self.assertIn("mkstemp", text)
        self.assertIn("os.replace", text)
        self.assertIn("SupervisorLeaseV15", text)
        self.assertNotIn('with_suffix(".tmp")', text)


if __name__ == "__main__":
    unittest.main()
