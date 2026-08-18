from __future__ import annotations


def validation_recommendation(
    *,
    risk,
    oos_fitness,
    walk_forward_pass_rate,
    cost_survival_rate,
    oos_trades,
    data_sufficient,
):

    risk_score = float(
        risk[
            "score"
        ]
    )


    oos_fitness = float(
        oos_fitness
    )


    oos_trades = int(
        oos_trades
    )


    if (
        not data_sufficient
        or oos_trades < 3
    ):

        recommendation = "KEEP_TESTING"

        reasons = (
            "insufficient_evidence",
        )


    elif (
        risk_score <= 25
        and oos_fitness > 0
        and walk_forward_pass_rate >= 0.60
        and cost_survival_rate >= 0.50
    ):

        recommendation = "PROMOTE"

        reasons = (
            "research_validation_passed",
        )


    elif (
        risk_score <= 45
        and oos_fitness >= -5
    ):

        recommendation = "KEEP_TESTING"

        reasons = (
            "mixed_but_acceptable_evidence",
        )


    elif risk_score <= 70:

        recommendation = "DEGRADE"

        reasons = (
            "high_overfitting_or_robustness_risk",
        )


    else:

        recommendation = "RETIRE"

        reasons = (
            "severe_validation_failure",
        )


    return {
        "recommendation":
            recommendation,

        "reasons":
            reasons,

        "production_promotion":
            False,

        "automatic_registry_change":
            False,

        "automatic_live_deployment":
            False,

        "automatic_retirement":
            False,

        "research_recommendation_only":
            True,
    }
