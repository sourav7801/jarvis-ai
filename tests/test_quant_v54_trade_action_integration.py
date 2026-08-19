from __future__ import annotations

import unittest
from unittest.mock import patch

from workstation import quant_terminal_v2
from workstation.quant_terminal_bridge import is_quant_terminal_request, requested_symbols


class QuantV54TradeActionIntegrationTests(unittest.TestCase):
    def test_exact_take_trade_command_routes_to_quant(self):
        self.assertTrue(is_quant_terminal_request("take trade in bitcoin"))
        self.assertEqual(requested_symbols("take trade in bitcoin"), ("BTC",))

    def test_split_bitcoin_typo_routes_to_quant(self):
        self.assertTrue(is_quant_terminal_request("do paper trading in bitcoi n"))
        self.assertEqual(requested_symbols("do paper trading in bitcoi n"), ("BTC",))

    @patch("workstation.paper_trade_action_router.paper_trade_action_payload")
    def test_terminal_handles_trade_action_before_legacy(self, action):
        action.return_value = {
            "success": True,
            "action": "paper_trade_armed",
            "symbol": "BTC",
            "speech": "BTC is armed for qualified paper entry.",
            "paper_only": True,
            "live_execution": False,
        }
        result = quant_terminal_v2.agent_payload("take trade in bitcoin")
        self.assertEqual(result["action"], "paper_trade_armed")
        self.assertFalse(result["live_execution"])

    @patch("workstation.paper_trade_action_router.paper_trade_action_payload")
    def test_plain_execute_gets_deterministic_context_guard(self, action):
        action.return_value = {
            "success": False,
            "action": "paper_trade_context_required",
            "speech": "Choose a market.",
            "paper_only": True,
            "live_execution": False,
        }
        result = quant_terminal_v2.agent_payload("EXECUTE")
        self.assertEqual(result["action"], "paper_trade_context_required")
        self.assertNotEqual(result["action"], "conversation_only")


if __name__ == "__main__":
    unittest.main()
