from __future__ import annotations

from statistics import (
    fmean,
)


def _clean(
    values,
):

    return [
        float(
            value
        )

        for value in values

        if value is not None
    ]


def iv_rank(
    current_iv,
    history,
):

    history = _clean(
        history
    )


    if not history:

        return None


    current = float(
        current_iv
    )


    low = min(
        history
    )

    high = max(
        history
    )


    if high == low:

        return 50.0


    return max(
        0.0,
        min(
            100.0,
            (
                current
                - low
            )
            / (
                high
                - low
            )
            * 100.0,
        ),
    )


def iv_percentile(
    current_iv,
    history,
):

    history = _clean(
        history
    )


    if not history:

        return None


    current = float(
        current_iv
    )


    count = sum(
        1

        for value in history

        if value <= current
    )


    return (
        count
        / len(
            history
        )
        * 100.0
    )


def strike_iv_skew(
    snapshot,
):

    rows = []


    for strike in snapshot.strikes:

        calls = [
            contract

            for contract
            in snapshot.contracts

            if (
                contract.strike
                == strike
                and contract.option_type
                == "call"
                and contract.implied_volatility
                is not None
            )
        ]


        puts = [
            contract

            for contract
            in snapshot.contracts

            if (
                contract.strike
                == strike
                and contract.option_type
                == "put"
                and contract.implied_volatility
                is not None
            )
        ]


        call_iv = (
            fmean(
                contract.implied_volatility
                for contract in calls
            )
            if calls
            else None
        )


        put_iv = (
            fmean(
                contract.implied_volatility
                for contract in puts
            )
            if puts
            else None
        )


        rows.append(
            {
                "strike":
                    strike,

                "distance_pct":
                    (
                        strike
                        / snapshot.spot
                        - 1.0
                    ),

                "call_iv":
                    call_iv,

                "put_iv":
                    put_iv,

                "put_minus_call_iv":
                    (
                        put_iv
                        - call_iv

                        if (
                            put_iv is not None
                            and call_iv is not None
                        )

                        else None
                    ),
            }
        )


    return tuple(
        rows
    )


def iv_term_structure(
    points,
):

    normalized = []


    for item in points:

        expiry = str(
            item[
                "expiry"
            ]
        )

        days = float(
            item[
                "days_to_expiry"
            ]
        )

        atm_iv = float(
            item[
                "atm_iv"
            ]
        )


        normalized.append(
            {
                "expiry":
                    expiry,

                "days_to_expiry":
                    days,

                "atm_iv":
                    atm_iv,
            }
        )


    normalized.sort(
        key=lambda item:
            item[
                "days_to_expiry"
            ]
    )


    slopes = []


    for left, right in zip(
        normalized,
        normalized[
            1:
        ],
    ):

        day_difference = (
            right[
                "days_to_expiry"
            ]
            - left[
                "days_to_expiry"
            ]
        )


        slopes.append(
            {
                "from_expiry":
                    left[
                        "expiry"
                    ],

                "to_expiry":
                    right[
                        "expiry"
                    ],

                "iv_change":
                    (
                        right[
                            "atm_iv"
                        ]
                        - left[
                            "atm_iv"
                        ]
                    ),

                "iv_change_per_day":
                    (
                        (
                            right[
                                "atm_iv"
                            ]
                            - left[
                                "atm_iv"
                            ]
                        )
                        / day_difference

                        if day_difference != 0

                        else None
                    ),
            }
        )


    return {
        "points":
            tuple(
                normalized
            ),

        "slopes":
            tuple(
                slopes
            ),

        "research_only":
            True,
    }
