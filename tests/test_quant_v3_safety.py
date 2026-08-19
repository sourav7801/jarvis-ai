from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class QuantV3SafetyTests(unittest.TestCase):
    def test_quant_v3_has_no_broker_order_surface(self):
        for relative in (
            "omni/trading_intelligence/quant_firm_engine.py",
            "omni/trading_intelligence/autonomous_paper_trader.py",
        ):
            text = (ROOT / relative).read_text(encoding="utf-8")
            for forbidden in ("place_order(", "modify_order(", "cancel_order("):
                self.assertNotIn(forbidden, text)
            self.assertIn("live_execution", text)


if __name__ == "__main__":
    unittest.main()
