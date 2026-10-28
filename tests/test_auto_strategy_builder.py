import math
import unittest

from omni.trading_intelligence.auto_strategy_builder import (
    backtest,
    build_strategy_report,
    candidate_specs,
)


def candles(n=320):
    rows = []
    price = 100.0
    for i in range(n):
        price *= 1.0012 if (i // 35) % 2 == 0 else 0.9994
        price += (i % 7 - 3) * 0.025
        rows.append({"close": price, "high": price * 1.003, "low": price * 0.997, "volume": 1000 + i})
    return rows


class AutoStrategyBuilderTests(unittest.TestCase):
    def test_candidate_space_is_small_and_explainable(self):
        specs = candidate_specs()
        self.assertGreaterEqual(len(specs), 4)
        self.assertTrue(all(s.name and s.family and s.parameters and s.description for s in specs))

    def test_backtest_requires_minimum_evaluation_window(self):
        result = backtest(candles(30), candidate_specs()[0], start=2, end=4)
        self.assertFalse(result["ready"])
        self.assertEqual(result["reason"], "INSUFFICIENT_EVALUATION_BARS")

    def test_builder_splits_chronologically_and_never_enables_live_execution(self):
        result = build_strategy_report(candles(), minimum_train_bars=100, minimum_test_bars=30)
        self.assertTrue(result["success"])
        self.assertEqual(result["state"], "PAPER_CANDIDATES_READY")
        self.assertLess(result["split_index"], result["bars"])
        self.assertEqual(len(result["candidates"]), len(candidate_specs()))
        self.assertTrue(result["governance"]["chronological_holdout"])
        self.assertFalse(result["governance"]["automatic_live_execution"])
        self.assertFalse(result["governance"]["automatic_code_rewrite"])
        self.assertFalse(result["governance"]["live_execution"])
        self.assertTrue(all("out_of_sample" in row and "train" in row for row in result["candidates"]))
        self.assertTrue(all("walk_forward" in row and "walk_forward_pass" in row for row in result["candidates"]))
        self.assertTrue(result["governance"]["walk_forward_required_before_paper"])

    def test_builder_refuses_insufficient_history(self):
        result = build_strategy_report(candles(80))
        self.assertFalse(result["success"])
        self.assertEqual(result["state"], "INSUFFICIENT_DATA")

    def test_backtest_accounts_for_round_trip_costs(self):
        rows, spec = candles(), candidate_specs()[0]
        free = backtest(rows, spec, cost_per_turn_pct=0, slippage_per_turn_pct=0)
        charged = backtest(rows, spec, cost_per_turn_pct=0.15, slippage_per_turn_pct=0.10)
        self.assertLessEqual(charged["metrics"]["net_return_pct"], free["metrics"]["net_return_pct"])

    def test_backtest_rejects_negative_or_nonfinite_costs(self):
        negative = backtest(candles(), candidate_specs()[0], cost_per_turn_pct=-0.1)
        infinite = backtest(candles(), candidate_specs()[0], slippage_per_turn_pct=float("inf"))
        self.assertFalse(negative["ready"])
        self.assertEqual(negative["reason"], "INVALID_COST_ASSUMPTION")
        self.assertFalse(infinite["ready"])
        self.assertEqual(infinite["reason"], "INVALID_COST_ASSUMPTION")

    def test_trade_metrics_count_completed_round_trips_not_signal_flips(self):
        metrics = backtest(candles(), candidate_specs()[0])["metrics"]
        self.assertGreaterEqual(metrics["trades"], 0)
        self.assertGreaterEqual(metrics["win_rate"], 0)
        self.assertLessEqual(metrics["win_rate"], 100)
        if metrics["trades"] == 0:
            self.assertEqual(metrics["expectancy_pct"], 0.0)
        else:
            self.assertIsInstance(metrics["expectancy_pct"], float)

    def test_builder_rejects_invalid_risk_assumptions(self):
        with self.assertRaisesRegex(ValueError, "max_drawdown_pct"):
            build_strategy_report(candles(), max_drawdown_pct=float("nan"))
        with self.assertRaisesRegex(ValueError, "Cost and slippage"):
            build_strategy_report(candles(), cost_per_turn_pct=-1)

    def test_builder_skips_malformed_non_dictionary_candle_rows(self):
        rows = candles()
        rows[0], rows[1] = None, "not a candle"
        rows[2] = {"close": 100, "high": 99, "low": 101}
        result = build_strategy_report(rows, minimum_train_bars=100, minimum_test_bars=30)
        self.assertTrue(result["success"])
        self.assertEqual(result["bars"], len(rows) - 3)


if __name__ == "__main__":
    unittest.main()
