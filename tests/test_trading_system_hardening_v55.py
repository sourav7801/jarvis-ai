from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import MagicMock, patch

from workstation.morning_trading_coordinator import (
    is_morning_start_request,
    start_morning_paper_workflow,
)
from workstation.multi_market_scanner import MultiMarketScanner
from workstation.paper_autonomy_engine import PaperAutonomyEngine
from workstation.paper_trading_desk import PaperTradingDesk
from workstation.paper_market_data import UnifiedPaperMarketData
from workstation.quant_terminal_v2 import completed_candles
from workstation.quant_terminal_v2 import scan_payload
from workstation.scanner_universe_registry import (
    ALWAYS_OPEN_SESSION,
    INDIA_CASH_SESSION,
    ScannerInstrument,
    UniverseSnapshot,
)
from workstation.trading_timeframe_profiles import requested_trading_profile


class TradingSystemHardeningTests(unittest.TestCase):
    def test_explicit_five_minute_command_installs_exact_profile(self):
        profile = requested_trading_profile("Jarvis start paper trading on 5 minutes only")
        self.assertEqual(profile.name, "5m_only")
        self.assertEqual(profile.timeframes, ("5m",))
        self.assertTrue(is_morning_start_request("Jarvis start paper trading on 5m only"))

    def test_paper_exploration_profile_uses_quarter_risk_and_remains_paper_only(self):
        profile = requested_trading_profile(
            "Jarvis use paper exploration mode and learn from paper trades"
        )
        self.assertEqual(profile.name, "paper_exploration")
        self.assertEqual(profile.timeframes, ("5m",))
        self.assertEqual(profile.minimum_score, 62.0)
        self.assertEqual(profile.risk_multiplier, 0.25)
        engine = PaperAutonomyEngine(universe=("BTC",))
        status = engine.configure_profile("paper_exploration")
        self.assertEqual(status["profile_risk_multiplier"], 0.25)
        self.assertFalse(status["live_execution"])

    def test_forming_candle_is_excluded(self):
        rows = [
            {"time": 0, "close_time": 59, "close": 1},
            {"time": 60, "close_time": 119, "close": 2},
            {"time": 120, "close_time": 179, "close": 3},
        ]
        self.assertEqual(len(completed_candles(rows, "1m", now_epoch=150)), 2)

    @patch("workstation.quant_terminal_v2._paper_session_open", return_value=True)
    @patch("workstation.quant_terminal_v2._timeframe_evidence")
    def test_five_minute_profile_fetches_only_five_minute_evidence(self, evidence, _session):
        evidence.return_value = {
            "timeframe": "5m",
            "available": True,
            "fresh": True,
            "trend": "BULLISH",
            "decision": {
                "success": True,
                "timeframe": "5m",
                "side": "LONG",
                "score": 82,
                "entry": 100,
                "stop": 99,
                "target": 102,
                "risk_reward": 2,
                "regime": "TRENDING",
                "votes": [],
            },
            "patterns": {
                "success": True,
                "state": "CONFIRMED_BREAKOUT",
                "direction": "BULLISH",
                "score": 80,
            },
        }
        result = scan_payload("NIFTY", profile="5m_only")
        evidence.assert_called_once_with("NIFTY", "5m")
        self.assertTrue(result["qualified"])
        self.assertEqual(result["timeframe"], "5m")

    @patch("workstation.quant_terminal_v2._paper_session_open", return_value=True)
    @patch("workstation.quant_terminal_v2._timeframe_evidence")
    def test_paper_exploration_can_learn_from_bounded_range_setup(
        self, evidence, _session
    ):
        evidence.return_value = {
            "timeframe": "5m",
            "available": True,
            "fresh": True,
            "trend": "BULLISH",
            "decision": {
                "success": True,
                "timeframe": "5m",
                "side": "LONG",
                "score": 66,
                "entry": 100,
                "stop": 99,
                "target": 102,
                "risk_reward": 2,
                "regime": "RANGE",
                "votes": [],
            },
            "patterns": {
                "success": True,
                "state": "NO_EDGE",
                "direction": "BULLISH",
                "score": 60,
            },
        }

        result = scan_payload("BTC", profile="paper_exploration")

        evidence.assert_called_once_with("BTC", "5m")
        self.assertTrue(result["qualified"])
        self.assertEqual(result["side"], "LONG")
        self.assertNotIn("ALL_TIMEFRAMES_RANGE", result["blockers"])
        self.assertFalse(result["live_execution"])

    @patch("workstation.quant_terminal_v2.scan_payload")
    def test_autonomy_uses_configured_single_timeframe_profile(self, scan_payload):
        scan_payload.return_value = {
            "success": True,
            "symbol": "NIFTY",
            "qualified": False,
            "side": "WAIT",
            "score": 60,
            "blockers": ["PATTERN_NOT_CONFIRMED"],
            "message": "WAIT",
        }
        engine = PaperAutonomyEngine(universe=("NIFTY",), profile="5m_only")
        result = engine.scan_once()
        scan_payload.assert_called_once_with("NIFTY", profile="5m_only")
        self.assertEqual(result["rejection_counts"]["PATTERN_NOT_CONFIRMED"], 1)
        self.assertEqual(engine.status()["timeframes"], ["5m"])

    @patch("workstation.bounded_decision_review.decision_review_coordinator.start")
    @patch("workstation.multi_market_scanner.multi_market_scanner.start")
    @patch("workstation.paper_autonomy_engine.paper_autonomy.start")
    def test_morning_button_starts_multi_market_and_immediate_paper_scan(
        self, autonomy_start, scanner_start, reviewer_start
    ):
        autonomy_start.return_value = {"running": True}
        scanner_start.return_value = {"running": True}
        reviewer_start.return_value = {"running": True}
        payload = start_morning_paper_workflow(profile="5m_only")
        autonomy_start.assert_called_once_with(profile="5m_only", scan_now=True)
        selected = scanner_start.call_args.kwargs["universes"]
        self.assertIn("BANKNIFTY", selected)
        self.assertIn("SENSEX30", selected)
        self.assertIn("CRYPTO_MAJOR", selected)
        self.assertEqual(payload["profile"]["timeframes"], ("5m",))

    def test_multi_market_scanner_preserves_universe_and_execution_gate(self):
        eligible = ScannerInstrument(
            "BTC", "Bitcoin", "CRYPTO", "GLOBAL", "CRYPTO_SPOT", "BINANCE_PUBLIC",
            "BTCUSDT", "USDT", ALWAYS_OPEN_SESSION, ("CRYPTO_MAJOR",), "BINANCE",
            "PUBLIC_REALTIME", True, "CURRENT_DATA",
        )
        research_only = ScannerInstrument(
            "AAPL", "Apple", "EQUITY", "GLOBAL", "NASDAQ", "PUBLIC",
            "AAPL", "USD", ALWAYS_OPEN_SESSION, ("GLOBAL_MAJOR",), "PUBLIC",
            "UNOFFICIAL_DELAYED", False, "AUTO_PAPER_BLOCKED",
        )
        scanner = MultiMarketScanner(max_workers=1)
        snapshots = [
            UniverseSnapshot("CRYPTO_MAJOR", (eligible,), "BINANCE", None, "PUBLIC", "now"),
            UniverseSnapshot("GLOBAL_MAJOR", (research_only,), "PUBLIC", None, "DELAYED", "now"),
        ]
        rows = {
            "BTC": {"success": True, "symbol": "BTC", "universes": ["CRYPTO_MAJOR"], "candidate": True, "auto_paper_eligible": True, "score": 80},
            "AAPL": {"success": True, "symbol": "AAPL", "universes": ["GLOBAL_MAJOR"], "candidate": True, "auto_paper_eligible": False, "score": 80},
        }
        with patch.object(scanner, "_snapshots", return_value=snapshots), patch.object(
            scanner, "_scan_one", side_effect=lambda item: rows[item.symbol]
        ):
            scanner.start(universes=("CRYPTO_MAJOR", "GLOBAL_MAJOR"), force=True)
            deadline = time.time() + 2
            while scanner.status()["running"] and time.time() < deadline:
                time.sleep(0.01)
        status = scanner.status()
        self.assertEqual(status["candidate_count"], 2)
        self.assertEqual(status["executable_watch_count"], 1)
        self.assertEqual(status["by_universe"]["GLOBAL_MAJOR"]["auto_paper_eligible"], 0)

    @patch("workstation.multi_market_scanner.analyze_chart_patterns")
    @patch("omni.trading_intelligence.quant_firm_engine.decide")
    @patch("workstation.quant_terminal_v2.candles_payload")
    def test_banknifty_constituent_uses_explicit_broker_symbol(
        self, candles_payload, decide, patterns
    ):
        candles_payload.return_value = {
            "success": True,
            "candles": [
                {
                    "time": index * 86_400,
                    "close_time": index * 86_400 + 86_399,
                    "open": 100 + index,
                    "high": 102 + index,
                    "low": 99 + index,
                    "close": 101 + index,
                    "volume": 1_000,
                }
                for index in range(80)
            ],
        }
        patterns.return_value = {
            "direction": "BULLISH",
            "score": 80,
            "state": "CONFIRMED_BREAKOUT",
            "breakout_level": 179,
            "breakdown_level": 150,
            "volume_ratio": 2,
            "structure": "BULLISH",
            "patterns": [],
            "message": "confirmed",
        }
        decide.return_value = MagicMock(
            to_dict=MagicMock(return_value={"side": "LONG", "score": 80})
        )
        instrument = ScannerInstrument(
            "AUBANK", "AU Small Finance Bank", "EQUITY", "INDIA", "NSE",
            "FYERS_READ_ONLY", "NSE:AUBANK-EQ", "INR", INDIA_CASH_SESSION,
            ("BANKNIFTY",), "NSE", "OFFICIAL_RUNTIME", True,
            "CURRENT_BROKER_DATA_AND_OPEN_SESSION_REQUIRED",
        )

        result = MultiMarketScanner._scan_one(instrument)

        candles_payload.assert_called_once_with("NSE:AUBANK-EQ", "1d", 180)
        self.assertTrue(result["success"])
        self.assertEqual(result["symbol"], "AUBANK")

    def test_crypto_valuation_is_converted_before_portfolio_risk(self):
        with tempfile.TemporaryDirectory() as tmp:
            desk = PaperTradingDesk(Path(tmp) / "paper.sqlite3", starting_equity=100000)
            opened = desk.open_position(
                symbol="BTC",
                side="LONG",
                entry=100,
                stop=99,
                target=102,
                quantity=1,
                valuation_multiplier=90,
                external_id="btc-bar-1",
            )
            self.assertTrue(opened["success"])
            snapshot = desk.snapshot(mark_loader=lambda _symbol: 101)
            self.assertEqual(snapshot["unrealized_pnl"], 90)
            self.assertEqual(snapshot["risk_at_stops"], 90)
            closed = desk.close_position(position_id=opened["position_id"], exit_price=101)
            self.assertEqual(closed["realized_pnl"], 90)

    def test_different_bar_ids_allow_multiple_same_day_paper_trades(self):
        with tempfile.TemporaryDirectory() as tmp:
            desk = PaperTradingDesk(Path(tmp) / "paper.sqlite3")
            first = desk.open_position(
                symbol="NIFTY", side="LONG", entry=100, stop=99, target=102,
                quantity=1, external_id="auto:NIFTY:5m:bar-1",
            )
            desk.close_position(position_id=first["position_id"], exit_price=102)
            second = desk.open_position(
                symbol="NIFTY", side="LONG", entry=103, stop=102, target=105,
                quantity=1, external_id="auto:NIFTY:5m:bar-2",
            )
            self.assertEqual(second["reason"], "PAPER_POSITION_OPENED")

    def test_configured_exchange_holiday_fails_closed(self):
        now = lambda: datetime(2026, 8, 25, 5, 0, tzinfo=timezone.utc)
        data = UnifiedPaperMarketData(market_runtime=MagicMock(), now=now)
        with patch.dict("os.environ", {"JARVIS_INDIA_MARKET_HOLIDAYS": "2026-08-25"}):
            self.assertFalse(data.session_open("NIFTY"))
        self.assertTrue(data.session_open("NIFTY"))

    def test_start_to_immediate_scan_to_real_sqlite_paper_fill(self):
        with tempfile.TemporaryDirectory() as tmp:
            desk = PaperTradingDesk(Path(tmp) / "paper.sqlite3")
            decision = {
                "success": True,
                "symbol": "NIFTY",
                "timeframe": "5m",
                "profile": "5m_only",
                "decision_version": "GOVERNED_TIMEFRAME_CONSENSUS_V3",
                "qualified": True,
                "side": "LONG",
                "candidate_side": "LONG",
                "score": 82.0,
                "regime": "TRENDING",
                "alignment": 100,
                "risk_reward": 2.0,
                "entry": 100.0,
                "stop": 99.0,
                "target": 102.0,
                "blockers": [],
                "evidence": [{"last_candle_time": 123456}],
                "votes": [],
                "decisions": [],
            }
            engine = PaperAutonomyEngine(
                universe=("NIFTY",),
                profile="5m_only",
                scan_interval_seconds=60,
                mark_interval_seconds=60,
                max_workers=1,
            )
            with patch("workstation.paper_autonomy_engine.paper_desk", desk), patch(
                "workstation.paper_autonomy_engine.live_mark_loader", return_value=100.0
            ), patch(
                "workstation.quant_terminal_v2.scan_payload", return_value=decision
            ), patch(
                "workstation.paper_trade_action_router._live_entry", return_value=(100.0, None)
            ), patch(
                "workstation.bounded_decision_review.decision_review_coordinator.policy_for",
                return_value={"allowed": True, "risk_multiplier": 1.0},
            ), patch(
                "workstation.bounded_decision_review.decision_review_coordinator.start",
                return_value={"running": True},
            ):
                engine.start(profile="5m_only", scan_now=True)
                deadline = time.time() + 2
                while desk.snapshot()["open_count"] == 0 and time.time() < deadline:
                    time.sleep(0.01)
                engine.stop()
            self.assertEqual(desk.snapshot()["open_count"], 1)
            self.assertEqual(engine.status()["profile"], "5m_only")

    def test_trading_hardening_source_has_no_live_order_surface(self):
        root = Path(__file__).resolve().parents[1]
        text = "\n".join(
            (root / "workstation" / name).read_text(encoding="utf-8")
            for name in (
                "multi_market_scanner.py",
                "paper_autonomy_engine.py",
                "bounded_decision_review.py",
            )
        )
        for forbidden in ("place_order(", "modify_order(", "cancel_order("):
            self.assertNotIn(forbidden, text)


if __name__ == "__main__":
    unittest.main()
