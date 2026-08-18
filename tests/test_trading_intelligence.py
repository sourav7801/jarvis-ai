import unittest

import pandas as pd

from workstation.trading_intelligence import analyze_symbol


def trending_frame(direction=1):
    close = [100 + direction * (index * 0.22 + (index % 7) * 0.03) for index in range(240)]
    return pd.DataFrame(
        {
            "Open": [value - direction * 0.04 for value in close],
            "High": [value + 0.24 for value in close],
            "Low": [value - 0.24 for value in close],
            "Close": close,
            "Volume": [1000 + index * 3 for index in range(240)],
        },
        index=pd.date_range("2026-08-01", periods=240, freq="5min", tz="Asia/Kolkata"),
    )


class TradingIntelligenceTests(unittest.TestCase):
    def test_aligned_broker_frames_produce_paper_watch_only(self):
        def loader(_symbol, timeframe, bars):
            self.assertIn(timeframe, {"5m", "15m", "1h"})
            self.assertEqual(bars, 240)
            return {"success": True, "data": trending_frame(), "data_quality": "BROKER_HISTORICAL"}

        result = analyze_symbol("BANKNIFTY", loader=loader, use_cache=False)
        self.assertTrue(result["success"])
        self.assertEqual(result["regime"], "LONG")
        self.assertEqual(result["setup"], "PAPER_WATCH_LONG")
        self.assertEqual(result["mode"], "RESEARCH_AND_PAPER_ONLY")
        self.assertIn("not a trade instruction", result["risk_notice"])
        self.assertEqual(len(result["timeframes"]), 3)

    def test_missing_broker_data_fails_without_inventing_signal(self):
        def loader(_symbol, timeframe, bars):
            return {"success": False, "message": f"No {timeframe} data"}

        result = analyze_symbol("NIFTY", loader=loader, use_cache=False)
        self.assertFalse(result["success"])
        self.assertEqual(result["timeframes"], [])
        self.assertEqual(len(result["errors"]), 3)

    def test_unsupported_symbol_is_rejected(self):
        with self.assertRaises(ValueError):
            analyze_symbol("BTCUSD", use_cache=False)


if __name__ == "__main__":
    unittest.main()
