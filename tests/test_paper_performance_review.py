from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from workstation.jarvis_os_v3 import dispatch_command
from workstation.paper_trading_desk import (
    PaperTradingDesk,
    is_performance_review_request,
)


class PaperPerformanceReviewTests(unittest.TestCase):
    def test_natural_loss_question_has_specific_intent(self):
        self.assertTrue(is_performance_review_request(
            "you have booked losses today and yesterday analyze why it happen"
        ))
        self.assertFalse(is_performance_review_request("analyze BANKNIFTY chart"))

    def test_review_uses_durable_trade_evidence_and_trailing_policy(self):
        with tempfile.TemporaryDirectory() as directory:
            desk = PaperTradingDesk(Path(directory) / "paper.sqlite3", starting_equity=100_000)
            opened = desk.open_position(
                symbol="TEST", side="LONG", entry=100, stop=99, target=102, quantity=10,
                score=64, strategy="RANGE_TEST", timeframe="5m",
                metadata={
                    "regime": "RANGE",
                    "contradictions": [{"reason": "opposing vote"}],
                    "evidence_graph": [{"side": "LONG", "regime_compatible": False}],
                    "exit_policy": {
                        "breakeven_at_r": .75, "trailing_at_r": 1.0,
                        "trailing_distance_r": .5, "max_hold_minutes": 390,
                    },
                },
            )
            desk.manage_positions({"TEST": 100.5})
            desk.close_position(position_id=opened["position_id"], exit_price=99, reason="STOP_HIT")
            review = desk.performance_review(days=1, now=datetime.now(timezone.utc))
            self.assertEqual(review["days"][0]["losses"], 1)
            self.assertEqual(review["trades"][0]["exit_reason"], "STOP_HIT")
            self.assertEqual(review["trades"][0]["contradiction_count"], 1)
            self.assertFalse(review["trades"][0]["trailing_activated"])
            self.assertTrue(any("below a 68 score" in item for item in review["findings"]))
            self.assertTrue(review["paper_only"])
            self.assertFalse(review["live_execution"])

    def test_v31_command_router_opens_paper_review_before_quant(self):
        evidence = {
            "success": True, "timezone": "Asia/Kolkata",
            "days": [{"date": "2026-08-26", "trades": 2, "wins": 0, "losses": 2, "net_pnl": -50}],
            "trades": [{"symbol": "TEST"}], "findings": ["2/2 losses entered below a 68 score"],
            "paper_only": True, "live_execution": False,
        }
        with patch("workstation.paper_trading_desk.paper_desk.performance_review", return_value=evidence):
            result = dispatch_command("analyze why my trading losses happened today")
        self.assertEqual(result["route"], "PAPER_PERFORMANCE_REVIEW")
        self.assertEqual(result["workspace_actions"][0]["window"], "paper")
        self.assertIn("durable portfolio ledger", result["response"])


if __name__ == "__main__":
    unittest.main()
