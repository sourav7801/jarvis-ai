from __future__ import annotations

import unittest
from unittest.mock import patch

from workstation.quant_terminal_bridge import (
    TRADING_URL,
    dispatch_quant_terminal,
    is_quant_terminal_request,
    requested_symbols,
    requested_timeframe,
)


class QuantTradingIntelligencePhase1Tests(unittest.TestCase):
    def test_open_trading_terminal_command_is_detected(self):
        self.assertTrue(
            is_quant_terminal_request(
                "Jarvis, open a trading terminal and start the crude oil chart."
            )
        )

    def test_standalone_scan_routes_to_quant(self):
        self.assertTrue(
            is_quant_terminal_request(
                "Can you scan a Nifty 50?"
            )
        )

    def test_plain_market_question_stays_with_master(self):
        self.assertFalse(
            is_quant_terminal_request(
                "What is Nifty 50?"
            )
        )

    def test_multi_market_request_resolves_all_markets(self):
        self.assertEqual(
            requested_symbols(
                "Open trading intelligence, watch crude oil, Nifty 50, "
                "Bank Nifty and Sensex."
            ),
            ("CRUDEOIL", "NIFTY", "BANKNIFTY", "SENSEX"),
        )

    def test_default_timeframe_is_fifteen_minutes(self):
        self.assertEqual(
            requested_timeframe("open trading terminal and watch crude oil"),
            "15m",
        )

    def test_explicit_timeframe_is_preserved(self):
        self.assertEqual(
            requested_timeframe(
                "open trading terminal and watch crude oil on 5 minute"
            ),
            "5m",
        )

    @patch("workstation.quant_terminal_bridge._open_terminal_browser")
    @patch("workstation.quant_terminal_bridge._post_terminal_agent")
    @patch("workstation.quant_terminal_bridge._start_paper_monitors")
    def test_terminal_request_starts_only_paper_monitors(
        self,
        start_monitors,
        post_agent,
        open_browser,
    ):
        start_monitors.return_value = ("session-a", "session-b")
        post_agent.return_value = {"action": "open_quant"}
        open_browser.return_value = True

        result = dispatch_quant_terminal(
            "Jarvis open trading intelligence and monitor Nifty 50 and Bank Nifty."
        ).to_dict()

        self.assertTrue(result["success"])
        self.assertTrue(result["paper_only"])
        self.assertFalse(result["live_execution"])
        self.assertTrue(result["browser_opened"])
        self.assertEqual(result["symbols"], ["NIFTY", "BANKNIFTY"])
        self.assertEqual(result["workspace_actions"], [])
        start_monitors.assert_called_once()
        open_browser.assert_called_once()
        self.assertEqual(TRADING_URL, "http://127.0.0.1:8787")

    @patch("workstation.quant_terminal_bridge._open_terminal_browser")
    @patch("workstation.quant_terminal_bridge._post_terminal_agent")
    @patch("workstation.quant_terminal_bridge._start_paper_monitors")
    def test_scan_followup_does_not_open_duplicate_browser_or_monitor(
        self,
        start_monitors,
        post_agent,
        open_browser,
    ):
        post_agent.return_value = {
            "action": "open_quant",
            "speech": "Opening read-only multi-timeframe intelligence for NIFTY.",
        }

        result = dispatch_quant_terminal(
            "Can you scan a Nifty 50?"
        ).to_dict()

        self.assertTrue(result["success"])
        self.assertFalse(result["browser_opened"])
        self.assertEqual(result["symbols"], ["NIFTY"])
        self.assertIn("Opening read-only multi-timeframe intelligence for NIFTY", result["response"])
        open_browser.assert_not_called()
        start_monitors.assert_not_called()
        post_agent.assert_called_once()


if __name__ == "__main__":
    unittest.main()
