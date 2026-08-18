import tempfile
import unittest

from datetime import (
    datetime,
    timedelta,
    timezone,
)

from pathlib import (
    Path,
)


import main


from omni.core_integrity import (
    verify_protected_core,
)

from omni.trading_intelligence.backtest_schema import (
    BacktestConfig,
    ExecutionCostConfig,
    commodity_future_config,
    option_premium_config,
)

from omni.trading_intelligence.cost_model import (
    ExecutionCostModel,
)

from omni.trading_intelligence.history_normalizer import (
    normalize_history_payload,
)

from omni.trading_intelligence.historical_backtester import (
    HistoricalBacktester,
)

from omni.trading_intelligence.market_schema import (
    Bar,
)

from omni.trading_intelligence.multi_timeframe import (
    resample_bars,
)

from omni.trading_intelligence.parameter_sweep import (
    ParameterSweepEngine,
)

from omni.trading_intelligence.strategy_compare import (
    StrategyComparator,
)

from omni.trading_intelligence.trade_journal import (
    TradeJournal,
)


def rising_bars(
    count=120,
):

    start = datetime(
        2026,
        1,
        1,
        9,
        15,
        tzinfo=timezone.utc,
    )


    output = []


    for index in range(
        count
    ):

        base = (
            100.0
            + index
            * 0.4
        )


        output.append(
            Bar(
                timestamp=
                    start
                    + timedelta(
                        minutes=index,
                    ),

                open=
                    base,

                high=
                    base
                    + 0.8,

                low=
                    base
                    - 0.4,

                close=
                    base
                    + 0.5,

                volume=
                    1000
                    + index
                    * 10,
            )
        )


    return output


def falling_bars(
    count=120,
):

    start = datetime(
        2026,
        1,
        1,
        9,
        15,
        tzinfo=timezone.utc,
    )


    output = []


    for index in range(
        count
    ):

        base = (
            200.0
            - index
            * 0.4
        )


        output.append(
            Bar(
                timestamp=
                    start
                    + timedelta(
                        minutes=index,
                    ),

                open=
                    base,

                high=
                    base
                    + 0.4,

                low=
                    base
                    - 0.8,

                close=
                    base
                    - 0.5,

                volume=
                    1000
                    + index
                    * 10,
            )
        )


    return output


