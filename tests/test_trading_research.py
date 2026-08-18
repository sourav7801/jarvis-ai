import unittest
from datetime import datetime, timedelta, timezone

from trading.research.market_data import Candle, DataProvenance, MarketDataset
from trading.research.replay import ReplayConfig, ReplayEngine
from trading.research.risk import PortfolioGuard, RiskLimits


def dataset(prices=(100.0, 101.0, 102.0, 103.0)):
    start = datetime(2026, 1, 1, 9, 15, tzinfo=timezone.utc)
    candles = [
        Candle(
            start + timedelta(minutes=5 * index),
            price,
            price + 1.0,
            price - 1.0,
            price + 1.0,
            1000.0,
        )
        for index, price in enumerate(prices)
    ]
    provenance = DataProvenance(
        "SYNTHETIC", "unit-test", datetime(2026, 1, 1, tzinfo=timezone.utc)
    )
    return MarketDataset.create("NIFTY", "5m", candles, provenance)


class MarketDataTests(unittest.TestCase):
    def test_checksum_is_deterministic(self):
        self.assertEqual(dataset().checksum, dataset().checksum)

    def test_naive_timestamp_is_rejected(self):
        with self.assertRaises(ValueError):
            Candle(datetime(2026, 1, 1), 100, 101, 99, 100)

    def test_duplicate_timestamp_is_rejected(self):
        item = Candle(
            datetime(2026, 1, 1, tzinfo=timezone.utc), 100, 101, 99, 100
        )
        provenance = DataProvenance(
            "SYNTHETIC", "test", datetime.now(timezone.utc)
        )
        with self.assertRaises(ValueError):
            MarketDataset.create("NIFTY", "5m", [item, item], provenance)

    def test_stale_dataset_is_rejected(self):
        with self.assertRaises(ValueError):
            dataset().assert_fresh(
                timedelta(hours=1),
                now=datetime(2026, 1, 2, tzinfo=timezone.utc),
            )

    def test_non_finite_price_is_rejected(self):
        with self.assertRaises(ValueError):
            Candle(
                datetime(2026, 1, 1, tzinfo=timezone.utc),
                float("nan"),
                101,
                99,
                100,
            )


class ReplayTests(unittest.TestCase):
    def test_signal_executes_on_next_bar(self):
        data = dataset()
        result = ReplayEngine(
            ReplayConfig(
                starting_capital=10_000,
                quantity=10,
                commission_bps=0,
                slippage_bps=0,
            )
        ).run(data, lambda _candles, _index: 1)

        self.assertEqual(len(result.trades), 1)
        self.assertEqual(result.trades[0].signal_timestamp, data.candles[0].timestamp)
        self.assertEqual(result.trades[0].entry_timestamp, data.candles[1].timestamp)
        self.assertAlmostEqual(result.ending_equity, 10_030.0)

    def test_fees_and_slippage_are_deterministic(self):
        engine = ReplayEngine(
            ReplayConfig(
                starting_capital=10_000,
                quantity=10,
                commission_bps=5,
                fixed_fee_per_fill=2,
                slippage_bps=10,
            )
        )
        first = engine.run(dataset(), lambda _candles, _index: 1)
        second = engine.run(dataset(), lambda _candles, _index: 1)
        self.assertEqual(first, second)
        self.assertGreater(first.total_fees, 0)
        self.assertLess(first.ending_equity, 10_030.0)

    def test_excessive_symbol_exposure_rejects_entry(self):
        limits = RiskLimits(max_symbol_exposure_pct=5)
        result = ReplayEngine(
            ReplayConfig(starting_capital=10_000, quantity=10), limits
        ).run(dataset(), lambda _candles, _index: 1)
        self.assertEqual(result.trades, ())
        self.assertGreater(result.rejected_signals, 0)


class PortfolioGuardTests(unittest.TestCase):
    def test_daily_loss_kill_switch_is_sticky(self):
        guard = PortfolioGuard(
            10_000,
            RiskLimits(max_daily_loss_pct=2, max_drawdown_pct=5),
        )
        self.assertFalse(guard.update_equity(9_700))
        self.assertTrue(guard.halted)
        self.assertEqual(guard.halt_reason, "MAX_DAILY_LOSS")
        self.assertFalse(guard.update_equity(10_100))

    def test_reset_requires_explicit_confirmation(self):
        guard = PortfolioGuard(10_000)
        with self.assertRaises(PermissionError):
            guard.reset_for_new_day(10_000)

    def test_missing_price_fails_closed(self):
        guard = PortfolioGuard(10_000)
        result = guard.evaluate_positions({"NIFTY": 1}, {}, 10_000)
        self.assertFalse(result["allowed"])
        self.assertEqual(result["reason"], "MISSING_PRICE")


if __name__ == "__main__":
    unittest.main()
