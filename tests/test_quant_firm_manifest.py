from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class QuantFirmManifestTests(unittest.TestCase):
    def test_manifest_declares_paper_only_and_regime_routing(self):
        text = (
            ROOT / "omni" / "trading_intelligence" / "quant_firm_manifest.md"
        ).read_text(encoding="utf-8")
        self.assertIn("Paper/research-only", text)
        self.assertIn("Regime routing", text)
        self.assertIn("Champion/challenger", text)
        self.assertIn("live_execution=false", text)


if __name__ == "__main__":
    unittest.main()
