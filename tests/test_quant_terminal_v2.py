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

    @patch("workstation.quant_terminal_v2._timeframe_evidence")
    def test_scan_stays_research_and_paper_only(self, evidence):
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
        self.assertEqual(result["setup"]["status"], "RESEARCH_CANDIDATE")

    def test_professional_terminal_static_shell_uses_lightweight_charts(self):
        index = (
            ROOT / "workstation" / "quant_terminal_v2_static" / "index.html"
        ).read_text(encoding="utf-8")
        app = (
            ROOT / "workstation" / "quant_terminal_v2_static" / "app.js"
        ).read_text(encoding="utf-8")
        self.assertIn("lightweight-charts@5.2.0", index)
        self.assertIn("TradingView Lightweight Charts", index)
        self.assertIn("CandlestickSeries", app)
        self.assertIn("HistogramSeries", app)
        self.assertIn("wss://stream.binance.com", app)
        self.assertIn("/api/live", app)

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


if __name__ == "__main__":
    unittest.main()
