from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from omni.trading_intelligence.adaptive_quant_brain import (
    adaptive_decide,
    indicator_snapshot,
    structure_snapshot,
)
from omni.trading_intelligence.indicator_plugin_registry import IndicatorPluginRegistry
from omni.trading_intelligence.strategy_research_lab import candidate_library, backtest_candidate
from omni.trading_intelligence.trade_learning_engine import TradeLearningEngine
from workstation.quant_intelligence_commands import is_quant_intelligence_command


def synthetic_candles(count: int = 360) -> list[dict]:
    rows = []
    price = 100.0
    for index in range(count):
        drift = 0.18 if index < count * 0.65 else (-0.05 if index % 7 == 0 else 0.10)
        open_price = price
        close = max(1.0, open_price + drift + ((index % 5) - 2) * 0.015)
        high = max(open_price, close) + 0.35 + (index % 3) * 0.02
        low = min(open_price, close) - 0.30 - (index % 4) * 0.015
        rows.append(
            {
                "time": 1_700_000_000 + index * 300,
                "open": open_price,
                "high": high,
                "low": low,
                "close": close,
                "volume": 1000.0 + (index % 20) * 40.0,
            }
        )
        price = close
    return rows


class AdaptiveQuantBrainV6Tests(unittest.TestCase):
    def test_indicator_and_structure_state(self):
        candles = synthetic_candles()
        indicators = indicator_snapshot(candles)
        structure = structure_snapshot(candles)
        for key in ("ema20", "ema50", "rsi14", "atr14", "vwap", "macd_hist", "adx", "relative_volume"):
            self.assertIn(key, indicators)
        for key in ("bias", "bos", "choch", "supports", "resistances", "fvg", "liquidity_sweep", "patterns"):
            self.assertIn(key, structure)

    def test_adaptive_decision_contract(self):
        result = adaptive_decide("BTC", "5m", synthetic_candles())
        self.assertEqual(result["symbol"], "BTC")
        self.assertEqual(result["timeframe"], "5m")
        self.assertIn(result["side"], {"LONG", "SHORT", "WAIT"})
        self.assertIn("indicators", result)
        self.assertIn("structure", result)
        self.assertIn("votes", result)
        self.assertTrue(result["paper_only"])
        self.assertFalse(result["live_execution"])

    def test_indicator_registry_requires_callable(self):
        registry = IndicatorPluginRegistry()
        registry.register(
            name="TEST_INDICATOR",
            function=lambda candles: len(candles),
            description="test",
        )
        result = registry.evaluate("TEST_INDICATOR", synthetic_candles(100))
        self.assertTrue(result["success"])
        self.assertEqual(result["value"], 100)
        missing = registry.evaluate("PREMIUM_LOCK", synthetic_candles(100))
        self.assertFalse(missing["success"])
        self.assertEqual(missing["reason"], "INDICATOR_NOT_REGISTERED")

    def test_learning_is_bounded_and_sample_gated(self):
        with tempfile.TemporaryDirectory() as folder:
            engine = TradeLearningEngine(Path(folder) / "learning.json")
            metadata = {
                "regime": "TRENDING",
                "risk_reward": 2.0,
                "votes": [
                    {"strategy": "TEST_TREND", "family": "trend", "side": "LONG", "score": 75.0}
                ],
            }
            for index in range(11):
                engine.record_outcome(
                    symbol="BTC",
                    side="LONG",
                    entry=100.0,
                    exit_price=104.0,
                    quantity=1.0,
                    pnl=4.0,
                    reason="TARGET_HIT",
                    metadata=metadata,
                    strategy="TEST_TREND",
                    score=75.0,
                    stop=98.0,
                    target=104.0,
                )
            self.assertEqual(engine.family_weights().get("trend"), 1.0)
            engine.record_outcome(
                symbol="BTC",
                side="LONG",
                entry=100.0,
                exit_price=104.0,
                quantity=1.0,
                pnl=4.0,
                reason="TARGET_HIT",
                metadata=metadata,
                strategy="TEST_TREND",
                score=75.0,
                stop=98.0,
                target=104.0,
            )
            weight = engine.family_weights().get("trend")
            self.assertIsNotNone(weight)
            self.assertGreaterEqual(weight, 0.85)
            self.assertLessEqual(weight, 1.15)
            self.assertNotEqual(weight, 1.0)

    def test_strategy_research_is_research_only(self):
        candidate = candidate_library("TRENDING")[0]
        report = backtest_candidate(synthetic_candles(), candidate)
        self.assertTrue(report["research_only"])
        self.assertFalse(report["live_execution"])
        self.assertIn("profit_factor", report)
        self.assertIn("expectancy_r", report)
        self.assertIn("max_drawdown_r", report)

    def test_intelligence_commands(self):
        commands = (
            "analyze my trading mistakes",
            "show strategy leaderboard",
            "create strategy for bitcoin",
            "explain current setup in bitcoin",
            "quant intelligence status",
        )
        for command in commands:
            with self.subTest(command=command):
                self.assertTrue(is_quant_intelligence_command(command))


if __name__ == "__main__":
    unittest.main()
