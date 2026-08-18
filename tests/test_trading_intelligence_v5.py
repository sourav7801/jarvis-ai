import tempfile
import unittest

from datetime import (
    datetime,
    timedelta,
    timezone,
)

from pathlib import Path


import main


from omni.core_integrity import (
    verify_protected_core,
)

from omni.trading_intelligence.backtest_schema import (
    BacktestConfig,
    ExecutionCostConfig,
)

from omni.trading_intelligence.candidate_validation_gate import (
    validation_recommendation,
)

from omni.trading_intelligence.cost_stress import (
    CostStressTester,
)

from omni.trading_intelligence.market_schema import (
    Bar,
)

from omni.trading_intelligence.monte_carlo import (
    MonteCarloTradeSimulator,
)

from omni.trading_intelligence.overfitting_risk import (
    overfitting_risk,
)

from omni.trading_intelligence.parameter_sensitivity import (
    ParameterSensitivityAnalyzer,
)

from omni.trading_intelligence.strategy_evolution_lab import (
    StrategyEvolutionLab,
)

from omni.trading_intelligence.strategy_registry import (
    strategy_registry,
)

from omni.trading_intelligence.strategy_validation_lab import (
    StrategyValidationLab,
)

from omni.trading_intelligence.validation_partitions import (
    chronological_split,
    rolling_windows,
)

from omni.trading_intelligence.validation_store import (
    ValidationStore,
)

from omni.trading_intelligence.walk_forward import (
    WalkForwardValidator,
)


def trend_bars(
    count=360,
    direction=1,
):

    start = datetime(
        2026,
        1,
        1,
        9,
        15,
        tzinfo=timezone.utc,
    )


    rows = []


    for index in range(count):

        trend = (
            index
            * 0.18
            * direction
        )

        wave = (
            (
                index % 20
            )
            - 10
        ) * 0.06


        price = (
            150
            + trend
            + wave
        )


        close = (
            price
            + 0.25
            * direction
        )


        rows.append(
            Bar(
                timestamp=
                    start
                    + timedelta(
                        minutes=index
                    ),

                open=
                    price,

                high=
                    max(
                        price,
                        close,
                    )
                    + 0.5,

                low=
                    min(
                        price,
                        close,
                    )
                    - 0.5,

                close=
                    close,

                volume=
                    1000
                    + index * 5,
            )
        )


    return rows


