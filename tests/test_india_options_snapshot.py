from __future__ import annotations

import unittest
from unittest.mock import patch

from workstation import india_options_intelligence as options


class IndiaOptionSnapshotTests(unittest.TestCase):
    def setUp(self):
        options._CHAIN_CACHE.clear()

    @patch("workstation.india_options_intelligence._fyers_json")
    def test_nearest_chain_uses_one_provider_request_and_caches(self, provider):
        provider.return_value = {
            "s": "ok",
            "data": {
                "expiryData": [{"expiry": 123, "date": "01-09-2026"}],
                "optionsChain": [
                    {"option_type": "", "ltp": 24000},
                    {"symbol": "NIFTYCE", "option_type": "CE", "strike_price": 24000, "ltp": 100, "oi": 10},
                ],
            },
        }

        first = options.option_chain_snapshot("NIFTY")
        second = options.option_chain_snapshot("NIFTY")

        self.assertTrue(first["success"])
        self.assertTrue(second["cache_hit"])
        provider.assert_called_once()


if __name__ == "__main__":
    unittest.main()
