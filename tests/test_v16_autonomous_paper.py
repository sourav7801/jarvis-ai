from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch

from workstation.v16_autonomous_paper import (
    SAFETY,
    autonomous_option_plan,
    install_v16_autonomous_option_bridge,
)


class V16AutonomousPaperTests(unittest.TestCase):
    def setUp(self):
        self.desk = SimpleNamespace(open_position=MagicMock(return_value={"success": True, "reason": "PAPER_POSITION_OPENED", "position_id": 7}))
        self.positions = []
        self.runtime = SimpleNamespace(
            desk=self.desk,
            reconcile=lambda: {"success": True, "issues": []},
            snapshot=lambda workspace: {
                "success": True,
                "workspace": workspace,
                "entry_session": "RUNNING",
                "account": {"positions": list(self.positions)},
                "scan": {"scanning": True},
            },
            mark_loader=lambda symbol: {
                "success": True,
                "symbol": symbol,
                "provider": "FYERS_DATA",
                "mark": 101.0,
                "ask": 101.0,
                "bid": 100.5,
                "eligible_for_entry": True,
                "eligible_for_exit": True,
                "verified": True,
            },
        )
        self.plan = {
            "success": True,
            "executable": True,
            "reason": "OPTION_READY_FOR_PAPER_DESK",
            "underlying": "NIFTY",
            "underlying_decision": {"side": "SHORT", "expected_value_r": 0.42, "risk_multiplier": 0.4},
            "desired_option_type": "put",
            "selected_contract": "NSE:NIFTY2691523300PE",
            "selected": {
                "symbol": "NSE:NIFTY2691523300PE",
                "option_type": "put",
                "strike": 23300,
                "expiry": "2026-09-15",
                "risk_multiplier": 0.25,
                "option_expected_value_r": 0.31,
                "option_utility": 0.12,
                "quote": {"delta": -0.42, "gamma": 0.001, "theta": -8.2, "vega": 6.1},
                "risk_plan": {"entry": 100.0, "stop": 80.0, "target": 145.0, "risk_reward": 2.25},
            },
        }
        self.spec = {
            "symbol": "NSE:NIFTY2691523300PE",
            "provider_symbol": "NSE:NIFTY2691523300PE",
            "asset_class": "OPTION",
            "instrument_type": "OPTION",
            "native_currency": "INR",
            "valuation_currency": "INR",
            "quantity_step": 1.0,
            "contract_multiplier": 65.0,
            "lot_size": 65.0,
            "tick_size": 0.05,
            "source": "FYERS_NSE_FO_SYMBOL_MASTER",
            "verified": True,
            "option_type": "PE",
            "strike": 23300,
            "expiry": "2026-09-15",
        }

    def execute(self, **kwargs):
        with patch("workstation.v16_option_paper.option_instrument_spec", return_value=dict(self.spec)):
            return autonomous_option_plan(
                self.runtime,
                self.plan,
                portfolio_bucket=kwargs.get("workspace", "INTRADAY"),
                bucket_allocation_fraction=kwargs.get("allocation", 0.5),
                session_generation=4,
                signal_id=kwargs.get("signal_id", "2026-09-14T09:25:00+05:30"),
            )

    def test_auto_plan_needs_no_manual_ticket_and_paper_desk_sizes(self):
        result = self.execute()
        self.assertTrue(result["success"], result)
        self.assertTrue(result["automation"])
        self.assertEqual(result["action"], "AUTO_BUY_LONG_PUT")
        self.assertEqual(result["stop"], 80.0)
        self.assertEqual(result["target"], 145.0)
        self.desk.open_position.assert_called_once()
        call = self.desk.open_position.call_args.kwargs
        self.assertIsNone(call["quantity"])
        self.assertEqual(call["portfolio_bucket"], "INTRADAY")
        self.assertEqual(call["symbol"], self.plan["selected_contract"])
        self.assertEqual(call["metadata"]["auto_contract_selection"], True)
        self.assertEqual(call["metadata"]["auto_risk_geometry"], True)
        self.assertEqual(call["metadata"]["auto_position_sizing"], True)
        self.assertEqual(call["source"], "JARVIS_V16_AUTONOMOUS_PAPER")

    def test_auto_plan_is_stably_idempotent_at_paper_desk_boundary(self):
        self.execute(signal_id="bar-123")
        first = self.desk.open_position.call_args.kwargs["external_id"]
        self.desk.open_position.reset_mock()
        self.execute(signal_id="bar-123")
        second = self.desk.open_position.call_args.kwargs["external_id"]
        self.assertEqual(first, second)
        self.assertIn("bar-123", first)

    def test_duplicate_underlying_option_exposure_is_blocked(self):
        self.positions.append({
            "symbol": "NSE:NIFTY2691523350PE",
            "asset_type": "OPTION",
            "metadata": {"underlying": "NIFTY", "portfolio_bucket": "INTRADAY"},
        })
        result = self.execute()
        self.assertFalse(result["success"])
        self.assertEqual(result["reason"], "UNDERLYING_OPTION_EXPOSURE_EXISTS")
        self.desk.open_position.assert_not_called()

    def test_paused_workspace_is_blocked(self):
        self.runtime.snapshot = lambda workspace: {
            "entry_session": "PAUSED",
            "account": {"positions": []},
            "scan": {"scanning": False},
        }
        result = self.execute()
        self.assertFalse(result["success"])
        self.assertEqual(result["reason"], "WORKSPACE_PAUSED")
        self.desk.open_position.assert_not_called()

    def test_stale_or_closed_quote_is_blocked(self):
        self.runtime.mark_loader = lambda symbol: {
            "success": True,
            "symbol": symbol,
            "provider": "FYERS_DATA",
            "mark": 101.0,
            "eligible_for_entry": False,
            "reason": "MARKET_SESSION_CLOSED",
        }
        result = self.execute()
        self.assertFalse(result["success"])
        self.assertEqual(result["reason"], "MARKET_SESSION_CLOSED")
        self.desk.open_position.assert_not_called()

    def test_live_quote_outside_planned_geometry_waits_for_next_plan(self):
        self.runtime.mark_loader = lambda symbol: {
            "success": True,
            "symbol": symbol,
            "provider": "FYERS_DATA",
            "mark": 160.0,
            "ask": 160.0,
            "eligible_for_entry": True,
            "verified": True,
        }
        result = self.execute()
        self.assertFalse(result["success"])
        self.assertEqual(result["reason"], "LIVE_OPTION_QUOTE_OUTSIDE_SETUP")
        self.desk.open_position.assert_not_called()

    def test_investment_auto_options_are_not_silently_enabled(self):
        result = self.execute(workspace="INVESTMENT")
        self.assertFalse(result["success"])
        self.assertEqual(result["reason"], "AUTO_OPTIONS_WORKSPACE_UNSUPPORTED")
        self.desk.open_position.assert_not_called()

    def test_safety_invariants_are_present_on_success_and_failure(self):
        results = [self.execute(), autonomous_option_plan(self.runtime, {"executable": False}, signal_id="x")]
        for result in results:
            for key, expected in SAFETY.items():
                self.assertIs(result[key], expected)

    def test_installer_routes_existing_adaptive_singleton_to_v16_runtime(self):
        from workstation.options_paper_execution_v151 import OPTIONS_PAPER_EXECUTION_V151

        original = OPTIONS_PAPER_EXECUTION_V151.open_plan
        self.addCleanup(setattr, OPTIONS_PAPER_EXECUTION_V151, "open_plan", original)
        with patch("workstation.v16_option_paper.option_instrument_spec", return_value=dict(self.spec)):
            bridge = install_v16_autonomous_option_bridge(self.runtime)
            result = OPTIONS_PAPER_EXECUTION_V151.open_plan(
                self.plan,
                desk=self.runtime.desk,
                portfolio_bucket="INTRADAY",
                bucket_allocation_fraction=0.5,
                session_generation=4,
                signal_id="bar-installed",
            )
        self.assertIs(self.runtime.v16_autonomy_service, bridge)
        self.assertTrue(result["automation"])
        self.assertEqual(self.desk.open_position.call_args.kwargs["quantity"], None)

    def test_autonomy_ui_assets_are_wired_into_v16_http(self):
        root = Path(__file__).resolve().parents[1]
        http = (root / "workstation/v16_terminal_http.py").read_text(encoding="utf-8")
        launcher = (root / "start_jarvis_professional_terminal_v16.py").read_text(encoding="utf-8")
        js = (root / "workstation/quant_terminal_v2_static/v16_autonomy_runtime.js").read_text(encoding="utf-8")
        self.assertIn("v16_autonomy_runtime.js", http)
        self.assertIn("v16_autonomy_runtime.css", http)
        self.assertIn("install_v16_autonomous_option_bridge", launcher)
        self.assertIn("START AUTONOMOUS PAPER", js)
        self.assertIn("MANUAL PAPER OVERRIDE", js)
        self.assertNotIn("broker order", js.lower().replace("no broker order", ""))


if __name__ == "__main__":
    unittest.main()
