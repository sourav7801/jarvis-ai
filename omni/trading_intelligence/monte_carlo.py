from __future__ import annotations

import random

from statistics import (
    fmean,
)


def _percentile(
    values,
    percentile,
):

    values = sorted(
        float(value)
        for value in values
    )


    if not values:
        return 0.0


    index = (
        len(values)
        - 1
    ) * float(percentile)


    lower = int(index)
    upper = min(
        lower + 1,
        len(values) - 1,
    )


    fraction = (
        index
        - lower
    )


    return (
        values[lower]
        * (
            1.0
            - fraction
        )
        + values[upper]
        * fraction
    )


class MonteCarloTradeSimulator:

    MAX_ITERATIONS = 5000


    @staticmethod
    def _drawdown(
        pnl_sequence,
        initial_capital,
    ):

        equity = float(
            initial_capital
        )

        peak = equity
        max_drawdown = 0.0


        for pnl in pnl_sequence:

            equity += float(pnl)

            peak = max(
                peak,
                equity,
            )

            max_drawdown = max(
                max_drawdown,
                peak - equity,
            )


        return (
            equity,
            max_drawdown,
        )


    def run(
        self,
        trades,
        *,
        initial_capital,
        iterations=1000,
        random_seed=1,
        bootstrap=True,
    ):

        trades = tuple(trades)

        if not trades:
            raise ValueError(
                "Monte Carlo requires at least one trade."
            )


        iterations = int(iterations)

        if (
            iterations <= 0
            or iterations > self.MAX_ITERATIONS
        ):
            raise ValueError(
                "Invalid Monte Carlo iteration count."
            )


        pnl = [
            float(
                trade.get(
                    "net_pnl",
                    0.0,
                )
            )

            for trade in trades
        ]


        rng = random.Random(
            random_seed
        )


        endings = []
        drawdowns = []


        for _ in range(iterations):

            if bootstrap:

                sequence = [
                    rng.choice(pnl)

                    for _ in range(
                        len(pnl)
                    )
                ]

            else:

                sequence = list(pnl)

                rng.shuffle(
                    sequence
                )


            ending, drawdown = (
                self._drawdown(
                    sequence,
                    initial_capital,
                )
            )


            endings.append(
                ending
            )

            drawdowns.append(
                drawdown
            )


        initial_capital = float(
            initial_capital
        )


        losing_runs = sum(
            1

            for value in endings

            if value < initial_capital
        )


        return {
            "success":
                True,

            "iterations":
                iterations,

            "trade_count":
                len(pnl),

            "bootstrap":
                bool(bootstrap),

            "median_ending_equity":
                _percentile(
                    endings,
                    0.50,
                ),

            "ending_equity_p05":
                _percentile(
                    endings,
                    0.05,
                ),

            "ending_equity_p95":
                _percentile(
                    endings,
                    0.95,
                ),

            "median_max_drawdown":
                _percentile(
                    drawdowns,
                    0.50,
                ),

            "max_drawdown_p95":
                _percentile(
                    drawdowns,
                    0.95,
                ),

            "loss_probability":
                (
                    losing_runs
                    / iterations
                ),

            "average_ending_equity":
                fmean(endings),

            "research_only":
                True,
        }


monte_carlo_trade_simulator = (
    MonteCarloTradeSimulator()
)
