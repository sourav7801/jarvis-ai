from __future__ import annotations

import unittest
from unittest.mock import patch

from workstation import quant_terminal_v2
from workstation.paper_trade_action_router import is_paper_trade_action_request


class QuantV541PaperDeskPrecedenceTests(unittest.TestCase):
    def test_open_paper_trading_is_not_a_direct_trade_action(self):
        self.assertFalse(is_paper_trade_action_request("open paper trading"))

    def test_portfolio_request_is_not_a_direct_trade_action(self):
        self.assertFalse(
            is_paper_trade_action_request(
                "Show my current paper trading portfolio, positions, P and L and risk exposure."
            )
        )

    @patch("workstation.paper_trade_action_router.paper_trade_action_payload")
    def test_open_paper_trading_keeps_paper_desk_contract(self, trade_action):
        trade_action.return_value = {
            "action": "paper_trade_context_required",
            "speech": "This must not win over paper desk routing.",
            "paper_only": True,
            "live_execution": False,
        }
        result = quant_terminal_v2.agent_payload("open paper trading")
        self.assertEqual(result["action"], "open_paper_desk")
        trade_action.assert_not_called()

    @patch("workstation.paper_trade_action_router.paper_trade_action_payload")
    def test_portfolio_keeps_paper_desk_contract(self, trade_action):
        trade_action.return_value = {
            "action": "paper_trade_context_required",
            "speech": "This must not win over portfolio routing.",
            "paper_only": True,
            "live_execution": False,
        }
        result = quant_terminal_v2.agent_payload(
            "Show my current paper trading portfolio, positions, P and L and risk exposure."
        )
        self.assertEqual(result["action"], "paper_portfolio")
        trade_action.assert_not_called()


if __name__ == "__main__":
    unittest.main()
