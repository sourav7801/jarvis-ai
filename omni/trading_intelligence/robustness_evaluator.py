from __future__ import annotations

from statistics import (
    fmean,
    pstdev,
)


from omni.trading_intelligence.historical_backtester import (
    historical_backtester,
)

from omni.trading_intelligence.strategy_fitness import (
    result_fitness,
)


class RegimeRobustnessEvaluator:

    def run(
        self,
        regime_datasets,
        strategy,
        config,
    ):

        if not regime_datasets:
            raise ValueError(
                "At least one regime dataset is required."
            )


        rows = []


        for regime, bars in regime_datasets.items():

            result = historical_backtester.run(
                bars,
                strategy,
                config,
            )


            fitness = result_fitness(
                result
            )


            rows.append(
                {
                    "regime":
                        str(regime),

                    "metrics":
                        result[
                            "metrics"
                        ],

                    "fitness":
                        fitness,

                    "profitable":
                        (
                            float(
                                result[
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


        scores = [
            item[
                "fitness"
            ][
                "score"
            ]

            for item in rows
        ]


        profitable = sum(
            1
            for item in rows
            if item["profitable"]
        )


        return {
            "success":
                True,

            "regimes":
                tuple(rows),

            "regime_count":
                len(rows),

            "profitable_regime_rate":
                profitable
                / len(rows),

            "average_fitness":
                fmean(scores),

            "worst_fitness":
                min(scores),

            "fitness_dispersion":
                (
                    pstdev(scores)
                    if len(scores) > 1
                    else 0.0
                ),

            "research_only":
                True,
        }


regime_robustness_evaluator = (
    RegimeRobustnessEvaluator()
)
