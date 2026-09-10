from __future__ import annotations

import inspect
from pathlib import Path
import unittest

from omni.agent_registry import default_agent_specs
from workstation import professional_terminal
from workstation import workspace_accounts


ROOT = Path(__file__).resolve().parents[1]


class V16ProfessionalTerminalConvergenceTests(unittest.TestCase):
    def test_three_workspaces_share_one_partitioned_paper_ledger(self):
        self.assertEqual(workspace_accounts.WORKSPACES, ("INTRADAY", "SWING", "INVESTMENT"))
        self.assertEqual(workspace_accounts.DEFAULT_ALLOCATIONS, {"INTRADAY": 0.5, "SWING": 0.3, "INVESTMENT": 0.2})
        self.assertAlmostEqual(sum(workspace_accounts.DEFAULT_ALLOCATIONS.values()), 1.0)
        source = inspect.getsource(workspace_accounts)
        self.assertIn("PAPER_DESK_SQLITE", source)
        self.assertIn("WORKSPACE_ALLOCATION_MISMATCH", source)
        self.assertIn("POSITION_WITHOUT_FILLED_ORDER", source)

    def test_terminal_keeps_entry_sessions_explicit_and_existing_positions_monitored(self):
        source = inspect.getsource(professional_terminal.TerminalRuntime)
        self.assertIn("reset_sessions", source)
        self.assertIn("positions_remain_monitored", source)
        self.assertIn("manage_positions", source)
        self.assertIn("LEDGER_RECONCILIATION_REQUIRED", source)

    def test_fixture_data_is_not_default_runtime_market_data(self):
        source = inspect.getsource(professional_terminal)
        self.assertIn("JARVIS_ENABLE_PROFESSIONAL_TERMINAL_FIXTURES", source)
        self.assertIn("SIMULATED_UI_TEST_FIXTURE", source)
        self.assertNotIn('JARVIS_ENABLE_PROFESSIONAL_TERMINAL_FIXTURES", "1"', source)

    def test_chart_and_reasoning_are_served_from_canonical_runtime_state(self):
        source = inspect.getsource(professional_terminal)
        for marker in (
            "/api/terminal/state",
            "/api/terminal/chart",
            "/api/terminal/quote",
            "/api/terminal/module",
            "workspace_sizing",
            "reconciliation",
        ):
            self.assertIn(marker, source)

    def test_v16_launcher_uses_verified_v15_lineage_without_v151_activation(self):
        launcher = (ROOT / "start_jarvis_professional_terminal_v16.py").read_text(encoding="utf-8")
        for marker in (
            "install_v11_quant_bridges",
            "install_v141_risk_geometry_bridges",
            "install_v15_reasoning_bridges",
            "JARVIS_V12_AUTO_PAPER_START\"] = \"0\"",
            "Live broker execution: LOCKED",
        ):
            self.assertIn(marker, launcher)
        self.assertNotIn("install_v151_options_bridges()", launcher)
        self.assertNotIn("install_v151_quant_http_bridge()", launcher)

    def test_permanent_agent_and_live_execution_boundaries_remain_fixed(self):
        names = {spec.name for spec in default_agent_specs()}
        self.assertEqual(len(names), 29)
        self.assertIn("critic", names)
        source = inspect.getsource(professional_terminal)
        for forbidden in ("place_order(", "submit_order(", "modify_order(", "cancel_order("):
            self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
