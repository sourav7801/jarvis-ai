from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class QuantV22ScanConsistencyTests(unittest.TestCase):
    def test_scan_consistency_hotfix_is_loaded_after_terminal_scripts(self):
        index = (
            ROOT / "workstation" / "quant_terminal_v2_static" / "index.html"
        ).read_text(encoding="utf-8")
        app_pos = index.index('/app.js')
        session_pos = index.index('/session_hotfix.js')
        scan_pos = index.index('/scan_consistency_hotfix.js')
        self.assertLess(app_pos, session_pos)
        self.assertLess(session_pos, scan_pos)

    def test_scan_hotfix_cancels_stale_async_results(self):
        source = (
            ROOT
            / "workstation"
            / "quant_terminal_v2_static"
            / "scan_consistency_hotfix.js"
        ).read_text(encoding="utf-8")
        self.assertIn("AbortController", source)
        self.assertIn("requestId !== scanSequence || symbol !== selectedSymbol", source)
        self.assertIn("payloadSymbol !== symbol", source)
        self.assertIn("cancelActiveScan", source)

    def test_switching_market_clears_previous_setup(self):
        source = (
            ROOT
            / "workstation"
            / "quant_terminal_v2_static"
            / "scan_consistency_hotfix.js"
        ).read_text(encoding="utf-8")
        self.assertIn('$("setupState").textContent = "NO SETUP"', source)
        self.assertIn('$("entryRef").textContent = "—"', source)
        self.assertIn('$("evidenceList").innerHTML', source)


if __name__ == "__main__":
    unittest.main()
