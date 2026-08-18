from __future__ import annotations


def _direction(
    value,
    threshold=0.0,
):

    if value is None:

        return 0.0


    value = float(
        value
    )


    if value > threshold:

        return 1.0


    if value < -threshold:

        return -1.0


    return 0.0


def derivatives_confirmation(
    chain_analysis,
    *,
    underlying_return=None,
    futures_return=None,
    futures_basis_pct=None,
):

    components = []


    if underlying_return is not None:

        components.append(
            (
                "underlying_momentum",
                _direction(
                    underlying_return
                ),
                1.0,
            )
        )


    if futures_return is not None:

        components.append(
            (
                "futures_momentum",
                _direction(
                    futures_return
                ),
                1.0,
            )
        )


    if futures_basis_pct is not None:

        components.append(
            (
                "futures_basis",
                _direction(
                    futures_basis_pct
                ),
                0.5,
            )
        )


    pcr = chain_analysis.get(
        "pcr_oi"
    )


    if pcr is not None:

        if pcr > 1.10:

            pcr_direction = 1.0

        elif pcr < 0.90:

            pcr_direction = -1.0

        else:

            pcr_direction = 0.0


        components.append(
            (
                "pcr_oi_heuristic",
                pcr_direction,
                0.5,
            )
        )


    call_doi = float(
        chain_analysis.get(
            "call_change_in_oi"
        )
        or 0.0
    )


    put_doi = float(
        chain_analysis.get(
            "put_change_in_oi"
        )
        or 0.0
    )


    if (
        call_doi != 0
        or put_doi != 0
    ):

        components.append(
            (
                "change_in_oi_structure",
                (
                    1.0
                    if put_doi > call_doi
                    else (
                        -1.0
                        if call_doi > put_doi
                        else 0.0
                    )
                ),
                0.75,
            )
        )


    weighted_sum = sum(
        direction
        * weight

        for _, direction, weight
        in components
    )


    total_weight = sum(
        weight

        for _, _, weight
        in components
    )


    score = (
        weighted_sum
        / total_weight
        if total_weight > 0
        else 0.0
    )


    liquidity_score = float(
        chain_analysis.get(
            "chain_liquidity_score"
        )
        or 0.0
    )


    if liquidity_score < 20:

        confidence = 0.25


    elif liquidity_score < 40:

        confidence = 0.50


    elif liquidity_score < 70:

        confidence = 0.70


    else:

        confidence = 0.85


    if score >= 0.45:

        regime = "BULLISH_CONFIRMATION"


    elif score <= -0.45:

        regime = "BEARISH_CONFIRMATION"


    else:

        regime = "MIXED"


    return {
        "success":
            True,

        "confirmation_score":
            score,

        "regime":
            regime,

        "confidence":
            confidence,

        "liquidity_score":
            liquidity_score,

        "components":
            tuple(
                {
                    "name":
                        name,

                    "direction":
                        direction,

                    "weight":
                        weight,
                }

                for name, direction, weight
                in components
            ),

        "heuristic":
            True,

        "predictive_guarantee":
            False,

        "research_only":
            True,
    }
