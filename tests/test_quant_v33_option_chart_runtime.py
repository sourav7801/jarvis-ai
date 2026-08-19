from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import patch

from workstation.option_chart_data import attach_chart_directive, option_candles


ROOT = Path(__file__).resolve().parents[1]


class QuantV33OptionChartRuntimeTests(unittest.TestCase):
    def test_runtime_js_supports_option_chart_action(self):
        source = (
            ROOT
            / "workstation"
            / "quant_terminal_v2_static"
            / "option_chart_runtime.js"
        ).read_text(encoding="utf-8")
        self.assertIn("option_analysis", source)
        self.assertIn("india_option_analysis", source)
        self.assertIn("/api/option-candles", source)
        self.assertIn("ticker.${spec.instrument_name}.100ms", source)
        self.assertIn("openOptionChart", source)

    @patch("workstation.option_chart_data._deribit_json")
    def test_exact_screenshot_contract_can_return_chart_candles(self, deribit_json):
        deribit_json.return_value = {
            "status": "ok",
            "ticks": [1_700_000_000_000],
            "open": [0.031],
            "high": [0.033],
            "low": [0.030],
            "close": [0.032],
            "volume": [4.0],
        }
        payload = option_candles(
            "DERIBIT_PUBLIC",
            "BTC-20AUG26-68000-C",
            "5m",
            100,
        )
        self.assertTrue(payload["success"])
        self.assertEqual(payload["provider_symbol"], "BTC-20AUG26-68000-C")
        self.assertEqual(payload["candles"][0]["close"], 0.032)

    def test_chart_request_attaches_exact_contract(self):
        result = attach_chart_directive(
            "open 68000 bitcoin tomorrow expiry call option chart",
            {
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
            },
        )
        self.assertEqual(result["chart"]["instrument_name"], "BTC-20AUG26-68000-C")
        self.assertFalse(result["live_execution"])

    def test_option_chart_modules_have_no_order_surface(self):
        paths = [
            ROOT / "workstation" / "option_chart_data.py",
            ROOT / "workstation" / "quant_terminal_v2_static" / "option_chart_runtime.js",
        ]
        combined = "\n".join(path.read_text(encoding="utf-8") for path in paths)
        for forbidden in ("place_order(", "modify_order(", "cancel_order(", "/orders/sync"):
            self.assertNotIn(forbidden, combined)


if __name__ == "__main__":
    unittest.main()
