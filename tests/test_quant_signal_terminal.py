from __future__ import annotations

import unittest
from unittest.mock import patch

from workstation import quant_signal_terminal, quant_terminal_v2


class QuantSignalTerminalTests(unittest.TestCase):
    @patch("workstation.quant_terminal_v2.scan_payload")
    def test_analysis_opens_live_signal_chart(self, decision):
        decision.return_value = {
            "success": True,
            "side": "LONG",
            "score": 72.5,
            "regime": "TRENDING",
            "entry": 100.0,
            "stop": 98.0,
            "target": 104.0,
            "risk_reward": 2.0,
            "votes": [],
            "paper_only": True,
            "live_execution": False,
            "profile": "intraday",
        }
        result = quant_signal_terminal.signal_terminal_payload(
            "analyze bitcoin 15 minute chart and tell me buy or sell"
        )
        self.assertEqual(result["action"], "open_signal_chart")
        self.assertEqual(result["signal"], "BUY")
        self.assertEqual(result["chart"]["symbol"], "BTC")
        self.assertEqual(result["chart"]["timeframe"], "15m")
        self.assertEqual(result["chart"]["layout"], 1)
        self.assertIn("RSI14", result["chart"]["indicators"])
        self.assertFalse(result["live_execution"])

    @patch("workstation.quant_signal_terminal.signal_terminal_payload")
    def test_terminal_agent_uses_signal_route_before_legacy(self, signal_payload):
        signal_payload.return_value = {
            "success": True,
            "action": "open_signal_chart",
            "symbol": "CRUDEOIL",
            "signal": "WAIT",
            "chart": {"symbol": "CRUDEOIL", "timeframe": "5m"},
            "speech": "WAIT",
            "paper_only": True,
            "live_execution": False,
        }
        result = quant_terminal_v2.agent_payload("analyze crude oil chart")
        self.assertEqual(result["action"], "open_signal_chart")
        signal_payload.assert_called_once()

    def test_wait_is_used_when_no_direction_exists(self):
        self.assertEqual(
            quant_signal_terminal._research_signal({"side": "WAIT"}),
            "WAIT",
        )


if __name__ == "__main__":
    unittest.main()
