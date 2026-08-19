from __future__ import annotations

import unittest
from unittest.mock import patch

from workstation import quant_firm_runtime


def candles(count: int = 120):
    rows = []
    price = 100.0
    for index in range(count):
        price += 0.4
        rows.append(
            {
                "time": index + 1,
                "open": price - 0.2,
                "high": price + 0.4,
                "low": price - 0.5,
                "close": price,
                "volume": 1000 + index * 10,
            }
        )
    return rows


class QuantFirmRuntimeTests(unittest.TestCase):
    @patch("workstation.quant_firm_runtime._candles", return_value=candles())
    def test_decision_runtime_is_paper_only(self, _loader):
        result = quant_firm_runtime.decision_payload("NIFTY", "5m")
        self.assertTrue(result["success"])
        self.assertTrue(result["paper_only"])
        self.assertFalse(result["live_execution"])

    @patch("workstation.quant_firm_runtime._candles", return_value=candles())
    def test_autonomous_runtime_never_enables_live_execution(self, _loader):
        result = quant_firm_runtime.autonomous_paper_payload("BTC", "5m")
        self.assertTrue(result["success"])
        self.assertTrue(result["paper_only"])
        self.assertFalse(result["live_execution"])

    @patch("workstation.quant_firm_runtime.decision_payload")
    def test_universe_results_are_ranked(self, decision):
        decision.side_effect = [
            {"success": True, "symbol": "NIFTY", "score": 60.0, "paper_only": True, "live_execution": False},
            {"success": True, "symbol": "BTC", "score": 80.0, "paper_only": True, "live_execution": False},
        ]
        result = quant_firm_runtime.scan_universe_payload(["NIFTY", "BTC"], "5m")
        self.assertEqual(result["results"][0]["symbol"], "BTC")
        self.assertFalse(result["live_execution"])


if __name__ == "__main__":
    unittest.main()
