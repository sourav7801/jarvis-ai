from __future__ import annotations

import unittest
from unittest.mock import patch

from workstation.quant_terminal_bridge import is_quant_terminal_request
from workstation import quant_terminal_v2


class QuantV31OptionsIntegrationTests(unittest.TestCase):
    def test_exact_screenshot_phrase_routes_to_quant(self):
        self.assertTrue(
            is_quant_terminal_request(
                "can i buy bitcoin 69000 option tomorrow expiry"
            )
        )

    @patch("workstation.crypto_options_intelligence.option_command_payload")
    def test_terminal_agent_delegates_option_command(self, option_payload):
        option_payload.return_value = {
            "action": "option_analysis",
            "speech": "option routed",
            "paper_only": True,
            "live_execution": False,
        }
        result = quant_terminal_v2.agent_payload(
            "can i buy bitcoin 69000 option tomorrow expiry"
        )
        self.assertEqual(result["action"], "option_analysis")
        self.assertFalse(result["live_execution"])
        option_payload.assert_called_once()

    def test_option_module_has_no_live_order_surface(self):
        from pathlib import Path
        source = (
            Path(__file__).resolve().parents[1]
            / "workstation"
            / "crypto_options_intelligence.py"
        ).read_text(encoding="utf-8")
        for forbidden in ("place_order(", "modify_order(", "cancel_order("):
            self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()