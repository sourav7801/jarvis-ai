from __future__ import annotations

from omni.trading_intelligence.signal_engine import (
    signal_engine,
)

from omni.trading_intelligence.strategy_registry import (
    strategy_registry,
)

from omni.trading_intelligence.strategy_schema import (
    Condition,
    StrategySpec,
)


DERIVATIVE_STRATEGIES = (
    StrategySpec(
        strategy_id=
            "derivatives_confirmation_v1",

        name=
            "Derivatives Confirmation",

        family=
            "derivatives_confirmation",

        supported_asset_classes=(
            "index",
            "equity",
            "commodity",
            "currency",
        ),

        supported_instrument_types=(
            "future",
            "option",
        ),

        supported_timeframes=(
            "1m",
            "3m",
            "5m",
            "15m",
        ),

        required_features=(
            "confirmation_score",
            "liquidity_score",
        ),

        long_entry=(
            Condition(
                "confirmation_score",
                "gt",
                0.45,
            ),

            Condition(
                "liquidity_score",
                "gt",
                40.0,
            ),
        ),

        short_entry=(
            Condition(
                "confirmation_score",
                "lt",
                -0.45,
            ),

            Condition(
                "liquidity_score",
                "gt",
                40.0,
            ),
        ),

        metadata={
            "research_only":
                True,

            "requires_derivatives_snapshot":
                True,
        },
    ),


    StrategySpec(
        strategy_id=
            "commodity_liquid_trend_v1",

        name=
            "Commodity Liquid Trend",

        family=
            "commodity_trend",

        supported_asset_classes=(
            "commodity",
        ),

        supported_instrument_types=(
            "future",
        ),

        supported_timeframes=(
            "5m",
            "15m",
            "1h",
        ),

        required_features=(
            "ema9",
            "ema21",
            "liquidity_score",
        ),

        long_entry=(
            Condition(
                "ema9",
                "gt",
                "ema21",
            ),

            Condition(
                "liquidity_score",
                "gt",
                40.0,
            ),
        ),

        short_entry=(
            Condition(
                "ema9",
                "lt",
                "ema21",
            ),

            Condition(
                "liquidity_score",
                "gt",
                40.0,
            ),
        ),

        metadata={
            "research_only":
                True,
        },
    ),


    StrategySpec(
        strategy_id=
            "expiry_confirmation_filter_v1",

        name=
            "Expiry Confirmation Filter",

        family=
            "expiry_derivatives",

        supported_asset_classes=(
            "index",
            "equity",
        ),

        supported_instrument_types=(
            "option",
            "future",
        ),

        supported_timeframes=(
            "1m",
            "3m",
            "5m",
        ),

        required_features=(
            "confirmation_score",
            "liquidity_score",
            "hours_to_expiry",
        ),

        long_entry=(
            Condition(
                "confirmation_score",
                "gt",
                0.55,
            ),

            Condition(
                "liquidity_score",
                "gt",
                50.0,
            ),

            Condition(
                "hours_to_expiry",
                "gt",
                1.0,
            ),
        ),

        short_entry=(
            Condition(
                "confirmation_score",
                "lt",
                -0.55,
            ),

            Condition(
                "liquidity_score",
                "gt",
                50.0,
            ),

            Condition(
                "hours_to_expiry",
                "gt",
                1.0,
            ),
        ),

        metadata={
            "research_only":
                True,

            "expiry_specific":
                True,
        },
    ),
)


def ensure_derivatives_strategies():

    for strategy in DERIVATIVE_STRATEGIES:

        strategy_registry.register(
            strategy
        )


    return DERIVATIVE_STRATEGIES


def derivatives_strategy_catalog():

    ensure_derivatives_strategies()


    ids = {
        strategy.strategy_id

        for strategy
        in DERIVATIVE_STRATEGIES
    }


    return tuple(
        row

        for row in strategy_registry.catalog()

        if row[
            "strategy_id"
        ]
        in ids
    )


def derivatives_signal(
    strategy_id,
    features,
    previous=None,
):

    ensure_derivatives_strategies()


    strategy = strategy_registry.get(
        strategy_id
    )


    if strategy is None:

        return {
            "success":
                False,

            "error":
                "Unknown derivatives strategy.",
        }


    result = signal_engine.evaluate(
        strategy,
        features,
        previous,
    )


    result[
        "derivatives_research"
    ] = True


    return result
