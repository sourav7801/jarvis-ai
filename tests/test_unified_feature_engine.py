from __future__ import annotations

from datetime import datetime, timedelta, timezone
import math
import unittest

from workstation.indicator_registry import INDICATOR_REGISTRY, IndicatorPlugin, IndicatorRegistry
from workstation.unified_feature_engine import UNIFIED_FEATURE_ENGINE, detect_swings


def candles(count: int = 160) -> list[dict]:
    start = datetime(2026, 1, 5, 3, 45, tzinfo=timezone.utc)
    rows = []
    previous = 100.0
    for index in range(count):
        trend = index * 0.08
        wave = math.sin(index / 4.0) * 2.2
        close = 100.0 + trend + wave
        open_price = previous
        high = max(open_price, close) + 0.7 + (0.25 if index % 9 == 0 else 0)
        low = min(open_price, close) - 0.7 - (0.25 if index % 11 == 0 else 0)
        rows.append(
            {
                "time": int((start + timedelta(minutes=5 * index)).timestamp()),
                "open": open_price,
                "high": high,
                "low": low,
                "close": close,
                "volume": 1000 + (index % 13) * 80,
            }
        )
        previous = close
    return rows


class IndicatorRegistryTests(unittest.TestCase):
    def test_blueprint_initial_indicator_library_is_registered(self):
        names = {row["name"] for row in INDICATOR_REGISTRY.catalog()}
        expected = {
            "SMA", "EMA", "WMA", "HMA", "VWAP", "Anchored VWAP",
            "RSI", "Stochastic RSI", "MACD", "ADX DMI", "ATR",
            "Bollinger Bands", "Keltner", "Supertrend", "Donchian",
            "Ichimoku", "CCI", "MFI", "ROC", "OBV", "CMF",
            "Relative Volume", "Volume Profile Approximation", "Z Score",
            "Realized Volatility", "Parkinson Volatility", "Regression Slope",
            "Correlation Beta", "Breadth", "Options OI Features",
        }
        self.assertEqual(names, expected)

    def test_plugin_metadata_and_series_are_aligned(self):
        result = INDICATOR_REGISTRY.calculate("MACD", candles())
        self.assertTrue(result["success"])
        self.assertEqual(result["indicator"]["version"], "1.0.0")
        self.assertEqual(len(result["series"]["macd"]), 160)
        self.assertIsNotNone(result["latest"]["histogram"])
        self.assertFalse(result["live_execution"])

    def test_context_indicators_require_explicit_inputs(self):
        missing = INDICATOR_REGISTRY.calculate("Correlation Beta", candles())
        self.assertFalse(missing["success"])
        closes = [row["close"] * (1 + 0.0005 * math.sin(i)) for i, row in enumerate(candles())]
        result = INDICATOR_REGISTRY.calculate(
            "Correlation Beta", candles(), parameters={"benchmark_close": closes}
        )
        self.assertTrue(result["success"])
        self.assertIsNotNone(result["latest"]["correlation"])

    def test_breadth_and_oi_features_are_deterministic(self):
        rows = candles(80)
        breadth = INDICATOR_REGISTRY.calculate(
            "Breadth", rows, parameters={"advances": [30] * 80, "declines": [20] * 80}
        )
        oi = INDICATOR_REGISTRY.calculate(
            "Options OI Features",
            rows,
            parameters={"call_oi": list(range(100, 180)), "put_oi": list(range(120, 200))},
        )
        self.assertEqual(breadth["latest"]["advance_decline"], 10.0)
        self.assertAlmostEqual(breadth["latest"]["breadth_percent"], 60.0)
        self.assertTrue(oi["success"])
        self.assertGreater(oi["latest"]["put_call_ratio"], 1.0)

    def test_registry_rejects_duplicate_plugin(self):
        registry = IndicatorRegistry()
        plugin = IndicatorPlugin(
            name="TEST", version="1", parameters={}, input_requirements=("close",),
            output_series=("value",), warmup=1, normalization="raw",
            timeframe_compatibility=("5m",), visualization={},
            calculator=lambda frame, params: {"value": frame.close},
        )
        registry.register(plugin)
        with self.assertRaises(ValueError):
            registry.register(plugin)


class UnifiedFeatureEngineTests(unittest.TestCase):
    def test_feature_snapshot_is_explainable_and_paper_only(self):
        result = UNIFIED_FEATURE_ENGINE.analyze(
            candles(), symbol="BTC", timeframe="5m", provider="BINANCE",
            provider_symbol="BTCUSDT", data_quality="PUBLIC_MARKET_DATA",
            verified=True, stale=False,
        )
        self.assertTrue(result["success"])
        self.assertEqual(result["feature_version"], "UNIFIED_FEATURE_ENGINE_V1")
        self.assertIn(result["structure"]["trend"], {"BULLISH", "BEARISH", "RANGE_OR_TRANSITION"})
        self.assertTrue(result["explainability"]["lookahead_safe"])
        self.assertFalse(result["explainability"]["institution_identity_claimed"])
        self.assertFalse(result["live_execution"])

    def test_swing_and_ranked_zone_outputs_have_evidence(self):
        result = UNIFIED_FEATURE_ENGINE.analyze(candles(), symbol="NIFTY", timeframe="15m")
        self.assertGreaterEqual(len(result["swings"]["highs"]), 2)
        self.assertGreaterEqual(len(result["swings"]["lows"]), 2)
        zones = result["support_resistance"]["support"] + result["support_resistance"]["resistance"]
        self.assertTrue(zones)
        self.assertTrue(all(0 <= row["strength_score"] <= 100 for row in zones))
        self.assertTrue(all(row["lower"] < row["upper"] for row in zones))
        self.assertIn("REACTION", zones[0]["evidence"])

    def test_period_and_liquidity_contracts_are_bounded(self):
        result = UNIFIED_FEATURE_ENGINE.analyze(candles(), symbol="CRUDEOIL", timeframe="5m")
        self.assertIsNotNone(result["period_levels"]["session"])
        self.assertIsNotNone(result["period_levels"]["opening_range"])
        self.assertIn(result["liquidity"]["premium_discount"], {"PREMIUM", "DISCOUNT", "EQUILIBRIUM"})
        self.assertEqual(result["liquidity"]["identity_claim"], "NONE_PRICE_ACTION_HEURISTICS_ONLY")

    def test_invalid_or_short_data_fails_closed(self):
        result = UNIFIED_FEATURE_ENGINE.analyze(candles(20), symbol="BTC", timeframe="5m")
        self.assertFalse(result["success"])
        self.assertEqual(result["bars"], 20)
        self.assertFalse(result["live_execution"])

    def test_swing_detection_does_not_use_last_forming_edge_as_pivot(self):
        from workstation.indicator_registry import normalize_ohlcv

        frame = normalize_ohlcv(candles(80))
        highs, lows = detect_swings(frame, window=2)
        self.assertTrue(all(point.index <= len(frame) - 3 for point in highs + lows))


if __name__ == "__main__":
    unittest.main()

