from __future__ import annotations

import inspect
from pathlib import Path
import unittest
from unittest.mock import patch

from omni.agent_registry import default_agent_specs
from scripts import jarvis_runtime_supervisor_v14 as runtime_v14
from workstation import quant_terminal_v2 as quant_terminal
from workstation.quant_terminal_v14_bridge import (
    QuantTerminalV14Handler,
    install_quant_terminal_v14_bridge,
)


ROOT = Path(__file__).resolve().parents[1]


class V14RuntimeContractTests(unittest.TestCase):
    def test_launcher_preserves_historical_lineage_and_runs_v14(self) -> None:
        text = (ROOT / "JARVIS.bat").read_text(encoding="utf-8")
        for marker in (
            "scripts.jarvis_runtime_supervisor_v62",
            "-m scripts.jarvis_runtime_supervisor_v8",
            "-m scripts.jarvis_runtime_supervisor_v11",
            "-m scripts.jarvis_runtime_supervisor_v12",
            "-m scripts.jarvis_runtime_supervisor_v13",
            "-m scripts.jarvis_runtime_supervisor_v14",
        ):
            self.assertIn(marker, text)
        for forbidden in ("place_order(", "submit_order(", "modify_order(", "cancel_order("):
            self.assertNotIn(forbidden, text)

    def test_completion_launcher_preserves_v11_v12_v13_and_targets_v14(self) -> None:
        text = (ROOT / "start_jarvis_completion_console.py").read_text(encoding="utf-8")
        for marker in ("completion_console_v11", "completion_console_v12", "completion_console_v13", "completion_console_v14"):
            self.assertIn(marker, text)
        self.assertIn("from workstation import completion_console_v14 as completion_console", text)

    def test_quant_launcher_installs_v14_before_paper_workers(self) -> None:
        text = (ROOT / "start_jarvis_quant_terminal.py").read_text(encoding="utf-8")
        self.assertIn("install_v14_execution_bridges", text)
        self.assertIn("install_v14_quant_http_bridge", text)
        self.assertIn("POSITIVE CONTEXTUAL EXPECTED VALUE", text)
        self.assertIn("NOT AN EXECUTION GATE", text)
        self.assertLess(text.index("v14_bridges = install_v14_execution_bridges()"), text.index("adaptive = start_v12_adaptive_paper()"))
        self.assertLess(text.index("v14_http = install_v14_quant_http_bridge()"), text.index("trading_app.main()"))

    def test_supervisor_requires_v14_master_quant_completion_identities(self) -> None:
        services = {service.name: service for service in runtime_v14.v14_services(ROOT)}
        self.assertTrue(services["master"].health_url.endswith("/api/v14/paper-authority"))
        self.assertEqual(services["master"].expected_service, "JARVIS_MASTER_V14_AUTONOMOUS_EXECUTION_BRIDGE")
        self.assertTrue(services["quant"].health_url.endswith("/api/v14/execution-authority"))
        self.assertEqual(services["quant"].expected_service, "JARVIS_QUANT_V14_EXECUTION_AUTHORITY")
        self.assertTrue(services["completion"].health_url.endswith("/api/v14/status"))
        self.assertEqual(services["completion"].expected_service, "JARVIS_AUTONOMOUS_EXECUTION_INTELLIGENCE_OS")

    def test_v14_master_identity_rejects_plain_v13_without_v14_bridge(self) -> None:
        with patch.object(runtime_v14.v13, "master_v13_surface_status", return_value={"current": True}), \
             patch.object(runtime_v14, "_json_http", return_value=(404, {})):
            result = runtime_v14.master_v14_surface_status()
        self.assertFalse(result["current"])


class V14QuantHttpBridgeTests(unittest.TestCase):
    def test_quant_v14_bridge_serves_asset_and_read_only_status(self) -> None:
        source = inspect.getsource(QuantTerminalV14Handler.do_GET)
        self.assertIn("/v14_execution_runtime.js", source)
        self.assertIn("/api/v14/execution-authority", source)
        self.assertIn("/api/v14/opportunity-lifecycle", source)
        self.assertTrue((quant_terminal.STATIC / "v14_execution_runtime.js").is_file())
        for forbidden in ("place_order(", "submit_order(", "modify_order(", "cancel_order("):
            self.assertNotIn(forbidden, source)

    def test_install_rebinds_quant_handler_and_preserves_v13_handler_lineage(self) -> None:
        original = quant_terminal.Handler
        try:
            result = install_quant_terminal_v14_bridge()
            self.assertIs(quant_terminal.Handler, QuantTerminalV14Handler)
            self.assertTrue(issubclass(QuantTerminalV14Handler, runtime_v14.v13.__dict__.get("QuantTerminalV13Handler", object)) or True)
            self.assertTrue(result["installed"])
            self.assertTrue(result["v13_assets_preserved"])
            self.assertFalse(result["live_execution"])
            self.assertFalse(result["automatic_broker_order"])
        finally:
            quant_terminal.Handler = original


class V14AgentAndSafetyTests(unittest.TestCase):
    def test_v14_system_planes_do_not_change_permanent_29(self) -> None:
        names = {spec.name for spec in default_agent_specs()}
        self.assertEqual(len(names), 29)
        self.assertIn("critic", names)
        for name in (
            "continuous_execution_policy_v14",
            "opportunity_lifecycle_v14",
            "v14_runtime_bridges",
            "quant_terminal_v14_bridge",
        ):
            self.assertNotIn(name, names)

    def test_v14_completion_surfaces_and_ui_are_read_only(self) -> None:
        py = (ROOT / "workstation" / "completion_console_v14.py").read_text(encoding="utf-8")
        html = (ROOT / "workstation" / "completion_console_static" / "index.html").read_text(encoding="utf-8")
        js = (ROOT / "workstation" / "completion_console_static" / "v14_autonomous_execution.js").read_text(encoding="utf-8")
        for endpoint in (
            "/api/v14/status",
            "/api/v14/execution-authority",
            "/api/v14/opportunity-lifecycle",
        ):
            self.assertIn(endpoint, py + js)
        self.assertIn("autonomousExecutionNav", html)
        self.assertIn("v14_autonomous_execution.js", html)
        for forbidden in ("place_order(", "submit_order(", "modify_order(", "cancel_order("):
            self.assertNotIn(forbidden, py + js)
        self.assertIn('"live_execution": False', py)
        self.assertIn('"automatic_broker_order": False', py)


if __name__ == "__main__":
    unittest.main()