class TradingIntelligenceV5Tests(
    unittest.TestCase
):

    def test_core(self):

        self.assertTrue(
            verify_protected_core().ok
        )


    def test_chronological_split(self):

        result = chronological_split(
            trend_bars()
        )


        self.assertTrue(
            result[
                "chronological"
            ]
        )

        self.assertFalse(
            result[
                "shuffled"
            ]
        )

        self.assertGreater(
            len(
                result[
                    "out_of_sample"
                ]
            ),
            0,
        )


    def test_split_is_ordered(self):

        result = chronological_split(
            trend_bars()
        )


        self.assertLess(
            result[
                "train"
            ][-1].timestamp,
            result[
                "validation"
            ][0].timestamp,
        )

        self.assertLess(
            result[
                "validation"
            ][-1].timestamp,
            result[
                "out_of_sample"
            ][0].timestamp,
        )


    def test_walk_windows(self):

        windows = rolling_windows(
            trend_bars(),
            train_size=120,
            validation_size=60,
            test_size=60,
            step=60,
        )


        self.assertGreaterEqual(
            len(windows),
            2,
        )


    def test_walk_forward(self):

        strategy = strategy_registry.get(
            "vwap_momentum_v1"
        )


        result = WalkForwardValidator().run(
            trend_bars(),
            strategy,

            BacktestConfig(
                warmup_bars=30,
                max_bars_in_trade=10,
            ),

            train_size=120,
            validation_size=60,
            test_size=60,
            step=60,
        )


        self.assertTrue(
            result[
                "success"
            ]
        )

        self.assertFalse(
            result[
                "candidate_reoptimized_on_oos"
            ]
        )


    def test_monte_carlo(self):

        trades = [
            {
                "net_pnl":
                    value
            }

            for value in (
                100,
                150,
                -80,
                120,
                -50,
                90,
            )
        ]


        result = MonteCarloTradeSimulator().run(
            trades,
            initial_capital=100000,
            iterations=100,
            random_seed=7,
        )


        self.assertEqual(
            result[
                "iterations"
            ],
            100,
        )

        self.assertGreaterEqual(
            result[
                "loss_probability"
            ],
            0,
        )

        self.assertLessEqual(
            result[
                "loss_probability"
            ],
            1,
        )


    def test_monte_carlo_limit(self):

        with self.assertRaises(
            ValueError
        ):

            MonteCarloTradeSimulator().run(
                [
                    {
                        "net_pnl":
                            1
                    }
                ],
                initial_capital=100,
                iterations=5001,
            )


    def test_parameter_sensitivity(self):

        strategy = strategy_registry.get(
            "vwap_momentum_v1"
        )


        result = (
            ParameterSensitivityAnalyzer()
            .run(
                trend_bars(240),
                strategy,

                BacktestConfig(
                    warmup_bars=30,
                    max_bars_in_trade=10,
                ),

                fields=(
                    "target_pct",
                    "max_bars_in_trade",
                ),
            )
        )


        self.assertEqual(
            result[
                "runs"
            ],
            6,
        )

        self.assertFalse(
            result[
                "automatic_parameter_selection"
            ]
        )


    def test_cost_stress(self):

        strategy = strategy_registry.get(
            "vwap_momentum_v1"
        )


        result = CostStressTester().run(
            trend_bars(180),
            strategy,

            BacktestConfig(
                warmup_bars=30,
                max_bars_in_trade=10,

                cost=ExecutionCostConfig(
                    brokerage_bps=1,
                    slippage_bps=1,
                    spread_bps=1,
                ),
            ),
        )


        self.assertEqual(
            result[
                "scenario_count"
            ],
            3,
        )

        self.assertFalse(
            result[
                "hardcoded_current_fee_schedule"
            ]
        )


    def test_overfit_low(self):

        result = overfitting_risk(
            train_fitness=20,
            validation_fitness=19,
            oos_fitness=18,
            walk_forward_pass_rate=1.0,
            sensitivity_instability=0.1,
            monte_carlo_loss_probability=0.1,
            cost_survival_rate=1.0,
            data_sufficient=True,
        )


        self.assertLess(
            result[
                "score"
            ],
            25,
        )


    def test_overfit_high(self):

        result = overfitting_risk(
            train_fitness=80,
            validation_fitness=10,
            oos_fitness=-30,
            walk_forward_pass_rate=0.1,
            sensitivity_instability=3.0,
            monte_carlo_loss_probability=0.9,
            cost_survival_rate=0.0,
            data_sufficient=False,
        )


        self.assertGreater(
            result[
                "score"
            ],
            70,
        )


    def test_promote_is_not_production(self):

        result = validation_recommendation(
            risk={
                "score":
                    10
            },
            oos_fitness=15,
            walk_forward_pass_rate=0.8,
            cost_survival_rate=1.0,
            oos_trades=10,
            data_sufficient=True,
        )


        self.assertEqual(
            result[
                "recommendation"
            ],
            "PROMOTE",
        )

        self.assertFalse(
            result[
                "production_promotion"
            ]
        )

        self.assertTrue(
            result[
                "research_recommendation_only"
            ]
        )


    def test_insufficient_keeps_testing(self):

        result = validation_recommendation(
            risk={
                "score":
                    5
            },
            oos_fitness=20,
            walk_forward_pass_rate=1,
            cost_survival_rate=1,
            oos_trades=1,
            data_sufficient=False,
        )


        self.assertEqual(
            result[
                "recommendation"
            ],
            "KEEP_TESTING",
        )


    def test_candidate_validation(self):

        strategy = strategy_registry.get(
            "vwap_momentum_v1"
        )


        report = StrategyValidationLab().validate(
            strategy,
            trend_bars(),

            BacktestConfig(
                warmup_bars=30,
                max_bars_in_trade=8,

                cost=ExecutionCostConfig(
                    brokerage_bps=1,
                    slippage_bps=1,
                    spread_bps=1,
                ),
            ),

            monte_carlo_iterations=100,
            random_seed=5,
        )


        self.assertTrue(
            report[
                "success"
            ]
        )

        self.assertFalse(
            report[
                "partitions"
            ][
                "oos_used_for_tuning"
            ]
        )

        self.assertIn(
            report[
                "recommendation"
            ][
                "recommendation"
            ],
            {
                "PROMOTE",
                "KEEP_TESTING",
                "DEGRADE",
                "RETIRE",
            },
        )

        self.assertFalse(
            report[
                "production_promotion"
            ]
        )


    def test_evolved_candidate_validation(self):

        candidate = (
            StrategyEvolutionLab()
            .mutate(
                "vwap_momentum_v1",
                count=1,
                random_seed=3,
            )[0]
        )


        report = StrategyValidationLab().validate(
            candidate,
            trend_bars(),

            BacktestConfig(
                warmup_bars=30,
            ),

            monte_carlo_iterations=50,
        )


        self.assertEqual(
            report[
                "candidate_id"
            ],
            candidate.candidate_id,
        )


    def test_validation_store(self):

        with tempfile.TemporaryDirectory() as tmp:

            store = ValidationStore(
                Path(tmp)
            )


            result = store.save(
                {
                    "research_only":
                        True,

                    "candidate":
                        "x",
                }
            )


            self.assertTrue(
                Path(
                    result[
                        "path"
                    ]
                ).exists()
            )


    def test_status(self):

        status = main.jarvis_trading_v5_status()


        self.assertTrue(
            status[
                "walk_forward_validation"
            ]
        )

        self.assertTrue(
            status[
                "overfitting_risk_score"
            ]
        )

        self.assertFalse(
            status[
                "oos_tuning"
            ]
        )

        self.assertFalse(
            status[
                "automatic_strategy_promotion"
            ]
        )

        self.assertFalse(
            status[
                "live_execution"
            ]
        )


    def test_v4_preserved(self):

        status = main.jarvis_trading_v4_status()

        self.assertTrue(
            status[
                "strategy_genomes"
            ]
        )

        self.assertFalse(
            status[
                "automatic_strategy_promotion"
            ]
        )


    def test_public_apis(self):

        for name in (
            "jarvis_trading_v5_status",
            "jarvis_trading_validate_candidate",
            "jarvis_walk_forward",
            "jarvis_monte_carlo_trades",
            "jarvis_parameter_sensitivity",
            "jarvis_cost_stress",
            "jarvis_save_validation_report",
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
