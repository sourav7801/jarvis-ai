from __future__ import annotations

from datetime import datetime
from pathlib import Path
import tempfile
import unittest

from omni.trading_intelligence.option_chain_schema import OptionChainSnapshot, OptionContractQuote
from omni.trading_intelligence.options_execution_intelligence_v151 import OPTIONS_EXECUTION_INTELLIGENCE_V151
from workstation.options_paper_execution_v151 import OPTIONS_PAPER_EXECUTION_V151
from workstation.paper_execution_sizing_v13 import install_v13_execution_sizing_bridge
from workstation.paper_trading_desk import PaperTradingDesk


NOW = datetime(2026, 9, 9, 10, 30)


def _decision(side="LONG", ev=0.35, utility=0.20, confidence=0.85, risk=0.90):
    return {
        "executable": True,
        "side": side,
        "expected_value_r": ev,
        "portfolio_adjusted_utility": utility,
        "confidence": confidence,
        "uncertainty": 1.0 - confidence,
        "risk_multiplier": risk,
        "hard_blockers": [],
        "paper_only": True,
        "live_execution": False,
    }


def _quote(symbol, strike, option_type, *, bid=98.0, ask=100.0, delta=None, theta=None, iv=None, expiry="2026-09-17"):
    return OptionContractQuote(
        underlying="NIFTY",
        expiry=expiry,
        strike=float(strike),
        option_type=option_type,
        ltp=(float(bid) + float(ask)) / 2.0,
        symbol=symbol,
        bid=float(bid),
        ask=float(ask),
        volume=2500.0,
        open_interest=12000.0,
        change_in_oi=850.0,
        implied_volatility=iv,
        delta=delta,
        gamma=None,
        theta=theta,
        vega=None,
    )


def _snapshot(*contracts):
    return OptionChainSnapshot(
        underlying="NIFTY",
        spot=25000.0,
        timestamp="2026-09-09T10:30:00+05:30",
        contracts=tuple(contracts),
    )


def _spec(symbol, *, lot=25.0, tick=0.05):
    return {
        "symbol": symbol,
        "provider_symbol": symbol,
        "asset_class": "OPTION",
        "instrument_type": "OPTION",
        "native_currency": "INR",
        "valuation_currency": "INR",
        "lot_size": lot,
        "contract_multiplier": lot,
        "quantity_step": 1.0,
        "tick_size": tick,
        "source": "TEST_VERIFIED_INSTRUMENT_MASTER",
        "verified": True,
        "verification_reason": "DETERMINISTIC_TEST_FIXTURE",
        "cost_model_status": "UNCONFIGURED",
    }


