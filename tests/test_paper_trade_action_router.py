from __future__ import annotations

import unittest
from unittest.mock import patch

from workstation.paper_trade_action_router import (
    execute_paper_trade_request,
    is_paper_trade_action_request,
    resolve_trade_symbols,
)


class PaperTradeActionRouterTests(unittest.TestCase):
    def test_exact_user_trade_command_is_recognized(self):
        self.assertTrue(is_paper_trade_action_request("take trade in bitcoin"))
        self.assertEqual(resolve_trade_symbols("take trade in bitcoin"), ("BTC",))

    def test_split_bitcoin_typo_is_resolved(self):
        self.assertTrue(is_paper_trade_action_request("do paper trading in bitcoi n"))
        self.assertEqual(resolve_trade_symbols("do paper trading in bitcoi n"), ("BTC",))

    def test_plain_execute_is_deterministic_guard(self):
        result = execute_paper_trade_request("EXECUTE")
        self.assertEqual(result["action"], "paper_trade_context_required")
        self.assertFalse(result["live_execution"])

    @patch("workstation.paper_trade_action_router._already_open", return_value=None)
    @patch("workstation.paper_trade_action_router._arm_autonomy", return_value={"running": True})
    @patch("workstation.paper_trade_action_router._consensus_payload")
    def test_no_qualified_setup_arms_autonomy_without_forcing_trade(
        self, consensus, _autonomy, _already
    ):
        consensus.return_value = {
            "success": True,
            "symbol": "BTC",
            "qualified": False,
            "side": "WAIT",
            "blockers": ["TIMEFRAME_DIRECTION_CONFLICT"],
            "message": "WAIT because timeframes disagree.",
            "decisions": [{
                "success": True,
                "symbol": "BTC",
                "timeframe": "5m",
                "side": "WAIT",
                "score": 55.0,
                "risk_reward": None,
            }],
        }
        result = execute_paper_trade_request("take trade in bitcoin")
        self.assertEqual(result["action"], "paper_trade_armed")
        self.assertEqual(result["symbol"], "BTC")
        self.assertTrue(result["autonomy"]["running"])
        self.assertFalse(result["live_execution"])

    @patch("workstation.paper_trade_action_router._publish_event")
    @patch("workstation.paper_trade_action_router._arm_autonomy", return_value={"running": True})
    @patch(
        "workstation.paper_market_data.PAPER_MARKET_DATA.quote",
        return_value={"success": True, "native_ltp": 68000.0, "valuation_ltp": 6120000.0},
    )
    @patch(
        "workstation.paper_market_data.PAPER_MARKET_DATA.instrument_spec",
        return_value={
            "symbol": "BTC", "provider_symbol": "BTCUSDT", "asset_class": "CRYPTO",
            "instrument_type": "SPOT", "native_currency": "USDT", "valuation_currency": "INR",
            "quantity_step": 0.00001, "contract_multiplier": 1.0, "tick_size": 0.01,
            "source": "BINANCE_PUBLIC_EXCHANGE_INFO", "verified": True,
            "verification_reason": "BINANCE_EXCHANGE_INFO",
        },
    )
    @patch("workstation.paper_trade_action_router._live_entry", return_value=(68000.0, None))
    @patch("workstation.paper_trade_action_router._already_open", return_value=None)
    @patch("workstation.paper_trade_action_router._consensus_payload")
    @patch("workstation.paper_trading_desk.paper_desk.open_position")
    def test_qualified_setup_opens_only_paper_position(
        self,
        open_position,
        consensus,
        _already,
        _live_entry,
        _instrument_spec,
        _valuation,
        _autonomy,
        _event,
    ):
        consensus.return_value = {
                "success": True,
                "symbol": "BTC",
                "timeframe": "5m / 15m / 1h",
                "decision_version": "MTF_CONSENSUS_V1",
                "qualified": True,
                "side": "LONG",
                "score": 74.0,
                "entry": 67950.0,
                "stop": 67000.0,
                "target": 69900.0,
                "risk_reward": 2.05,
                "regime": "TRENDING",
                "votes": [],
                "alignment": 100,
                "decisions": [],
        }
        open_position.return_value = {
            "success": True,
            "reason": "PAPER_POSITION_OPENED",
            "side": "LONG",
            "entry": 68000.0,
            "stop": 67000.0,
            "target": 69900.0,
            "paper_only": True,
            "live_execution": False,
        }
        result = execute_paper_trade_request("take trade in bitcoin")
        self.assertEqual(result["action"], "paper_trade_opened")
        self.assertEqual(result["symbol"], "BTC")
        self.assertFalse(result["live_execution"])
        open_position.assert_called_once()

    @patch("workstation.paper_trade_action_router._already_open")
    def test_existing_position_blocks_duplicate(self, already):
        already.return_value = {"symbol": "BTC", "side": "LONG"}
        result = execute_paper_trade_request("paper trade bitcoin")
        self.assertEqual(result["action"], "paper_trade_existing_position")
        self.assertFalse(result["live_execution"])


if __name__ == "__main__":
    unittest.main()
