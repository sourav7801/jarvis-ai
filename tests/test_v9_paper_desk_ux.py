from __future__ import annotations

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
PAPER_DESK = ROOT / "workstation" / "quant_terminal_v2_static" / "paper_desk_runtime.js"


class V9PaperDeskUxTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.js = PAPER_DESK.read_text(encoding="utf-8")

    def test_independent_horizon_controls_are_preserved(self) -> None:
        for marker in (
            "intraday_only",
            "swing_only",
            "investment_only",
            "stop_intraday",
            "stop_swing",
            "stop_investment",
            "mandateStart${key}",
            "mandateStop${key}",
            "START ALL",
            "STOP ALL",
        ):
            self.assertIn(marker, self.js)

    def test_narrow_layout_responds_to_panel_width(self) -> None:
        self.assertIn("ResizeObserver", self.js)
        self.assertIn("paper-narrow", self.js)
        self.assertIn("card.getBoundingClientRect().width<620", self.js)
        self.assertIn("paper-narrow .mandate-grid{grid-template-columns:1fr}", self.js)

    def test_decision_board_has_no_horizontal_scroll_contract(self) -> None:
        self.assertIn("overflow-x:hidden", self.js)
        self.assertIn("decision-card", self.js)
        self.assertIn("word-break:break-word", self.js)
        self.assertIn("paperMandateFilters", self.js)
        self.assertIn("paperStateFilters", self.js)
        self.assertIn("SCANNED", self.js)
        self.assertIn("QUALIFIED", self.js)
        self.assertIn("OPENED", self.js)
        self.assertIn("BLOCKED", self.js)

    def test_missing_scores_render_as_dash_not_zero(self) -> None:
        self.assertIn('if(value===null||value===undefined||value==="")return "—"', self.js)
        self.assertIn("scoreText(row.discovery_score)", self.js)
        self.assertIn("scoreText(row.execution_score)", self.js)

    def test_next_trigger_is_not_fabricated(self) -> None:
        self.assertIn("row.next_trigger||row.next_confirmation", self.js)
        self.assertIn("Awaiting qualifying completed-bar evidence.", self.js)

    def test_live_execution_is_not_enabled_from_ui(self) -> None:
        compact = self.js.replace(" ", "").lower()
        self.assertNotIn("live_execution:true", compact)
        self.assertNotIn("automatic_broker_order:true", compact)


if __name__ == "__main__":
    unittest.main()
