from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class QuantV6ChartRuntimeTests(unittest.TestCase):
    def test_runtime_has_adaptive_decision_endpoint(self):
        source = (
            ROOT
            / "workstation"
            / "quant_terminal_v2_static"
            / "adaptive_brain_runtime.js"
        ).read_text(encoding="utf-8")
        self.assertIn("/api/intelligence/decision", source)
        self.assertIn("SUPPORT", source)
        self.assertIn("RESIST", source)
        self.assertIn("ENTRY", source)
        self.assertIn("STOP", source)
        self.assertIn("TARGET", source)
        self.assertIn("BOS", source)
        self.assertIn("CHOCH", source)

    def test_runtime_has_no_order_surface(self):
        source = (
            ROOT
            / "workstation"
            / "quant_terminal_v2_static"
            / "adaptive_brain_runtime.js"
        ).read_text(encoding="utf-8")
        for forbidden in ("place_order", "modify_order", "cancel_order", "/orders/sync"):
            self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
