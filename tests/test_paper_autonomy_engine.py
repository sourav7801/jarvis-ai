from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

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

    def test_conflicted_consensus_never_opens_position(self):
        desk = MagicMock()
        desk.snapshot.return_value = {"positions": []}
        with patch("workstation.paper_autonomy_engine.paper_desk", desk), patch.object(
            self.engine,
            "_scan_symbol",
            return_value={
                "success": True,
                "symbol": "BTC",
                "qualified": False,
                "side": "WAIT",
                "score": 0.0,
                "risk_reward": None,
                "blockers": ["TIMEFRAME_DIRECTION_CONFLICT"],
            },
        ):
            result = self.engine.scan_once()
        self.assertEqual(result["candidate_count"], 0)
        desk.open_position.assert_not_called()

    @patch(
        "workstation.paper_market_data.PAPER_MARKET_DATA.quote",
        return_value={"success": True, "native_ltp": 100.0, "valuation_ltp": 9000.0},
    )
    @patch(
        "workstation.paper_market_data.PAPER_MARKET_DATA.instrument_spec",
        return_value={
            "symbol": "BTC", "provider_symbol": "BTCUSDT", "asset_class": "CRYPTO",
            "instrument_type": "SPOT", "native_currency": "USDT", "valuation_currency": "INR",
            "quantity_step": 0.001, "contract_multiplier": 1.0, "tick_size": 0.01,
            "source": "BINANCE_PUBLIC_EXCHANGE_INFO", "verified": True,
            "verification_reason": "BINANCE_EXCHANGE_INFO",
        },
    )
    @patch("workstation.paper_trading_desk.live_mark_loader", return_value=100.0)
    def test_qualified_consensus_opens_one_synthetic_position(self, _mark, _spec, _quote):
        desk = MagicMock()
        desk.snapshot.return_value = {"positions": []}
        desk.open_position.return_value = {
            "success": True,
            "reason": "PAPER_POSITION_OPENED",
        }
        qualified = {
            "success": True,
            "symbol": "BTC",
            "timeframe": "5m / 15m / 1h",
            "decision_version": "MTF_CONSENSUS_V1",
            "qualified": True,
            "side": "LONG",
            "score": 75.0,
            "regime": "TRENDING",
            "alignment": 100,
            "risk_reward": 2.0,
            "entry": 100.0,
            "stop": 98.0,
            "target": 104.0,
            "votes": [],
            "decisions": [],
        }
        with patch("workstation.paper_autonomy_engine.paper_desk", desk), patch.object(
            self.engine, "_scan_symbol", return_value=qualified
        ):
            result = self.engine.scan_once()
        self.assertEqual(result["candidate_count"], 2)
        self.assertEqual(len(result["opened"]), 1)
        desk.open_position.assert_called_once()

    def test_desk_level_risk_lock_is_visible_in_autonomy_rejection_telemetry(self):
        desk = MagicMock()
        desk.snapshot.return_value = {"positions": []}
        desk.open_position.return_value = {
            "success": False,
            "reason": "DAILY_LOSS_LOCK",
            "paper_only": True,
            "live_execution": False,
        }
        qualified = {
            "success": True,
            "symbol": "BTC",
            "timeframe": "5m",
            "decision_version": "SINGLE_TF_V1",
            "qualified": True,
            "side": "LONG",
            "score": 75.0,
            "regime": "TRENDING",
            "alignment": 100,
            "risk_reward": 2.0,
            "entry": 100.0,
            "stop": 98.0,
            "target": 104.0,
            "votes": [],
            "decisions": [],
        }
        instrument_spec = {
            "symbol": "BTC", "provider_symbol": "BTCUSDT", "asset_class": "CRYPTO",
            "instrument_type": "SPOT", "native_currency": "USDT", "valuation_currency": "INR",
            "quantity_step": 0.001, "contract_multiplier": 1.0, "tick_size": 0.01,
            "source": "BINANCE_PUBLIC_EXCHANGE_INFO", "verified": True,
            "verification_reason": "BINANCE_EXCHANGE_INFO",
        }
        with patch("workstation.paper_autonomy_engine.paper_desk", desk), patch.object(
            self.engine, "_scan_symbol", return_value=qualified
        ), patch(
            "workstation.paper_trade_action_router._live_entry", return_value=(100.0, None)
        ), patch(
            "workstation.paper_market_data.PAPER_MARKET_DATA.instrument_spec", return_value=instrument_spec
        ), patch(
            "workstation.paper_market_data.PAPER_MARKET_DATA.quote",
            return_value={"success": True, "native_ltp": 100.0, "valuation_ltp": 9000.0},
        ):
            result = self.engine.scan_once()

        self.assertEqual(result["opened"], [])
        self.assertEqual(result["rejection_counts"]["DAILY_LOSS_LOCK"], 2)
        self.assertEqual(self.engine.status()["last_rejection_counts"]["DAILY_LOSS_LOCK"], 2)

    def test_source_has_no_live_order_surface(self):
        source = Path(__file__).resolve().parents[1] / "workstation" / "paper_autonomy_engine.py"
        text = source.read_text(encoding="utf-8")
        for forbidden in ("place_order(", "modify_order(", "cancel_order(", "/orders/sync"):
            self.assertNotIn(forbidden, text)


if __name__ == "__main__":
    unittest.main()
