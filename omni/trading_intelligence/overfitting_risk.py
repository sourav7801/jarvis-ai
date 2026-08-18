from __future__ import annotations


def _gap(
    stronger,
    weaker,
):

    stronger = float(stronger)
    weaker = float(weaker)

    deterioration = max(
        0.0,
        stronger - weaker,
    )


    return (
        deterioration
        / max(
            abs(stronger),
            10.0,
        )
    )


def overfitting_risk(
    *,
    train_fitness,
    validation_fitness,
    oos_fitness,
    walk_forward_pass_rate,
    sensitivity_instability,
    monte_carlo_loss_probability,
    cost_survival_rate,
    data_sufficient=True,
):

    train_gap = _gap(
        train_fitness,
        validation_fitness,
    )


    validation_gap = _gap(
        validation_fitness,
        oos_fitness,
    )


    train_validation_penalty = min(
        25.0,
        train_gap
        * 25.0,
    )


    oos_penalty = min(
        25.0,
        validation_gap
        * 25.0,
    )


    walk_forward_penalty = (
        max(
            0.0,
            1.0
            - float(
                walk_forward_pass_rate
            ),
        )
        * 15.0
    )


    sensitivity_penalty = min(
        15.0,
        max(
            0.0,
            float(
                sensitivity_instability
            ),
        )
        * 15.0,
    )


    monte_carlo_penalty = (
        max(
            0.0,
            min(
                1.0,
                float(
                    monte_carlo_loss_probability
                ),
            ),
        )
        * 10.0
    )


    cost_penalty = (
        max(
            0.0,
            1.0
            - float(
                cost_survival_rate
            ),
        )
        * 10.0
    )


    insufficiency_penalty = (
        25.0
        if not data_sufficient
        else 0.0
    )


    score = min(
        100.0,
        (
            train_validation_penalty
            + oos_penalty
            + walk_forward_penalty
            + sensitivity_penalty
            + monte_carlo_penalty
            + cost_penalty
            + insufficiency_penalty
        ),
    )


    if score <= 25:
        level = "LOW"

    elif score <= 45:
        level = "MODERATE"

    elif score <= 70:
        level = "HIGH"

    else:
        level = "SEVERE"


    return {
        "score":
            score,

        "level":
            level,

        "components": {
            "train_validation_gap":
                train_validation_penalty,

            "validation_oos_gap":
                oos_penalty,

            "walk_forward":
                walk_forward_penalty,

            "parameter_sensitivity":
                sensitivity_penalty,

            "monte_carlo":
                monte_carlo_penalty,

            "cost_stress":
                cost_penalty,

            "data_sufficiency":
                insufficiency_penalty,
        },

        "research_only":
            True,
    }
