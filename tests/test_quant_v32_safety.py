from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class QuantV32SafetyTests(unittest.TestCase):
    def test_options_modules_are_read_only_and_paper_only(self):
        for relative in (
            "workstation/crypto_options_intelligence.py",
            "workstation/india_options_intelligence.py",
            "workstation/options_intelligence_router.py",
        ):
            source = (ROOT / relative).read_text(encoding="utf-8")
            for forbidden in ("place_order(", "modify_order(", "cancel_order("):
                self.assertNotIn(forbidden, source)

    def test_india_options_uses_fyers_data_endpoint_not_order_endpoint(self):
        source = (ROOT / "workstation/india_options_intelligence.py").read_text(encoding="utf-8")
        self.assertIn("/options-chain-v3", source)
        self.assertNotIn("/orders/sync", source)
        self.assertIn('"live_execution": False', source)


if __name__ == "__main__":
    unittest.main()
