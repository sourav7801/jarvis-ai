from __future__ import annotations

from bisect import (
    bisect_right,
)

from datetime import (
    datetime,
    timezone,
)


def _timestamp(
    value,
):

    if isinstance(
        value,
        datetime,
    ):

        result = value


    else:

        text = str(
            value
        )


        if text.endswith(
            "Z"
        ):

            text = (
                text[:-1]
                + "+00:00"
            )


        result = datetime.fromisoformat(
            text
        )


    if result.tzinfo is None:

        result = result.replace(
            tzinfo=timezone.utc
        )


    return result.astimezone(
        timezone.utc
    )


def _bar_value(
    bar,
    name,
):

    if isinstance(
        bar,
        dict,
    ):

        return bar[
            name
        ]


    return getattr(
        bar,
        name
    )


def synchronize_derivatives(
    underlying_bars,
    futures_bars,
    chain_snapshots,
    *,
    max_chain_age_seconds=300,
):

    underlying = sorted(
        tuple(
            underlying_bars
        ),
        key=lambda bar:
            _timestamp(
                _bar_value(
                    bar,
                    "timestamp",
                )
            ),
    )


    futures = sorted(
        tuple(
            futures_bars
        ),
        key=lambda bar:
            _timestamp(
                _bar_value(
                    bar,
                    "timestamp",
                )
            ),
    )


    chains = sorted(
        tuple(
            chain_snapshots
        ),
        key=lambda row:
            _timestamp(
                row[
                    "captured_at"
                ]
            ),
    )


    futures_times = [
        _timestamp(
            _bar_value(
                bar,
                "timestamp",
            )
        )

        for bar in futures
    ]


    chain_times = [
        _timestamp(
            row[
                "captured_at"
            ]
        )

        for row in chains
    ]


    output = []


    for spot_bar in underlying:

        spot_time = _timestamp(
            _bar_value(
                spot_bar,
                "timestamp",
            )
        )


        future_index = (
            bisect_right(
                futures_times,
                spot_time,
            )
            - 1
        )


        chain_index = (
            bisect_right(
                chain_times,
                spot_time,
            )
            - 1
        )


        if future_index < 0:

            continue


        if chain_index < 0:

            continue


        future_bar = futures[
            future_index
        ]


        chain = chains[
            chain_index
        ]


        chain_time = chain_times[
            chain_index
        ]


        age = (
            spot_time
            - chain_time
        ).total_seconds()


        if age < 0:

            raise RuntimeError(
                "Future chain data leakage detected."
            )


        if age > float(
            max_chain_age_seconds
        ):

            continue


        spot_close = float(
            _bar_value(
                spot_bar,
                "close",
            )
        )


        future_close = float(
            _bar_value(
                future_bar,
                "close",
            )
        )


        output.append(
            {
                "timestamp":
                    spot_time.isoformat(),

                "spot_close":
                    spot_close,

                "future_close":
                    future_close,

                "futures_basis":
                    (
                        future_close
                        - spot_close
                    ),

                "chain_captured_at":
                    chain[
                        "captured_at"
                    ],

                "chain_age_seconds":
                    age,

                "pcr_oi":
                    chain.get(
                        "pcr_oi"
                    ),

                "atm_iv":
                    chain.get(
                        "atm_iv"
                    ),

                "atm_skew":
                    chain.get(
                        "atm_skew"
                    ),

                "call_oi":
                    chain.get(
                        "call_oi"
                    ),

                "put_oi":
                    chain.get(
                        "put_oi"
                    ),

                "atm_strike":
                    chain.get(
                        "atm_strike"
                    ),

                "future_data_after_signal":
                    False,

                "chain_data_after_signal":
                    False,
            }
        )


    return {
        "rows":
            tuple(
                output
            ),

        "row_count":
            len(
                output
            ),

        "backward_asof_only":
            True,

        "future_data_leakage":
            False,

        "research_only":
            True,
    }
