from __future__ import annotations


def derivatives_regime(
    features,
):

    features = dict(
        features
    )


    iv_rank = features.get(
        "atm_iv_rank"
    )


    pcr = features.get(
        "pcr_oi"
    )


    delta_call = features.get(
        "delta_call_oi"
    )


    delta_put = features.get(
        "delta_put_oi"
    )


    basis = features.get(
        "futures_basis"
    )


    components = {}


    if iv_rank is None:

        components[
            "volatility"
        ] = "UNKNOWN"


    elif float(
        iv_rank
    ) >= 70:

        components[
            "volatility"
        ] = "HIGH_IV"


    elif float(
        iv_rank
    ) <= 30:

        components[
            "volatility"
        ] = "LOW_IV"


    else:

        components[
            "volatility"
        ] = "MID_IV"


    if pcr is None:

        components[
            "pcr"
        ] = "UNKNOWN"


    elif float(
        pcr
    ) >= 1.2:

        components[
            "pcr"
        ] = "PUT_OI_HEAVY"


    elif float(
        pcr
    ) <= 0.8:

        components[
            "pcr"
        ] = "CALL_OI_HEAVY"


    else:

        components[
            "pcr"
        ] = "BALANCED_OI"


    if (
        delta_call is None
        or delta_put is None
    ):

        components[
            "oi_change"
        ] = "UNKNOWN"


    elif delta_put > delta_call:

        components[
            "oi_change"
        ] = "PUT_OI_BUILDING_FASTER"


    elif delta_call > delta_put:

        components[
            "oi_change"
        ] = "CALL_OI_BUILDING_FASTER"


    else:

        components[
            "oi_change"
        ] = "OI_CHANGE_BALANCED"


    if basis is None:

        components[
            "basis"
        ] = "UNKNOWN"


    elif float(
        basis
    ) > 0:

        components[
            "basis"
        ] = "FUTURES_PREMIUM"


    elif float(
        basis
    ) < 0:

        components[
            "basis"
        ] = "FUTURES_DISCOUNT"


    else:

        components[
            "basis"
        ] = "FLAT_BASIS"


    known = sum(
        1

        for value in components.values()

        if value != "UNKNOWN"
    )


    return {
        "regime":
            "|".join(
                components.values()
            ),

        "components":
            components,

        "feature_coverage":
            known
            / len(
                components
            ),

        "predictive_guarantee":
            False,

        "trade_instruction":
            False,

        "research_only":
            True,
    }
