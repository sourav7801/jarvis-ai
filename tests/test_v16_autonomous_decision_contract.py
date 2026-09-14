from __future__ import annotations

import unittest

from workstation import v16_trading_stages as stages


class V16AutonomousDecisionContractTests(unittest.TestCase):
    def _row(self, **updates):
        row = {
            "symbol": "NIFTY",
            "strategy": "5m_only",
            "side": "LONG",
            "entry": 23398.10,
            "stop": 23347.14,
            "target": 23500.00,
            "adaptive_side": "LONG",
            "adaptive_executable": True,
            "adaptive_expected_value_r": 0.64,
            "adaptive_confidence": 0.71,
            "adaptive_probability_win": 0.58,
            "success": True,
            "session_open": True,
            "hard_blockers": [],
        }
        row.update(updates)
        return row

    def test_wait_surfaces_real_engine_reason_without_inventing_contract(self):
        row = self._row(
            adaptive_executable=False,
            adaptive_side="WAIT",
            hard_blockers=["INSUFFICIENT_TIMEFRAME_DATA"],
            reason="INSUFFICIENT_TIMEFRAME_DATA",
            option_proposal=None,
            execution_result=None,
        )
        decision = stages.summarise([row])["autonomous_options"]["NIFTY"]
        self.assertEqual(decision["status"], "WAIT")
        self.assertIsNone(decision["candidate_contract"])
        self.assertIn("INSUFFICIENT_TIMEFRAME_DATA", decision["rejection_reasons"])
        self.assertEqual(decision["gates"]["AUTONOMOUS_CHAIN"]["state"], "WAIT")

    def test_actionable_contract_and_expression_come_from_engine_proposal(self):
        row = self._row(
            option_proposal={
                "success": True,
                "executable": True,
                "action": "PAPER_BUY_CALL",
                "selected_contract": "NSE:NIFTY2691523400CE",
                "selected": {
                    "symbol": "NSE:NIFTY2691523400CE",
                    "option_type": "call",
                    "strike": 23400,
                    "expiry": "2026-09-15",
                    "option_expected_value_r": 0.42,
                    "risk_plan": {"entry": 118.0, "stop": 82.0, "target": 190.0},
                    "instrument_spec": {"tick_size": 0.05},
                    "quote": {"open_interest": 500000},
                    "economics": {"spread_pct": 0.012},
                },
            },
        )
        decision = stages.summarise([row])["autonomous_options"]["NIFTY"]
        self.assertEqual(decision["status"], "ACTIONABLE")
        self.assertEqual(decision["expression"], "LONG CALL")
        self.assertEqual(decision["candidate_contract"], "NSE:NIFTY2691523400CE")
        self.assertEqual(decision["strike"], 23400)
        self.assertEqual(decision["gates"]["MARKET_SESSION"]["state"], "PASS")
        self.assertEqual(decision["gates"]["AUTONOMOUS_CHAIN"]["state"], "PASS")

    def test_option_risk_geometry_never_uses_underlying_geometry(self):
        row = self._row(
            entry=23398.10,
            stop=23347.14,
            target=23500.00,
            option_proposal={
                "executable": True,
                "selected": {
                    "symbol": "NSE:NIFTY2691523300PE",
                    "option_type": "put",
                    "risk_plan": {"entry": 56.75, "stop": 39.50, "target": 91.25},
                    "instrument_spec": {"tick_size": 0.05},
                    "economics": {"spread_pct": 0.01},
                    "quote": {"open_interest": 138020300},
                },
            },
        )
        decision = stages.summarise([row])["autonomous_options"]["NIFTY"]
        self.assertEqual(decision["entry"], 56.75)
        self.assertEqual(decision["stop"], 39.50)
        self.assertEqual(decision["target"], 91.25)
        self.assertNotEqual(decision["entry"], row["entry"])
        self.assertEqual(decision["gates"]["RISK_GEOMETRY"]["state"], "PASS")

    def test_missing_premium_plan_is_not_rendered_as_zero_geometry(self):
        decision = stages.summarise([
            self._row(
                adaptive_executable=False,
                adaptive_side="WAIT",
                adaptive_expected_value_r=-0.25,
                option_proposal=None,
            )
        ])["autonomous_options"]["NIFTY"]
        self.assertIsNone(decision["entry"])
        self.assertIsNone(decision["stop"])
        self.assertIsNone(decision["target"])
        self.assertEqual(decision["gates"]["RISK_GEOMETRY"]["state"], "WAIT")
        self.assertIn("NON_POSITIVE_EV", decision["rejection_reasons"])

    def test_market_session_is_distinct_from_paper_entry_session(self):
        decision = stages.summarise([
            self._row(
                session_open=False,
                adaptive_executable=False,
                adaptive_side="WAIT",
                adaptive_expected_value_r=-0.4,
                hard_blockers=["MARKET_SESSION_CLOSED"],
            )
        ])["autonomous_options"]["NIFTY"]
        self.assertEqual(decision["status"], "WAIT")
        self.assertEqual(decision["primary_reason"], "MARKET_SESSION_CLOSED")
        self.assertEqual(decision["gates"]["MARKET_SESSION"]["state"], "BLOCKED")
        self.assertIn("NON_POSITIVE_EV", decision["rejection_reasons"])

    def test_paper_open_surfaces_position_stage_and_paper_desk_sizing(self):
        row = self._row(
            option_proposal={
                "executable": True,
                "selected": {
                    "symbol": "NSE:NIFTY2691523400CE",
                    "option_type": "call",
                    "risk_plan": {"entry": 118.0, "stop": 82.0, "target": 190.0},
                    "instrument_spec": {"tick_size": 0.05},
                    "economics": {"spread_pct": 0.01},
                    "quote": {"open_interest": 500000},
                },
            },
            execution_result={
                "success": True,
                "reason": "PAPER_POSITION_OPENED",
                "position_id": 91,
                "entry_reference": 118.05,
                "sizing": {"planned_quantity": 75, "risk_amount": 2700.0},
            },
        )
        decision = stages.summarise([row])["autonomous_options"]["NIFTY"]
        self.assertEqual(decision["status"], "POSITION_OPEN")
        self.assertEqual(decision["execution_stage"], "POSITION_OPEN")
        self.assertEqual(decision["quantity"], 75)
        self.assertEqual(decision["risk"], 2700.0)
        self.assertEqual(decision["gates"]["FRESH_LIVE_OPTION_QUOTE"]["state"], "PASS")

    def test_failure_remains_paper_only_and_surfaces_rejection(self):
        row = self._row(
            option_proposal={"executable": True, "selected_contract": "NSE:NIFTY2691523400CE", "selected": {"symbol": "NSE:NIFTY2691523400CE", "option_type": "call", "risk_plan": {"entry": 118.0, "stop": 82.0, "target": 190.0}}},
            execution_result={"success": False, "reason": "LIVE_MARK_OUTSIDE_SETUP"},
        )
        decision = stages.summarise([row])["autonomous_options"]["NIFTY"]
        self.assertEqual(decision["status"], "BLOCKED")
        self.assertIn("LIVE_MARK_OUTSIDE_SETUP", decision["rejection_reasons"])
        self.assertTrue(decision["paper_only"])
        self.assertFalse(decision["live_execution"])
        self.assertFalse(decision["automatic_broker_order"])


if __name__ == "__main__":
    unittest.main()
