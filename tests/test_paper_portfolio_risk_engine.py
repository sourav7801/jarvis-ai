from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from workstation.paper_trading_desk import PaperTradingDesk


class PaperPortfolioRiskEngineTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "paper.sqlite3"

    def tearDown(self):
        self.temp.cleanup()

    @staticmethod
    def _open(desk: PaperTradingDesk, symbol: str = "AAA", quantity: float = 100):
        return desk.open_position(
            symbol=symbol,
            side="LONG",
            entry=100,
            stop=99,
            target=104,
            quantity=quantity,
            asset_type="EQUITY",
            strategy="BREAKOUT_V2",
        )

    def test_daily_loss_lock_blocks_every_new_entry_at_desk_boundary(self):
        desk = PaperTradingDesk(
            self.path,
            starting_equity=100_000,
            max_daily_loss_fraction=0.01,
            max_drawdown_fraction=0,
        )
        opened = self._open(desk, quantity=1_000)
        self.assertTrue(opened["success"])
        desk.close_position(position_id=opened["position_id"], exit_price=98, reason="TEST_LOSS")

        snapshot = desk.snapshot()
        self.assertLessEqual(snapshot["daily_total_pnl"], -2_000)
        self.assertIn("DAILY_LOSS_LOCK", snapshot["risk_locks"])
        blocked = self._open(desk, "BBB", 10)
        self.assertFalse(blocked["success"])
        self.assertEqual(blocked["reason"], "DAILY_LOSS_LOCK")

    def test_persistent_peak_equity_enforces_drawdown_lock_after_restart(self):
        desk = PaperTradingDesk(
            self.path,
            starting_equity=100_000,
            max_daily_loss_fraction=0,
            max_drawdown_fraction=0.01,
        )
        winner = self._open(desk, "WIN", 500)
        desk.close_position(position_id=winner["position_id"], exit_price=104, reason="TEST_WIN")
        self.assertEqual(desk.snapshot()["peak_equity"], 102_000)
        loser = self._open(desk, "LOSS", 1_000)
        desk.close_position(position_id=loser["position_id"], exit_price=98, reason="TEST_LOSS")

        restored = PaperTradingDesk(
            self.path,
            starting_equity=100_000,
            max_daily_loss_fraction=0,
            max_drawdown_fraction=0.01,
        )
        snapshot = restored.snapshot()
        self.assertEqual(snapshot["peak_equity"], 102_000)
        self.assertGreaterEqual(snapshot["drawdown_percent"], 1.0)
        blocked = self._open(restored, "NEXT", 10)
        self.assertEqual(blocked["reason"], "MAX_DRAWDOWN_LOCK")

    def test_symbol_and_configured_correlation_cluster_limits(self):
        strict_symbol = PaperTradingDesk(
            self.path,
            starting_equity=100_000,
            max_symbol_exposure_fraction=0.10,
        )
        blocked = self._open(strict_symbol, "AAA", 101)
        self.assertEqual(blocked["reason"], "MAX_SYMBOL_EXPOSURE")

        second_path = Path(self.temp.name) / "correlated.sqlite3"
        correlated = PaperTradingDesk(
            second_path,
            starting_equity=100_000,
            max_symbol_exposure_fraction=0.20,
            max_correlated_exposure_fraction=0.15,
            correlation_clusters={"AAA": "TECH", "BBB": "TECH"},
        )
        self.assertTrue(self._open(correlated, "AAA", 100)["success"])
        rejected = self._open(correlated, "BBB", 100)
        self.assertEqual(rejected["reason"], "MAX_CORRELATED_EXPOSURE")
        snapshot = correlated.snapshot()
        self.assertEqual(snapshot["correlation_clusters_status"], "CONFIGURED")
        self.assertAlmostEqual(snapshot["correlation_cluster_exposure"]["TECH"], 10_000)

    def test_exposure_breakdowns_and_mae_mfe_are_durable(self):
        desk = PaperTradingDesk(self.path, starting_equity=100_000)
        opened = desk.open_position(
            symbol="AAA",
            side="LONG",
            entry=100,
            stop=95,
            target=110,
            quantity=10,
            asset_type="EQUITY",
            strategy="BREAKOUT_V2",
        )
        self.assertTrue(opened["success"])
        position_id = opened["position_id"]

        desk.manage_positions({"AAA": 103})
        desk.manage_positions({"AAA": 98})
        live = desk.snapshot(mark_loader=lambda _symbol: 101)
        self.assertAlmostEqual(live["symbol_exposure"]["AAA"], 1_010)
        self.assertAlmostEqual(live["asset_class_exposure"]["EQUITY"], 1_010)
        self.assertAlmostEqual(live["strategy_exposure"]["BREAKOUT_V2"], 1_010)
        self.assertAlmostEqual(live["direction_exposure"]["LONG"], 1_010)

        closed = desk.close_position(position_id=position_id, exit_price=101, reason="MANUAL_REVIEW")
        self.assertAlmostEqual(closed["mfe_pnl"], 30)
        self.assertAlmostEqual(closed["mae_pnl"], -20)
        self.assertAlmostEqual(closed["mfe_r"], 0.6)
        self.assertAlmostEqual(closed["mae_r"], -0.4)
        restored = PaperTradingDesk(self.path).closed_positions()[0]
        self.assertAlmostEqual(restored["mfe_pnl"], 30)
        self.assertAlmostEqual(restored["mae_pnl"], -20)
        self.assertEqual(restored["exit_reason"], "MANUAL_REVIEW")


if __name__ == "__main__":
    unittest.main()
