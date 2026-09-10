from __future__ import annotations

import unittest

from workstation.v16_trading_workspace_state import build_workspace_state


class FakeQuant:
    def __init__(self, *, provider_state: str = "CONNECTED", candle_age: int = 60):
        self.provider_state = provider_state
        self.candle_age = candle_age

    def __call__(self, path, params=None, timeout=3.0):
        now = 2_000_000_000
        if path == "/api/health":
            return {"success": True, "service": "JARVIS_QUANT_TERMINAL"}
        if path == "/api/provider":
            return {
                "provider": "FYERS",
                "state": self.provider_state,
                "configured": True,
                "token_saved": True,
            }
        if path == "/api/paper/portfolio-controller":
            return {
                "success": True,
                "running": True,
                "all_running": True,
                "active_mandates": ["INTRADAY", "SWING", "INVESTMENT"],
                "allocations": {
                    "INTRADAY": 0.50,
                    "SWING": 0.30,
                    "INVESTMENT": 0.20,
                },
                "mandates": {
                    "INTRADAY": {"running": True},
                    "SWING": {"running": True},
                    "INVESTMENT": {"running": True},
                },
                "candidate_routing": {
                    "intraday_symbols": ["NIFTY", "BANKNIFTY"],
                    "swing_symbols": ["RELIANCE"],
                    "investment_symbols": ["TCS"],
                },
                "decision_board": [
                    {
                        "symbol": "NIFTY",
                        "mandate": "INTRADAY",
                        "qualified": True,
                        "candidate_side": "LONG",
                        "adaptive_expected_value_r": 0.31,
                        "hard_blockers": [],
                    },
                    {
                        "symbol": "RELIANCE",
                        "mandate": "SWING",
                        "qualified": False,
                        "hard_blockers": ["NON_POSITIVE_EV"],
                    },
                    {
                        "symbol": "TCS",
                        "mandate": "INVESTMENT",
                        "qualified": True,
                        "candidate_side": "LONG",
                        "hard_blockers": [],
                    },
                ],
            }
        if path == "/api/paper/portfolio":
            return {
                "success": True,
                "equity": 100000.0,
                "realized_pnl": 1500.0,
                "positions": [
                    {
                        "symbol": "NIFTY",
                        "portfolio_bucket": "INTRADAY",
                        "notional": 12000.0,
                        "risk_at_stop": 300.0,
                        "unrealized_pnl": 120.0,
                    },
                    {
                        "symbol": "TCS",
                        "portfolio_bucket": "INVESTMENT",
                        "notional": 15000.0,
                        "risk_at_stop": 250.0,
                        "unrealized_pnl": -50.0,
                    },
                ],
            }
        if path == "/api/scanner/multi":
            return {"success": True, "running": True}
        if path == "/api/paper/autonomy":
            return {"success": True, "running": True}
        if path == "/api/candles":
            return {
                "success": True,
                "source": "FYERS",
                "data_quality": "BROKER_HISTORICAL",
                "candles": [
                    {
                        "time": 2_000_000_000 - self.candle_age,
                        "open": 100.0,
                        "high": 102.0,
                        "low": 99.0,
                        "close": 101.0,
                    }
                ],
            }
        raise AssertionError(f"unexpected path {path}")


class CanonicalWorkspaceStateTests(unittest.TestCase):
    def test_intraday_snapshot_is_workspace_scoped_and_paper_only(self):
        state = build_workspace_state(
            "INTRADAY",
            symbol="NIFTY",
            timeframe="5m",
            client=FakeQuant(),
            now_epoch=2_000_000_000,
        )

        self.assertTrue(state["success"])
        self.assertEqual(state["contract"], "JARVIS_V16_CANONICAL_TRADING_WORKSPACE_STATE")
        self.assertEqual(state["workspace"], "INTRADAY")
        self.assertEqual([row["symbol"] for row in state["positions"]], ["NIFTY"])
        self.assertEqual([row["symbol"] for row in state["scan_decisions"]], ["NIFTY"])
        self.assertEqual(state["capital"]["workspace_equity"], 50000.0)
        self.assertEqual(state["capital"]["committed_capital"], 12000.0)
        self.assertEqual(state["capital"]["available_capital"], 38000.0)
        self.assertTrue(state["session"]["new_entries_allowed"])
        self.assertEqual(state["market_data"]["chart"]["state"], "FRESH")
        self.assertTrue(state["safety"]["paper_only"])
        self.assertFalse(state["safety"]["live_execution"])
        self.assertFalse(state["safety"]["automatic_broker_order"])
        self.assertFalse(state["safety"]["naked_option_selling"])
        self.assertTrue(state["safety"]["live_orders_locked"])

    def test_stale_data_blocks_new_entries_without_hiding_open_positions(self):
        state = build_workspace_state(
            "INTRADAY",
            client=FakeQuant(candle_age=5000),
            now_epoch=2_000_000_000,
        )

        self.assertEqual(state["market_data"]["chart"]["state"], "STALE")
        self.assertFalse(state["session"]["new_entries_allowed"])
        self.assertTrue(state["session"]["position_management_remains_active"])
        self.assertEqual(len(state["positions"]), 1)

    def test_provider_auth_failure_blocks_fyers_entry(self):
        state = build_workspace_state(
            "INTRADAY",
            client=FakeQuant(provider_state="LOGIN_REQUIRED"),
            now_epoch=2_000_000_000,
        )

        self.assertEqual(state["market_data"]["provider"]["state"], "LOGIN_REQUIRED")
        self.assertFalse(state["market_data"]["provider"]["new_entries_allowed"])
        self.assertFalse(state["risk"]["new_entries_allowed"])
        self.assertIn(
            "FYERS_LOGIN_REQUIRED",
            state["market_data"]["degradation_reasons"],
        )

    def test_investment_snapshot_keeps_long_only_safety_contract(self):
        state = build_workspace_state(
            "INVESTMENT",
            symbol="TCS",
            client=FakeQuant(),
            now_epoch=2_000_000_000,
        )

        self.assertEqual(state["workspace"], "INVESTMENT")
        self.assertEqual([row["symbol"] for row in state["positions"]], ["TCS"])
        self.assertTrue(state["safety"]["investment_long_only"])

    def test_options_is_visible_but_not_falsely_declared_converged(self):
        state = build_workspace_state(
            "OPTIONS",
            symbol="NIFTY",
            client=FakeQuant(),
            now_epoch=2_000_000_000,
        )

        self.assertFalse(state["session"]["new_entries_allowed"])
        self.assertIn(
            "OPTIONS_WORKSPACE_CONVERGENCE_PENDING",
            state["market_data"]["degradation_reasons"],
        )
        self.assertTrue(state["safety"]["live_orders_locked"])


if __name__ == "__main__":
    unittest.main()
