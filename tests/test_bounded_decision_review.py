import json
from pathlib import Path
import tempfile
import unittest

from workstation.bounded_decision_review import BoundedDecisionReviewCoordinator
from workstation.paper_trading_desk import PaperTradingDesk


class BoundedDecisionReviewTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.db_path = root / "paper.sqlite3"
        self.ledger_path = root / "decision_reviews.json"
        self.desk = PaperTradingDesk(
            self.db_path,
            starting_equity=100_000,
            max_open_positions=20,
        )

    def tearDown(self):
        self.temp.cleanup()

    def _closed_trade(self, index, *, pnl="loss", strategy="BREAKOUT", timeframe="5m", regime="RANGE"):
        entry = 100.0
        stop = 99.0
        target = 102.0
        opened = self.desk.open_position(
            symbol=f"TEST{index}",
            side="LONG",
            entry=entry,
            stop=stop,
            target=target,
            quantity=1,
            timeframe=timeframe,
            strategy=strategy,
            score=72,
            source="AUTONOMOUS_PAPER",
            external_id=f"review-test-{index}",
            metadata={
                "regime": regime,
                "alignment": 0.5 if pnl == "loss" else 0.9,
                "patterns": ["RANGE_BREAKOUT"],
                "decision_version": "TEST_V1",
            },
        )
        self.assertTrue(opened["success"])
        closed = self.desk.close_position(
            position_id=opened["position_id"],
            exit_price=99.0 if pnl == "loss" else 102.0,
            reason="STOP_HIT" if pnl == "loss" else "TARGET_HIT",
        )
        self.assertTrue(closed["success"])

    def test_six_losses_disable_strategy_timeframe_and_are_fully_attributed(self):
        for index in range(6):
            self._closed_trade(index)
        coordinator = BoundedDecisionReviewCoordinator(
            db_path=self.db_path,
            ledger_path=self.ledger_path,
        )
        result = coordinator.review_once()
        self.assertEqual(result["new_reviews"], 6)
        self.assertEqual(result["policy_revisions"], 1)

        policy = coordinator.policy_for("BREAKOUT", "5m")
        self.assertFalse(policy["allowed"])
        self.assertEqual(policy["action"], "TEMPORARILY_DISABLE_COMBINATION")
        self.assertGreaterEqual(policy["risk_multiplier"], 0.5)
        self.assertLessEqual(policy["risk_multiplier"], 1.0)
        self.assertLessEqual(policy["minimum_score_delta"], 8.0)
        self.assertLessEqual(policy["minimum_risk_reward_delta"], 0.4)

        state = coordinator.snapshot()
        review = state["reviewed_trades"]["paper_desk:1"]
        self.assertEqual(review["timeframe"], "5m")
        self.assertEqual(review["regime"], "RANGE")
        self.assertEqual(review["risk"]["planned_risk_reward"], 2.0)
        self.assertEqual(review["reward"]["realized_r"], -1.0)
        self.assertIn("THESIS_INVALIDATED_AT_STOP", review["attribution_flags"])
        self.assertIn("WEAK_TIMEFRAME_ALIGNMENT", review["attribution_flags"])
        self.assertIn("BREAKOUT_STRATEGY_IN_NON_TREND_REGIME", review["attribution_flags"])
        self.assertTrue(review["synthetic_paper"])
        self.assertFalse(review["live_execution"])

    def test_review_is_idempotent_and_ledger_survives_restart(self):
        for index in range(5):
            self._closed_trade(index, pnl="win", strategy="TREND", regime="TRENDING_UP")
        first = BoundedDecisionReviewCoordinator(db_path=self.db_path, ledger_path=self.ledger_path)
        self.assertEqual(first.review_once()["new_reviews"], 5)
        revision_count = len(first.snapshot()["policy_revisions"])

        second = BoundedDecisionReviewCoordinator(db_path=self.db_path, ledger_path=self.ledger_path)
        result = second.review_once()
        self.assertEqual(result["new_reviews"], 0)
        self.assertEqual(result["policy_revisions"], 0)
        self.assertEqual(len(second.snapshot()["policy_revisions"]), revision_count)
        policy = second.policy_for("TREND", "5m")
        self.assertTrue(policy["allowed"])
        self.assertEqual(policy["risk_multiplier"], 1.0)
        self.assertEqual(policy["action"], "BASELINE_NO_RISK_INCREASE")

    def test_active_restriction_has_auditable_rollback(self):
        for index in range(6):
            self._closed_trade(index)
        coordinator = BoundedDecisionReviewCoordinator(db_path=self.db_path, ledger_path=self.ledger_path)
        coordinator.review_once()
        policy = coordinator.policy_for("BREAKOUT", "5m")
        rolled_back = coordinator.rollback(policy["rollback_token"], reason="operator verified data defect")
        self.assertTrue(rolled_back["success"])
        restored = coordinator.policy_for("BREAKOUT", "5m")
        self.assertTrue(restored["allowed"])
        self.assertEqual(restored["action"], "BASELINE_INSUFFICIENT_EVIDENCE")

        saved = json.loads(self.ledger_path.read_text(encoding="utf-8"))
        self.assertEqual(saved["policy_revisions"][0]["status"], "ROLLED_BACK")
        self.assertEqual(saved["rollback_events"][0]["reason"], "operator verified data defect")
        self.assertFalse(saved["safety"]["self_modifying_code"])
        repeated = coordinator.review_once()
        self.assertEqual(repeated["new_reviews"], 0)
        self.assertEqual(repeated["policy_revisions"], 0)
        self.assertTrue(coordinator.policy_for("BREAKOUT", "5m")["allowed"])

    def test_loss_streak_tightens_gates_without_disabling_or_increasing_risk(self):
        for index in range(3):
            self._closed_trade(index, pnl="loss", strategy="MEAN_REVERSION", timeframe="15m")
        for index in range(3, 5):
            self._closed_trade(index, pnl="win", strategy="MEAN_REVERSION", timeframe="15m")
        coordinator = BoundedDecisionReviewCoordinator(
            db_path=self.db_path,
            ledger_path=self.ledger_path,
        )
        coordinator.review_once()
        policy = coordinator.policy_for("MEAN_REVERSION", "15m")
        self.assertTrue(policy["allowed"])
        self.assertEqual(policy["action"], "REDUCE_RISK_AND_TIGHTEN_GATES")
        self.assertGreaterEqual(policy["risk_multiplier"], 0.5)
        self.assertLess(policy["risk_multiplier"], 1.0)
        self.assertGreater(policy["minimum_score_delta"], 0.0)
        self.assertGreater(policy["minimum_risk_reward_delta"], 0.0)

    def test_coordinator_has_no_execution_or_code_mutation_surface(self):
        source = (
            Path(__file__).resolve().parents[1]
            / "workstation"
            / "bounded_decision_review.py"
        ).read_text(encoding="utf-8").lower()
        self.assertNotIn("place_order", source)
        self.assertNotIn("submit_order", source)
        self.assertNotIn("fyers_apiv3", source)
        self.assertNotIn("subprocess", source)
        status = BoundedDecisionReviewCoordinator(
            db_path=self.db_path,
            ledger_path=self.ledger_path,
        ).status()
        self.assertTrue(status["paper_only"])
        self.assertFalse(status["live_execution"])
        self.assertFalse(status["self_modifying_code"])


if __name__ == "__main__":
    unittest.main()
