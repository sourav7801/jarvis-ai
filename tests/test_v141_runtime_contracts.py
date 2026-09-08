from __future__ import annotations

import inspect
import unittest
from pathlib import Path

from omni.agent_registry import default_agent_specs
from scripts import jarvis_runtime_supervisor_v141 as runtime_v141
from workstation.quant_terminal_v141_bridge import QuantTerminalV141Handler


ROOT = Path(__file__).resolve().parents[1]


class V141RuntimeContracts(unittest.TestCase):
    def test_quant_launcher_installs_v141_before_paper_workers(self) -> None:
        source = (ROOT / "start_jarvis_quant_terminal.py").read_text(encoding="utf-8")
        self.assertIn('os.environ["JARVIS_AUTO_PAPER_START"] = "0"', source)
        self.assertIn("install_v14_execution_bridges", source)
        self.assertIn("install_v141_risk_geometry_bridges", source)
        self.assertIn("install_v141_quant_http_bridge", source)
        self.assertLess(source.index("v141_bridges = install_v141_risk_geometry_bridges()"), source.index("adaptive = start_v12_adaptive_paper()"))
        self.assertIn("Static 67/68/70 score boundary: OBSERVABILITY ONLY", source)
        self.assertIn("CONTEXTUAL_EXPECTED_VALUE_NOT_STATIC_SCORE", source)

    def test_completion_launcher_preserves_v11_through_v14_markers_and_runs_v141(self) -> None:
        source = (ROOT / "start_jarvis_completion_console.py").read_text(encoding="utf-8")
        for marker in ("completion_console_v11", "completion_console_v12", "completion_console_v13", "completion_console_v14", "completion_console_v141"):
            self.assertIn(marker, source)
        self.assertIn("from workstation import completion_console_v141 as completion_console", source)

    def test_main_launcher_preserves_historical_supervisors_and_runs_v141(self) -> None:
        source = (ROOT / "JARVIS.bat").read_text(encoding="utf-8")
        for marker in (
            "scripts.jarvis_runtime_supervisor_v62",
            "-m scripts.jarvis_runtime_supervisor_v8",
            "-m scripts.jarvis_runtime_supervisor_v11",
            "-m scripts.jarvis_runtime_supervisor_v12",
            "-m scripts.jarvis_runtime_supervisor_v13",
            "-m scripts.jarvis_runtime_supervisor_v14",
            "-m scripts.jarvis_runtime_supervisor_v141",
        ):
            self.assertIn(marker, source)
        for forbidden in ("place_order(", "submit_order(", "modify_order(", "cancel_order("):
            self.assertNotIn(forbidden, source)

    def test_quant_http_bridge_preserves_v14_and_adds_trace(self) -> None:
        source = inspect.getsource(QuantTerminalV141Handler.do_GET)
        self.assertIn("/api/v14.1/risk-geometry", source)
        self.assertIn("/api/v14.1/execution-trace", source)
        self.assertIn("/api/v14.1/status", source)
        self.assertTrue(issubclass(QuantTerminalV141Handler, __import__("workstation.quant_terminal_v14_bridge", fromlist=["QuantTerminalV14Handler"]).QuantTerminalV14Handler))
        for forbidden in ("place_order(", "submit_order(", "modify_order(", "cancel_order("):
            self.assertNotIn(forbidden, source)

    def test_v141_service_identities(self) -> None:
        services = {service.name: service for service in runtime_v141.v141_services(ROOT)}
        self.assertTrue(services["master"].health_url.endswith("/api/v14.1/paper-authority"))
        self.assertEqual(services["master"].expected_service, "JARVIS_MASTER_V141_RISK_GEOMETRY_BRIDGE")
        self.assertTrue(services["quant"].health_url.endswith("/api/v14.1/status"))
        self.assertEqual(services["quant"].expected_service, "JARVIS_QUANT_V141_RISK_GEOMETRY_CONVERGENCE")
        self.assertTrue(services["completion"].health_url.endswith("/api/v14.1/status"))
        self.assertEqual(services["completion"].expected_service, "JARVIS_RISK_GEOMETRY_CONVERGENCE_OS")

    def test_permanent_agent_boundary_remains_exactly_29_with_critic(self) -> None:
        names = {spec.name for spec in default_agent_specs()}
        self.assertEqual(len(names), 29)
        self.assertIn("critic", names)
        for name in ("risk_geometry_v141", "v141_runtime_bridges", "quant_terminal_v141_bridge"):
            self.assertNotIn(name, names)

    def test_new_v141_sources_expose_no_live_order_api(self) -> None:
        paths = (
            "workstation/risk_geometry_v141.py",
            "workstation/v141_runtime_bridges.py",
            "workstation/quant_terminal_v141_bridge.py",
            "workstation/completion_console_v141.py",
            "workstation/jarvis_os_v141_bridge.py",
            "scripts/jarvis_runtime_supervisor_v141.py",
            "start_jarvis_master_v141.py",
        )
        text = "\n".join((ROOT / path).read_text(encoding="utf-8") for path in paths)
        for forbidden in ("place_order(", "submit_order(", "modify_order(", "cancel_order("):
            self.assertNotIn(forbidden, text)
        self.assertIn("paper_only", text)
        self.assertIn("live_execution", text)


if __name__ == "__main__":
    unittest.main()
