
from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import patch

from workstation.quant_terminal_bridge import (
    dispatch_quant_terminal,
    is_explicit_terminal_open,
    is_quant_terminal_request,
)
from workstation import quant_terminal_v2

ROOT = Path(__file__).resolve().parents[1]


class QuantV4PaperDeskIntegrationTests(unittest.TestCase):
    def test_exact_user_paper_commands_route_to_quant(self):
        commands = (
            "open paper trading terminal",
            "open paper trading",
            "my paper trading position",
            "Show my current paper trading portfolio, positions, P and L and risk exposure.",
            "start autonomous paper trading",
            "stop autonomous paper trading",
            "autonomous paper trading status",
        )
        for command in commands:
            with self.subTest(command=command):
                self.assertTrue(is_quant_terminal_request(command))

    def test_open_paper_trading_is_explicit_terminal_open(self):
        self.assertTrue(is_explicit_terminal_open("open paper trading"))
        self.assertTrue(is_explicit_terminal_open("open paper trading terminal"))

    def test_open_paper_trading_never_requires_open_symbol(self):
        from workstation.quant_terminal_bridge import requested_symbols
        self.assertEqual(requested_symbols("open paper trading"), ())

    def test_plain_definition_stays_outside_quant(self):
        self.assertFalse(is_quant_terminal_request("what is nifty 50"))

    def test_terminal_agent_returns_paper_portfolio(self):
        result = quant_terminal_v2.agent_payload("my paper trading position")
        self.assertEqual(result["action"], "paper_portfolio")
        self.assertIn("portfolio", result)
        self.assertFalse(result["live_execution"])

    def test_terminal_agent_opens_paper_desk(self):
        result = quant_terminal_v2.agent_payload("open paper trading")
        self.assertEqual(result["action"], "open_paper_desk")
        self.assertFalse(result["live_execution"])

    @patch("workstation.quant_terminal_bridge._open_terminal_browser", return_value=True)
    @patch(
        "workstation.quant_terminal_bridge._post_terminal_agent",
        return_value={
            "action": "conversation_only",
            "speech": "That request is not wired to a deterministic trading action yet.",
        },
    )
    def test_explicit_terminal_open_suppresses_unwired_fallback(self, _agent, _browser):
        result = dispatch_quant_terminal("open trading terminal")
        self.assertNotIn("not wired", result.response.lower())
        self.assertIn("terminal opened", result.response.lower())

    def test_backend_has_paper_endpoints(self):
        source = (ROOT / "workstation" / "quant_terminal_v2.py").read_text(encoding="utf-8")
        for endpoint in (
            '"/api/paper/portfolio"',
            '"/api/paper/autonomy"',
            '"/api/paper/command"',
            '"/api/paper/autonomy/start"',
            '"/api/paper/autonomy/stop"',
        ):
            self.assertIn(endpoint, source)

    def test_ui_loads_paper_runtime(self):
        html = (ROOT / "workstation" / "quant_terminal_v2_static" / "index.html").read_text(encoding="utf-8")
        self.assertIn("/paper_desk_runtime.js", html)

    def test_legacy_monitor_mirrors_to_persistent_ledger(self):
        source = (ROOT / "omni" / "paper_trade_monitor.py").read_text(encoding="utf-8")
        self.assertIn('external_id=f"monitor:{session_id}"', source)
        self.assertIn("paper_desk.open_position", source)
        self.assertIn("paper_desk.close_position", source)

    def test_v4_files_have_no_live_order_surface(self):
        paths = (
            ROOT / "workstation" / "paper_trading_desk.py",
            ROOT / "workstation" / "paper_autonomy_engine.py",
            ROOT / "workstation" / "quant_terminal_v2_static" / "paper_desk_runtime.js",
        )
        combined = "\n".join(path.read_text(encoding="utf-8") for path in paths)
        for forbidden in ("place_order(", "modify_order(", "cancel_order(", "/orders/sync"):
            self.assertNotIn(forbidden, combined)


if __name__ == "__main__":
    unittest.main()
