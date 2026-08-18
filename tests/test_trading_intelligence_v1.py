import unittest

from datetime import (
    datetime,
    timedelta,
    timezone,
)


import main


from omni.core_integrity import (
    verify_protected_core,
)

from omni.trading_intelligence.feature_engine import (
    FeatureEngine,
)

from omni.trading_intelligence.fyers_market_adapter import (
    FyersReadOnlyAdapter,
)

from omni.trading_intelligence.instrument_master import (
    InstrumentMaster,
)

from omni.trading_intelligence.market_schema import (
    AssetClass,
    Bar,
    Instrument,
    InstrumentType,
    OptionType,
)

from omni.trading_intelligence.options_features import (
    black_scholes_greeks,
    intrinsic_value,
    moneyness,
    option_feature_snapshot,
)

from omni.trading_intelligence.regime_engine import (
    MarketRegimeEngine,
)

from omni.trading_intelligence.signal_engine import (
    SignalEngine,
)

from omni.trading_intelligence.strategy_registry import (
    strategy_registry,
)

from omni.trading_intelligence.strategy_schema import (
    Condition,
)

from omni.trading_intelligence.trading_dataset import (
    TradingDataset,
)

from omni.trading_intelligence.trading_guardrails import (
    trading_research_guard,
)

from omni.trading_intelligence.trading_metrics import (
    evaluate_trades,
)


def sample_bars(
    count=60,
):

    base = datetime(
        2026,
        8,
        1,
        9,
        15,
        tzinfo=timezone.utc,
    )


    bars = []


    for index in range(
        count
    ):

        price = (
            100.0
            + index
            * 0.5
        )


        bars.append(
            Bar(
                timestamp=
                    base
                    + timedelta(
                        minutes=index,
                    ),

                open=
                    price,

                high=
                    price
                    + 1.0,

                low=
                    price
                    - 1.0,

                close=
                    price
                    + 0.25,

                volume=
                    1000.0
                    + index
                    * 20.0,

                open_interest=
                    5000.0
                    + index
                    * 10.0,
            )
        )


    return bars


class FakeFyers:

    def quotes(
        self,
        payload,
    ):

        return {
            "success":
                True,

            "payload":
                payload,
        }


    def history(
        self,
        payload,
    ):

        return {
            "history":
                payload,
        }


    def option_chain(
        self,
        payload,
    ):

        return {
            "option_chain":
                payload,
        }


    def place_order(
        self,
        payload,
    ):

        raise AssertionError(
            "Must never execute."
        )


