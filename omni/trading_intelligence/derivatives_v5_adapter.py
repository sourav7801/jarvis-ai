from __future__ import annotations


def validate_derivatives_candidate(
    candidate,
    bars,
    base_config,
    *,
    regime_datasets=None,
    monte_carlo_iterations=500,
    random_seed=1,
):

    import main


    iterations = max(
        1,
        min(
            int(
                monte_carlo_iterations
            ),
            5000,
        ),
    )


    result = (
        main
        .jarvis_trading_validate_candidate(
            candidate,
            bars,
            base_config,
            regime_datasets=
                regime_datasets,
            monte_carlo_iterations=
                iterations,
            random_seed=
                random_seed,
        )
    )


    return {
        "success":
            True,

        "v5_report":
            result,

        "v5_authoritative":
            True,

        "oos_tuning":
            False,

        "automatic_strategy_promotion":
            False,

        "automatic_broker_order":
            False,

        "research_only":
            True,
    }


def walk_forward_derivatives(
    bars,
    strategy,
    config,
    *,
    train_size,
    validation_size,
    test_size,
    step=None,
):

    import main


    result = main.jarvis_walk_forward(
        bars,
        strategy,
        config,
        train_size,
        validation_size,
        test_size,
        step=step,
    )


    return {
        "success":
            True,

        "walk_forward":
            result,

        "chronological":
            True,

        "oos_tuning":
            False,

        "automatic_parameter_selection":
            False,

        "automatic_strategy_promotion":
            False,

        "research_only":
            True,
    }
