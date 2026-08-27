from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import patch

from workstation import quant_terminal_v2


ROOT = Path(__file__).resolve().parents[1]


class QuantTerminalV2Tests(unittest.TestCase):
    def test_supported_symbols_cover_india_commodities_and_crypto(self):
        self.assertEqual(quant_terminal_v2.normalize_symbol("Nifty 50"), "NIFTY")
        self.assertEqual(quant_terminal_v2.normalize_symbol("crude oil"), "CRUDEOIL")
        self.assertEqual(quant_terminal_v2.normalize_symbol("bitcoin"), "BTC")
        self.assertEqual(quant_terminal_v2.normalize_symbol("ethereum"), "ETH")

    def test_timeframes_are_canonical(self):
        self.assertEqual(quant_terminal_v2.normalize_timeframe("15"), "15m")
        self.assertEqual(quant_terminal_v2.normalize_timeframe("60"), "1h")
        self.assertEqual(quant_terminal_v2.normalize_timeframe("daily"), "1d")

    @patch("workstation.quant_terminal_v2._crypto_candles")
    def test_crypto_candles_use_public_provider(self, crypto_loader):
        crypto_loader.return_value = {
            "success": True,
            "source": "BINANCE_PUBLIC",
            "candles": [{"time": 1, "open": 1, "high": 1, "low": 1, "close": 1}],
        }
        result = quant_terminal_v2.candles_payload("BTC", "5m", 100)
        self.assertTrue(result["success"])
        crypto_loader.assert_called_once_with("BTC", "5m", 100)

    @patch("workstation.quant_terminal_v2.candles_payload")
    def test_timeframe_evidence_marks_nested_quant_decision_successful(self, candles_loader):
        candles = []
        price = 100.0
        for index in range(90):
            price += 0.25
            candles.append(
                {
                    "time": index + 1,
                    "open": price - 0.1,
                    "high": price + 0.3,
                    "low": price - 0.4,
                    "close": price,
                    "volume": 1000 + index,
                }
            )
        candles_loader.return_value = {
            "success": True,
            "source": "TEST",
            "data_quality": "VERIFIED",
            "provider_symbol": "TEST:BTC",
            "candles": candles,
        }
        result = quant_terminal_v2._timeframe_evidence("BTC", "5m")
        self.assertTrue(result["decision"]["success"])
        self.assertFalse(result["decision"]["live_execution"])

    @patch("workstation.quant_terminal_v2._paper_session_open", return_value=True)
    @patch("workstation.quant_terminal_v2._timeframe_evidence")
    def test_scan_stays_research_and_paper_only(self, evidence, _session):
        evidence.side_effect = [
            {
                "timeframe": "5m",
                "available": True,
                "trend": "BULLISH",
                "close": 100.0,
                "atr14": 2.0,
            },
            {
                "timeframe": "15m",
                "available": True,
                "trend": "BULLISH",
                "close": 101.0,
                "atr14": 2.5,
            },
            {
                "timeframe": "1h",
                "available": True,
                "trend": "BULLISH",
                "close": 102.0,
                "atr14": 3.0,
            },
        ]
        result = quant_terminal_v2.scan_payload("NIFTY")
        self.assertTrue(result["success"])
        self.assertTrue(result["paper_only"])
        self.assertFalse(result["live_execution"])
        self.assertEqual(result["bias"], "BULLISH")
        self.assertEqual(result["alignment"], 100)
        self.assertTrue(result["qualified"])
        self.assertEqual(result["side"], "LONG")
        self.assertEqual(result["setup"]["status"], "PAPER_QUALIFIED")

    @patch("workstation.quant_terminal_v2._paper_session_open", return_value=True)
    @patch("workstation.quant_terminal_v2._timeframe_evidence")
    def test_conflicting_timeframe_signals_fail_closed_to_wait(self, evidence, _session):
        def row(timeframe, side, trend):
            return {
                "timeframe": timeframe,
                "available": True,
                "trend": trend,
                "close": 100.0,
                "atr14": 2.0,
                "decision": {
                    "success": True,
                    "symbol": "BTC",
                    "timeframe": timeframe,
                    "regime": "TRENDING",
                    "side": side,
                    "score": 75.0,
                    "entry": 100.0,
                    "stop": 98.0 if side == "LONG" else 102.0,
                    "target": 104.0 if side == "LONG" else 96.0,
                    "risk_reward": 2.0,
                    "votes": [],
                },
            }

        evidence.side_effect = [
            row("5m", "SHORT", "BEARISH"),
            row("15m", "LONG", "BULLISH"),
            row("1h", "LONG", "BULLISH"),
        ]
        result = quant_terminal_v2.scan_payload("BTC")
        self.assertEqual(result["side"], "WAIT")
        self.assertFalse(result["qualified"])
        self.assertIsNone(result["setup"])
        self.assertIn("TIMEFRAME_DIRECTION_CONFLICT", result["blockers"])

    @patch("workstation.quant_terminal_v2._paper_session_open", return_value=False)
    @patch("workstation.quant_terminal_v2._timeframe_evidence")
    def test_closed_market_blocks_automatic_entry(self, evidence, _session):
        evidence.side_effect = [
            {
                "timeframe": timeframe,
                "available": True,
                "trend": "BULLISH",
                "close": 100.0,
                "atr14": 2.0,
                "decision": {
                    "success": True,
                    "symbol": "NIFTY",
                    "timeframe": timeframe,
                    "regime": "TRENDING",
                    "side": "LONG",
                    "score": 75.0,
                    "entry": 100.0,
                    "stop": 98.0,
                    "target": 104.0,
                    "risk_reward": 2.0,
                    "votes": [],
                },
            }
            for timeframe in ("5m", "15m", "1h")
        ]
        result = quant_terminal_v2.scan_payload("NIFTY")
        self.assertEqual(result["side"], "WAIT")
        self.assertIn("MARKET_SESSION_CLOSED", result["blockers"])

    def test_professional_terminal_static_shell_uses_lightweight_charts(self):
        index = (
            ROOT / "workstation" / "quant_terminal_v2_static" / "index.html"
        ).read_text(encoding="utf-8")
        app = (
            ROOT / "workstation" / "quant_terminal_v2_static" / "app.js"
        ).read_text(encoding="utf-8")
        vendor = (
            ROOT
            / "workstation"
            / "quant_terminal_v2_static"
            / "lightweight-charts.standalone.production.js"
        ).read_text(encoding="utf-8")
        self.assertIn('src="/lightweight-charts.standalone.production.js"', index)
        self.assertIn('return"5.2.0"', vendor)
        self.assertIn("TradingView Lightweight Charts", index)
        self.assertIn("CandlestickSeries", app)
        self.assertIn("HistogramSeries", app)
        self.assertIn("wss://stream.binance.com", app)
        self.assertIn("/api/live", app)
        self.assertNotIn("/api/decision?", app)

    def test_automatic_paper_consensus_starts_on_boot_without_live_execution(self):
        with patch.object(quant_terminal_v2, "AUTO_PAPER_START", True), patch(
            "workstation.paper_autonomy_engine.paper_autonomy.start",
            return_value={"running": True, "paper_only": True, "live_execution": False},
        ) as start:
            result = quant_terminal_v2.start_paper_autonomy_on_boot()
        self.assertTrue(result["running"])
        self.assertFalse(result["live_execution"])
        start.assert_called_once_with()

    def test_quant_launcher_uses_v2_terminal(self):
        launcher = (ROOT / "start_jarvis_quant_terminal.py").read_text(encoding="utf-8")
        self.assertIn("from workstation import quant_terminal_v2 as trading_app", launcher)

    def test_live_bridge_exposes_no_order_surface(self):
        source = (ROOT / "workstation" / "fyers_live_bridge_service.py").read_text(
            encoding="utf-8"
        )
        for forbidden in ("place_order", "modify_order", "cancel_order"):
            self.assertNotIn(forbidden, source)
        self.assertIn('"live_orders": False', source)

    @patch("workstation.quant_terminal_v2._port_open", return_value=False)
    def test_provider_payload_remains_execution_locked(self, _port_open):
        with patch("agents.fyers_auth_manager.is_configured", return_value=False):
            result = quant_terminal_v2.provider_payload()
        self.assertTrue(result["paper_only"])
        self.assertFalse(result["live_execution"])
        self.assertEqual(result["state"], "LOGIN_REQUIRED")

    @patch("workstation.quant_terminal_v2._port_open", return_value=True)
    @patch("workstation.quant_terminal_v2._bridge_request")
    def test_provider_reports_degraded_stream_instead_of_false_connected(self, bridge, _port):
        bridge.return_value = {
            "running": True,
            "connected": True,
            "error": "Connection to remote host was lost.",
            "live_orders": False,
        }
        with patch("agents.fyers_auth_manager.is_configured", return_value=True):
            result = quant_terminal_v2.provider_payload()
        self.assertEqual(result["state"], "DEGRADED")
        self.assertFalse(result["live_execution"])

    def test_uniform_health_interprets_existing_connected_provider_contract(self):
        ready, error = quant_terminal_v2.provider_health_state(
            {
                "state": "CONNECTED",
                "bridge": {"connected": True, "error": None},
            }
        )
        self.assertTrue(ready)
        self.assertIsNone(error)
        degraded, message = quant_terminal_v2.provider_health_state(
            {
                "state": "DEGRADED",
                "bridge": {"connected": False, "error": "session rejected"},
            }
        )
        self.assertFalse(degraded)
        self.assertEqual(message, "session rejected")

    @patch("agents.fyers_data_adapter.get_quote")
    @patch("workstation.quant_terminal_v2._bridge_request", return_value=None)
    @patch("workstation.quant_terminal_v2._port_open", return_value=True)
    def test_fixed_indian_watch_symbol_uses_rest_quote_when_stream_missing(
        self, _port, _bridge, quote
    ):
        quote.return_value = {
            "success": True,
            "ltp": 24123.5,
            "change": 10.0,
            "change_percent": 0.04,
        }
        with patch("workstation.quant_terminal_v2.symbol_metadata", return_value={
            "market": "INDIA", "provider_symbol": "NSE:NIFTY50-INDEX"
        }):
            result = quant_terminal_v2.live_payload("NIFTY")
        self.assertTrue(result["success"])
        self.assertEqual(result["snapshot_kind"], "REST_QUOTE_FALLBACK")
        self.assertTrue(result["stream_degraded"])
        self.assertEqual(result["snapshot"]["ltp"], 24123.5)
        self.assertFalse(result["live_orders"])

    def test_watchlist_hydrates_immediately_and_never_swallows_errors(self):
        app = (ROOT / "workstation" / "quant_terminal_v2_static" / "app.js").read_text(
            encoding="utf-8"
        )
        self.assertIn("async function refreshAllWatch()", app)
        self.assertIn("const watchHydration=refreshAllWatch()", app)
        self.assertIn("updateWatchTile(item.symbol,null,{message:error.message})", app)


if __name__ == "__main__":
    unittest.main()
