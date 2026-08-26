from __future__ import annotations

import unittest
from unittest.mock import patch

from workstation.advanced_pattern_engine import analyze_chart_patterns
from workstation.equity_universe import (
    NIFTY50_FALLBACK,
    nifty50_constituents,
    resolve_equity_symbol,
    resolve_equity_symbols_from_text,
)
from workstation.global_equity_data import global_equity_candles
from workstation.morning_trading_coordinator import is_morning_start_request
from workstation.nifty50_breakout_scanner import is_nifty50_scan_request
from workstation.quant_terminal_bridge import requested_symbols, requested_timeframe


def _candles(count: int = 70, *, final_close: float | None = None) -> list[dict]:
    rows = []
    for index in range(count):
        close = 100.0 + index * 0.05
        rows.append(
            {
                "time": 1_700_000_000 + index * 300,
                "open": close - 0.2,
                "high": close + 0.5,
                "low": close - 0.5,
                "close": close,
                "volume": 1_000.0,
            }
        )
    if final_close is not None:
        rows[-1].update(
            {
                "open": final_close - 1.0,
                "high": final_close + 0.5,
                "low": final_close - 1.5,
                "close": final_close,
                "volume": 2_500.0,
            }
        )
    return rows


class EquityUniverseTests(unittest.TestCase):
    def test_official_loader_requires_and_returns_exactly_50(self):
        header = "Company Name,Industry,Symbol,Series,ISIN Code\n"
        body = "".join(
            f"{label},{industry},{symbol},EQ,TEST{index:03d}\n"
            for index, (symbol, label, industry) in enumerate(NIFTY50_FALLBACK)
        )
        rows, source = nifty50_constituents(force_refresh=True, loader=lambda _url: header + body)
        self.assertEqual(len(rows), 50)
        self.assertEqual(source, "OFFICIAL_NSE_RUNTIME")
        self.assertEqual(rows[36].symbol, "RELIANCE")
        self.assertEqual(rows[36].provider_symbol, "NSE:RELIANCE-EQ")

    def test_reliance_and_global_symbols_resolve_deterministically(self):
        reliance = resolve_equity_symbol("Reliance Industries")
        apple = resolve_equity_symbol("NASDAQ:AAPL")
        tokyo = resolve_equity_symbol("YF:7203.T")
        self.assertEqual(reliance.provider_symbol, "NSE:RELIANCE-EQ")
        self.assertEqual(apple.market, "GLOBAL")
        self.assertEqual(tokyo.provider_symbol, "7203.T")
        self.assertEqual(resolve_equity_symbols_from_text("open Reliance daily chart"), ("RELIANCE",))
        self.assertIn("AAPL", requested_symbols("analyze Apple daily chart"))

    def test_swing_language_selects_daily_chart(self):
        self.assertEqual(requested_timeframe("open Reliance swing chart"), "1d")
        self.assertTrue(is_nifty50_scan_request("scan all Nifty 50 companies for breakouts"))
        self.assertTrue(is_morning_start_request("Jarvis, start trading"))


class PatternAndGlobalDataTests(unittest.TestCase):
    def test_breakout_level_excludes_latest_candle(self):
        rows = _candles(final_close=110.0)
        prior_high = max(row["high"] for row in rows[-21:-1])
        result = analyze_chart_patterns(rows)
        self.assertTrue(result["lookahead_safe"])
        self.assertEqual(result["breakout_level"], prior_high)
        self.assertEqual(result["direction"], "BULLISH")
        self.assertEqual(result["state"], "CONFIRMED_BREAKOUT")

    def test_global_chart_response_is_normalized_and_research_only(self):
        timestamps = [1_700_000_000, 1_700_000_300]
        provider = {
            "chart": {
                "error": None,
                "result": [
                    {
                        "timestamp": timestamps,
                        "meta": {"currency": "USD", "exchangeName": "NMS"},
                        "indicators": {
                            "quote": [
                                {
                                    "open": [100.0, 101.0],
                                    "high": [102.0, 103.0],
                                    "low": [99.0, 100.0],
                                    "close": [101.0, 102.0],
                                    "volume": [1000, 1200],
                                }
                            ]
                        },
                    }
                ],
            }
        }
        result = global_equity_candles("AAPL", "5m", 100, loader=lambda _url: provider)
        self.assertTrue(result["success"])
        self.assertEqual(result["bars"], 2)
        self.assertFalse(result["auto_execution_eligible"])
        self.assertEqual(result["candles"][-1]["close"], 102.0)


class SwingConsensusTests(unittest.TestCase):
    @staticmethod
    def _evidence(timeframe: str) -> dict:
        return {
            "timeframe": timeframe,
            "available": True,
            "trend": "BULLISH",
            "decision": {
                "success": True,
                "timeframe": timeframe,
                "side": "LONG",
                "score": 80.0,
                "entry": 100.0,
                "stop": 95.0,
                "target": 110.0,
                "risk_reward": 2.0,
                "regime": "TRENDING",
                "votes": [],
            },
        }

    @patch("workstation.quant_terminal_v2._paper_session_open", return_value=False)
    @patch("workstation.quant_terminal_v2._timeframe_evidence")
    def test_swing_profile_returns_conditional_levels_when_market_closed(self, evidence, _session):
        evidence.side_effect = lambda _symbol, timeframe: self._evidence(timeframe)
        from workstation.quant_terminal_v2 import scan_payload

        result = scan_payload("RELIANCE", profile="swing")
        self.assertEqual(result["timeframe"], "1h / 4h / 1d")
        self.assertFalse(result["qualified"])
        self.assertTrue(result["research_candidate"])
        self.assertEqual(result["setup"]["status"], "CONDITIONAL_RESEARCH_ONLY")
        self.assertEqual(result["entry"], 100.0)
        self.assertIn("MARKET_SESSION_CLOSED", result["blockers"])


if __name__ == "__main__":
    unittest.main()
