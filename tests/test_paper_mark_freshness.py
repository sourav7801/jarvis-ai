from __future__ import annotations

from datetime import datetime, timedelta, timezone
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from workstation.paper_autonomy_engine import PaperAutonomyEngine
from workstation.paper_trading_desk import PaperTradingDesk, live_mark_snapshot


class PaperMarkFreshnessTests(unittest.TestCase):
    def test_fresh_verified_mark_is_exit_eligible(self):
        payload = {
            "success": True,
            "source": "BINANCE_PUBLIC", "symbol": "BTC",
            "live_orders": False,
            "snapshot": {"ltp": 101, "received_at": datetime.now(timezone.utc).isoformat(), "exchange_timestamp": datetime.now(timezone.utc).isoformat()},
        }
        with patch("workstation.quant_terminal_v2.live_payload", return_value=payload):
            result = live_mark_snapshot("BTC")
        self.assertTrue(result["eligible_for_exit"])
        self.assertTrue(result["verified"])
        self.assertFalse(result["stale"])

    def test_stale_mark_carries_diagnostic_price_but_cannot_exit(self):
        payload = {
            "success": True,
            "source": "BINANCE_PUBLIC", "symbol": "BTC",
            "live_orders": False,
            "snapshot": {
                "ltp": 90,
                "received_at": (datetime.now(timezone.utc) - timedelta(minutes=10)).isoformat(),
                "exchange_timestamp": (datetime.now(timezone.utc) - timedelta(minutes=10)).isoformat(),
            },
        }
        with patch("workstation.quant_terminal_v2.live_payload", return_value=payload):
            result = live_mark_snapshot("BTC", stale_after_seconds=30)
        self.assertEqual(result["mark"], 90)
        self.assertTrue(result["stale"])
        self.assertFalse(result["eligible_for_exit"])
        self.assertEqual(result["reason"], "STALE_MARK")

    def test_missing_timestamp_fails_closed(self):
        payload = {"success": True, "symbol": "BTC", "source": "FYERS", "live_orders": False, "snapshot": {"ltp": 100}}
        with patch("workstation.quant_terminal_v2.live_payload", return_value=payload):
            result = live_mark_snapshot("BTC")
        self.assertFalse(result["verified"])
        self.assertFalse(result["eligible_for_exit"])
        self.assertEqual(result["reason"], "MARK_RECEIVED_TIMESTAMP_MISSING")

    def test_autonomy_does_not_close_on_stale_stop_cross(self):
        with tempfile.TemporaryDirectory() as folder:
            desk = PaperTradingDesk(Path(folder) / "paper.sqlite3")
            desk.open_position(symbol="NIFTY", side="LONG", entry=100, stop=95, target=110, quantity=1)
            engine = PaperAutonomyEngine(universe=("NIFTY",), max_workers=1)
            stale = {
                "success": True,
                "symbol": "NIFTY",
                "mark": 90,
                "verified": True,
                "stale": True,
                "eligible_for_exit": False,
                "reason": "STALE_MARK",
            }
            with patch("workstation.paper_autonomy_engine.paper_desk", desk), patch(
                "workstation.paper_autonomy_engine.live_mark_snapshot", return_value=stale
            ):
                result = engine.mark_once()
            self.assertEqual(desk.snapshot()["open_count"], 1)
            self.assertEqual(result["closed"], [])
            self.assertEqual(result["rejection_counts"], {"STALE_MARK": 1})


if __name__ == "__main__":
    unittest.main()
