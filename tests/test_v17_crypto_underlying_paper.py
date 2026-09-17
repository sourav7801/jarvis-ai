from __future__ import annotations

import unittest
from unittest.mock import patch

from omni.trading_intelligence.adaptive_opportunity_policy import (
    ADAPTIVE_OPPORTUNITY_POLICY,
    POLICY_VERSION,
)
from workstation.adaptive_paper_autonomy_engine import AdaptivePaperAutonomyEngine
from workstation.v17_crypto_paper_lane import (
    ADAPTIVE_AUTHORITY,
    CRYPTO_PAPER_UNIVERSE,
    crypto_paper_lane,
)


class _Runtime:
    def control(self, workspace, action):
        return {"success": True, "state": "RUNNING" if action == "start" else "PAUSED", "workspace": workspace}


class _Service:
    def status(self, workspace):
        return {"success": True, "workspace": workspace, "entry_session": "RUNNING"}


class _StatusRuntime(_Runtime):
    v17_autonomy_service = _Service()


class _CryptoLane:
    def start(self):
        return {
            "success": True,
            "running": True,
            "state": "RUNNING",
            "universe": ["BTC", "ETH", "SOL"],
            "qualification_authority": ADAPTIVE_AUTHORITY,
            "decision_authority": ADAPTIVE_AUTHORITY,
            "adaptive_policy_version": POLICY_VERSION,
            "last_rows_summary": [
                {
                    "symbol": "BTC",
                    "adaptive_side": "LONG",
                    "adaptive_action": "PROBE",
                    "adaptive_executable": True,
                    "adaptive_expected_value_r": 0.12,
                    "adaptive_confidence": 0.42,
                    "reason": "POSITIVE_EDGE_LOW_CONFIDENCE_PAPER_PROBE",
                }
            ],
            "positions": [],
            "open_positions": 0,
            "paper_only": True,
            "live_execution": False,
            "deribit_options_execution": False,
            "legacy_numeric_gates_are_execution_authority": False,
        }

    def stop_new_entries(self):
        return {
            "success": True,
            "running": False,
            "state": "PAUSED",
            "paper_only": True,
            "live_execution": False,
        }

    def status(self):
        return self.start()


