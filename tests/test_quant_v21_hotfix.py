from __future__ import annotations

import unittest
from pathlib import Path

from workstation.quant_terminal_bridge import (
    is_explicit_terminal_open,
    is_quant_terminal_request,
)

ROOT = Path(__file__).resolve().parents[1]


class QuantV21HotfixTests(unittest.TestCase):
    def test_voice_typo_open_trading_terminl_routes_to_quant(self):
        text = "open trading terminl"
        self.assertTrue(is_explicit_terminal_open(text))
        self.assertTrue(is_quant_terminal_request(text))

    def test_similar_non_terminal_phrase_stays_out(self):
        self.assertFalse(is_explicit_terminal_open("open trading strategy"))

    def test_session_expiry_hotfix_is_loaded(self):
        index = (
            ROOT / "workstation" / "quant_terminal_v2_static" / "index.html"
        ).read_text(encoding="utf-8")
        hotfix = (
            ROOT / "workstation" / "quant_terminal_v2_static" / "session_hotfix.js"
        ).read_text(encoding="utf-8")
        self.assertIn('/session_hotfix.js', index)
        self.assertIn("SESSION EXPIRED", hotfix)
        self.assertIn("token is expired", hotfix)
        self.assertIn("RE-AUTHENTICATE FYERS", hotfix)


if __name__ == "__main__":
    unittest.main()
