from __future__ import annotations

import unittest

from omni.trading_intelligence.quant_firm_engine import (
    decide,
    position_size,
    select_option_candidate,
    strategy_votes,
)


def sample_candles(count: int = 120):
    rows = []
    price = 100.0
    for index in range(count):
        price += 0.35
        rows.append(
            {
                "time": index + 1,
                "open": price - 0.20,
                "high": price + 0.40,
                "low": price - 0.50,
                "close": price,
                "volume": 1000 + index * 15,
            }
        )
    return rows


class QuantFirmEngineTests(unittest.TestCase):
    def test_strategy_ensemble_produces_multiple_votes(self):
        votes = strategy_votes(sample_candles())
        self.assertGreaterEqual(len(votes), 3)
        self.assertTrue(any(vote.family == "trend" for vote in votes))
        self.assertTrue(any(vote.family in {"momentum", "breakout"} for vote in votes))

    def test_decision_is_paper_only(self):
        result = decide("NIFTY", "5m", sample_candles())
        self.assertTrue(result.paper_only)
        self.assertFalse(result.live_execution)
        self.assertIn(result.side, {"LONG", "SHORT", "WAIT"})
        self.assertGreaterEqual(result.score, 0.0)
        self.assertLessEqual(result.score, 100.0)

    def test_position_sizing_caps_notional_and_risk(self):
        quantity = position_size(100000.0, 100.0, 98.0, risk_fraction=0.005)
        self.assertGreater(quantity, 0)
        self.assertLessEqual(quantity * 100.0, 20000.0)
        self.assertLessEqual(quantity * 2.0, 500.0)

    def test_option_selector_is_directional_and_paper_only(self):
        chain = [
            {"option_type": "CE", "strike": 100, "bid": 5.0, "ask": 5.2, "ltp": 5.1, "volume": 1000, "oi": 10000},
            {"option_type": "CE", "strike": 105, "bid": 3.0, "ask": 3.2, "ltp": 3.1, "volume": 5000, "oi": 30000},
            {"option_type": "PE", "strike": 100, "bid": 4.8, "ask": 5.0, "ltp": 4.9, "volume": 1000, "oi": 10000},
        ]
        result = select_option_candidate(chain, "BULLISH", 101.0)
        self.assertIsNotNone(result)
        self.assertEqual(result["option_type"], "CE")
        self.assertTrue(result["paper_only"])
        self.assertFalse(result["live_execution"])


if __name__ == "__main__":
    unittest.main()