class V17CryptoUnderlyingPaperTests(unittest.TestCase):
    @staticmethod
    def _preferences():
        return {
            "start_workspaces": ["INTRADAY", "SWING", "INVESTMENT"],
            "options_capital_fraction": 0.50,
            "one_touch_autopilot": True,
            "chart_first_options": True,
            "learning_enabled": True,
        }

    @staticmethod
    def _crypto_candidate(**overrides):
        row = {
            "success": True,
            "symbol": "BTC",
            "candidate_side": "LONG",
            "side": "LONG",
            "score": 0.0,
            "alignment": 100.0,
            "risk_reward": 2.4,
            "entry": 100.0,
            "stop": 95.0,
            "target": 112.0,
            "regime": "TREND",
            "blockers": [
                "SCORE_BELOW_GATE",
                "ALIGNMENT_BELOW_GATE",
                "RISK_REWARD_BELOW_GATE",
            ],
            "reasons_not_to_trade": [],
            "pattern_confirmation": {
                "state": "CONFIRMED_BREAKOUT",
                "direction": "BULLISH",
            },
            "votes": [
                {
                    "side": "LONG",
                    "family": "trend",
                    "strategy": "CRYPTO_TREND_TEST",
                    "regime_compatible": True,
                }
            ],
            "decisions": [{"name": "trend"}],
            "evidence": [{"available": True, "fresh": True}],
        }
        row.update(overrides)
        return row

    def test_lane_is_crypto_underlying_only_and_canonical_paper(self):
        self.assertEqual(CRYPTO_PAPER_UNIVERSE, ("BTC", "ETH", "SOL"))
        self.assertIsInstance(crypto_paper_lane.engine, AdaptivePaperAutonomyEngine)
        self.assertEqual(tuple(crypto_paper_lane.engine.universe), CRYPTO_PAPER_UNIVERSE)
        self.assertFalse(crypto_paper_lane.engine.manage_marks)
        status = crypto_paper_lane.status()
        self.assertTrue(status["canonical_paper_desk"])
        self.assertFalse(status["separate_crypto_ledger"])
        self.assertTrue(status["deribit_options_research_only"])
        self.assertFalse(status["deribit_options_execution"])
        self.assertTrue(status["paper_only"])
        self.assertFalse(status["live_execution"])
        self.assertFalse(status["automatic_broker_order"])
        self.assertEqual(status["qualification_authority"], ADAPTIVE_AUTHORITY)
        self.assertEqual(status["decision_authority"], ADAPTIVE_AUTHORITY)
        self.assertEqual(status["adaptive_policy_version"], POLICY_VERSION)
        self.assertFalse(status["legacy_numeric_gates_are_execution_authority"])
        self.assertTrue(status["hard_safety_gates_preserved"])
        self.assertIsInstance(status["last_rows_summary"], list)

    def test_crypto_legacy_numeric_gates_are_soft_evidence(self):
        decision = ADAPTIVE_OPPORTUNITY_POLICY.evaluate(
            self._crypto_candidate(),
            learning_state={},
            allowed_sides=("LONG", "SHORT"),
        )
        self.assertTrue(decision["executable"])
        self.assertIn(decision["action"], {"PRIMARY", "PROBE"})
        self.assertIn("SCORE_BELOW_GATE", decision["soft_evidence"])
        self.assertIn("ALIGNMENT_BELOW_GATE", decision["soft_evidence"])
        self.assertIn("RISK_REWARD_BELOW_GATE", decision["soft_evidence"])
        self.assertNotIn("SCORE_BELOW_GATE", decision["hard_blockers"])
        self.assertFalse(decision["legacy_static_score_gate"])
        self.assertFalse(decision["legacy_static_alignment_gate"])
        self.assertFalse(decision["legacy_static_risk_reward_gate"])
        self.assertGreater(decision["expected_value_r"], 0.0)
        self.assertGreater(decision["risk_multiplier"], 0.0)

    def test_crypto_invalid_risk_geometry_still_blocks(self):
        decision = ADAPTIVE_OPPORTUNITY_POLICY.evaluate(
            self._crypto_candidate(stop=None),
            learning_state={},
            allowed_sides=("LONG", "SHORT"),
        )
        self.assertFalse(decision["executable"])
        self.assertEqual(decision["action"], "WAIT")
        self.assertIn("INVALID_RISK_LEVELS", decision["hard_blockers"])
        self.assertEqual(decision["risk_multiplier"], 0.0)

    def test_one_touch_start_includes_crypto_underlying_lane(self):
        from workstation import v17_terminal_http as http

        with patch.object(http, "load_preferences", return_value=self._preferences()), patch.object(
            http, "crypto_paper_lane", _CryptoLane()
        ):
            result = http._autopilot_control(_Runtime(), {"action": "start"})
        self.assertTrue(result["success"])
        self.assertIn("CRYPTO_UNDERLYING", result["results"])
        self.assertEqual(result["states"]["CRYPTO_UNDERLYING"], "RUNNING")
        self.assertEqual(result["results"]["CRYPTO_UNDERLYING"]["decision_authority"], ADAPTIVE_AUTHORITY)
        self.assertTrue(result["paper_only"])
        self.assertFalse(result["live_execution"])
        self.assertFalse(result["automatic_broker_order"])

    def test_one_touch_stop_pauses_crypto_new_entries(self):
        from workstation import v17_terminal_http as http

        with patch.object(http, "load_preferences", return_value=self._preferences()), patch.object(
            http, "crypto_paper_lane", _CryptoLane()
        ):
            result = http._autopilot_control(_Runtime(), {"action": "stop"})
        self.assertTrue(result["success"])
        self.assertEqual(result["states"]["CRYPTO_UNDERLYING"], "PAUSED")
        self.assertTrue(result["paper_only"])
        self.assertFalse(result["live_execution"])

    def test_v17_status_exposes_nonblank_crypto_adaptive_rows(self):
        from workstation import v17_terminal_http as http

        with patch.object(http, "load_preferences", return_value=self._preferences()), patch.object(
            http, "_fyers_stream_status", return_value={"state": "CONNECTED", "fresh": True}
        ), patch.object(http, "crypto_paper_lane", _CryptoLane()):
            result = http._v17_status(_StatusRuntime(), "OPTIONS")

        lane = result["crypto_underlying_paper"]
        self.assertEqual(lane["qualification_authority"], ADAPTIVE_AUTHORITY)
        self.assertEqual(lane["decision_authority"], ADAPTIVE_AUTHORITY)
        self.assertEqual(lane["adaptive_policy_version"], POLICY_VERSION)
        self.assertFalse(lane["legacy_numeric_gates_are_execution_authority"])
        self.assertEqual(lane["last_rows_summary"][0]["symbol"], "BTC")
        self.assertEqual(lane["last_rows_summary"][0]["adaptive_action"], "PROBE")
        self.assertTrue(lane["last_rows_summary"][0]["adaptive_executable"])


if __name__ == "__main__":
    unittest.main()
