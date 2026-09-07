from __future__ import annotations

import unittest

from workstation.adaptive_discovery_router_v13 import _eligible_rows, status


class _Scanner:
    def __init__(self, rows):
        self._results = rows


class V13ContinuousDiscoveryTests(unittest.TestCase):
    def test_low_discovery_score_can_still_be_routed_for_deeper_evaluation(self) -> None:
        scanner = _Scanner([
            {
                "success": True,
                "symbol": "BTC",
                "auto_paper_eligible": True,
                "direction": "BULLISH",
                "state": "BREAKOUT_WATCH",
                "score": 22.0,
                "quant_score": 70.0,
                "quant_side": "LONG",
            },
            {
                "success": True,
                "symbol": "ETH",
                "auto_paper_eligible": True,
                "direction": "BEARISH",
                "state": "CONFIRMED_BREAKDOWN",
                "score": 82.0,
                "quant_score": 80.0,
                "quant_side": "SHORT",
            },
        ])
        rows = _eligible_rows(scanner)
        self.assertEqual({row["symbol"] for row in rows}, {"BTC", "ETH"})
        btc = next(row for row in rows if row["symbol"] == "BTC")
        self.assertEqual(btc["legacy_discovery_score"], 22.0)
        self.assertFalse(btc["discovery_score_is_execution_authority"])
        self.assertTrue(btc["candidate"])

    def test_failed_or_non_directional_rows_are_not_invented_as_opportunities(self) -> None:
        scanner = _Scanner([
            {"success": False, "symbol": "BAD", "auto_paper_eligible": True, "direction": "BULLISH", "score": 99.0},
            {"success": True, "symbol": "FLAT", "auto_paper_eligible": True, "direction": "NEUTRAL", "score": 99.0},
        ])
        self.assertEqual(_eligible_rows(scanner), [])

    def test_status_keeps_discovery_non_executable(self) -> None:
        payload = status()
        self.assertFalse(payload["execution_authority"])
        self.assertFalse(payload["live_execution"])
        self.assertFalse(payload["automatic_broker_order"])


if __name__ == "__main__":
    unittest.main()
