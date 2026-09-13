from __future__ import annotations

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "workstation" / "quant_terminal_v2_static"


class V16AutonomyWorkflowUITests(unittest.TestCase):
    def test_primary_workflow_is_one_click_autonomous(self):
        js = (STATIC / "v16_autonomy_runtime.js").read_text(encoding="utf-8")
        self.assertIn("START JARVIS", js)
        self.assertIn("PAUSE NEW ENTRIES", js)
        self.assertIn("STOP FOR DAY", js)
        self.assertIn("WAIT means the evidence rejected a trade", js)
        self.assertIn("JARVIS scans, verifies, chooses the strategy expression", js)

    def test_legacy_signal_panels_are_demoted_to_supporting_evidence(self):
        js = (STATIC / "v16_autonomy_runtime.js").read_text(encoding="utf-8")
        self.assertIn("EVIDENCE & RESEARCH · supporting diagnostics", js)
        self.assertIn("convergeLegacyEvidence", js)
        self.assertIn("MANUAL PAPER OVERRIDE · OPTIONAL / DEBUG", js)

    def test_options_normal_path_does_not_require_manual_ticket(self):
        js = (STATIC / "v16_autonomy_runtime.js").read_text(encoding="utf-8")
        self.assertIn("No contract click, lot input, stop/target input or BUY click is required", js)
        self.assertIn("AUTO SELECT", js)
        self.assertIn("PAPER DESK", js)
        self.assertNotIn("place_order", js.lower())
        self.assertNotIn("broker_order", js.lower())

    def test_v16_http_boundary_serves_autonomy_runtime(self):
        source = (ROOT / "workstation" / "v16_terminal_http.py").read_text(encoding="utf-8")
        self.assertIn("/v16_autonomy_runtime.js", source)
        self.assertIn("/v16_autonomy_runtime.css", source)
        self.assertIn("window.JARVIS_V16_CANONICAL=true", source)

    def test_v16_index_does_not_start_legacy_paper_desk_poller(self):
        html = (STATIC / "index.html").read_text(encoding="utf-8")
        self.assertIn("if (!window.JARVIS_V16_CANONICAL)", html)
        self.assertIn('legacyPaperDesk.src = "/paper_desk_runtime.js"', html)
        self.assertNotIn('<script src="/paper_desk_runtime.js"></script>', html)
        self.assertIn("Canonical V16 Paper Desk active", html)

    def test_autonomous_control_center_is_pinned_above_supporting_evidence(self):
        html = (STATIC / "index.html").read_text(encoding="utf-8")
        self.assertIn("function pinAutonomousSurface()", html)
        self.assertIn("intel.prepend(primary)", html)
        self.assertIn('primary.insertAdjacentElement("afterend", evidence)', html)
        self.assertIn("legacyDesk.hidden = true", html)


if __name__ == "__main__":
    unittest.main()
