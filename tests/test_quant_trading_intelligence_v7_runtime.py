from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import patch

from workstation.quant_terminal_bridge import (
    dispatch_quant_terminal,
    is_explicit_terminal_open,
    is_quant_terminal_request,
)

ROOT = Path(__file__).resolve().parents[1]


class QuantTradingIntelligenceV7RuntimeTests(unittest.TestCase):
    def test_exact_scan_nifty_followup_routes_to_quant(self):
        self.assertTrue(is_quant_terminal_request("Can you scan a nifty 50?"))

    def test_analyze_crude_routes_to_quant(self):
        self.assertTrue(is_quant_terminal_request("Analyze crude oil on 15 minute."))

    def test_plain_definition_does_not_hijack_master(self):
        self.assertFalse(is_quant_terminal_request("What is Nifty 50?"))

    def test_terminal_open_tolerates_dropped_character_voice_typo(self):
        text = "open trading terminl"
        self.assertTrue(is_explicit_terminal_open(text))
        self.assertTrue(is_quant_terminal_request(text))

    def test_terminal_fuzzy_match_does_not_hijack_generic_trading_phrase(self):
        self.assertFalse(is_explicit_terminal_open("open trading strategy"))

    @patch("workstation.quant_terminal_bridge._open_terminal_browser")
    @patch("workstation.quant_terminal_bridge._post_terminal_agent")
    @patch("workstation.quant_terminal_bridge._start_paper_monitors")
    def test_scan_is_one_shot_not_background_monitor(
        self,
        start_monitors,
        post_agent,
        open_browser,
    ):
        post_agent.return_value = {
            "action": "open_quant",
            "speech": "Opening read-only multi-timeframe intelligence for NIFTY.",
        }

        result = dispatch_quant_terminal("Can you scan a nifty 50?").to_dict()

        self.assertEqual(result["symbols"], ["NIFTY"])
        self.assertFalse(result["browser_opened"])
        self.assertFalse(result["live_execution"])
        self.assertTrue(result["paper_only"])
        start_monitors.assert_not_called()
        open_browser.assert_not_called()
        post_agent.assert_called_once()

    def test_master_router_uses_quant_bridge(self):
        source = (
            ROOT / "workstation" / "jarvis_os_v3.py"
        ).read_text(encoding="utf-8")
        self.assertIn("is_quant_terminal_request", source)
        self.assertIn("dispatch_quant_terminal", source)

    def test_home_ui_has_clean_utf8_status_icons(self):
        source = (
            ROOT / "workstation" / "jarvis_os_v3_assets" / "index.html"
        ).read_text(encoding="utf-8")
        for bad in ("Â·", "â—", "â›¶", "â—‰", "â€”", "â–¡", "Ã—", "â†’", "â€¦"):
            self.assertNotIn(bad, source)
        self.assertIn("● VOICE READY", source)
        self.assertIn("TRADING INTELLIGENCE", source)

    def test_voice_state_labels_are_not_question_marks(self):
        source = (
            ROOT / "workstation" / "jarvis_os_v3_assets" / "app.js"
        ).read_text(encoding="utf-8")
        self.assertIn('"● LISTENING"', source)
        self.assertNotIn('"? LISTENING"', source)


if __name__ == "__main__":
    unittest.main()