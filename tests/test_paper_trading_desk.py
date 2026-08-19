from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from workstation.paper_trading_desk import PaperTradingDesk, paper_command_kind


class PaperTradingDeskTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.desk = PaperTradingDesk(
            Path(self.temp.name) / "paper.sqlite3",
            starting_equity=100000,
            max_open_positions=4,
            max_total_risk_fraction=0.04,
            max_single_risk_fraction=0.01,
            max_gross_exposure_multiple=2.0,
        )

    def tearDown(self):
        self.temp.cleanup()

    def test_open_mark_and_close_position(self):
        opened = self.desk.open_position(
            symbol="NIFTY",
            side="LONG",
            entry=100.0,
            stop=98.0,
            target=104.0,
            quantity=10,
            external_id="test:nifty",
        )
        self.assertTrue(opened["success"])
        self.assertFalse(opened["live_execution"])

        snap = self.desk.snapshot(mark_loader=lambda _symbol: 102.0)
        self.assertEqual(snap["open_count"], 1)
        self.assertAlmostEqual(snap["unrealized_pnl"], 20.0)
        self.assertAlmostEqual(snap["risk_at_stops"], 20.0)

        closed = self.desk.close_position(
            symbol="NIFTY",
            exit_price=103.0,
            reason="TEST_EXIT",
        )
        self.assertTrue(closed["success"])
        self.assertAlmostEqual(closed["realized_pnl"], 30.0)
        final = self.desk.snapshot()
        self.assertEqual(final["open_count"], 0)
        self.assertAlmostEqual(final["realized_pnl"], 30.0)

    def test_duplicate_external_id_is_idempotent(self):
        kwargs = dict(
            symbol="BTC",
            side="LONG",
            entry=100.0,
            stop=99.0,
            target=102.0,
            quantity=10,
            external_id="same-id",
        )
        first = self.desk.open_position(**kwargs)
        second = self.desk.open_position(**kwargs)
        self.assertTrue(first["success"])
        self.assertEqual(second["reason"], "ALREADY_RECORDED")
        self.assertEqual(self.desk.snapshot()["open_count"], 1)

    def test_portfolio_risk_gate(self):
        result = self.desk.open_position(
            symbol="NIFTY",
            side="LONG",
            entry=100.0,
            stop=90.0,
            target=120.0,
            quantity=500,
        )
        self.assertFalse(result["success"])
        self.assertIn(result["reason"], {"SINGLE_TRADE_RISK_LIMIT", "GROSS_EXPOSURE_LIMIT"})

    def test_stop_target_evaluation(self):
        self.desk.open_position(
            symbol="CRUDEOIL",
            side="LONG",
            entry=100.0,
            stop=95.0,
            target=110.0,
            quantity=10,
        )
        closed = self.desk.evaluate_stops_targets({"CRUDEOIL": 111.0})
        self.assertEqual(len(closed), 1)
        self.assertEqual(closed[0]["reason"], "TARGET_HIT")

    def test_natural_paper_commands(self):
        self.assertEqual(paper_command_kind("open paper trading"), "OPEN_DESK")
        self.assertEqual(paper_command_kind("my paper trading position"), "PORTFOLIO")
        self.assertEqual(
            paper_command_kind("Show my current paper trading portfolio, positions, P and L and risk exposure."),
            "PORTFOLIO",
        )
        self.assertEqual(paper_command_kind("start autonomous paper trading"), "AUTO_START")
        self.assertEqual(paper_command_kind("stop autonomous paper trading"), "AUTO_STOP")

    def test_live_execution_is_permanently_false(self):
        self.assertFalse(self.desk.live_execution)
        self.assertFalse(self.desk.snapshot()["live_execution"])


if __name__ == "__main__":
    unittest.main()
