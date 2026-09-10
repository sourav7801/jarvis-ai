from __future__ import annotations

import inspect
from pathlib import Path
import unittest

from omni.agent_registry import default_agent_specs
from omni.trading_intelligence import v16_market_bus
from workstation import professional_terminal
from workstation import v16_terminal_http
from workstation import v16_trading_stages
from workstation import workspace_accounts


ROOT = Path(__file__).resolve().parents[1]


class V16ProfessionalTerminalConvergenceTests(unittest.TestCase):
    def test_three_workspaces_share_one_partitioned_paper_ledger(self):
        self.assertEqual(workspace_accounts.WORKSPACES, ("INTRADAY", "SWING", "INVESTMENT"))
        self.assertEqual(
            workspace_accounts.DEFAULT_ALLOCATIONS,
            {"INTRADAY": 0.5, "SWING": 0.3, "INVESTMENT": 0.2},
        )
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

    def test_production_terminal_contains_no_default_simulated_market_fixture(self):
        source = inspect.getsource(professional_terminal)
        self.assertNotIn("SIMULATED_UI_TEST_FIXTURE", source)
        self.assertNotIn("JARVIS_ENABLE_PROFESSIONAL_TERMINAL_FIXTURES", source)

    def test_canonical_workspace_state_contract_is_exposed(self):
        source = inspect.getsource(professional_terminal.TerminalRuntime.workspace_state)
        for marker in (
            '"session"',
            '"capital"',
            '"market_data"',
            '"watchlist"',
            '"selected_instrument"',
            '"chart"',
            '"proposed_setup"',
            '"positions"',
            '"orders"',
            '"scan_decisions"',
            '"risk"',
            '"execution_trace"',
            '"paper_only"',
            '"live_execution"',
        ):
            self.assertIn(marker, source)
        self.assertEqual(
            v16_terminal_http.CANONICAL_WORKSPACE_STATE_PATH,
            "/api/v16/trading/workspace-state",
        )
        http_source = inspect.getsource(v16_terminal_http.build_handler)
        self.assertIn("runtime.workspace_state(name)", http_source)
        self.assertIn('payload["live_orders_locked"] = True', http_source)
        self.assertIn('payload["automatic_broker_order"] = False', http_source)

    def test_legacy_per_panel_routes_remain_compatibility_only(self):
        source = inspect.getsource(professional_terminal.build_handler)
        for marker in (
            "/api/terminal/state",
            "/api/terminal/chart",
            "/api/terminal/quote",
            "/api/terminal/module",
        ):
            self.assertIn(marker, source)

    def test_market_bus_key_is_completed_candle_scoped(self):
        close = v16_market_bus.last_completed_candle(
            [
                {"time": 1000, "open": 1, "high": 2, "low": 1, "close": 2},
                {"time": 1300, "open": 2, "high": 3, "low": 2, "close": 3},
            ],
            "5m",
            now_epoch=1599,
        )
        self.assertEqual(close, 1300.0)
        key = v16_market_bus.evidence_key(
            provider="FYERS",
            market="NSE",
            instrument="NIFTY",
            timeframe="5m",
            candle_close=close,
        )
        self.assertEqual(key, ("FYERS", "NSE", "NIFTY", "5m", 1300.0))
        bus_source = inspect.getsource(v16_market_bus.CanonicalMarketBus)
        self.assertNotIn("place_order", bus_source)
        self.assertNotIn("submit_order", bus_source)

    def test_stage_machine_has_exact_progress_and_rejection_vocabulary(self):
        self.assertIn("ACTIONABLE", v16_trading_stages.PROGRESS_STAGES)
        self.assertIn("PAPER_FILLED", v16_trading_stages.PROGRESS_STAGES)
        self.assertIn("JOURNALED", v16_trading_stages.PROGRESS_STAGES)
        self.assertIn("RATE_LIMITED", v16_trading_stages.REJECTION_STAGES)
        self.assertIn("STALE_DATA", v16_trading_stages.REJECTION_STAGES)
        self.assertIn("INSUFFICIENT_CAPITAL", v16_trading_stages.REJECTION_STAGES)

    def test_v16_launcher_uses_verified_v15_lineage_without_v151_activation(self):
        launcher = (ROOT / "start_jarvis_professional_terminal_v16.py").read_text(encoding="utf-8")
        for marker in (
            "install_v11_quant_bridges",
            "install_v141_risk_geometry_bridges",
            "install_v15_reasoning_bridges",
            "JARVIS_V12_AUTO_PAPER_START\"] = \"0\"",
            "Live broker execution: LOCKED",
            "v16_terminal_http import build_handler",
        ):
            self.assertIn(marker, launcher)
        self.assertNotIn("install_v151_options_bridges()", launcher)
        self.assertNotIn("install_v151_quant_http_bridge()", launcher)

    def test_permanent_agent_and_live_execution_boundaries_remain_fixed(self):
        names = {spec.name for spec in default_agent_specs()}
        self.assertEqual(len(names), 29)
        self.assertIn("critic", names)
        source = inspect.getsource(professional_terminal) + inspect.getsource(v16_terminal_http)
        for forbidden in ("place_order(", "submit_order(", "modify_order(", "cancel_order("):
            self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