class V151OptionsDecisionTests(unittest.TestCase):
    def test_bullish_underlying_selects_good_call_not_put(self):
        call = _quote("NIFTY17SEP25000CE", 25000, "call", delta=0.52, theta=-6.0, iv=0.16)
        put = _quote("NIFTY17SEP25000PE", 25000, "put", delta=-0.48, theta=-6.0, iv=0.17)
        specs = {call.symbol: _spec(call.symbol), put.symbol: _spec(put.symbol)}
        result = OPTIONS_EXECUTION_INTELLIGENCE_V151.evaluate(
            _snapshot(call, put), _decision("LONG"), verified_snapshot=True, verified_specs=specs, now=NOW
        )
        self.assertTrue(result["executable"], result)
        self.assertEqual(result["action"], "PAPER_BUY_CALL")
        self.assertEqual(result["selected_contract"], call.symbol)
        self.assertEqual(result["selected"]["option_type"], "call")
        self.assertTrue(result["long_premium_only"])
        self.assertFalse(result["live_execution"])

    def test_bearish_underlying_selects_put(self):
        call = _quote("NIFTY17SEP25000CE", 25000, "call", delta=0.52)
        put = _quote("NIFTY17SEP25000PE", 25000, "put", delta=-0.48)
        specs = {call.symbol: _spec(call.symbol), put.symbol: _spec(put.symbol)}
        result = OPTIONS_EXECUTION_INTELLIGENCE_V151.evaluate(
            _snapshot(call, put), _decision("SHORT"), verified_snapshot=True, verified_specs=specs, now=NOW
        )
        self.assertTrue(result["executable"], result)
        self.assertEqual(result["action"], "PAPER_BUY_PUT")
        self.assertEqual(result["selected_contract"], put.symbol)

    def test_bullish_underlying_does_not_force_bad_call_trade(self):
        bad = _quote("NIFTY17SEP25000CE", 25000, "call", bid=70.0, ask=110.0, delta=0.50)
        result = OPTIONS_EXECUTION_INTELLIGENCE_V151.evaluate(
            _snapshot(bad), _decision("LONG"), verified_snapshot=True,
            verified_specs={bad.symbol: _spec(bad.symbol)}, now=NOW
        )
        self.assertFalse(result["executable"])
        self.assertEqual(result["action"], "NO_OPTION_TRADE")
        self.assertEqual(result["reason"], "OPTION_SPREAD_TOO_WIDE")

    def test_unverified_chain_and_unverified_spec_fail_closed(self):
        call = _quote("NIFTY17SEP25000CE", 25000, "call")
        no_chain = OPTIONS_EXECUTION_INTELLIGENCE_V151.evaluate(
            _snapshot(call), _decision("LONG"), verified_snapshot=False,
            verified_specs={call.symbol: _spec(call.symbol)}, now=NOW
        )
        self.assertEqual(no_chain["reason"], "OPTION_CHAIN_NOT_VERIFIED")
        no_spec = OPTIONS_EXECUTION_INTELLIGENCE_V151.evaluate(
            _snapshot(call), _decision("LONG"), verified_snapshot=True, verified_specs={}, now=NOW
        )
        self.assertFalse(no_spec["executable"])
        self.assertEqual(no_spec["reason"], "OPTION_INSTRUMENT_SPEC_UNVERIFIED")

    def test_missing_greeks_are_unavailable_not_fabricated(self):
        call = _quote("NIFTY17SEP25000CE", 25000, "call", delta=None, theta=None, iv=None)
        result = OPTIONS_EXECUTION_INTELLIGENCE_V151.evaluate(
            _snapshot(call), _decision("LONG"), verified_snapshot=True,
            verified_specs={call.symbol: _spec(call.symbol)}, now=NOW
        )
        self.assertTrue(result["executable"], result)
        selected = result["selected"]
        self.assertIsNone(selected["quote"]["delta"])
        self.assertIsNone(selected["quote"]["theta"])
        self.assertIsNone(selected["quote"]["implied_volatility"])
        self.assertFalse(selected["greeks_fabricated"])
        self.assertFalse(selected["iv_fabricated"])

    def test_expiry_day_long_premium_is_disabled(self):
        call = _quote("NIFTY09SEP25000CE", 25000, "call", expiry="2026-09-09")
        result = OPTIONS_EXECUTION_INTELLIGENCE_V151.evaluate(
            _snapshot(call), _decision("LONG"), verified_snapshot=True,
            verified_specs={call.symbol: _spec(call.symbol)}, now=NOW
        )
        self.assertFalse(result["executable"])
        self.assertEqual(result["reason"], "ZERO_DTE_LONG_PREMIUM_DISABLED")

    def test_premium_geometry_is_valid_and_explicitly_modelled(self):
        call = _quote("NIFTY17SEP25000CE", 25000, "call", delta=0.50)
        result = OPTIONS_EXECUTION_INTELLIGENCE_V151.evaluate(
            _snapshot(call), _decision("LONG"), verified_snapshot=True,
            verified_specs={call.symbol: _spec(call.symbol)}, now=NOW
        )
        plan = result["selected"]["risk_plan"]
        self.assertLess(plan["stop"], plan["entry"])
        self.assertLess(plan["entry"], plan["target"])
        self.assertTrue(plan["premium_levels_are_risk_plan_estimates"])
        self.assertFalse(plan["premium_levels_are_market_quotes"])
        self.assertTrue(plan["future_option_premium_not_claimed"])


class V151OptionsPaperDeskTests(unittest.TestCase):
    def test_verified_option_plan_opens_one_or_more_paper_lots(self):
        call = _quote("NIFTY17SEP25000CE", 25000, "call", bid=98.0, ask=100.0, delta=0.52)
        result = OPTIONS_EXECUTION_INTELLIGENCE_V151.evaluate(
            _snapshot(call), _decision("LONG", ev=0.50, utility=0.35, confidence=0.90, risk=1.0),
            verified_snapshot=True, verified_specs={call.symbol: _spec(call.symbol, lot=25.0)}, now=NOW
        )
        self.assertTrue(result["executable"], result)
        install_v13_execution_sizing_bridge()
        with tempfile.TemporaryDirectory() as directory:
            desk = PaperTradingDesk(
                Path(directory) / "options-paper.sqlite3",
                starting_equity=100000.0,
                max_open_positions=8,
                max_total_risk_fraction=0.05,
                max_single_risk_fraction=0.01,
                max_gross_exposure_multiple=2.0,
            )
            opened = OPTIONS_PAPER_EXECUTION_V151.open_plan(result, desk=desk)
        self.assertTrue(opened["success"], opened)
        self.assertEqual(opened["reason"], "PAPER_POSITION_OPENED")
        self.assertGreaterEqual(float(opened["quantity"]), 1.0)
        self.assertEqual(opened["option_contract"], call.symbol)
        self.assertTrue(opened["long_premium_only"])
        self.assertFalse(opened["live_execution"])


if __name__ == "__main__":
    unittest.main()
