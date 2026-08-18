from __future__ import annotations

from dataclasses import replace


from omni.trading_intelligence.candidate_validation_gate import (
    validation_recommendation,
)

from omni.trading_intelligence.cost_stress import (
    cost_stress_tester,
)

from omni.trading_intelligence.historical_backtester import (
    historical_backtester,
)

from omni.trading_intelligence.monte_carlo import (
    monte_carlo_trade_simulator,
)

from omni.trading_intelligence.overfitting_risk import (
    overfitting_risk,
)

from omni.trading_intelligence.parameter_sensitivity import (
    parameter_sensitivity_analyzer,
)

from omni.trading_intelligence.strategy_fitness import (
    result_fitness,
)

from omni.trading_intelligence.validation_partitions import (
    chronological_split,
)

from omni.trading_intelligence.walk_forward import (
    walk_forward_validator,
)

from omni.trading_intelligence.robustness_evaluator import (
    regime_robustness_evaluator,
)


class StrategyValidationLab:

    @staticmethod
    def _strategy_and_config(
        candidate,
        base_config,
    ):

        if hasattr(
            candidate,
            "strategy"
        ):

            strategy = candidate.strategy

            overrides = dict(
                getattr(
                    candidate,
                    "config_overrides",
                    {},
                )
            )


            config = replace(
                base_config,
                **overrides
            )


            candidate_id = getattr(
                candidate,
                "candidate_id",
                strategy.strategy_id,
            )


        else:

            strategy = candidate
            config = base_config

            candidate_id = getattr(
                strategy,
                "strategy_id",
                "candidate",
            )


        return (
            strategy,
            config,
            str(candidate_id),
        )


    def validate(
        self,
        candidate,
        bars,
        base_config,
        *,
        regime_datasets=None,
        monte_carlo_iterations=500,
        random_seed=1,
    ):

        strategy, config, candidate_id = (
            self._strategy_and_config(
                candidate,
                base_config,
            )
        )


        minimum_segment = max(
            32,
            int(
                config.warmup_bars
            )
            + 2,
        )


        split = chronological_split(
            bars,
            train_ratio=0.60,
            validation_ratio=0.20,
            minimum_segment_bars=
                minimum_segment,
        )


        train_result = historical_backtester.run(
            split["train"],
            strategy,
            config,
        )


        validation_result = historical_backtester.run(
            split["validation"],
            strategy,
            config,
        )


        oos_result = historical_backtester.run(
            split["out_of_sample"],
            strategy,
            config,
        )


        train_fitness = result_fitness(
            train_result
        )

        validation_fitness = result_fitness(
            validation_result
        )

        oos_fitness = result_fitness(
            oos_result
        )


        total = len(bars)

        train_size = max(
            minimum_segment,
            int(
                total * 0.40
            ),
        )

        validation_size = max(
            minimum_segment,
            int(
                total * 0.20
            ),
        )

        test_size = max(
            minimum_segment,
            int(
                total * 0.20
            ),
        )


        while (
            train_size
            + validation_size
            + test_size
            > total
        ):

            if train_size > minimum_segment:
                train_size -= 1

            elif validation_size > minimum_segment:
                validation_size -= 1

            elif test_size > minimum_segment:
                test_size -= 1

            else:
                raise ValueError(
                    "Insufficient data for walk-forward validation."
                )


        walk_forward = walk_forward_validator.run(
            bars,
            strategy,
            config,
            train_size=train_size,
            validation_size=validation_size,
            test_size=test_size,
            step=test_size,
        )


        development_bars = tuple(
            split["train"]
        ) + tuple(
            split["validation"]
        )


        sensitivity = (
            parameter_sensitivity_analyzer
            .run(
                development_bars,
                strategy,
                config,
            )
        )


        cost_stress = cost_stress_tester.run(
            split["out_of_sample"],
            strategy,
            config,
        )


        oos_trades = tuple(
            oos_result[
                "trades"
            ]
        )


        monte_source = (
            oos_trades

            if oos_trades

            else tuple(
                validation_result[
                    "trades"
                ]
            )
        )


        monte_carlo = None


        if monte_source:

            monte_carlo = (
                monte_carlo_trade_simulator
                .run(
                    monte_source,
                    initial_capital=
                        config.initial_capital,
                    iterations=
                        monte_carlo_iterations,
                    random_seed=
                        random_seed,
                    bootstrap=True,
                )
            )


        data_sufficient = (
            split[
                "counts"
            ][
                "out_of_sample"
            ]
            >= minimum_segment
            and len(
                oos_trades
            )
            >= 3
        )


        loss_probability = (
            monte_carlo[
                "loss_probability"
            ]
            if monte_carlo is not None
            else 1.0
        )


        risk = overfitting_risk(
            train_fitness=
                train_fitness[
                    "score"
                ],

            validation_fitness=
                validation_fitness[
                    "score"
                ],

            oos_fitness=
                oos_fitness[
                    "score"
                ],

            walk_forward_pass_rate=
                walk_forward[
                    "oos_pass_rate"
                ],

            sensitivity_instability=
                sensitivity[
                    "instability_score"
                ],

            monte_carlo_loss_probability=
                loss_probability,

            cost_survival_rate=
                cost_stress[
                    "survival_rate"
                ],

            data_sufficient=
                data_sufficient,
        )


        recommendation = (
            validation_recommendation(
                risk=risk,

                oos_fitness=
                    oos_fitness[
                        "score"
                    ],

                walk_forward_pass_rate=
                    walk_forward[
                        "oos_pass_rate"
                    ],

                cost_survival_rate=
                    cost_stress[
                        "survival_rate"
                    ],

                oos_trades=
                    len(
                        oos_trades
                    ),

                data_sufficient=
                    data_sufficient,
            )
        )


        regime_robustness = None


        if regime_datasets:

            regime_robustness = (
                regime_robustness_evaluator
                .run(
                    regime_datasets,
                    strategy,
                    config,
                )
            )


        return {
            "success":
                True,

            "candidate_id":
                candidate_id,

            "strategy_id":
                strategy.strategy_id,

            "partitions":
                {
                    "counts":
                        split[
                            "counts"
                        ],

                    "chronological":
                        True,

                    "oos_used_for_tuning":
                        False,
                },

            "train":
                train_result,

            "validation":
                validation_result,

            "out_of_sample":
                oos_result,

            "fitness": {
                "train":
                    train_fitness,

                "validation":
                    validation_fitness,

                "out_of_sample":
                    oos_fitness,
            },

            "walk_forward":
                walk_forward,

            "parameter_sensitivity":
                sensitivity,

            "cost_stress":
                cost_stress,

            "monte_carlo":
                monte_carlo,

            "regime_robustness":
                regime_robustness,

            "data_sufficient":
                data_sufficient,

            "overfitting_risk":
                risk,

            "recommendation":
                recommendation,

            "production_promotion":
                False,

            "automatic_registry_mutation":
                False,

            "live_execution":
                False,

            "research_only":
                True,
        }


strategy_validation_lab = (
    StrategyValidationLab()
)
