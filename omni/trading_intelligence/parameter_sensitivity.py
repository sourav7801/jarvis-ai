from __future__ import annotations

from dataclasses import replace

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


DEFAULT_VALUES = {
    "stop_loss_pct":
        (
            0.01,
            0.02,
            0.03,
        ),

    "target_pct":
        (
            0.02,
            0.04,
            0.06,
        ),

    "trailing_stop_pct":
        (
            None,
            0.01,
            0.02,
        ),

    "max_bars_in_trade":
        (
            10,
            20,
            40,
        ),
}


class ParameterSensitivityAnalyzer:

    MAX_RUNS = 30


    def run(
        self,
        bars,
        strategy,
        base_config,
        *,
        fields=(
            "stop_loss_pct",
            "target_pct",
            "max_bars_in_trade",
        ),
    ):

        results = []

        run_count = 0


        for field in fields:

            if field not in DEFAULT_VALUES:

                raise ValueError(
                    "Unsupported sensitivity field: "
                    + str(field)
                )


            field_results = []


            for value in DEFAULT_VALUES[
                field
            ]:

                run_count += 1

                if run_count > self.MAX_RUNS:
                    raise ValueError(
                        "Sensitivity analysis exceeds run limit."
                    )


                config = replace(
                    base_config,
                    **{
                        field:
                            value
                    }
                )


                backtest = historical_backtester.run(
                    bars,
                    strategy,
                    config,
                )


                fitness = result_fitness(
                    backtest
                )


                field_results.append(
                    {
                        "value":
                            value,

                        "fitness":
                            fitness,

                        "net_pnl":
                            float(
                                backtest[
                                    "metrics"
                                ].get(
                                    "net_pnl",
                                    0.0,
                                )
                            ),
                    }
                )


            scores = [
                item[
                    "fitness"
                ][
                    "score"
                ]

                for item
                in field_results
            ]


            mean_score = (
                fmean(scores)
                if scores
                else 0.0
            )


            dispersion = (
                pstdev(scores)
                if len(scores) > 1
                else 0.0
            )


            normalized_instability = (
                dispersion
                / max(
                    abs(mean_score),
                    10.0,
                )
            )


            results.append(
                {
                    "field":
                        field,

                    "results":
                        tuple(field_results),

                    "mean_fitness":
                        mean_score,

                    "dispersion":
                        dispersion,

                    "normalized_instability":
                        normalized_instability,
                }
            )


        instability = (
            fmean(
                item[
                    "normalized_instability"
                ]
                for item in results
            )
            if results
            else 0.0
        )


        return {
            "success":
                True,

            "fields":
                tuple(results),

            "runs":
                run_count,

            "instability_score":
                instability,

            "automatic_parameter_selection":
                False,

            "research_only":
                True,
        }


parameter_sensitivity_analyzer = (
    ParameterSensitivityAnalyzer()
)
