from __future__ import annotations

from unittest import TestCase
from unittest.mock import patch

from workstation import v16_option_paper


SYMBOL = "NSE:NIFTY2691522400PE"


class FakeDesk:
    def __init__(self):
        self.open_calls = []
        self.close_calls = []

    def open_position(self, **kwargs):
        self.open_calls.append(kwargs)
        return {
            "success": True,
            "reason": "PAPER_POSITION_OPENED",
            "position_id": 17,
            "entry": kwargs["entry"],
            "quantity": kwargs["quantity"],
            "paper_only": True,
            "live_execution": False,
        }

    def close_position(self, **kwargs):
        self.close_calls.append(kwargs)
        return {
            "success": True,
            "reason": "PAPER_POSITION_CLOSED",
            "position_id": kwargs["position_id"],
            "exit_price": kwargs["exit_price"],
            "paper_only": True,
            "live_execution": False,
        }


class FakeRuntime:
    def __init__(self, *, certificate=None, reconciliation=True, positions=None):
        self.desk = FakeDesk()
        self._certificate = certificate or {
            "success": True,
            "symbol": SYMBOL,
            "mark": 100.0,
            "bid": 99.5,
            "ask": 100.5,
            "verified": True,
            "eligible_for_entry": True,
            "eligible_for_exit": True,
            "reason": None,
        }
        self._reconciliation = reconciliation
        self._positions = positions or []

    def mark_loader(self, _symbol):
        return dict(self._certificate)

    def reconcile(self, **_kwargs):
        return {"success": self._reconciliation, "issues": [] if self._reconciliation else ["TEST_LEDGER_ISSUE"]}

    def snapshot(self, _workspace):
        return {"account": {"positions": list(self._positions)}}


class V16OptionPaperTests(TestCase):
    def test_naked_short_is_rejected_before_any_execution_path(self):
        runtime = FakeRuntime()
        result = v16_option_paper.option_order(
            runtime,
            {"action": "SELL", "workspace": "INTRADAY", "symbol": SYMBOL, "option_type": "PE"},
        )
        self.assertFalse(result["success"])
        self.assertEqual(result["reason"], "NAKED_SHORT_OPTION_BLOCKED")
        self.assertFalse(runtime.desk.open_calls)
        self.assertIs(result["live_execution"], False)

    def test_market_closed_or_stale_entry_never_creates_paper_fill(self):
        runtime = FakeRuntime(certificate={
            "success": True,
            "symbol": SYMBOL,
            "mark": 100.0,
            "bid": 99.5,
            "ask": 100.5,
            "eligible_for_entry": False,
            "eligible_for_exit": False,
            "reason": "MARKET_SESSION_CLOSED",
        })
        with patch.object(v16_option_paper.accounts, "session", return_value={"state": "RUNNING", "generation": 3, "allocation": .5}):
            result = v16_option_paper.option_order(
                runtime,
                {"action": "BUY", "workspace": "INTRADAY", "symbol": SYMBOL, "option_type": "PE", "stop": 90, "target": 120},
            )
        self.assertFalse(result["success"])
        self.assertEqual(result["reason"], "MARKET_SESSION_CLOSED")
        self.assertFalse(runtime.desk.open_calls)

    def test_long_option_buy_delegates_to_existing_canonical_paper_desk(self):
        runtime = FakeRuntime()
        spec = {
            "symbol": SYMBOL,
            "provider_symbol": SYMBOL,
            "asset_class": "OPTION",
            "instrument_type": "OPTION",
            "native_currency": "INR",
            "valuation_currency": "INR",
            "quantity_step": 1.0,
            "contract_multiplier": 75.0,
            "tick_size": .05,
            "source": "FYERS_NSE_FO_SYMBOL_MASTER",
            "verified": True,
            "verification_reason": "FYERS_DAILY_SYMBOL_MASTER_EXACT_MATCH",
        }
        with (
            patch.object(v16_option_paper.accounts, "session", return_value={"state": "RUNNING", "generation": 8, "allocation": .5}),
            patch.object(v16_option_paper, "option_instrument_spec", return_value=spec),
        ):
            result = v16_option_paper.option_order(
                runtime,
                {
                    "action": "BUY",
                    "workspace": "INTRADAY",
                    "symbol": SYMBOL,
                    "option_type": "PE",
                    "underlying": "NIFTY",
                    "strike": 22400,
                    "expiry": "2026-09-15",
                    "lots": 1,
                    "stop": 90,
                    "target": 120,
                    "timeframe": "5m",
                    "client_order_id": "test-v16-option-order",
                },
            )
        self.assertTrue(result["success"])
        self.assertEqual(result["action"], "BUY_LONG_PUT")
        self.assertEqual(len(runtime.desk.open_calls), 1)
        call = runtime.desk.open_calls[0]
        self.assertEqual(call["side"], "LONG")
        self.assertEqual(call["asset_type"], "OPTION")
        self.assertEqual(call["portfolio_bucket"], "INTRADAY")
        self.assertEqual(call["instrument_spec"], spec)
        self.assertEqual(call["metadata"]["session_generation"], 8)
        self.assertIs(call["metadata"]["live_execution"], False)

    def test_close_long_option_is_allowed_as_risk_reduction_without_starting_scanner(self):
        runtime = FakeRuntime(
            reconciliation=False,
            positions=[{"id": 11, "symbol": SYMBOL, "side": "LONG", "quantity": 1}],
        )
        result = v16_option_paper.option_order(
            runtime,
            {"action": "CLOSE", "workspace": "INTRADAY", "symbol": SYMBOL, "option_type": "PE", "position_id": 11},
        )
        self.assertTrue(result["success"])
        self.assertEqual(result["action"], "CLOSE_LONG_OPTION")
        self.assertEqual(runtime.desk.close_calls[0]["position_id"], 11)
        self.assertEqual(runtime.desk.close_calls[0]["exit_price"], 99.5)


if __name__ == "__main__":
    import unittest
    unittest.main()
