from __future__ import annotations

from statistics import fmean


from omni.trading_intelligence.historical_backtester import (
    historical_backtester,
)

from omni.trading_intelligence.strategy_fitness import (
    result_fitness,
)

from omni.trading_intelligence.validation_partitions import (
    rolling_windows,
)


class WalkForwardValidator:

    def run(
        self,
        bars,
        strategy,
        config,
        *,
        train_size,
        validation_size,
        test_size,
        step=None,
    ):

        windows = rolling_windows(
            bars,
            train_size=train_size,
            validation_size=validation_size,
            test_size=test_size,
            step=step,
        )


        results = []


        for window in windows:

            train_result = historical_backtester.run(
                window["train"],
                strategy,
                config,
            )

            validation_result = historical_backtester.run(
                window["validation"],
                strategy,
                config,
            )

            oos_result = historical_backtester.run(
                window["out_of_sample"],
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


            results.append(
                {
                    "window_id":
                        window["window_id"],

                    "indexes":
                        window["indexes"],

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

                    "oos_profitable":
                        (
                            float(
                                oos_result[
                                    "metrics"
                                ].get(
                                    "net_pnl",
                                    0.0,
                                )
                            )
                            > 0
                        ),
                }
            )


        oos_scores = [
            item[
                "fitness"
            ][
                "out_of_sample"
            ][
                "score"
            ]

            for item in results
        ]


        profitable = sum(
            1
            for item in results
            if item[
                "oos_profitable"
            ]
        )


        pass_rate = (
            profitable
            / len(results)
            if results
            else 0.0
        )


        return {
            "success":
                True,

            "windows":
                tuple(results),

            "window_count":
                len(results),

            "oos_profitable_windows":
                profitable,

            "oos_pass_rate":
                pass_rate,

            "average_oos_fitness":
                (
                    fmean(oos_scores)
                    if oos_scores
                    else 0.0
                ),

            "chronological":
                True,

            "candidate_reoptimized_on_oos":
                False,

            "research_only":
                True,
        }


walk_forward_validator = (
    WalkForwardValidator()
)
