from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from omni.trading_intelligence.continuous_execution_policy_v14 import ContinuousExecutionPolicyV14
from workstation.opportunity_lifecycle_v14 import OpportunityLifecycleV14


def _row(*, score: float = 10.0, side: str = "LONG") -> dict:
    return {
        "success": True,
        "symbol": "BTC",
        "profile": "adaptive_intraday",
        "timeframe": "5m",
        "candidate_side": side,
        "side": "WAIT",
        "score": score,
        "alignment": 40.0,
        "risk_reward": 2.0,
        "entry": 80000.0,
        "stop": 79500.0 if side == "LONG" else 80500.0,
        "target": 81000.0 if side == "LONG" else 79000.0,
        "blockers": ["SCORE_BELOW_GATE", "ALIGNMENT_BELOW_GATE"],
        "reasons_not_to_trade": ["SCORE_BELOW_GATE", "ALIGNMENT_BELOW_GATE"],
        "paper_only": True,
        "live_execution": False,
    }


def _contextual(*, ev: float, confidence: float, hard=None, side: str = "LONG") -> dict:
    return {
        "policy_version": "CONTEXTUAL_DECISION_ENGINE_V13",
        "action": "WAIT",
        "executable": False,
        "side": "WAIT",
        "probability_win": 0.51,
        "expected_value_r": ev,
        "confidence": confidence,
        "uncertainty": 1.0 - confidence,
        "required_edge_r": 0.20,
        "risk_multiplier": 0.0,
        "hard_blockers": list(hard or []),
        "soft_evidence": ["SCORE_BELOW_GATE", "ALIGNMENT_BELOW_GATE"],
        "base_v12_decision": {"side": side, "risk_multiplier": 0.0},
        "portfolio_correlation": {
            "success": True,
            "state": "NO_OPEN_PEERS",
            "risk_multiplier": 1.0,
            "paper_only": True,
            "live_execution": False,
        },
        "paper_only": True,
        "live_execution": False,
    }


class ContinuousExecutionPolicyV14Tests(unittest.TestCase):
    def test_positive_ev_executes_even_when_confidence_is_very_low_and_score_is_low(self) -> None:
        engine = ContinuousExecutionPolicyV14()
        with patch(
            "omni.trading_intelligence.continuous_execution_policy_v14.CONTEXTUAL_DECISION_ENGINE_V13.evaluate",
            return_value=_contextual(ev=0.01, confidence=0.05),
        ):
            decision = engine.evaluate(_row(score=3.0))
        self.assertTrue(decision["executable"])
        self.assertEqual(decision["side"], "LONG")
        self.assertGreater(decision["risk_multiplier"], 0.0)
        self.assertEqual(decision["action"], "PROBE")
        self.assertFalse(decision["arbitrary_confidence_execution_gate"])
        self.assertFalse(decision["legacy_static_score_gate"])
        self.assertEqual(decision["positive_ev_execution_boundary_r"], 0.0)
        self.assertFalse(decision["live_execution"])

    def test_negative_ev_waits_even_with_high_legacy_score(self) -> None:
        engine = ContinuousExecutionPolicyV14()
        with patch(
            "omni.trading_intelligence.continuous_execution_policy_v14.CONTEXTUAL_DECISION_ENGINE_V13.evaluate",
            return_value=_contextual(ev=-0.001, confidence=0.99),
        ):
            decision = engine.evaluate(_row(score=99.0))
        self.assertFalse(decision["executable"])
        self.assertEqual(decision["action"], "WAIT")
        self.assertEqual(decision["risk_multiplier"], 0.0)
        self.assertIn("NON_POSITIVE_CONTEXTUAL_EXPECTED_VALUE", decision["reasons"])

    def test_stale_data_remains_hard_veto_despite_positive_ev(self) -> None:
        engine = ContinuousExecutionPolicyV14()
        with patch(
            "omni.trading_intelligence.continuous_execution_policy_v14.CONTEXTUAL_DECISION_ENGINE_V13.evaluate",
            return_value=_contextual(ev=2.0, confidence=0.95, hard=["STALE_MARKET_DATA"]),
        ):
            decision = engine.evaluate(_row(score=99.0))
        self.assertFalse(decision["executable"])
        self.assertIn("STALE_MARKET_DATA", decision["hard_blockers"])
        self.assertEqual(decision["risk_multiplier"], 0.0)

    def test_correlation_can_only_reduce_continuous_risk(self) -> None:
        engine = ContinuousExecutionPolicyV14()
        contextual = _contextual(ev=0.8, confidence=0.8)
        contextual["portfolio_correlation"] = {
            "success": True,
            "state": "VERY_HIGH_SAME_DIRECTION_CORRELATION",
            "risk_multiplier": 0.35,
            "paper_only": True,
            "live_execution": False,
        }
        with patch(
            "omni.trading_intelligence.continuous_execution_policy_v14.CONTEXTUAL_DECISION_ENGINE_V13.evaluate",
            return_value=contextual,
        ):
            decision = engine.evaluate(_row(score=20.0))
        self.assertTrue(decision["executable"])
        self.assertLessEqual(decision["risk_multiplier"], 0.35)
        self.assertTrue(decision["correlation_can_only_reduce_risk"])


class OpportunityLifecycleV14Tests(unittest.TestCase):
    def test_lifecycle_replaces_ambiguous_watching_with_exact_states(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            lifecycle = OpportunityLifecycleV14(Path(folder) / "lifecycle.json")
            actionable = lifecycle.observe_row(
                {
                    "symbol": "BTC",
                    "adaptive_executable": True,
                    "adaptive_expected_value_r": 0.12,
                    "adaptive_confidence": 0.21,
                    "adaptive_action": "PROBE",
                    "hard_blockers": [],
                },
                bucket="INTRADAY",
                lane="5M",
            )
            self.assertEqual(actionable["state"], "ACTIONABLE")
            waiting = lifecycle.observe_row(
                {
                    "symbol": "ETH",
                    "adaptive_executable": False,
                    "adaptive_expected_value_r": -0.01,
                    "hard_blockers": [],
                },
                bucket="INTRADAY",
                lane="15M",
            )
            self.assertEqual(waiting["state"], "WAIT_NEGATIVE_OR_ZERO_EV")
            blocked = lifecycle.observe_row(
                {
                    "symbol": "SOL",
                    "adaptive_executable": False,
                    "adaptive_expected_value_r": 1.0,
                    "hard_blockers": ["STALE_MARKET_DATA"],
                },
                bucket="INTRADAY",
                lane="5M",
            )
            self.assertEqual(blocked["state"], "BLOCKED_SAFETY_OR_DATA")
            snapshot = lifecycle.snapshot()
            self.assertTrue(snapshot["watching_is_not_a_terminal_state"])
            self.assertEqual(snapshot["state_counts"]["ACTIONABLE"], 1)
            self.assertEqual(snapshot["top_hard_blockers"][0]["reason"], "STALE_MARKET_DATA")


if __name__ == "__main__":
    unittest.main()