class TradingIntelligenceV2Tests(
    unittest.TestCase
):

    def test_core(
        self,
    ):

        self.assertTrue(
            verify_protected_core().ok
        )


    def test_cost_fill_buy_is_worse(
        self,
    ):

        model = ExecutionCostModel(
            ExecutionCostConfig(
                slippage_bps=10,
                spread_bps=20,
            )
        )


        result = model.fill(
            100,
            "buy",
        )


        self.assertGreater(
            result[
                "fill_price"
            ],
            100,
        )


    def test_cost_fill_sell_is_worse(
        self,
    ):

        model = ExecutionCostModel(
            ExecutionCostConfig(
                slippage_bps=10,
                spread_bps=20,
            )
        )


        result = model.fill(
            100,
            "sell",
        )


        self.assertLess(
            result[
                "fill_price"
            ],
            100,
        )


    def test_option_long_blocks_short(
        self,
    ):

        config = option_premium_config(
            lot_size=75,
        )


        self.assertFalse(
            config.allow_short
        )


        self.assertEqual(
            config.instrument_kind,
            "option_long",
        )


    def test_manual_option_short_rejected(
        self,
    ):

        with self.assertRaises(
            ValueError
        ):

            BacktestConfig(
                instrument_kind=
                    "option_long",

                allow_short=
                    True,
            )


    def test_commodity_config(
        self,
    ):

        config = commodity_future_config(
            contracts=2,
            lot_size=100,
        )


        self.assertTrue(
            config.allow_long
        )

        self.assertTrue(
            config.allow_short
        )

        self.assertEqual(
            config.contract_multiplier,
            100,
        )


    def test_history_list_normalizer(
        self,
    ):

        payload = {
            "success":
                True,

            "candles": [
                [
                    1700000000,
                    100,
                    102,
                    99,
                    101,
                    1000,
                ],

                [
                    1700000060,
                    101,
                    103,
                    100,
                    102,
                    1100,
                ],
            ],
        }


        bars = normalize_history_payload(
            payload,
            symbol="TEST",
        )


        self.assertEqual(
            len(
                bars
            ),
            2,
        )


        self.assertEqual(
            bars[
                0
            ].symbol,
            "TEST",
        )


    def test_history_dict_normalizer(
        self,
    ):

        payload = {
            "data": [
                {
                    "timestamp":
                        "2026-01-01T09:15:00+00:00",

                    "open":
                        100,

                    "high":
                        102,

                    "low":
                        99,

                    "close":
                        101,

                    "volume":
                        1000,
                },

                {
                    "timestamp":
                        "2026-01-01T09:16:00+00:00",

                    "open":
                        101,

                    "high":
                        103,

                    "low":
                        100,

                    "close":
                        102,

                    "volume":
                        1000,
                },
            ]
        }


        bars = normalize_history_payload(
            payload
        )


        self.assertEqual(
            len(
                bars
            ),
            2,
        )


    def test_resample(
        self,
    ):

        bars = rising_bars(
            10
        )


        result = resample_bars(
            bars,
            5,
            base_timeframe_minutes=1,
            closed_only=True,
        )


        self.assertEqual(
            len(
                result
            ),
            2,
        )


    def test_resample_drops_partial(
        self,
    ):

        bars = rising_bars(
            8
        )


        result = resample_bars(
            bars,
            5,
            base_timeframe_minutes=1,
            closed_only=True,
        )


        self.assertEqual(
            len(
                result
            ),
            1,
        )


    def test_long_backtest(
        self,
    ):

        config = BacktestConfig(
            initial_capital=100000,
            allow_long=True,
            allow_short=False,
            warmup_bars=30,
        )


        result = HistoricalBacktester().run(
            rising_bars(),
            "vwap_momentum_v1",
            config,
        )


        self.assertTrue(
            result[
                "success"
            ]
        )


        self.assertGreaterEqual(
            len(
                result[
                    "trades"
                ]
            ),
            1,
        )


        self.assertFalse(
            result[
                "live_execution"
            ]
        )


    def test_short_backtest(
        self,
    ):

        config = BacktestConfig(
            initial_capital=100000,
            allow_long=False,
            allow_short=True,
            warmup_bars=30,
        )


        result = HistoricalBacktester().run(
            falling_bars(),
            "vwap_momentum_v1",
            config,
        )


        self.assertGreaterEqual(
            len(
                result[
                    "trades"
                ]
            ),
            1,
        )


        self.assertEqual(
            result[
                "trades"
            ][0][
                "side"
            ],
            "SHORT",
        )


    def test_next_bar_open_fill_model(
        self,
    ):

        config = BacktestConfig(
            allow_short=False,
            warmup_bars=30,
        )


        result = HistoricalBacktester().run(
            rising_bars(),
            "vwap_momentum_v1",
            config,
        )


        self.assertEqual(
            result[
                "fill_model"
            ],
            "signal_close_to_next_bar_open",
        )


    def test_stop_loss(
        self,
    ):

        bars = rising_bars(
            80
        )


        # Force a large adverse bar after likely entry.
        bars[
            35
        ] = Bar(
            timestamp=
                bars[
                    35
                ].timestamp,

            open=
                bars[
                    35
                ].open,

            high=
                bars[
                    35
                ].high,

            low=
                50,

            close=
                bars[
                    35
                ].close,

            volume=
                bars[
                    35
                ].volume,
        )


        config = BacktestConfig(
            allow_short=False,
            warmup_bars=30,
            stop_loss_pct=0.02,
        )


        result = HistoricalBacktester().run(
            bars,
            "vwap_momentum_v1",
            config,
        )


        reasons = {
            trade[
                "exit_reason"
            ]

            for trade in result[
                "trades"
            ]
        }


        self.assertTrue(
            {
                "stop",
                "stop_gap",
            }
            & reasons
        )


    def test_target(
        self,
    ):

        config = BacktestConfig(
            allow_short=False,
            warmup_bars=30,
            target_pct=0.01,
        )


        result = HistoricalBacktester().run(
            rising_bars(),
            "vwap_momentum_v1",
            config,
        )


        reasons = {
            trade[
                "exit_reason"
            ]

            for trade in result[
                "trades"
            ]
        }


        self.assertTrue(
            {
                "target",
                "target_gap",
            }
            & reasons
        )


    def test_trailing_stop_config(
        self,
    ):

        config = BacktestConfig(
            allow_short=False,
            trailing_stop_pct=0.02,
        )


        self.assertEqual(
            config.trailing_stop_pct,
            0.02,
        )


    def test_max_bars_exit(
        self,
    ):

        config = BacktestConfig(
            allow_short=False,
            warmup_bars=30,
            max_bars_in_trade=3,
        )


        result = HistoricalBacktester().run(
            rising_bars(),
            "vwap_momentum_v1",
            config,
        )


        reasons = {
            trade[
                "exit_reason"
            ]

            for trade in result[
                "trades"
            ]
        }


        self.assertIn(
            "max_bars",
            reasons,
        )


    def test_costs_reduce_pnl(
        self,
    ):

        clean = BacktestConfig(
            allow_short=False,
            warmup_bars=30,
        )


        costly = BacktestConfig(
            allow_short=False,
            warmup_bars=30,

            cost=ExecutionCostConfig(
                brokerage_bps=10,
                slippage_bps=10,
                spread_bps=10,
            ),
        )


        bars = rising_bars()


        a = HistoricalBacktester().run(
            bars,
            "vwap_momentum_v1",
            clean,
        )


        b = HistoricalBacktester().run(
            bars,
            "vwap_momentum_v1",
            costly,
        )


        self.assertLess(
            b[
                "metrics"
            ][
                "net_pnl"
            ],
            a[
                "metrics"
            ][
                "net_pnl"
            ],
        )


    def test_equity_curve(
        self,
    ):

        config = BacktestConfig(
            allow_short=False,
            warmup_bars=30,
            max_bars_in_trade=5,
        )


        result = HistoricalBacktester().run(
            rising_bars(),
            "vwap_momentum_v1",
            config,
        )


        self.assertEqual(
            len(
                result[
                    "equity_curve"
                ]
            ),
            len(
                result[
                    "trades"
                ]
            ),
        )


    def test_drawdown_metric_present(
        self,
    ):

        result = HistoricalBacktester().run(
            rising_bars(),
            "vwap_momentum_v1",
            BacktestConfig(
                allow_short=False,
                warmup_bars=30,
            ),
        )


        self.assertIn(
            "max_drawdown_pct",
            result[
                "metrics"
            ],
        )


    def test_parameter_sweep(
        self,
    ):

        engine = ParameterSweepEngine()


        result = engine.run(
            rising_bars(),
            "vwap_momentum_v1",

            BacktestConfig(
                allow_short=False,
                warmup_bars=30,
            ),

            {
                "target_pct":
                    (
                        0.01,
                        0.02,
                    ),

                "stop_loss_pct":
                    (
                        0.01,
                        0.02,
                    ),
            },

            objective=
                "net_pnl",
        )


        self.assertEqual(
            result[
                "combinations"
            ],
            4,
        )


        self.assertFalse(
            result[
                "automatic_promotion"
            ]
        )


    def test_sweep_limit(
        self,
    ):

        engine = ParameterSweepEngine()


        with self.assertRaises(
            ValueError
        ):

            engine.run(
                rising_bars(),
                "vwap_momentum_v1",

                BacktestConfig(
                    allow_short=False,
                    warmup_bars=30,
                ),

                {
                    "target_pct":
                        tuple(
                            0.001
                            * (
                                i + 1
                            )

                            for i in range(
                                201
                            )
                        )
                },
            )


    def test_strategy_compare(
        self,
    ):

        result = StrategyComparator().compare(
            rising_bars(),

            (
                "vwap_momentum_v1",
                "rsi_mean_reversion_v1",
            ),

            BacktestConfig(
                allow_short=False,
                warmup_bars=30,
            ),

            objective=
                "net_pnl",
        )


        self.assertEqual(
            len(
                result[
                    "ranked"
                ]
            ),
            2,
        )


        self.assertFalse(
            result[
                "automatic_promotion"
            ]
        )


    def test_trade_journal(
        self,
    ):

        result = HistoricalBacktester().run(
            rising_bars(),
            "vwap_momentum_v1",

            BacktestConfig(
                allow_short=False,
                warmup_bars=30,
            ),
        )


        with tempfile.TemporaryDirectory() as tmp:

            journal = TradeJournal(
                Path(
                    tmp
                )
            )


            saved = journal.save(
                result,
                name="test",
            )


            self.assertTrue(
                Path(
                    saved[
                        "json"
                    ]
                ).exists()
            )


    def test_v2_status(
        self,
    ):

        status = main.jarvis_trading_v2_status()


        self.assertTrue(
            status[
                "historical_backtester"
            ]
        )


        self.assertTrue(
            status[
                "option_long_premium_simulation"
            ]
        )


        self.assertFalse(
            status[
                "naked_option_premium_short"
            ]
        )


        self.assertFalse(
            status[
                "live_execution"
            ]
        )


    def test_public_apis(
        self,
    ):

        for name in (
            "jarvis_trading_v2_status",
            "jarvis_backtest_config",
            "jarvis_option_backtest_config",
            "jarvis_commodity_backtest_config",
            "jarvis_backtest",
            "jarvis_backtest_fyers",
            "jarvis_normalize_market_history",
            "jarvis_resample_bars",
            "jarvis_parameter_sweep",
            "jarvis_compare_strategies",
            "jarvis_save_backtest",
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
