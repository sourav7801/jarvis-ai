from __future__ import annotations

import unittest

from omni.trading_intelligence.chart_pattern_engine import detect_chart_patterns


def compression_candles(count: int = 80) -> list[dict]:
    rows = []
    center = 100.0
    for index in range(count):
        width = max(0.5, 6.0 - index * 0.06)
        open_price = center + (0.15 if index % 2 == 0 else -0.15)
        close = center + (-0.10 if index % 3 == 0 else 0.10)
        rows.append(
            {
                "open": open_price,
                "high": center + width,
                "low": center - width,
                "close": close,
                "volume": 1000.0,
            }
        )
    return rows


class ChartPatternEngineV6Tests(unittest.TestCase):
    def test_pattern_engine_returns_research_labels(self):
        result = detect_chart_patterns(compression_candles())
        self.assertIsInstance(result, list)
        for row in result:
            self.assertIn("pattern", row)
            self.assertIn("bias", row)


if __name__ == "__main__":
    unittest.main()
