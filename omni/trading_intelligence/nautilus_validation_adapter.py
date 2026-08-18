from __future__ import annotations


def nautilus_v5_validation_gate(
    v5_report,
    nautilus_result,
):

    recommendation_block = (
        v5_report.get(
            "recommendation",
            {}
        )
    )


    recommendation = (
        recommendation_block.get(
            "recommendation"
        )
    )


    nautilus_safe = (
        nautilus_result.get(
            "success"
        )
        is True

        and nautilus_result.get(
            "live_execution"
        )
        is False

        and nautilus_result.get(
            "broker_adapter"
        )
        is False

        and nautilus_result.get(
            "paper_only"
        )
        is True
    )


    has_evidence = (
        int(
            nautilus_result.get(
                "fill_count",
                0,
            )
        )
        > 0
    )


    research_eligible = (
        recommendation
        == "PROMOTE"

        and nautilus_safe

        and has_evidence
    )


    if not nautilus_safe:

        state = "REJECT"


    elif not has_evidence:

        state = "KEEP_TESTING"


    elif recommendation == "PROMOTE":

        state = (
            "EXTENDED_RESEARCH_ELIGIBLE"
        )


    elif recommendation in {
        "KEEP_TESTING",
        None,
    }:

        state = "KEEP_TESTING"


    elif recommendation == "DEGRADE":

        state = "DEGRADE"


    else:

        state = "RETIRE"


    return {
        "state":
            state,

        "v5_recommendation":
            recommendation,

        "nautilus_safe":
            nautilus_safe,

        "nautilus_evidence":
            has_evidence,

        "extended_research_eligible":
            research_eligible,

        "production_promotion":
            False,

        "automatic_registry_mutation":
            False,

        "automatic_broker_order":
            False,

        "live_deployment":
            False,

        "research_only":
            True,
    }
