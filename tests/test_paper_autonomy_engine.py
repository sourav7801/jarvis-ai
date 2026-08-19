from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from workstation.paper_autonomy_engine import PaperAutonomyEngine
from workstation.paper_trading_desk import PaperTradingDesk


class PaperAutonomyEngineTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.desk = PaperTradingDesk(
            Path(self.temp.name) / "paper.sqlite3",
            starting_equity=100000,
            max_open_positions=4,
        )
        self.engine = PaperAutonomyEngine(
            universe=("NIFTY", "BTC"),
            timeframes=("5m",),
            min_score=68,
            min_risk_reward=1.5,
            scan_interval_seconds=5,
            mark_interval_seconds=0.25,
            max_workers=2,
        )

    def tearDown(self):
        self.engine.stop()
        self.temp.cleanup()

    def test_live_execution_locked(self):
        self.assertFalse(self.engine.live_execution)
        self.assertFalse(self.engine.status()["live_execution"])

    def test_status_contract(self):
        status = self.engine.status()
        self.assertIn("scan_cycles", status)
        self.assertIn("positions_opened", status)
        self.assertTrue(status["paper_only"])

    def test_start_stop(self):
        with patch.object(self.engine, "_scan_loop", return_value=None), patch.object(
            self.engine, "_mark_loop", return_value=None
        ):
            started = self.engine.start()
            self.assertTrue(started["running"])
            stopped = self.engine.stop()
            self.assertFalse(stopped["running"])

    def test_rank_prefers_score_then_rr(self):
        high = {"score": 80, "risk_reward": 1.5}
        lower = {"score": 70, "risk_reward": 3.0}
        self.assertGreater(self.engine._rank_key(high), self.engine._rank_key(lower))

    def test_source_has_no_live_order_surface(self):
        source = Path(__file__).resolve().parents[1] / "workstation" / "paper_autonomy_engine.py"
        text = source.read_text(encoding="utf-8")
        for forbidden in ("place_order(", "modify_order(", "cancel_order(", "/orders/sync"):
            self.assertNotIn(forbidden, text)


if __name__ == "__main__":
    unittest.main()
