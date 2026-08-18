import tempfile
import unittest
from pathlib import Path

from workstation.paper_runtime import PaperTradingRuntime


class FakeMarketRuntime:
    def __init__(self, connected=True):
        self.connected = connected
        self.prices = {"NIFTY": 24_500.0, "BANKNIFTY": 56_500.0, "SENSEX": 80_000.0}

    def status(self):
        return {"connected": self.connected, "provider": "FYERS", "running": True}

    def snapshot(self, symbol):
        price = self.prices.get(symbol)
        return {"symbol": symbol, "ltp": price} if price else None


class FakeOptionMarketData:
    symbols = ("NIFTY", "BANKNIFTY", "SENSEX")

    def __init__(self, session_open=True):
        self.is_session_open = session_open

    def quote(self, symbol):
        if symbol == "MCX:CRUDEOIL26SEP7900CE":
            return {
                "success": True,
                "symbol": symbol,
                "provider_symbol": symbol,
                "ltp": 560.0,
                "native_ltp": 560.0,
                "valuation_ltp": 560.0,
                "asset_class": "OPTION",
                "description": "CRUDEOIL 17 Sep 26 7900 CE",
                "currency": "INR",
                "provider": "FYERS",
                "session_open": self.is_session_open,
            }
        return {"success": False, "symbol": symbol}

    def status(self):
        return {"providers": {"FYERS": {"ready": True, "error": None}}}

    def public_universe(self):
        return []

    def session_open(self, _symbol):
        return self.is_session_open


def long_signal(symbol):
    prices = {"NIFTY": 24_500.0, "BANKNIFTY": 56_500.0, "SENSEX": 80_000.0}
    price = prices[symbol]
    return {
        "success": True,
        "symbol": symbol,
        "setup": "PAPER_WATCH_LONG",
        "confidence": 88,
        "regime": "TRENDING_UP",
        "strategy": "TREND_FOLLOWING",
        "strategy_score": 84,
        "chart_patterns": ["HIGHER_HIGHS"],
        "risk_reward": 2.2,
        "entry": price,
        "stop_loss": price - 100,
        "take_profit": price + 220,
        "atr14": 66.67,
        "decision_gate": "QUALIFIED",
        "timestamp": "2026-08-17T09:30:00+00:00",
    }


