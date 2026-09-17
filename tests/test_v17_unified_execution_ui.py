import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "workstation" / "quant_terminal_v2_static"


class V17UnifiedExecutionUiTests(unittest.TestCase):
    def test_cross_market_card_is_primary_execution_surface(self):
        text = (STATIC / "v17_crypto_paper_runtime.js").read_text(encoding="utf-8")
        self.assertIn("AUTONOMOUS CROSS-MARKET PAPER EXECUTION", text)
        self.assertIn('id="v17UnifiedPipeline"', text)
        self.assertIn('id="v17UnifiedDecision"', text)
        self.assertIn('id="v17UnifiedStart"', text)
        self.assertIn('id="v17UnifiedPause"', text)
        self.assertIn('id="v17UnifiedStopDay"', text)
        self.assertIn('legacyPrimary.hidden = true', text)
        for stage in ("SCAN", "DATA", "DECISION", "RISK", "CAPITAL", "PAPER ORDER", "POSITION", "JOURNAL"):
            self.assertIn(f'["{stage}"', text)

    def test_options_workspace_keeps_unified_execution_visible(self):
        text = (STATIC / "v16_workspace_router.js").read_text(encoding="utf-8")
        self.assertIn('node.id === "v17CryptoPaperCard"', text)
        self.assertIn('const unified = $("v17CryptoPaperCard")', text)
        self.assertIn("intel.prepend(unified)", text)

    def test_viewed_chain_is_not_presented_as_execution_authority(self):
        text = (STATIC / "v16_option_decision_runtime.js").read_text(encoding="utf-8")
        self.assertIn("OPTION WORKSPACE DETAIL · VIEWED CHAIN", text)
        self.assertIn("VIEWED CHAIN · RESEARCH ONLY", text)
        self.assertIn("Cross-market V17 execution continues independently", text)
        self.assertNotIn("WAIT · NO ENGINE ROW", text)


if __name__ == "__main__":
    unittest.main()
