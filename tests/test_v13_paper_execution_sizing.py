from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from workstation.paper_execution_sizing_v13 import (
    install_v13_execution_sizing_bridge,
    plan_auto_quantity,
    status as sizing_status,
)
from workstation.paper_trading_desk import PaperTradingDesk


CRYPTO_SPEC = {
    "symbol": "BTC",
    "provider_symbol": "BTCUSDT",
    "asset_class": "CRYPTO",
    "instrument_type": "SPOT",
    "native_currency": "USDT",
    "valuation_currency": "INR",
    "quantity_step": 0.00001,
    "contract_multiplier": 1.0,
    "tick_size": 0.01,
    "source": "TEST_VERIFIED_BINANCE_SPEC",
    "verified": True,
    "verification_reason": "TEST",
    "cost_model_status": "UNCONFIGURED",
}


class V13PaperExecutionSizingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.desk = PaperTradingDesk(
            Path(self.temp.name) / "paper.sqlite3",
            starting_equity=100000.0,
            max_open_positions=8,
            max_total_risk_fraction=0.04,
            max_single_risk_fraction=0.01,
            max_gross_exposure_multiple=2.0,
        )

    def tearDown(self) -> None:
        self.temp.cleanup()

    @staticmethod
    def request(**overrides):
        payload = {
            "symbol": "BTC",
            "side": "LONG",
            "entry": 80000.0,
            "stop": 79500.0,
            "target": 81500.0,
            "quantity": None,
            "timeframe": "15m",
            "strategy": "V13_CONTEXTUAL_TEST",
            "score": 55.0,
            "source": "V13_TEST",
            "asset_type": "CRYPTO",
            "risk_multiplier": 0.20,
            "valuation_multiplier": 83.0,
            "instrument_spec": dict(CRYPTO_SPEC),
            "portfolio_bucket": "INTRADAY",
            "bucket_allocation_fraction": 0.50,
        }
        payload.update(overrides)
        return payload

    def test_fractional_crypto_auto_size_is_not_floored_to_zero(self) -> None:
        plan = plan_auto_quantity(self.desk, self.request())
        self.assertTrue(plan["success"])
        self.assertGreater(plan["quantity"], 0.0)
        self.assertLess(plan["quantity"], 1.0)
        self.assertEqual(plan["quantity_step"], 0.00001)
        self.assertTrue(plan["fractional_quantity_supported"])
        self.assertLessEqual(plan["planned_trade_risk"], plan["risk_budget"] + 1e-6)

    def test_tight_stop_is_downsized_to_bucket_exposure_instead_of_rejected(self) -> None:
        plan = plan_auto_quantity(
            self.desk,
            self.request(stop=79950.0, target=80150.0, risk_multiplier=1.0),
        )
        self.assertTrue(plan["success"])
        self.assertEqual(plan["limiting_constraint"], "BUCKET_EXPOSURE_LIMIT")
        self.assertGreater(plan["quantity"], 0.0)
        self.assertLessEqual(plan["planned_notional"], 100000.0 + 1.0)

    def test_probe_multiplier_is_not_increased_by_the_planner(self) -> None:
        plan = plan_auto_quantity(self.desk, self.request(risk_multiplier=0.04))
        self.assertTrue(plan["success"])
        self.assertAlmostEqual(plan["requested_risk_multiplier"], 0.04)
        self.assertLessEqual(plan["planned_trade_risk"], 40.0 + 1e-6)

    def test_runtime_bridge_opens_fractional_btc_paper_position(self) -> None:
        install_v13_execution_sizing_bridge()
        result = self.desk.open_position(**self.request())
        self.assertTrue(result["success"], result)
        self.assertEqual(result["reason"], "PAPER_POSITION_OPENED")
        self.assertGreater(float(result["quantity"]), 0.0)
        self.assertLess(float(result["quantity"]), 1.0)
        self.assertTrue(result["constraint_aware_auto_sizing"])
        self.assertTrue(result["fractional_auto_sizing"])
        self.assertFalse(result["live_execution"])

    def test_explicit_quantity_is_preserved(self) -> None:
        install_v13_execution_sizing_bridge()
        result = self.desk.open_position(**self.request(quantity=0.001, external_id="explicit-btc"))
        self.assertTrue(result["success"], result)
        self.assertAlmostEqual(float(result["quantity"]), 0.001, places=8)
        self.assertNotIn("sizing", result)

    def test_sizing_contract_never_relaxes_risk_or_enables_live_execution(self) -> None:
        install_v13_execution_sizing_bridge()
        status = sizing_status()
        self.assertTrue(status["installed"])
        self.assertTrue(status["fractional_crypto_auto_sizing"])
        self.assertTrue(status["constraint_aware_auto_sizing"])
        self.assertFalse(status["risk_limits_relaxed"])
        self.assertFalse(status["live_execution"])
        self.assertFalse(status["automatic_broker_order"])


if __name__ == "__main__":
    unittest.main()
