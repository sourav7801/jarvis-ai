from __future__ import annotations

import unittest
from unittest.mock import patch

from workstation import quant_terminal_v2
from workstation.quant_terminal_bridge import is_quant_terminal_request


class QuantV32OptionsIntegrationTests(unittest.TestCase):
    def test_exact_crypto_screenshot_command_routes_to_quant(self):
        self.assertTrue(
            is_quant_terminal_request(
                "can i buy bitcoin 69000 option tomorrow expiry"
            )
        )

    def test_nifty_option_command_routes_to_quant(self):
        self.assertTrue(
            is_quant_terminal_request(
                "analyze nifty 24500 call next expiry"
            )
        )

    def test_banknifty_option_command_routes_to_quant(self):
        self.assertTrue(
            is_quant_terminal_request(
                "paper buy bank nifty 57000 put next expiry"
            )
        )

    @patch("workstation.options_intelligence_router.options_command_payload")
    def test_terminal_delegates_options_before_legacy_agent(self, options):
        options.return_value = {
            "action": "option_analysis",
            "speech": "verified option analysis",
            "paper_only": True,
            "live_execution": False,
        }

        result = quant_terminal_v2.agent_payload(
            "analyze nifty 24500 call next expiry"
        )

        self.assertEqual(result["action"], "option_analysis")
        self.assertFalse(result["live_execution"])

    def test_plain_nifty_definition_does_not_become_trade_command(self):
        self.assertFalse(
            is_quant_terminal_request(
                "what is nifty 50"
            )
        )


if __name__ == "__main__":
    unittest.main()