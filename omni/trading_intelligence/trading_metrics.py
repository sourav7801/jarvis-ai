from __future__ import annotations

from math import (
    sqrt,
)

from statistics import (
    fmean,
    pstdev,
)


def _trade_net_pnl(
    trade,
):

    if "net_pnl" in trade:

        return float(
            trade[
                "net_pnl"
            ]
        )


    if "pnl" in trade:

        return float(
            trade[
                "pnl"
            ]
        )


    return (
        float(
            trade.get(
                "gross_pnl",
                0.0,
            )
        )
        - float(
            trade.get(
                "fees",
                0.0,
            )
        )
        - float(
            trade.get(
                "slippage",
                0.0,
            )
        )
    )


def _max_drawdown(
    values,
):

    equity = 0.0

    peak = 0.0

    maximum = 0.0


    for pnl in values:

        equity += pnl

        peak = max(
            peak,
            equity,
        )

        drawdown = (
            peak
            - equity
        )

        maximum = max(
            maximum,
            drawdown,
        )


    return maximum


def evaluate_trades(
    trades,
):

    trades = [
        dict(
            trade
        )

        for trade in trades
    ]


    pnl = [
        _trade_net_pnl(
            trade
        )

        for trade in trades
    ]


    count = len(
        pnl
    )


    if count == 0:

        return {
            "trades":
                0,

            "net_pnl":
                0.0,

            "win_rate":
                0.0,

            "profit_factor":
                None,

            "expectancy":
                0.0,

            "max_drawdown":
                0.0,

            "sharpe_per_trade":
                None,

            "avg_win":
                None,

            "avg_loss":
                None,

            "payoff_ratio":
                None,

            "gross_profit":
                0.0,

            "gross_loss":
                0.0,

            "fees":
                0.0,

            "slippage":
                0.0,

            "turnover":
                0.0,

            "research_only":
                True,
        }


    wins = [
        value

        for value in pnl

        if value > 0
    ]


    losses = [
        value

        for value in pnl

        if value < 0
    ]


    gross_profit = sum(
        wins
    )

    gross_loss = abs(
        sum(
            losses
        )
    )


    avg_win = (
        fmean(
            wins
        )
        if wins
        else None
    )


    avg_loss = (
        abs(
            fmean(
                losses
            )
        )
        if losses
        else None
    )


    profit_factor = (
        gross_profit
        / gross_loss
        if gross_loss > 0
        else (
            float(
                "inf"
            )
            if gross_profit > 0
            else None
        )
    )


    payoff = (
        avg_win
        / avg_loss
        if (
            avg_win is not None
            and avg_loss
        )
        else None
    )


    sigma = (
        pstdev(
            pnl
        )
        if count > 1
        else 0.0
    )


    sharpe = (
        (
            fmean(
                pnl
            )
            / sigma
            * sqrt(
                count
            )
        )
        if sigma > 0
        else None
    )


    return {
        "trades":
            count,

        "net_pnl":
            sum(
                pnl
            ),

        "win_rate":
            (
                len(
                    wins
                )
                / count
            ),

        "loss_rate":
            (
                len(
                    losses
                )
                / count
            ),

        "profit_factor":
            profit_factor,

        "expectancy":
            fmean(
                pnl
            ),

        "max_drawdown":
            _max_drawdown(
                pnl
            ),

        "sharpe_per_trade":
            sharpe,

        "avg_win":
            avg_win,

        "avg_loss":
            avg_loss,

        "payoff_ratio":
            payoff,

        "gross_profit":
            gross_profit,

        "gross_loss":
            gross_loss,

        "fees":
            sum(
                float(
                    trade.get(
                        "fees",
                        0.0,
                    )
                )

                for trade
                in trades
            ),

        "slippage":
            sum(
                float(
                    trade.get(
                        "slippage",
                        0.0,
                    )
                )

                for trade
                in trades
            ),

        "turnover":
            sum(
                abs(
                    float(
                        trade.get(
                            "turnover",
                            0.0,
                        )
                    )
                )

                for trade
                in trades
            ),

        "research_only":
            True,
    }
