from __future__ import annotations

from collections import (
    Counter,
)


def nautilus_portfolio_research(
    results,
):

    results = tuple(
        results
    )


    if not results:

        raise ValueError(
            "At least one research result is required."
        )


    total_fills = 0

    total_positions = 0

    known_pnl = []

    kinds = Counter()

    instruments = []


    for result in results:

        if (
            result.get(
                "research_only"
            )
            is not True
        ):

            raise ValueError(
                "Portfolio accepts research-only results."
            )


        if (
            result.get(
                "live_execution"
            )
            is not False
        ):

            raise ValueError(
                "Live result rejected."
            )


        if (
            result.get(
                "broker_adapter"
            )
            is not False
        ):

            raise ValueError(
                "Broker-connected result rejected."
            )


        instrument = dict(
            result.get(
                "instrument",
                {}
            )
        )


        kind = str(
            instrument.get(
                "research_kind",
                "unknown",
            )
        )


        kinds[
            kind
        ] += 1


        instruments.append(
            instrument
        )


        total_fills += int(
            result.get(
                "fill_count",
                0,
            )
        )


        total_positions += int(
            result.get(
                "position_report_rows",
                0,
            )
        )


        pnl = result.get(
            "realized_pnl_numeric"
        )


        if pnl is not None:

            known_pnl.append(
                float(
                    pnl
                )
            )


    return {
        "success":
            True,

        "result_count":
            len(
                results
            ),

        "instrument_kinds":
            dict(
                kinds
            ),

        "instruments":
            tuple(
                instruments
            ),

        "total_fills":
            total_fills,

        "total_position_rows":
            total_positions,

        "known_realized_pnl_count":
            len(
                known_pnl
            ),

        "aggregate_known_realized_pnl":
            (
                sum(
                    known_pnl
                )
                if known_pnl
                else None
            ),

        "multi_instrument_research":
            True,

        "multi_strategy_foundation":
            True,

        "capital_allocation":
            False,

        "broker_position_sizing":
            False,

        "portfolio_live_execution":
            False,

        "automatic_portfolio_rebalance":
            False,

        "research_only":
            True,
    }
