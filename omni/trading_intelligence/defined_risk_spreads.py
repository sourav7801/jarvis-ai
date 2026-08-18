from __future__ import annotations


SUPPORTED = {
    "bull_call",
    "bear_call",
    "bear_put",
    "bull_put",
}


def build_vertical_spread(
    kind,
    *,
    lower_strike,
    higher_strike,
    lower_premium,
    higher_premium,
    quantity=1.0,
    multiplier=1.0,
):

    kind = str(
        kind
    ).strip().lower()


    if kind not in SUPPORTED:

        raise ValueError(
            "Unsupported defined-risk vertical spread."
        )


    lower = float(
        lower_strike
    )

    higher = float(
        higher_strike
    )


    if higher <= lower:

        raise ValueError(
            "higher_strike must exceed lower_strike."
        )


    lower_premium = float(
        lower_premium
    )

    higher_premium = float(
        higher_premium
    )

    quantity = float(
        quantity
    )

    multiplier = float(
        multiplier
    )


    if (
        quantity <= 0
        or multiplier <= 0
    ):

        raise ValueError(
            "quantity and multiplier must be positive."
        )


    width = (
        higher
        - lower
    )


    if kind == "bull_call":

        option_type = "call"

        legs = (
            {
                "side":
                    "BUY",

                "strike":
                    lower,

                "premium":
                    lower_premium,
            },

            {
                "side":
                    "SELL",

                "strike":
                    higher,

                "premium":
                    higher_premium,
            },
        )


        net_debit = (
            lower_premium
            - higher_premium
        )


        max_loss = max(
            0.0,
            net_debit
        )


        max_profit = max(
            0.0,
            width
            - net_debit
        )


        breakeven = (
            lower
            + net_debit
        )


    elif kind == "bear_call":

        option_type = "call"

        legs = (
            {
                "side":
                    "SELL",

                "strike":
                    lower,

                "premium":
                    lower_premium,
            },

            {
                "side":
                    "BUY",

                "strike":
                    higher,

                "premium":
                    higher_premium,
            },
        )


        credit = (
            lower_premium
            - higher_premium
        )


        max_profit = max(
            0.0,
            credit
        )


        max_loss = max(
            0.0,
            width
            - credit
        )


        breakeven = (
            lower
            + credit
        )


    elif kind == "bear_put":

        option_type = "put"

        legs = (
            {
                "side":
                    "SELL",

                "strike":
                    lower,

                "premium":
                    lower_premium,
            },

            {
                "side":
                    "BUY",

                "strike":
                    higher,

                "premium":
                    higher_premium,
            },
        )


        net_debit = (
            higher_premium
            - lower_premium
        )


        max_loss = max(
            0.0,
            net_debit
        )


        max_profit = max(
            0.0,
            width
            - net_debit
        )


        breakeven = (
            higher
            - net_debit
        )


    else:

        option_type = "put"

        legs = (
            {
                "side":
                    "BUY",

                "strike":
                    lower,

                "premium":
                    lower_premium,
            },

            {
                "side":
                    "SELL",

                "strike":
                    higher,

                "premium":
                    higher_premium,
            },
        )


        credit = (
            higher_premium
            - lower_premium
        )


        max_profit = max(
            0.0,
            credit
        )


        max_loss = max(
            0.0,
            width
            - credit
        )


        breakeven = (
            higher
            - credit
        )


    scale = (
        quantity
        * multiplier
    )


    return {
        "kind":
            kind,

        "option_type":
            option_type,

        "legs":
            legs,

        "lower_strike":
            lower,

        "higher_strike":
            higher,

        "width":
            width,

        "breakeven":
            breakeven,

        "max_profit":
            max_profit
            * scale,

        "max_loss":
            max_loss
            * scale,

        "quantity":
            quantity,

        "multiplier":
            multiplier,

        "defined_risk":
            True,

        "naked_short":
            False,

        "research_only":
            True,
    }


def vertical_payoff(
    spread,
    settlement,
):

    settlement = float(
        settlement
    )


    option_type = spread[
        "option_type"
    ]


    gross = 0.0

    premium_cashflow = 0.0


    for leg in spread[
        "legs"
    ]:

        strike = float(
            leg[
                "strike"
            ]
        )

        premium = float(
            leg[
                "premium"
            ]
        )


        side = (
            1.0
            if leg[
                "side"
            ] == "BUY"
            else -1.0
        )


        if option_type == "call":

            intrinsic = max(
                0.0,
                settlement
                - strike,
            )


        else:

            intrinsic = max(
                0.0,
                strike
                - settlement,
            )


        gross += (
            side
            * intrinsic
        )


        premium_cashflow += (
            -side
            * premium
        )


    pnl_per_unit = (
        gross
        + premium_cashflow
    )


    return (
        pnl_per_unit
        * float(
            spread[
                "quantity"
            ]
        )
        * float(
            spread[
                "multiplier"
            ]
        )
    )
