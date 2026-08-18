from __future__ import annotations

from collections import (
    defaultdict,
)

from statistics import (
    fmean,
)


from omni.trading_intelligence.derivatives_history_store import (
    derivatives_history_store,
)


def _percentile_rank(
    history,
    current,
):

    if (
        current is None
        or not history
    ):

        return None


    values = [
        float(
            value
        )

        for value in history

        if value is not None
    ]


    if not values:

        return None


    return (
        sum(
            1

            for value in values

            if value <= float(
                current
            )
        )
        / len(
            values
        )
        * 100.0
    )


def _range_rank(
    history,
    current,
):

    if current is None:

        return None


    values = [
        float(
            value
        )

        for value in history

        if value is not None
    ]


    if len(
        values
    ) < 2:

        return None


    low = min(
        values
    )

    high = max(
        values
    )


    if high == low:

        return 50.0


    return (
        (
            float(
                current
            )
            - low
        )
        / (
            high
            - low
        )
        * 100.0
    )


class DerivativesHistoryAnalytics:

    def analyze(
        self,
        symbol,
        *,
        lookback=252,
    ):

        history = (
            derivatives_history_store
            .history(
                symbol,
                limit=lookback,
            )
        )


        if not history:

            return {
                "symbol":
                    str(
                        symbol
                    ),

                "available":
                    False,

                "snapshot_count":
                    0,

                "research_only":
                    True,
            }


        latest = history[
            0
        ]


        previous = (
            history[
                1
            ]

            if len(
                history
            ) > 1

            else None
        )


        iv_history = [
            row.get(
                "atm_iv"
            )

            for row in history

            if row.get(
                "atm_iv"
            ) is not None
        ]


        current_iv = latest.get(
            "atm_iv"
        )


        delta_call_oi = None

        delta_put_oi = None


        if previous is not None:

            if (
                latest.get(
                    "call_oi"
                )
                is not None
                and previous.get(
                    "call_oi"
                )
                is not None
            ):

                delta_call_oi = (
                    latest[
                        "call_oi"
                    ]
                    - previous[
                        "call_oi"
                    ]
                )


            if (
                latest.get(
                    "put_oi"
                )
                is not None
                and previous.get(
                    "put_oi"
                )
                is not None
            ):

                delta_put_oi = (
                    latest[
                        "put_oi"
                    ]
                    - previous[
                        "put_oi"
                    ]
                )


        by_expiry = {}


        for row in history:

            expiry = row.get(
                "selected_expiry"
            )


            if (
                expiry
                and expiry
                not in by_expiry
            ):

                by_expiry[
                    expiry
                ] = {
                    "captured_at":
                        row[
                            "captured_at"
                        ],

                    "atm_iv":
                        row.get(
                            "atm_iv"
                        ),

                    "atm_skew":
                        row.get(
                            "atm_skew"
                        ),

                    "pcr_oi":
                        row.get(
                            "pcr_oi"
                        ),
                }


        return {
            "symbol":
                str(
                    symbol
                ),

            "available":
                True,

            "snapshot_count":
                len(
                    history
                ),

            "latest":
                latest,

            "atm_iv_rank":
                _range_rank(
                    iv_history,
                    current_iv,
                ),

            "atm_iv_percentile":
                _percentile_rank(
                    iv_history,
                    current_iv,
                ),

            "atm_skew":
                latest.get(
                    "atm_skew"
                ),

            "pcr_oi":
                latest.get(
                    "pcr_oi"
                ),

            "delta_call_oi":
                delta_call_oi,

            "delta_put_oi":
                delta_put_oi,

            "term_structure":
                by_expiry,

            "average_atm_iv":
                (
                    fmean(
                        iv_history
                    )

                    if iv_history

                    else None
                ),

            "predictive_guarantee":
                False,

            "research_only":
                True,
        }


derivatives_history_analytics = (
    DerivativesHistoryAnalytics()
)
