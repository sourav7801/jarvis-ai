
from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import patch

from workstation.quant_terminal_bridge import is_quant_terminal_request
from workstation import quant_terminal_v2

ROOT = Path(__file__).resolve().parents[1]


class QuantV5NautilusIntegrationTests(unittest.TestCase):
    def test_exact_user_universe_command_routes_to_quant(self):
        self.assertTrue(
            is_quant_terminal_request(
                "Scan all supported markets for qualified paper setups using the current risk gates."
            )
        )

    @patch("workstation.nautilus_universe_router.scan_all_supported_markets")
    def test_terminal_uses_universe_router_before_legacy_fallback(self, scan):
        scan.return_value = {
            "success": True,
            "results": [],
            "qualified": [],
            "timeframe": "5m",
            "paper_only": True,
            "live_execution": False,
        }
        result = quant_terminal_v2.agent_payload(
            "Scan all supported markets for qualified paper setups using the current risk gates."
        )
        self.assertEqual(result["action"], "quant_universe_scan")
        self.assertTrue(result["paper_only"])
        self.assertFalse(result["live_execution"])

    def test_launcher_starts_nautilus_in_isolated_environment(self):
        source = (ROOT / "JARVIS.bat").read_text(encoding="utf-8", errors="replace")
        self.assertIn("JARVIS_NAUTILUS_QUANT_CORE_V5", source)
        self.assertIn(".venv-nautilus", source)
        self.assertIn("start_jarvis_nautilus_core.py", source)

    def test_terminal_loads_nautilus_ui_runtime(self):
        html = (
            ROOT / "workstation" / "quant_terminal_v2_static" / "index.html"
        ).read_text(encoding="utf-8")
        self.assertIn("/nautilus_core_runtime.js", html)

    def test_service_has_no_broker_order_surface(self):
        source = (
            ROOT / "workstation" / "nautilus_core_service.py"
        ).read_text(encoding="utf-8")
        for forbidden in ("place_order(", "modify_order(", "cancel_order(", "/orders/sync"):
            self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
