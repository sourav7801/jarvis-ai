from __future__ import annotations


SIGNAL_VALUE = {
    "LONG":
        1.0,

    "SHORT":
        -1.0,

    "FLAT":
        0.0,

    "EXIT":
        0.0,
}


def derivatives_ensemble(
    signals,
    *,
    weights=None,
    threshold=0.25,
):

    signals = dict(
        signals
    )


    if not signals:

        raise ValueError(
            "At least one signal is required."
        )


    normalized = {}


    for strategy_id, signal in (
        signals.items()
    ):

        signal = str(
            signal
        ).upper()


        if signal not in SIGNAL_VALUE:

            raise ValueError(
                "Unsupported signal: "
                + signal
            )


        normalized[
            str(
                strategy_id
            )
        ] = signal


    if weights is None:

        weights = {
            strategy_id:
                1.0

            for strategy_id
            in normalized
        }


    else:

        weights = {
            str(
                key
            ):
                max(
                    0.0,
                    float(
                        value
                    ),
                )

            for key, value
            in dict(
                weights
            ).items()
        }


    total_weight = sum(
        weights.get(
            strategy_id,
            0.0,
        )

        for strategy_id
        in normalized
    )


    if total_weight <= 0:

        raise ValueError(
            "Ensemble weights must contain positive mass."
        )


    contributions = {}


    score = 0.0


    for strategy_id, signal in (
        normalized.items()
    ):

        weight = (
            weights.get(
                strategy_id,
                0.0,
            )
            / total_weight
        )


        contribution = (
            SIGNAL_VALUE[
                signal
            ]
            * weight
        )


        contributions[
            strategy_id
        ] = {
            "signal":
                signal,

            "weight":
                weight,

            "contribution":
                contribution,
        }


        score += contribution


    threshold = abs(
        float(
            threshold
        )
    )


    if score >= threshold:

        consensus = "LONG"


    elif score <= -threshold:

        consensus = "SHORT"


    else:

        consensus = "FLAT"


    return {
        "consensus":
            consensus,

        "score":
            score,

        "threshold":
            threshold,

        "contributions":
            contributions,

        "execution_allowed":
            False,

        "broker_order":
            False,

        "capital_allocation":
            False,

        "research_only":
            True,
    }
