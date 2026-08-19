from __future__ import annotations

import unittest
from unittest.mock import patch

from workstation.nautilus_universe_router import (
    is_universe_scan_request,
    universe_command_payload,
)


class NautilusV5ContractTests(unittest.TestCase):
    def test_all_supported_markets_routes_to_quant_universe(self):
        self.assertTrue(
            is_universe_scan_request(
                "Scan all supported markets for qualified paper setups using the current risk gates."
            )
        )

    def test_single_market_question_does_not_match_universe(self):
        self.assertFalse(is_universe_scan_request("Analyze crude oil"))

    @patch("workstation.nautilus_universe_router.scan_all_supported_markets")
    def test_universe_payload_is_paper_only(self, scan):
        scan.return_value = {
            "success": True,
            "results": [],
            "qualified": [],
            "timeframe": "5m",
            "paper_only": True,
            "live_execution": False,
        }
        result = universe_command_payload("scan all supported markets")
        self.assertEqual(result["action"], "quant_universe_scan")
        self.assertTrue(result["paper_only"])
        self.assertFalse(result["live_execution"])

    def test_nautilus_service_source_has_no_order_routes(self):
        from pathlib import Path

        root = Path(__file__).resolve().parents[1]
        source = (root / "workstation" / "nautilus_core_service.py").read_text(encoding="utf-8")
        for forbidden in ("place_order(", "modify_order(", "cancel_order(", "/orders/sync"):
            self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
