from __future__ import annotations

from dataclasses import (
    replace,
)

from itertools import (
    product,
)


from omni.trading_intelligence.historical_backtester import (
    historical_backtester,
)


SWEEPABLE_FIELDS = {
    "quantity",
    "contract_multiplier",
    "stop_loss_pct",
    "target_pct",
    "trailing_stop_pct",
    "max_bars_in_trade",
    "exit_on_opposite_signal",
}


HIGHER_IS_BETTER = {
    "net_pnl",
    "return_pct",
    "win_rate",
    "profit_factor",
    "expectancy",
    "payoff_ratio",
    "sharpe_per_trade",
}


LOWER_IS_BETTER = {
    "max_drawdown",
    "max_drawdown_pct",
    "fees",
    "slippage",
}


class ParameterSweepEngine:

    MAX_COMBINATIONS = 200


    @staticmethod
    def _score(
        result,
        objective,
    ):

        value = (
            result[
                "metrics"
            ]
            .get(
                objective
            )
        )


        if value is None:

            return float(
                "-inf"
            )


        value = float(
            value
        )


        if objective in LOWER_IS_BETTER:

            return -value


        return value


    def run(
        self,
        bars,
        strategy,
        base_config,
        grid,
        *,
        objective="net_pnl",
    ):

        if (
            objective
            not in HIGHER_IS_BETTER
            and objective
            not in LOWER_IS_BETTER
        ):

            raise ValueError(
                "Unsupported sweep objective."
            )


        grid = dict(
            grid
        )


        unknown = (
            set(
                grid
            )
            - SWEEPABLE_FIELDS
        )


        if unknown:

            raise ValueError(
                "Unsupported sweep fields: "
                + repr(
                    sorted(
                        unknown
                    )
                )
            )


        keys = tuple(
            grid
        )


        values = [
            tuple(
                grid[
                    key
                ]
            )

            for key in keys
        ]


        combinations = 1


        for options in values:

            combinations *= len(
                options
            )


        if combinations > self.MAX_COMBINATIONS:

            raise ValueError(
                "Parameter sweep exceeds "
                + str(
                    self.MAX_COMBINATIONS
                )
                + " combinations."
            )


        results = []


        for combination in product(
            *values
        ):

            overrides = dict(
                zip(
                    keys,
                    combination,
                )
            )


            config = replace(
                base_config,
                **overrides
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
                {
                    "parameters":
                        overrides,

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

                    "result":
                        result,
                }
            )


        ranked = sorted(
            results,
            key=lambda item:
                self._score(
                    item[
                        "result"
                    ],
                    objective,
                ),
            reverse=True,
        )


        return {
            "success":
                True,

            "objective":
                objective,

            "combinations":
                combinations,

            "ranked":
                tuple(
                    ranked
                ),

            "best_candidate":
                (
                    ranked[
                        0
                    ]
                    if ranked
                    else None
                ),

            "automatic_promotion":
                False,

            "research_only":
                True,
        }


parameter_sweep_engine = (
    ParameterSweepEngine()
)
