import unittest

from workstation.paper_learning import PaperLearningLedger


class PaperLearningLedgerTests(unittest.TestCase):
    def test_loss_review_records_flags_and_reduces_strategy_risk(self):
        ledger = PaperLearningLedger()
        ledger.remember_entry(
            "CRUDEOIL",
            {
                "strategy": "BREAKOUT",
                "patterns": ["BULLISH_BREAKOUT"],
                "confidence": 84,
                "risk_reward": 2.2,
                "entry_price": 8000,
                "stop_loss": 7950,
                "take_profit": 8110,
                "quantity": 2,
            },
        )
        review = ledger.review_trade(
            {
                "trade_id": "loss-1",
                "symbol": "CRUDEOIL",
                "quantity": 2,
                "entry_price": 8000,
                "net_pnl": -100,
                "closed_at": "2026-08-17T10:00:00+00:00",
                "reason": "STOP_LOSS",
            }
        )
        self.assertEqual(review["outcome"], "LOSS")
        self.assertEqual(review["r_multiple"], -1.0)
        self.assertIn("THESIS_INVALIDATED_AT_STOP", review["review_flags"])
        self.assertLess(ledger.policy("BREAKOUT")["risk_multiplier"], 1.0)

    def test_three_consecutive_losses_pause_strategy(self):
        ledger = PaperLearningLedger()
        for index in range(3):
            ledger.remember_entry(
                "BTC",
                {
                    "strategy": "TREND_FOLLOWING",
                    "patterns": ["HIGHER_HIGHS"],
                    "confidence": 84,
                    "risk_reward": 2.2,
                    "entry_price": 100,
                    "stop_loss": 99,
                    "take_profit": 102.2,
                    "quantity": 1,
                },
            )
            ledger.review_trade(
                {
                    "trade_id": f"loss-{index}",
                    "symbol": "BTC",
                    "quantity": 1,
                    "entry_price": 100,
                    "net_pnl": -1,
                    "closed_at": f"2026-08-17T10:0{index}:00+00:00",
                    "reason": "STOP_LOSS",
                }
            )
        self.assertFalse(ledger.policy("TREND_FOLLOWING")["allowed"])
        self.assertEqual(ledger.snapshot()["daily_reviews"][0]["losses"], 3)


if __name__ == "__main__":
    unittest.main()