class TradingIntelligenceV1Tests(
    unittest.TestCase
):

    def test_core(
        self,
    ):

        self.assertTrue(
            verify_protected_core()
            .ok
        )


    def test_equity_instrument(
        self,
    ):

        instrument = Instrument(
            symbol=
                "RELIANCE",

            exchange=
                "NSE",

            asset_class=
                AssetClass.EQUITY,

            instrument_type=
                InstrumentType.STOCK,
        )


        self.assertEqual(
            instrument.symbol,
            "RELIANCE",
        )


    def test_option_requires_strike(
        self,
    ):

        with self.assertRaises(
            ValueError
        ):

            Instrument(
                symbol=
                    "NIFTY",

                exchange=
                    "NSE",

                asset_class=
                    AssetClass.INDEX,

                instrument_type=
                    InstrumentType.OPTION,

                expiry=
                    "2026-08-27",

                option_type=
                    OptionType.CALL,
            )


    def test_option_instrument(
        self,
    ):

        instrument = Instrument(
            symbol=
                "NIFTY",

            exchange=
                "NSE",

            asset_class=
                AssetClass.INDEX,

            instrument_type=
                InstrumentType.OPTION,

            underlying=
                "NIFTY",

            expiry=
                "2026-08-27",

            strike=
                25000,

            option_type=
                OptionType.CALL,

            lot_size=
                75,

            tick_size=
                0.05,
        )


        self.assertEqual(
            instrument.option_type,
            OptionType.CALL,
        )


    def test_instrument_master(
        self,
    ):

        master = InstrumentMaster()


        master.register(
            {
                "symbol":
                    "NIFTY",

                "exchange":
                    "NSE",

                "asset_class":
                    "index",

                "instrument_type":
                    "option",

                "underlying":
                    "NIFTY",

                "expiry":
                    "2026-08-27",

                "strike":
                    25000,

                "option_type":
                    "CE",
            }
        )


        self.assertEqual(
            len(
                master.search(
                    "NIFTY"
                )
            ),
            1,
        )


    def test_dataset_sorting(
        self,
    ):

        bars = sample_bars(
            3
        )


        dataset = TradingDataset(
            reversed(
                bars
            )
        )


        self.assertEqual(
            dataset.bars[
                0
            ].timestamp,
            bars[
                0
            ].timestamp,
        )


    def test_feature_snapshot(
        self,
    ):

        result = FeatureEngine.snapshot(
            sample_bars()
        )


        self.assertIsNotNone(
            result[
                "ema9"
            ]
        )


        self.assertIsNotNone(
            result[
                "ema21"
            ]
        )


        self.assertIsNotNone(
            result[
                "rsi14"
            ]
        )


        self.assertIsNotNone(
            result[
                "atr14"
            ]
        )


        self.assertIsNotNone(
            result[
                "vwap"
            ]
        )


    def test_intrinsic_call(
        self,
    ):

        self.assertEqual(
            intrinsic_value(
                110,
                100,
                "call",
            ),
            10,
        )


    def test_moneyness_call(
        self,
    ):

        self.assertEqual(
            moneyness(
                110,
                100,
                "CE",
            ),
            "ITM",
        )


    def test_black_scholes_call_delta(
        self,
    ):

        result = black_scholes_greeks(
            100,
            100,
            30 / 365,
            0.05,
            0.20,
            "call",
        )


        self.assertGreater(
            result[
                "delta"
            ],
            0.0,
        )


        self.assertLess(
            result[
                "delta"
            ],
            1.0,
        )


        self.assertGreater(
            result[
                "gamma"
            ],
            0.0,
        )


    def test_black_scholes_put_delta(
        self,
    ):

        result = black_scholes_greeks(
            100,
            100,
            30 / 365,
            0.05,
            0.20,
            "put",
        )


        self.assertLess(
            result[
                "delta"
            ],
            0.0,
        )


    def test_option_feature_snapshot(
        self,
    ):

        result = option_feature_snapshot(
            spot=
                25000,

            strike=
                25000,

            option_type=
                "CE",

            premium=
                200,

            bid=
                199,

            ask=
                201,

            open_interest=
                100000,

            change_in_oi=
                5000,

            volume=
                20000,

            implied_volatility=
                15.0,

            time_to_expiry_years=
                5 / 365,

            risk_free_rate=
                0.06,
        )


        self.assertEqual(
            result[
                "moneyness"
            ],
            "ATM",
        )


        self.assertEqual(
            result[
                "spread"
            ],
            2.0,
        )


        self.assertIsNotNone(
            result[
                "greeks"
            ]
        )


    def test_regime(
        self,
    ):

        result = MarketRegimeEngine().classify(
            sample_bars()
        )


        self.assertIn(
            result[
                "regime"
            ],
            {
                "TREND_UP",
                "TREND_UP_HIGH_VOL",
                "RANGE",
                "RANGE_HIGH_VOL",
            },
        )


    def test_strategy_catalog(
        self,
    ):

        ids = {
            item[
                "strategy_id"
            ]

            for item
            in strategy_registry.catalog()
        }


        self.assertIn(
            "vwap_momentum_v1",
            ids,
        )


        self.assertIn(
            "ema_trend_v1",
            ids,
        )


    def test_invalid_strategy_operator(
        self,
    ):

        with self.assertRaises(
            ValueError
        ):

            Condition(
                "close",
                "python_eval",
                10,
            )


    def test_cross_above(
        self,
    ):

        condition = Condition(
            "ema9",
            "cross_above",
            "ema21",
        )


        self.assertTrue(
            SignalEngine.condition(
                condition,

                {
                    "ema9":
                        11,

                    "ema21":
                        10,
                },

                {
                    "ema9":
                        9,

                    "ema21":
                        10,
                },
            )
        )


    def test_signal_research_only(
        self,
    ):

        strategy = strategy_registry.get(
            "vwap_momentum_v1"
        )


        result = SignalEngine.evaluate(
            strategy,

            {
                "close":
                    102,

                "vwap":
                    100,

                "ema9":
                    101,

                "ema21":
                    99,

                "volume_z20":
                    1.0,
            },
        )


        self.assertEqual(
            result[
                "signal"
            ],
            "LONG",
        )


        self.assertFalse(
            result[
                "execution_allowed"
            ]
        )


    def test_metrics(
        self,
    ):

        result = evaluate_trades(
            (
                {
                    "gross_pnl":
                        100,

                    "fees":
                        10,

                    "slippage":
                        5,
                },

                {
                    "gross_pnl":
                        -50,

                    "fees":
                        5,

                    "slippage":
                        5,
                },

                {
                    "gross_pnl":
                        80,

                    "fees":
                        5,

                    "slippage":
                        5,
                },
            )
        )


        self.assertEqual(
            result[
                "trades"
            ],
            3,
        )


        self.assertGreater(
            result[
                "net_pnl"
            ],
            0,
        )


        self.assertGreater(
            result[
                "profit_factor"
            ],
            1,
        )


        self.assertGreater(
            result[
                "win_rate"
            ],
            0,
        )


    def test_live_order_guard(
        self,
    ):

        self.assertFalse(
            trading_research_guard
            .check(
                "order.place"
            )[
                "allowed"
            ]
        )


    def test_market_read_guard(
        self,
    ):

        self.assertTrue(
            trading_research_guard
            .check(
                "market.read"
            )[
                "allowed"
            ]
        )


    def test_fyers_read_only_adapter(
        self,
    ):

        adapter = FyersReadOnlyAdapter(
            FakeFyers()
        )


        result = adapter.quote(
            {
                "symbols":
                    "NSE:NIFTY50-INDEX"
            }
        )


        self.assertTrue(
            result[
                "success"
            ]
        )


    def test_fyers_live_method_blocked(
        self,
    ):

        adapter = FyersReadOnlyAdapter(
            FakeFyers()
        )


        with self.assertRaises(
            PermissionError
        ):

            adapter.place_order


    def test_public_status(
        self,
    ):

        result = main.jarvis_trading_v1_status()


        self.assertTrue(
            result[
                "research_only"
            ]
        )


        self.assertFalse(
            result[
                "live_execution"
            ]
        )


        self.assertFalse(
            result[
                "automatic_broker_order"
            ]
        )


    def test_public_apis(
        self,
    ):

        for name in (
            "jarvis_trading_v1_status",
            "jarvis_trading_register_instrument",
            "jarvis_trading_find_instruments",
            "jarvis_trading_features",
            "jarvis_trading_option_features",
            "jarvis_trading_regime",
            "jarvis_trading_strategy_catalog",
            "jarvis_trading_signal",
            "jarvis_trading_metrics",
            "jarvis_trading_guard",
            "jarvis_fyers_readonly_capabilities",
        ):

            self.assertTrue(
                callable(
                    getattr(
                        main,
                        name,
                    )
                )
            )


if __name__ == "__main__":

    unittest.main()
