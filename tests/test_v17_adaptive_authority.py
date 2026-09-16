import unittest

from omni.trading_intelligence.adaptive_opportunity_policy import (
    ADAPTIVE_OPPORTUNITY_POLICY,
)


class V17AdaptiveAuthorityTests(unittest.TestCase):
    @staticmethod
    def strong_low_score_candidate(**overrides):
        row = {
            "success": True,
            "symbol": "NIFTY",
            "candidate_side": "LONG",
            "side": "LONG",
            "score": 0.0,
            "alignment": 100.0,
            "risk_reward": 2.0,
            "entry": 100.0,
            "stop": 95.0,
            "target": 110.0,
            "regime": "TREND",
            "blockers": ["SCORE_BELOW_GATE"],
            "reasons_not_to_trade": [],
            "pattern_confirmation": {
                "state": "CONFIRMED_BREAKOUT",
                "direction": "BULLISH",
            },
            "votes": [
                {
                    "side": "LONG",
                    "family": "trend",
                    "strategy": "TEST_TREND",
                    "regime_compatible": True,
                }
            ],
            "decisions": [{"name": "trend"}],
            "evidence": [{"available": True, "fresh": True}],
        }
        row.update(overrides)
        return row

    def test_legacy_numeric_score_gate_is_soft_evidence_not_binary_authority(self):
        decision = ADAPTIVE_OPPORTUNITY_POLICY.evaluate(
            self.strong_low_score_candidate(),
            learning_state={},
            allowed_sides=("LONG", "SHORT"),
        )
        self.assertTrue(decision["executable"])
        self.assertIn("SCORE_BELOW_GATE", decision["soft_evidence"])
        self.assertNotIn("SCORE_BELOW_GATE", decision["hard_blockers"])
        self.assertFalse(decision["legacy_static_score_gate"])
        self.assertFalse(decision["legacy_static_alignment_gate"])
        self.assertFalse(decision["legacy_static_risk_reward_gate"])
        self.assertGreater(decision["expected_value_r"], 0.0)
        self.assertGreater(decision["risk_multiplier"], 0.0)

    def test_real_data_safety_blocker_still_fails_closed(self):
        decision = ADAPTIVE_OPPORTUNITY_POLICY.evaluate(
            self.strong_low_score_candidate(
                blockers=["SCORE_BELOW_GATE", "STALE_MARKET_DATA"]
            ),
            learning_state={},
            allowed_sides=("LONG", "SHORT"),
        )
        self.assertFalse(decision["executable"])
        self.assertEqual(decision["action"], "WAIT")
        self.assertEqual(decision["risk_multiplier"], 0.0)
        self.assertIn("STALE_MARKET_DATA", decision["hard_blockers"])
        self.assertIn("SCORE_BELOW_GATE", decision["soft_evidence"])


if __name__ == "__main__":
    unittest.main()
