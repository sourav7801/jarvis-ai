from __future__ import annotations


def evolve_derivatives_strategy(
    strategy_id,
    regime_datasets,
    base_config,
    *,
    candidate_count=8,
    random_seed=1,
):

    import main


    candidate_count = max(
        1,
        min(
            int(
                candidate_count
            ),
            50,
        ),
    )


    result = main.jarvis_evolve_strategy(
        strategy_id,
        regime_datasets,
        base_config,
        candidate_count=
            candidate_count,
        random_seed=
            random_seed,
    )


    return {
        "success":
            True,

        "v4_result":
            result,

        "regime_count":
            len(
                regime_datasets
            ),

        "candidate_limit":
            50,

        "automatic_strategy_promotion":
            False,

        "automatic_registry_mutation":
            False,

        "automatic_broker_order":
            False,

        "research_only":
            True,
    }
