from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from workstation.paper_trading_desk import PaperTradingDesk, paper_dashboard_payload


class PaperInstrumentAccountingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.desk = PaperTradingDesk(Path(self.temp.name) / "paper.sqlite3", starting_equity=100000)

    def tearDown(self):
        self.temp.cleanup()

    @staticmethod
    def _spec(**overrides):
        value = {
            "symbol": "CRUDEOIL",
            "provider_symbol": "MCX:CRUDEOILM26SEPFUT",
            "asset_class": "COMMODITY",
            "instrument_type": "FUTURE",
            "native_currency": "INR",
            "valuation_currency": "INR",
            "quantity_step": 1.0,
            "contract_multiplier": 100.0,
            "tick_size": 0.1,
            "source": "FYERS_PUBLIC_SYMBOL_MASTER",
            "verified": True,
            "verification_reason": "FYERS_SYMBOL_MASTER",
            "cost_model_status": "UNCONFIGURED",
        }
        value.update(overrides)
        return value

    def test_verified_future_uses_contract_multiplier_and_tick_grid(self):
        opened = self.desk.open_position(
            symbol="CRUDEOIL",
            side="LONG",
            entry=100.04,
            stop=98.96,
            target=104.06,
            asset_type="COMMODITY",
            instrument_spec=self._spec(),
        )
        self.assertTrue(opened["success"])
        self.assertEqual(opened["entry"], 100.0)
        self.assertEqual(opened["stop"], 98.9)
        self.assertEqual(opened["target"], 104.0)
        self.assertEqual(opened["contract_multiplier"], 100.0)
        self.assertEqual(opened["quantity"], 9.0)
        snapshot = self.desk.snapshot(mark_loader=lambda _symbol: 101.0)
        self.assertAlmostEqual(snapshot["unrealized_pnl"], 900.0)
        self.assertAlmostEqual(snapshot["positions"][0]["notional"], 90_900.0)

    def test_unverified_derivative_fails_closed(self):
        result = self.desk.open_position(
            symbol="CRUDEOIL",
            side="LONG",
            entry=100,
            stop=99,
            target=102,
            asset_type="COMMODITY",
            instrument_spec=self._spec(verified=False, contract_multiplier=0, tick_size=0),
        )
        self.assertFalse(result["success"])
        self.assertEqual(result["reason"], "INSTRUMENT_SPEC_UNVERIFIED")
        self.assertEqual(self.desk.snapshot()["open_count"], 0)

    def test_crypto_quantity_is_fractional_and_step_quantized(self):
        spec = self._spec(
            symbol="BTC",
            provider_symbol="BTCUSDT",
            asset_class="CRYPTO",
            instrument_type="SPOT",
            native_currency="USDT",
            quantity_step=0.001,
            contract_multiplier=1.0,
            tick_size=0.01,
            source="BINANCE_PUBLIC_EXCHANGE_INFO",
            verification_reason="BINANCE_EXCHANGE_INFO",
        )
        result = self.desk.open_position(
            symbol="BTC",
            side="LONG",
            entry=100,
            stop=90,
            target=120,
            quantity=0.012345,
            asset_type="CRYPTO",
            valuation_multiplier=90,
            instrument_spec=spec,
        )
        self.assertTrue(result["success"])
        self.assertAlmostEqual(result["quantity"], 0.012)
        position = self.desk.snapshot(mark_loader=lambda _symbol: 101)["positions"][0]
        self.assertAlmostEqual(position["unrealized_pnl"], 1.08)
        self.assertEqual(position["native_currency"], "USDT")
        self.assertEqual(position["valuation_currency"], "INR")

    def test_costs_apply_only_when_explicitly_configured(self):
        spec = self._spec(
            asset_class="EQUITY", instrument_type="SPOT", contract_multiplier=1,
            quantity_step=1, tick_size=None, source="VERIFIED_CASH_SYMBOL",
        )
        opened = self.desk.open_position(
            symbol="RELIANCE",
            side="LONG",
            entry=100,
            stop=99,
            target=102,
            quantity=10,
            asset_type="EQUITY",
            instrument_spec=spec,
            execution_cost_config={"slippage_bps": 10, "fixed_per_order": 1},
        )
        self.assertTrue(opened["success"])
        self.assertEqual(opened["cost_model_status"], "CONFIGURED")
        self.assertAlmostEqual(opened["entry"], 100.1)
        closed = self.desk.close_position(position_id=opened["position_id"], exit_price=101, reason="TEST")
        self.assertAlmostEqual(closed["exit_price"], 100.899)
        self.assertAlmostEqual(closed["gross_pnl"], 7.99)
        self.assertAlmostEqual(closed["realized_pnl"], 5.99)

    def test_default_cost_model_is_explicitly_unconfigured(self):
        opened = self.desk.open_position(
            symbol="NIFTY", side="LONG", entry=100, stop=99, target=102, quantity=1
        )
        self.assertTrue(opened["success"])
        self.assertEqual(opened["cost_model_status"], "UNCONFIGURED")
        self.assertEqual(opened["entry_fees"], 0.0)

    @patch("workstation.paper_trading_desk.urllib.request.urlopen")
    def test_master_paper_dashboard_uses_quant_owned_autonomy_state(self, urlopen):
        class Response:
            def __enter__(self): return self
            def __exit__(self, *_args): return False
            def read(self, _limit):
                return b'{"running":true,"paper_only":true,"live_execution":false,"scan_cycles":7}'

        urlopen.return_value = Response()
        with patch("workstation.paper_trading_desk.paper_desk", self.desk):
            payload = paper_dashboard_payload()
        self.assertTrue(payload["autonomy"]["running"])
        self.assertEqual(payload["autonomy"]["telemetry_source"], "QUANT_SERVICE_8787")
        self.assertFalse(payload["live_execution"])


if __name__ == "__main__":
    unittest.main()
