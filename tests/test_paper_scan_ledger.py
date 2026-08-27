from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from workstation.paper_scan_ledger import PaperScanLedger


class PaperScanLedgerTests(unittest.TestCase):
    def test_records_truthful_paper_only_cycle_and_rows(self):
        with tempfile.TemporaryDirectory() as directory:
            ledger = PaperScanLedger(Path(directory) / "scans.sqlite3")
            cycle_id = ledger.record(
                {
                    "scan_at": "2026-08-28T00:00:00+00:00",
                    "profile": "intraday",
                    "timeframes": ["5m", "15m", "1h"],
                    "elapsed_ms": 123.4,
                    "funnel": {"scanned": 2, "data_ok": 1, "qualified": 0, "opened": 0},
                    "rejection_counts": {"SCORE_BELOW_GATE": 1},
                    "provider_failures": {"FYERS": 1},
                    "rows": [
                        {"symbol": "NIFTY", "success": False, "blockers": ["DATA_UNAVAILABLE"]},
                        {"symbol": "BTC", "success": True, "qualified": False, "score": 55},
                    ],
                }
            )
            recent = ledger.recent()
            self.assertEqual(recent[0]["id"], cycle_id)
            self.assertEqual(recent[0]["rows"], 2)
            self.assertEqual(recent[0]["provider_failures"], {"FYERS": 1})
            self.assertTrue(recent[0]["paper_only"])
            self.assertFalse(recent[0]["live_execution"])

    def test_retention_is_bounded(self):
        with tempfile.TemporaryDirectory() as directory:
            ledger = PaperScanLedger(Path(directory) / "scans.sqlite3", retention_cycles=10)
            for index in range(12):
                ledger.record(
                    {
                        "scan_at": f"2026-08-28T00:00:{index:02d}+00:00",
                        "profile": "5m_only",
                        "timeframes": ["5m"],
                        "elapsed_ms": index,
                        "rows": [],
                    }
                )
            recent = ledger.recent(100)
            self.assertEqual(len(recent), 10)
            self.assertEqual(recent[0]["elapsed_ms"], 11.0)

    def test_trends_aggregate_funnel_failures_and_blockers_without_predictive_claims(self):
        with tempfile.TemporaryDirectory() as directory:
            ledger = PaperScanLedger(Path(directory) / "scans.sqlite3")
            for index, data_ok in enumerate((1, 2)):
                ledger.record(
                    {
                        "scan_at": f"2026-08-28T00:00:0{index}+00:00",
                        "profile": "intraday",
                        "timeframes": ["5m", "15m", "1h"],
                        "elapsed_ms": 100 + index * 20,
                        "funnel": {
                            "scanned": 2,
                            "data_ok": data_ok,
                            "session_open": 1,
                            "qualified": index,
                            "opened": 0,
                        },
                        "provider_failures": {"FYERS": 2 - data_ok},
                        "rejection_counts": {"SCORE_BELOW_GATE": 2 - index},
                        "rows": [],
                    }
                )
            trends = ledger.trends()
            self.assertEqual(trends["cycles"], 2)
            self.assertEqual(trends["funnel_totals"]["scanned"], 4)
            self.assertEqual(trends["rates"]["data_ok_percent"], 75.0)
            self.assertEqual(trends["provider_failures"], {"FYERS": 1})
            self.assertEqual(trends["blockers"], {"SCORE_BELOW_GATE": 3})
            self.assertEqual(len(trends["series"]), 2)
            self.assertFalse(trends["live_execution"])


if __name__ == "__main__":
    unittest.main()
