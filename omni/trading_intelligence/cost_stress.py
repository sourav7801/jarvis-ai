from __future__ import annotations

from dataclasses import replace


from omni.trading_intelligence.historical_backtester import (
    historical_backtester,
)

from omni.trading_intelligence.strategy_fitness import (
    result_fitness,
)


DEFAULT_SCENARIOS = (
    {
        "name":
            "baseline",

        "fee_multiplier":
            1.0,

        "extra_slippage_bps":
            0.0,

        "extra_spread_bps":
            0.0,
    },

    {
        "name":
            "moderate_stress",

        "fee_multiplier":
            1.5,

        "extra_slippage_bps":
            5.0,

        "extra_spread_bps":
            5.0,
    },

    {
        "name":
            "severe_stress",

        "fee_multiplier":
            2.0,

        "extra_slippage_bps":
            15.0,

        "extra_spread_bps":
            15.0,
    },
)


def _scaled_cost(
    cost,
    scenario,
):

    multiplier = float(
        scenario[
            "fee_multiplier"
        ]
    )


    return replace(
        cost,

        brokerage_bps=
            cost.brokerage_bps
            * multiplier,

        exchange_bps=
            cost.exchange_bps
            * multiplier,

        other_bps=
            cost.other_bps
            * multiplier,

        tax_bps_buy=
            cost.tax_bps_buy
            * multiplier,

        tax_bps_sell=
            cost.tax_bps_sell
            * multiplier,

        fixed_per_order=
            cost.fixed_per_order
            * multiplier,

        per_contract=
            cost.per_contract
            * multiplier,

        slippage_bps=
            (
                cost.slippage_bps
                * multiplier
                + float(
                    scenario[
                        "extra_slippage_bps"
                    ]
                )
            ),

        spread_bps=
            (
                cost.spread_bps
                * multiplier
                + float(
                    scenario[
                        "extra_spread_bps"
                    ]
                )
            ),
    )


class CostStressTester:

    def run(
        self,
        bars,
        strategy,
        base_config,
        *,
        scenarios=DEFAULT_SCENARIOS,
    ):

        results = []


        for scenario in scenarios:

            stressed_cost = _scaled_cost(
                base_config.cost,
                scenario,
            )


            config = replace(
                base_config,
                cost=stressed_cost,
            )


            result = historical_backtester.run(
                bars,
                strategy,
                config,
            )


            fitness = result_fitness(
                result
            )


            results.append(
                {
                    "scenario":
                        dict(
                            scenario
                        ),

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


        surviving = sum(
            1

            for item in results

            if item[
                "profitable"
            ]
        )


        return {
            "success":
                True,

            "scenarios":
                tuple(results),

            "scenario_count":
                len(results),

            "profitable_scenarios":
                surviving,

            "survival_rate":
                (
                    surviving
                    / len(results)
                    if results
                    else 0.0
                ),

            "hardcoded_current_fee_schedule":
                False,

            "research_only":
                True,
        }


cost_stress_tester = (
    CostStressTester()
)
