from __future__ import annotations

from omni.trading_intelligence.trading_metrics import (
    evaluate_trades,
)


def paper_performance_summary(
    strategy_trades,
):

    output = {}


    for strategy_id, trades in (
        strategy_trades.items()
    ):

        trades = tuple(
            trades
        )


        metrics = evaluate_trades(
            trades
        )


        output[
            str(
                strategy_id
            )
        ] = {
            "trade_count":
                len(
                    trades
                ),

            "metrics":
                metrics,
        }


    ranking = sorted(
        output.items(),
        key=lambda item:
            float(
                item[
                    1
                ][
                    "metrics"
                ].get(
                    "net_pnl",
                    0.0,
                )
            ),
        reverse=True,
    )


    return {
        "strategies":
            output,

        "ranking":
            tuple(
                strategy_id

                for strategy_id, _
                in ranking
            ),

        "paper_only":
            True,

        "live_execution":
            False,

        "research_only":
            True,
    }
