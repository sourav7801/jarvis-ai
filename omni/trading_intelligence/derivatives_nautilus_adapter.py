from __future__ import annotations


def validate_derivatives_portfolio(
    portfolio,
    *,
    v5_report=None,
    train_size=None,
    validation_size=None,
    test_size=None,
    step=None,
    timeout=180,
):

    import main


    requested_walk_forward = any(
        value is not None

        for value in (
            train_size,
            validation_size,
            test_size,
        )
    )


    if requested_walk_forward:

        if (
            train_size is None
            or validation_size is None
            or test_size is None
        ):

            raise ValueError(
                "train_size, validation_size and test_size "
                "must all be supplied for Nautilus walk-forward."
            )


        evidence = (
            main
            .jarvis_nautilus_portfolio_walk_forward(
                portfolio,
                train_size,
                validation_size,
                test_size,
                step=step,
                timeout=timeout,
            )
        )


        mode = "walk_forward"


    else:

        evidence = (
            main
            .jarvis_nautilus_portfolio_backtest(
                portfolio,
                timeout=timeout,
            )
        )


        mode = "backtest"


    gate = None


    if (
        v5_report is not None
        and mode == "walk_forward"
    ):

        gate = (
            main
            .jarvis_nautilus_c3_v5_gate(
                v5_report,
                evidence,
            )
        )


    return {
        "success":
            True,

        "mode":
            mode,

        "nautilus_evidence":
            evidence,

        "v5_gate":
            gate,

        "v5_authoritative":
            True,

        "automatic_portfolio_allocation":
            False,

        "automatic_portfolio_rebalance":
            False,

        "automatic_broker_order":
            False,

        "live_execution":
            False,

        "research_only":
            True,
    }
