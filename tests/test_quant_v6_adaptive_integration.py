from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import patch

from workstation import quant_terminal_v2
from workstation.paper_trade_action_router import is_paper_trade_action_request, resolve_trade_symbols
from workstation.quant_intelligence_commands import is_quant_intelligence_command
from workstation.quant_terminal_bridge import is_quant_terminal_request, requested_symbols


ROOT = Path(__file__).resolve().parents[1]


class QuantV6AdaptiveIntegrationTests(unittest.TestCase):
    def test_paper_desk_precedence_is_preserved(self):
        self.assertFalse(is_paper_trade_action_request("open paper trading"))
        self.assertFalse(is_paper_trade_action_request("show my paper trading portfolio"))
        opened = quant_terminal_v2.agent_payload("open paper trading")
        portfolio = quant_terminal_v2.agent_payload(
            "Show my current paper trading portfolio, positions, P and L and risk exposure."
        )
        self.assertEqual(opened["action"], "open_paper_desk")
        self.assertEqual(portfolio["action"], "paper_portfolio")

    def test_direct_trade_commands_are_deterministic(self):
        self.assertTrue(is_quant_terminal_request("take trade in bitcoin"))
        self.assertEqual(requested_symbols("take trade in bitcoin"), ("BTC",))
        self.assertTrue(is_quant_terminal_request("do paper trading in bitcoi n"))
        self.assertEqual(requested_symbols("do paper trading in bitcoi n"), ("BTC",))
        self.assertEqual(resolve_trade_symbols("do paper trading in bitcoi n"), ("BTC",))

    def test_plain_execute_routes_to_context_guard(self):
        self.assertTrue(is_quant_terminal_request("EXECUTE"))
        result = quant_terminal_v2.agent_payload("EXECUTE")
        self.assertEqual(result["action"], "paper_trade_context_required")
        self.assertFalse(result["live_execution"])

    @patch("workstation.paper_trade_action_router.paper_trade_action_payload")
    def test_direct_trade_handler_precedes_legacy_fallback(self, action):
        action.return_value = {
            "success": True,
            "action": "paper_trade_armed",
            "symbol": "BTC",
            "speech": "BTC armed.",
            "paper_only": True,
            "live_execution": False,
        }
        result = quant_terminal_v2.agent_payload("take trade in bitcoin")
        self.assertEqual(result["action"], "paper_trade_armed")
        self.assertFalse(result["live_execution"])

    def test_intelligence_commands_route_to_quant(self):
        commands = (
            "analyze my trading mistakes",
            "show strategy leaderboard",
            "create strategy for bitcoin",
            "explain current setup in bitcoin",
            "quant intelligence status",
        )
        for command in commands:
            with self.subTest(command=command):
                self.assertTrue(is_quant_intelligence_command(command))
                self.assertTrue(is_quant_terminal_request(command))

    def test_quant_firm_runtime_uses_adaptive_brain(self):
        source = (ROOT / "workstation" / "quant_firm_runtime.py").read_text(encoding="utf-8")
        self.assertIn("adaptive_decide", source)

    def test_paper_close_records_learning_outcome(self):
        source = (ROOT / "workstation" / "paper_trading_desk.py").read_text(encoding="utf-8")
        self.assertIn("record_closed_row", source)

    def test_terminal_pipeline_includes_intelligence_and_trade_actions(self):
        source = (ROOT / "workstation" / "quant_terminal_v2.py").read_text(encoding="utf-8")
        self.assertIn("quant_intelligence_command_payload", source)
        self.assertIn("paper_trade_action_payload", source)
        paper_index = source.index("paper_result = paper_command_payload(command)")
        trade_index = source.index("trade_action = paper_trade_action_payload(command)")
        self.assertLess(paper_index, trade_index)

    def test_no_live_broker_order_surface_in_v6_modules(self):
        paths = (
            ROOT / "omni" / "trading_intelligence" / "adaptive_quant_brain.py",
            ROOT / "omni" / "trading_intelligence" / "trade_learning_engine.py",
            ROOT / "omni" / "trading_intelligence" / "strategy_research_lab.py",
            ROOT / "workstation" / "paper_trade_action_router.py",
            ROOT / "workstation" / "quant_intelligence_commands.py",
        )
        combined = "\n".join(path.read_text(encoding="utf-8") for path in paths)
        for forbidden in ("place_order(", "modify_order(", "cancel_order(", "/orders/sync"):
            self.assertNotIn(forbidden, combined)


if __name__ == "__main__":
    unittest.main()