class PaperTradingRuntimeTests(unittest.TestCase):
    def runtime(self, directory, **kwargs):
        return PaperTradingRuntime(
            state_file=Path(directory) / "paper.json",
            market_runtime=kwargs.pop("market_runtime", FakeMarketRuntime()),
            analyzer=kwargs.pop("analyzer", long_signal),
            starting_capital=100_000.0,
            **kwargs,
        )

    def test_manual_fill_is_local_paper_only(self):
        with tempfile.TemporaryDirectory() as directory:
            runtime = self.runtime(directory)
            result = runtime.place_order("NIFTY", "BUY", 2)
            self.assertTrue(result["ok"])
            self.assertTrue(result["paper_only"])
            self.assertFalse(result["state"]["live_orders"])
            self.assertEqual(result["state"]["positions"][0]["side"], "LONG")
            self.assertEqual(result["state"]["positions"][0]["quantity"], 2)

    def test_guarded_manual_fill_attaches_protection_and_learning_context(self):
        with tempfile.TemporaryDirectory() as directory:
            runtime = self.runtime(directory)
            result = runtime.place_guarded_order("NIFTY", "BUY", 2)
            position = result["state"]["positions"][0]
            self.assertLess(position["stop_loss"], position["average_price"])
            self.assertGreater(position["take_profit"], position["average_price"])
            context = result["state"]["learning"]["entry_context"]["NIFTY"]
            self.assertEqual(context["strategy"], "MANUAL_GUARDED")
            self.assertEqual(context["risk_reward"], 2.2)
            self.assertFalse(result["state"]["live_orders"])

    def test_exact_long_option_fill_is_synthetic_protected_and_marked(self):
        contract = {
            "provider_symbol": "MCX:CRUDEOIL26SEP7900CE",
            "description": "CRUDEOIL 17 Sep 26 7900 CE",
            "underlying": "CRUDEOIL",
            "strike": 7900.0,
            "option_type": "CE",
            "expiry": "2026-09-17T18:00:00+00:00",
            "tick_size": 0.1,
        }
        with tempfile.TemporaryDirectory() as directory:
            runtime = self.runtime(directory, market_data=FakeOptionMarketData())
            result = runtime.place_option_order(contract, "BUY", 1)
            position = result["state"]["positions"][0]
            self.assertEqual(position["symbol"], "MCX:CRUDEOIL26SEP7900CE")
            self.assertEqual(position["asset_class"], "OPTION")
            self.assertEqual(position["average_price"], 560.112)
            self.assertEqual(position["stop_loss"], 280.0)
            self.assertEqual(position["take_profit"], 1120.0)
            self.assertEqual(result["result"]["stop_loss"], 280.0)
            self.assertEqual(result["result"]["take_profit"], 1120.0)
            self.assertFalse(result["state"]["live_orders"])

    def test_naked_option_sell_is_rejected(self):
        contract = {"provider_symbol": "MCX:CRUDEOIL26SEP7900CE"}
        with tempfile.TemporaryDirectory() as directory:
            runtime = self.runtime(directory, market_data=FakeOptionMarketData())
            with self.assertRaisesRegex(ValueError, "Naked option selling is disabled"):
                runtime.place_option_order(contract, "SELL", 1)

    def test_closed_market_rejects_new_option_entry_even_when_fyers_returns_ltp(self):
        contract = {
            "provider_symbol": "MCX:CRUDEOIL26SEP7900CE",
            "underlying": "CRUDEOIL",
            "strike": 7900.0,
            "option_type": "CE",
        }
        with tempfile.TemporaryDirectory() as directory:
            runtime = self.runtime(
                directory,
                market_data=FakeOptionMarketData(session_open=False),
            )
            with self.assertRaisesRegex(RuntimeError, "market session is closed"):
                runtime.place_option_order(contract, "BUY", 1)
            self.assertEqual(runtime.public_state()["positions"], [])

    def test_closed_market_still_allows_existing_option_position_to_be_removed(self):
        contract = {
            "provider_symbol": "MCX:CRUDEOIL26SEP7900CE",
            "underlying": "CRUDEOIL",
            "strike": 7900.0,
            "option_type": "CE",
        }
        market_data = FakeOptionMarketData(session_open=True)
        with tempfile.TemporaryDirectory() as directory:
            runtime = self.runtime(directory, market_data=market_data)
            runtime.place_option_order(contract, "BUY", 1)
            market_data.is_session_open = False
            result = runtime.place_option_order(contract, "SELL", 1)
            self.assertEqual(result["state"]["positions"], [])
            self.assertFalse(result["state"]["live_orders"])

    def test_closed_market_rejects_regular_guarded_entry(self):
        with tempfile.TemporaryDirectory() as directory:
            runtime = self.runtime(
                directory,
                market_data=FakeOptionMarketData(session_open=False),
            )
            with self.assertRaisesRegex(RuntimeError, "market session is closed"):
                runtime.place_guarded_order("NIFTY", "BUY", 1)
            self.assertEqual(runtime.public_state()["positions"], [])

    def test_scan_backfills_legacy_position_learning_context(self):
        with tempfile.TemporaryDirectory() as directory:
            runtime = self.runtime(directory)
            runtime.place_guarded_order("NIFTY", "BUY", 2)
            runtime.learning.entry_context.clear()
            state = runtime.scan_once()
            context = state["learning"]["entry_context"]["NIFTY"]
            self.assertEqual(context["strategy"], "UNCLASSIFIED")
            self.assertEqual(context["regime"], "LEGACY_POSITION")

    def test_fill_requires_validated_market_data_mark(self):
        with tempfile.TemporaryDirectory() as directory:
            market = FakeMarketRuntime(connected=False)
            market.prices = {}
            runtime = self.runtime(directory, market_runtime=market)
            with self.assertRaisesRegex(RuntimeError, "No validated market-data price"):
                runtime.place_order("NIFTY", "BUY", 1)
            self.assertEqual(runtime.public_state()["positions"], [])

    def test_scan_does_not_trade_until_autopilot_is_explicitly_armed(self):
        with tempfile.TemporaryDirectory() as directory:
            runtime = self.runtime(directory)
            state = runtime.scan_once()
            self.assertFalse(state["autopilot"])
            self.assertEqual(state["positions"], [])
            self.assertEqual(len(state["signals"]), 3)

            runtime.set_autopilot(True)
            state = runtime.scan_once()
            self.assertTrue(state["autopilot"])
            self.assertEqual({item["symbol"] for item in state["positions"]}, {"NIFTY", "BANKNIFTY", "SENSEX"})
            self.assertFalse(state["live_orders"])

    def test_paper_account_is_durable(self):
        with tempfile.TemporaryDirectory() as directory:
            runtime = self.runtime(directory)
            runtime.place_order("NIFTY", "SELL", 1)
            runtime.set_autopilot(True)
            runtime.stop()

            restored = self.runtime(directory)
            state = restored.public_state()
            self.assertTrue(state["autopilot"])
            self.assertEqual(len(state["positions"]), 1)
            self.assertEqual(state["positions"][0]["side"], "SHORT")
            self.assertEqual(len(state["orders"]), 1)

    def test_start_arms_autopilot_automatically(self):
        with tempfile.TemporaryDirectory() as directory:
            runtime = self.runtime(directory)
            state = runtime.start()
            try:
                self.assertTrue(state["autopilot"])
                self.assertTrue(state["auto_arm_on_start"])
                self.assertFalse(state["live_orders"])
            finally:
                runtime.stop()


if __name__ == "__main__":
    unittest.main()
