from __future__ import annotations

import unittest
from unittest.mock import patch

from workstation.options_intelligence_router import options_command_payload


class OptionsIntelligenceRouterTests(unittest.TestCase):
    @patch("workstation.options_intelligence_router.analyze_india_option_request")
    @patch("workstation.options_intelligence_router.option_command_payload")
    def test_india_options_take_priority(self, crypto, india):
        india.return_value = {"action": "india_option_analysis", "live_execution": False}
        result = options_command_payload("analyze nifty 24500 call next expiry")
        self.assertEqual(result["action"], "india_option_analysis")
        crypto.assert_not_called()

    @patch("workstation.options_intelligence_router.analyze_india_option_request", return_value=None)
    @patch("workstation.options_intelligence_router.option_command_payload")
    def test_crypto_options_fallback(self, crypto, _india):
        crypto.return_value = {"action": "crypto_option_analysis", "live_execution": False}
        result = options_command_payload("analyze bitcoin 69000 call tomorrow expiry")
        self.assertEqual(result["action"], "crypto_option_analysis")
        crypto.assert_called_once()


if __name__ == "__main__":
    unittest.main()
