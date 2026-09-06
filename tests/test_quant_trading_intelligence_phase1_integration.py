from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import patch

from workstation.quant_terminal_bridge import (
    TRADING_URL,
    dispatch_quant_terminal,
    is_quant_terminal_request,
    requested_symbols,
)


ROOT = Path(__file__).resolve().parents[1]


class QuantTradingIntelligencePhase1IntegrationTests(unittest.TestCase):
    def test_jarvis_launcher_starts_quant_terminal(self):
        launcher = (ROOT / "JARVIS.bat").read_text(
            encoding="utf-8",
            errors="ignore",
        )
        supervisor = (ROOT / "scripts" / "jarvis_runtime_supervisor.py").read_text(
            encoding="utf-8",
            errors="ignore",
        )
        v7_wrapper = (ROOT / "scripts" / "jarvis_runtime_supervisor_v7.py")
        direct_v62 = "-m scripts.jarvis_runtime_supervisor_v62" in launcher
        via_v7 = "-m scripts.jarvis_runtime_supervisor_v7" in launcher
        self.assertTrue(direct_v62 or via_v7)
        if via_v7:
            source = v7_wrapper.read_text(encoding="utf-8")
            self.assertIn("reclaim_obsolete_quant_listener", source)
            self.assertIn("default_services", source)
        self.assertIn("start_jarvis_quant_terminal.py", supervisor)
        self.assertNotIn(
            'start "JARVIS Quant Trading Intelligence" /min "%JARVIS_PY%"',
            launcher,
        )

    def test_home_dashboard_has_dedicated_trading_entry(self):
        source = (
            ROOT / "workstation" / "jarvis_os_v3_assets" / "index.html"
        ).read_text(encoding="utf-8")
        self.assertIn("TRADING INTELLIGENCE", source)
        self.assertIn(TRADING_URL, source)

    def test_master_router_intercepts_terminal_request(self):
        source = (
            ROOT / "workstation" / "jarvis_os_v3.py"
        ).read_text(encoding="utf-8")
        self.assertIn("dispatch_quant_terminal", source)
        self.assertIn('"QUANT_TRADING_INTELLIGENCE"', source)

    def test_command_order_is_preserved(self):
        self.assertEqual(
            requested_symbols(
                "Open trading intelligence, watch crude oil, Nifty 50, "
                "Bank Nifty and Sensex."
            ),
            ("CRUDEOIL", "NIFTY", "BANKNIFTY", "SENSEX"),
        )

    @patch("workstation.quant_terminal_bridge._open_terminal_browser")
    @patch("workstation.quant_terminal_bridge._post_terminal_agent")
    @patch("workstation.quant_terminal_bridge._start_paper_monitors")
    def test_multi_market_terminal_monitor_is_paper_only(
        self,
        start_monitors,
        post_agent,
        open_browser,
    ):
        start_monitors.return_value = (
            "crude-session",
            "nifty-session",
            "bank-session",
            "sensex-session",
        )
        post_agent.return_value = {"action": "open_quant"}
        open_browser.return_value = True

        request = (
            "Jarvis, open a trading terminal, start the crude oil chart, "
            "and monitor crude oil, Nifty 50, Bank Nifty and Sensex."
        )

        self.assertTrue(is_quant_terminal_request(request))
        result = dispatch_quant_terminal(request).to_dict()
        self.assertTrue(result["paper_only"])
        self.assertFalse(result["live_execution"])
        self.assertTrue(result["browser_opened"])
        self.assertEqual(
            result["symbols"],
            ["CRUDEOIL", "NIFTY", "BANKNIFTY", "SENSEX"],
        )
        self.assertEqual(result["workspace_actions"], [])


if __name__ == "__main__":
    unittest.main()
