from __future__ import annotations

import unittest
from unittest.mock import patch

from workstation.option_chart_data import (
    DERIBIT_WS,
    attach_chart_directive,
    option_candles,
    option_live,
)


class OptionChartDataTests(unittest.TestCase):
    def test_crypto_option_analysis_gets_chart_directive(self):
        payload = {
            "action": "option_analysis",
            "request": {
                "underlying": "BTC",
                "strike": 68000.0,
                "option_type": "call",
            },
            "candidates": [
                {
                    "instrument_name": "BTC-20AUG26-68000-C",
                    "expiry": "2026-08-20",
                    "strike": 68000.0,
                    "option_type": "call",
                }
            ],
            "speech": "Option contract found.",
            "paper_only": True,
            "live_execution": False,
        }
        result = attach_chart_directive(
            "open 68000 bitcoin tomorrow expiry call option chart",
            payload,
        )
        self.assertEqual(result["chart"]["instrument_name"], "BTC-20AUG26-68000-C")
        self.assertEqual(result["chart"]["provider"], "DERIBIT_PUBLIC")
        self.assertEqual(result["chart"]["websocket_url"], DERIBIT_WS)
        self.assertIn("ticker.BTC-20AUG26-68000-C.100ms", result["chart"]["realtime_channel"])
        self.assertFalse(result["live_execution"])

    def test_analysis_without_chart_word_does_not_replace_chart(self):
        payload = {
            "action": "option_analysis",
            "request": {"underlying": "BTC", "strike": 68000.0, "option_type": "call"},
            "candidates": [{"instrument_name": "BTC-20AUG26-68000-C", "option_type": "call"}],
        }
        result = attach_chart_directive("analyze bitcoin 68000 call tomorrow expiry", payload)
        self.assertNotIn("chart", result)

    def test_india_option_chart_directive_uses_fyers(self):
        payload = {
            "action": "india_option_analysis",
            "request": {"underlying": "NIFTY", "option_type": "CE"},
            "contract": {
                "symbol": "NSE:NIFTY26AUG24500CE",
                "strike": 24500.0,
                "option_type": "CE",
            },
            "paper_only": True,
            "live_execution": False,
        }
        result = attach_chart_directive("open nifty 24500 call option chart", payload)
        self.assertEqual(result["chart"]["provider"], "FYERS_READ_ONLY")
        self.assertEqual(result["chart"]["instrument_name"], "NSE:NIFTY26AUG24500CE")

    @patch("workstation.option_chart_data._deribit_json")
    def test_deribit_chart_response_is_normalized(self, deribit_json):
        deribit_json.return_value = {
            "status": "ok",
            "ticks": [1000, 2000],
            "open": [1.0, 2.0],
            "high": [1.5, 2.5],
            "low": [0.5, 1.5],
            "close": [1.2, 2.2],
            "volume": [10.0, 20.0],
        }
        result = option_candles("DERIBIT_PUBLIC", "BTC-20AUG26-68000-C", "5m", 200)
        self.assertTrue(result["success"])
        self.assertEqual(len(result["candles"]), 2)
        self.assertEqual(result["candles"][1]["close"], 2.2)
        self.assertFalse(result["live_execution"])

    @patch("workstation.option_chart_data._deribit_json")
    def test_deribit_live_ticker_is_read_only(self, deribit_json):
        deribit_json.return_value = {
            "last_price": 0.03,
            "mark_price": 0.031,
            "mark_iv": 32.91,
            "open_interest": 42.0,
            "underlying_price": 68093.0,
            "greeks": {"delta": 0.51},
            "timestamp": 1_700_000_000_000,
        }
        result = option_live("DERIBIT_PUBLIC", "BTC-20AUG26-68000-C")
        self.assertTrue(result["success"])
        self.assertEqual(result["snapshot"]["mark_iv"], 32.91)
        self.assertFalse(result["live_execution"])

    def test_invalid_instrument_is_rejected(self):
        with self.assertRaises(ValueError):
            option_candles("DERIBIT_PUBLIC", "BTC;rm -rf", "5m", 100)


if __name__ == "__main__":
    unittest.main()
