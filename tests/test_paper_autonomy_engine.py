from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from datetime import datetime, timezone
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

    def test_scan_status_retains_funnel_latency_provider_failures_and_blockers(self):
        desk = MagicMock()
        desk.snapshot.return_value = {"positions": []}

        def scan(symbol):
            if symbol == "NIFTY":
                return {
                    "success": False,
                    "symbol": symbol,
                    "source": "FYERS",
                    "message": "session token rejected",
                }
            return {
                "success": True,
                "symbol": symbol,
                "source": "BINANCE_PUBLIC",
                "data_quality": "PUBLIC_LIVE",
                "session_open": True,
                "qualified": False,
                "side": "WAIT",
                "score": 52.0,
            }

        with patch("workstation.paper_autonomy_engine.paper_desk", desk), patch.object(
            self.engine,
            "_scan_symbol",
            side_effect=scan,
        ):
            result = self.engine.scan_once()

        status = self.engine.status()
        self.assertEqual(result["rows"], 2)
        self.assertGreaterEqual(status["last_scan_elapsed_ms"], 0.0)
        self.assertEqual(
            status["last_scan_funnel"],
            {"scanned": 2, "data_ok": 1, "session_open": 1, "qualified": 0, "opened": 0},
        )
        self.assertEqual(status["last_provider_failure_counts"], {"FYERS": 1})
        summaries = {item["symbol"]: item for item in status["last_rows_summary"]}
        self.assertEqual(summaries["NIFTY"]["blockers"], ["DATA_UNAVAILABLE"])
        self.assertEqual(summaries["BTC"]["blockers"], ["NO_QUALIFIED_SETUP"])

    def test_scan_persists_bounded_cycle_evidence_when_ledger_is_configured(self):
        desk = MagicMock()
        desk.snapshot.return_value = {"positions": []}
        ledger = MagicMock()
        ledger.record.return_value = 41
        ledger.recent.return_value = [{"id": 41, "paper_only": True, "live_execution": False}]
        ledger.trends.return_value = {"cycles": 1, "rates": {"data_ok_percent": 100.0}}
        self.engine.scan_ledger = ledger
        row = {
            "success": True,
            "symbol": "BTC",
            "source": "BINANCE_PUBLIC",
            "session_open": True,
            "qualified": False,
            "side": "WAIT",
            "score": 52.0,
            "blockers": ["SCORE_BELOW_GATE"],
        }
        with patch("workstation.paper_autonomy_engine.paper_desk", desk), patch.object(
            self.engine, "_scan_symbol", return_value=row
        ):
            self.engine.scan_once()

        recorded = ledger.record.call_args.args[0]
        self.assertEqual(recorded["funnel"]["scanned"], 2)
        self.assertEqual(recorded["rows"][0]["blockers"], ["SCORE_BELOW_GATE"])
        status = self.engine.status()
        self.assertEqual(status["last_scan_ledger_id"], 41)
        self.assertEqual(status["recent_scan_history"][0]["id"], 41)
        self.assertEqual(status["scan_history_trends"]["cycles"], 1)

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
            "message": "Three timeframes confirmed a governed long setup.",
            "pattern_confirmation": {
                "state": "CONFIRMED_BREAKOUT",
                "patterns": [{"name": "RANGE_EXPANSION", "direction": "BULLISH"}],
            },
            "evidence": [{
                "timeframe": "5m",
                "source": "BINANCE_PUBLIC",
                "data_quality": "PUBLIC_LIVE",
                "journal_bars": [
                    {"time": 1, "open": 99, "high": 101, "low": 98, "close": 100, "volume": 10}
                ],
                "features": {
                    "structure": {"bias": "BULLISH"},
                    "liquidity": {"fair_value_gaps": [{"side": "BULLISH"}]},
                    "indicators": {"results": {"ema_20": {"value": 99.5}}},
                },
            }],
        }
        with patch("workstation.paper_autonomy_engine.paper_desk", desk), patch.object(
            self.engine, "_scan_symbol", return_value=qualified
        ):
            result = self.engine.scan_once()
        self.assertEqual(result["candidate_count"], 2)
        self.assertEqual(len(result["opened"]), 1)
        desk.open_position.assert_called_once()
        metadata = desk.open_position.call_args.kwargs["metadata"]
        self.assertEqual(metadata["entry_reason"], qualified["message"])
        self.assertEqual(metadata["chart_patterns"][0]["name"], "RANGE_EXPANSION")
        self.assertEqual(metadata["entry_chart_snapshot"]["bars"][0]["close"], 100)
        self.assertEqual(metadata["feature_snapshot"]["structure"]["bias"], "BULLISH")

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

    def test_recent_same_strategy_close_enforces_profile_cooldown_without_opening(self):
        desk = MagicMock()
        desk.snapshot.return_value = {"positions": []}
        desk.closed_positions.return_value = [
            {
                "symbol": "BTC",
                "strategy": "QUANT_ENSEMBLE_V2_GOVERNED_CONSENSUS_V4",
                "closed_at": datetime.now(timezone.utc).isoformat(),
                "metadata": {"profile": "5m_only"},
            }
        ]
        qualified = {
            "success": True,
            "symbol": "BTC",
            "timeframe": "5m",
            "decision_version": "SINGLE_TF_V1",
            "qualified": True,
            "side": "LONG",
            "score": 80.0,
            "regime": "TRENDING",
            "alignment": 100,
            "risk_reward": 2.2,
            "entry": 100.0,
            "stop": 98.0,
            "target": 104.4,
            "blockers": [],
        }
        with patch("workstation.paper_autonomy_engine.paper_desk", desk), patch.object(
            self.engine, "_scan_symbol", return_value=qualified
        ):
            result = self.engine.scan_once()

        self.assertEqual(result["opened"], [])
        self.assertEqual(result["rejection_counts"]["REENTRY_COOLDOWN_ACTIVE"], 2)
        desk.open_position.assert_not_called()
        self.assertEqual(self.engine.status()["reentry_policy_version"], "PAPER_REENTRY_COOLDOWN_V1")
        self.assertEqual(self.engine.status()["reentry_cooldown_minutes"], 10.0)

    def test_source_has_no_live_order_surface(self):
        source = Path(__file__).resolve().parents[1] / "workstation" / "paper_autonomy_engine.py"
        text = source.read_text(encoding="utf-8")
        for forbidden in ("place_order(", "modify_order(", "cancel_order(", "/orders/sync"):
            self.assertNotIn(forbidden, text)


if __name__ == "__main__":
    unittest.main()
