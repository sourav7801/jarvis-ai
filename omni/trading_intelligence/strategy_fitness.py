from __future__ import annotations

from math import (
    isfinite,
    tanh,
)

from statistics import (
    fmean,
    pstdev,
)


def _finite(
    value,
    default=0.0,
):

    if value is None:

        return float(
            default
        )


    value = float(
        value
    )


    if not isfinite(
        value
    ):

        return float(
            default
        )


    return value


def result_fitness(
    result,
    *,
    minimum_trades=5,
):

    metrics = result[
        "metrics"
    ]


    trades = int(
        metrics.get(
            "trades",
            0,
        )
    )


    return_pct = _finite(
        metrics.get(
            "return_pct"
        )
    )


    expectancy = _finite(
        metrics.get(
            "expectancy"
        )
    )


    average_loss = abs(
        _finite(
            metrics.get(
                "avg_loss"
            ),
            1.0,
        )
    )


    if average_loss <= 0:

        average_loss = 1.0


    expectancy_ratio = (
        expectancy
        / average_loss
    )


    profit_factor = _finite(
        metrics.get(
            "profit_factor"
        )
    )


    win_rate = max(
        0.0,
        min(
            1.0,
            _finite(
                metrics.get(
                    "win_rate"
                )
            ),
        ),
    )


    drawdown_pct = max(
        0.0,
        _finite(
            metrics.get(
                "max_drawdown_pct"
            )
        ),
    )


    return_score = (
        tanh(
            return_pct
            * 8.0
        )
        * 30.0
    )


    expectancy_score = (
        tanh(
            expectancy_ratio
        )
        * 20.0
    )


    pf_score = (
        max(
            0.0,
            min(
                3.0,
                profit_factor,
            )
        )
        / 3.0
        * 20.0
    )


    win_score = (
        win_rate
        * 10.0
    )


    drawdown_penalty = (
        min(
            1.0,
            drawdown_pct
        )
        * 35.0
    )


    trade_penalty = (
        (
            minimum_trades
            - trades
        )
        / minimum_trades
        * 20.0

        if trades
        < minimum_trades

        else 0.0
    )


    score = (
        return_score
        + expectancy_score
        + pf_score
        + win_score
        - drawdown_penalty
        - trade_penalty
    )


    return {
        "score":
            score,

        "components": {
            "return_score":
                return_score,

            "expectancy_score":
                expectancy_score,

            "profit_factor_score":
                pf_score,

            "win_rate_score":
                win_score,

            "drawdown_penalty":
                drawdown_penalty,

            "trade_count_penalty":
                trade_penalty,
        },

        "trades":
            trades,

        "research_only":
            True,
    }


def multi_regime_fitness(
    regime_results,
):

    if not regime_results:

        raise ValueError(
            "At least one regime result required."
        )


    regime_scores = {
        regime:
            result_fitness(
                result
            )[
                "score"
            ]

        for regime, result
        in regime_results.items()
    }


    values = list(
        regime_scores.values()
    )


    average = fmean(
        values
    )


    stability_penalty = (
        pstdev(
            values
        )
        if len(
            values
        ) > 1
        else 0.0
    )


    worst = min(
        values
    )


    robust_score = (
        average
        - 0.50
        * stability_penalty
        + 0.20
        * worst
    )


    return {
        "score":
            robust_score,

        "average_regime_score":
            average,

        "stability_penalty":
            stability_penalty,

        "worst_regime_score":
            worst,

        "regime_scores":
            regime_scores,

        "research_only":
            True,
    }
