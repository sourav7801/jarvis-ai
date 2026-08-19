from __future__ import annotations

import unittest

from omni.trading_intelligence.autonomous_paper_trader import AutonomousPaperTrader


def bullish_candles(count: int = 140):
    rows = []
    price = 100.0
    for index in range(count):
        price += 0.45
        rows.append(
            {
                "time": index + 1,
                "open": price - 0.25,
                "high": price + 0.50,
                "low": price - 0.55,
                "close": price,
                "volume": 1500 + index * 20,
            }
        )
    return rows


class AutonomousPaperTraderTests(unittest.TestCase):
    def test_live_execution_is_permanently_false(self):
        trader = AutonomousPaperTrader()
        self.assertFalse(trader.live_execution)

    def test_strong_signal_can_create_paper_intent_only(self):
        trader = AutonomousPaperTrader(min_score=50.0)
        result = trader.evaluate("NIFTY", "5m", bullish_candles())
        self.assertTrue(result["paper_only"])
        self.assertFalse(result["live_execution"])
        if result["paper_intent"] is not None:
            self.assertEqual(result["paper_intent"]["status"], "PAPER_INTENT")
            self.assertFalse(result["paper_intent"]["live_execution"])

    def test_daily_loss_lock_blocks_new_positions(self):
        trader = AutonomousPaperTrader(equity=100000.0, max_daily_loss_fraction=0.02)
        trader.closed_pnl = -2500.0
        result = trader.evaluate("NIFTY", "5m", bullish_candles())
        self.assertEqual(result["risk_gate"], "DAILY_LOSS_LOCK")
        self.assertIsNone(result["paper_intent"])

    def test_universe_scan_never_enables_live_execution(self):
        trader = AutonomousPaperTrader(min_score=50.0)
        results = trader.scan_universe(
            ["NIFTY", "CRUDEOIL", "BTC"],
            "5m",
            lambda symbol, timeframe: bullish_candles(),
        )
        self.assertEqual(len(results), 3)
        self.assertTrue(all(row.get("live_execution") is False for row in results))


if __name__ == "__main__":
    unittest.main()
