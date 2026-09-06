from __future__ import annotations

import unittest
from pathlib import Path
import tempfile
from unittest.mock import MagicMock

from workstation.paper_portfolio_controller import PaperPortfolioController
from workstation.paper_trading_desk import PaperTradingDesk


class PaperPortfolioControllerTests(unittest.TestCase):
    def test_start_arms_three_governed_paper_buckets(self):
        engines = {
            "INTRADAY": MagicMock(),
            "SWING": MagicMock(),
            "INVESTMENT": MagicMock(),
        }
        for engine in engines.values():
            engine.configure_mandate.return_value = {"success": True}
            engine.start.return_value = {
                "success": True,
                "running": True,
                "paper_only": True,
                "live_execution": False,
            }
            engine.status.return_value = engine.start.return_value

        controller = PaperPortfolioController(engines=engines)
        result = controller.start(intraday_profile="adaptive_intraday")

        self.assertTrue(result["running"])
        self.assertEqual(result["allocations"], {
            "INTRADAY": 0.50,
            "SWING": 0.30,
            "INVESTMENT": 0.20,
        })
        engines["INTRADAY"].start.assert_called_once_with(profile="adaptive_intraday", scan_now=True)
        engines["SWING"].start.assert_called_once_with(profile="swing", scan_now=True)
        engines["INVESTMENT"].start.assert_called_once_with(profile="investment", scan_now=True)
        self.assertTrue(result["paper_only"])
        self.assertFalse(result["live_execution"])

    def test_invalid_allocation_is_rejected(self):
        controller = PaperPortfolioController(engines={})
        with self.assertRaises(ValueError):
            controller.configure({"INTRADAY": 0.8, "SWING": 0.3, "INVESTMENT": 0.2})

    def test_bucket_risk_limit_prevents_one_horizon_using_another_budget(self):
        with tempfile.TemporaryDirectory() as temp:
            desk = PaperTradingDesk(
                Path(temp) / "desk.sqlite3",
                starting_equity=100_000,
                max_total_risk_fraction=0.04,
            )
            first = desk.open_position(
                symbol="BTC",
                side="LONG",
                entry=100,
                stop=99,
                target=102,
                quantity=20,
                portfolio_bucket="INVESTMENT",
                bucket_allocation_fraction=0.20,
            )
            second = desk.open_position(
                symbol="ETH",
                side="LONG",
                entry=100,
                stop=99,
                target=102,
                quantity=800,
                portfolio_bucket="INVESTMENT",
                bucket_allocation_fraction=0.20,
            )

            self.assertTrue(first["success"])
            self.assertFalse(second["success"])
            self.assertEqual(second["reason"], "BUCKET_RISK_LIMIT")
            snapshot = desk.snapshot()
            self.assertEqual(snapshot["bucket_risk_at_stops"]["INVESTMENT"], 20)


if __name__ == "__main__":
    unittest.main()
