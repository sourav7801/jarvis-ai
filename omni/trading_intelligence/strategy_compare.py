from __future__ import annotations

from omni.trading_intelligence.historical_backtester import (
    historical_backtester,
)

from omni.trading_intelligence.strategy_registry import (
    strategy_registry,
)


SUPPORTED_OBJECTIVES = {
    "net_pnl",
    "return_pct",
    "profit_factor",
    "expectancy",
    "win_rate",
    "max_drawdown_pct",
}


class StrategyComparator:

    @staticmethod
    def _sort_value(
        result,
        objective,
    ):

        value = result[
            "metrics"
        ].get(
            objective
        )


        if value is None:

            return float(
                "-inf"
            )


        value = float(
            value
        )


        if objective == "max_drawdown_pct":

            return -value


        return value


    def compare(
        self,
        bars,
        strategy_ids,
        config,
        *,
        objective="net_pnl",
    ):

        if objective not in SUPPORTED_OBJECTIVES:

            raise ValueError(
                "Unsupported comparison objective."
            )


        results = []


        for strategy_id in strategy_ids:

            strategy = (
                strategy_registry
                .get(
                    strategy_id
                )
            )


            if strategy is None:

                raise ValueError(
                    "Unknown strategy: "
                    + str(
                        strategy_id
                    )
                )


            result = (
                historical_backtester
                .run(
                    bars,
                    strategy,
                    config,
                )
            )


            results.append(
                result
            )


        ranked = sorted(
            results,
            key=lambda result:
                self._sort_value(
                    result,
                    objective,
                ),
            reverse=True,
        )


        return {
            "success":
                True,

            "objective":
                objective,

            "ranked":
                tuple(
                    {
                        "rank":
                            index + 1,

                        "strategy_id":
                            result[
                                "strategy_id"
                            ],

                        "strategy_name":
                            result[
                                "strategy_name"
                            ],

                        "metrics":
                            result[
                                "metrics"
                            ],

                        "trade_count":
                            len(
                                result[
                                    "trades"
                                ]
                            ),
                    }

                    for index, result
                    in enumerate(
                        ranked
                    )
                ),

            "automatic_promotion":
                False,

            "research_only":
                True,
        }


strategy_comparator = (
    StrategyComparator()
)
