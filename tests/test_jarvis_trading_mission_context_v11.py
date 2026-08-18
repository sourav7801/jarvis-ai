from __future__ import annotations

import ast
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class TradingMissionContextV11Tests(unittest.TestCase):
    def test_legacy_default_timeframe_remains_daily(self):
        source = (ROOT / "agents" / "trading_agent.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        function = next(
            node for node in tree.body
            if isinstance(node, ast.FunctionDef) and node.name == "extract_timeframe"
        )
        self.assertEqual(ast.literal_eval(function.args.defaults[-1]), "1d")

    def test_explicit_crude_aliases_exist(self):
        source = (ROOT / "agents" / "trading_agent.py").read_text(encoding="utf-8")
        self.assertIn('("crude oil", "CRUDEOIL")', source)
        self.assertIn('("crude", "CRUDEOIL")', source)

    def test_no_silent_nifty_fallback_message_exists(self):
        source = (ROOT / "agents" / "trading_agent.py").read_text(encoding="utf-8")
        self.assertIn("I will not silently substitute NIFTY", source)

    def test_paper_monitor_route_exists(self):
        source = (ROOT / "workstation" / "jarvis_os_v3.py").read_text(encoding="utf-8")
        self.assertIn('"route": "PAPER_MONITOR"', source)
        self.assertIn("Live broker execution remains locked", source)

    def test_paper_monitor_contains_no_broker_order_calls(self):
        source = (ROOT / "omni" / "paper_trade_monitor.py").read_text(
            encoding="utf-8"
        ).lower()
        for forbidden in (
            "place_order(",
            "modify_order(",
            "cancel_order(",
            "broker_order(",
        ):
            self.assertNotIn(forbidden, source)
        self.assertIn('"live_execution": false', source)


if __name__ == "__main__":
    unittest.main()
