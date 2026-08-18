from __future__ import annotations


def reconcile_native_nautilus(
    native_result,
    nautilus_result,
):

    native_trades = tuple(
        native_result.get(
            "trades",
            ()
        )
    )


    native_metrics = dict(
        native_result.get(
            "metrics",
            {}
        )
    )


    native_pnl = native_metrics.get(
        "net_pnl"
    )


    nautilus_pnl = (
        nautilus_result.get(
            "realized_pnl_numeric"
        )
    )


    pnl_gap = None

    pnl_gap_pct = None


    if (
        native_pnl is not None
        and nautilus_pnl is not None
    ):

        native_pnl = float(
            native_pnl
        )

        nautilus_pnl = float(
            nautilus_pnl
        )


        pnl_gap = (
            nautilus_pnl
            - native_pnl
        )


        pnl_gap_pct = (
            pnl_gap
            / max(
                abs(
                    native_pnl
                ),
                1.0,
            )
        )


    return {
        "success":
            True,

        "native_engine":
            "jarvis_v2",

        "nautilus_engine":
            nautilus_result.get(
                "engine"
            ),

        "native_trade_count":
            len(
                native_trades
            ),

        "nautilus_fill_count":
            int(
                nautilus_result.get(
                    "fill_count",
                    0,
                )
            ),

        "nautilus_position_rows":
            int(
                nautilus_result.get(
                    "position_report_rows",
                    0,
                )
            ),

        "native_net_pnl":
            native_pnl,

        "nautilus_realized_pnl":
            nautilus_pnl,

        "pnl_gap":
            pnl_gap,

        "pnl_gap_pct":
            pnl_gap_pct,

        "pnl_comparable":
            (
                native_pnl is not None
                and nautilus_pnl is not None
            ),

        "timing_semantics": {
            "jarvis_v2":
                "signal_close_to_next_bar_open",

            "nautilus":
                "event_driven_bar_execution",

            "direct_equivalence_expected":
                False,
        },

        "interpretation":
            (
                "Differences are evidence to investigate, "
                "not an automatic failure, because the engines "
                "use intentionally different bar-execution semantics."
            ),

        "automatic_strategy_decision":
            False,

        "production_promotion":
            False,

        "research_only":
            True,
    }
