from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import patch

from workstation import quant_terminal_v2


ROOT = Path(__file__).resolve().parents[1]


class QuantV33OptionChartIntegrationTests(unittest.TestCase):
    def test_backend_exposes_option_chart_routes(self):
        source = (
            ROOT / "workstation" / "quant_terminal_v2.py"
        ).read_text(encoding="utf-8")
        self.assertIn('path == "/api/option-candles"', source)
        self.assertIn('path == "/api/option-live"', source)
        self.assertIn("attach_chart_directive", source)

    def test_terminal_loads_option_runtime(self):
        source = (
            ROOT / "workstation" / "quant_terminal_v2_static" / "index.html"
        ).read_text(encoding="utf-8")
        self.assertIn('/option_chart_runtime.js', source)

    @patch("workstation.options_intelligence_router.options_command_payload")
    def test_exact_screenshot_command_returns_chart_directive(self, options):
        options.return_value = {
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

        result = quant_terminal_v2.agent_payload(
            "open 68000 bitcoin tomorrow expiry call option chart"
        )

        self.assertEqual(
            result["chart"]["instrument_name"],
            "BTC-20AUG26-68000-C",
        )
        self.assertEqual(result["chart"]["provider"], "DERIBIT_PUBLIC")
        self.assertFalse(result["live_execution"])

    def test_option_chart_runtime_has_no_live_order_surface(self):
        source = (
            ROOT
            / "workstation"
            / "quant_terminal_v2_static"
            / "option_chart_runtime.js"
        ).read_text(encoding="utf-8")
        for forbidden in ("place_order(", "modify_order(", "cancel_order(", "/orders/sync"):
            self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()