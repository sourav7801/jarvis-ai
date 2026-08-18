from __future__ import annotations

from omni.trading_intelligence.strategy_schema import (
    Condition,
    StrategySpec,
)


def built_in_strategies():

    return (
        StrategySpec(
            strategy_id=
                "vwap_momentum_v1",

            name=
                "VWAP Momentum",

            family=
                "momentum",

            supported_asset_classes=(
                "equity",
                "index",
                "commodity",
                "currency",
            ),

            supported_instrument_types=(
                "stock",
                "spot",
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
                "close",
                "vwap",
                "ema9",
                "ema21",
                "volume_z20",
            ),

            long_entry=(
                Condition(
                    "close",
                    "gt",
                    "vwap",
                ),

                Condition(
                    "ema9",
                    "gt",
                    "ema21",
                ),
            ),

            short_entry=(
                Condition(
                    "close",
                    "lt",
                    "vwap",
                ),

                Condition(
                    "ema9",
                    "lt",
                    "ema21",
                ),
            ),

            parameters={
                "minimum_volume_z":
                    0.0,
            },

            metadata={
                "research_only":
                    True,
            },
        ),


        StrategySpec(
            strategy_id=
                "ema_trend_v1",

            name=
                "EMA Trend",

            family=
                "trend",

            supported_asset_classes=(
                "equity",
                "index",
                "commodity",
                "currency",
                "forex",
            ),

            supported_instrument_types=(
                "stock",
                "spot",
                "future",
                "option",
                "fx",
            ),

            supported_timeframes=(
                "1m",
                "5m",
                "15m",
                "1h",
            ),

            required_features=(
                "ema9",
                "ema21",
            ),

            long_entry=(
                Condition(
                    "ema9",
                    "cross_above",
                    "ema21",
                ),
            ),

            short_entry=(
                Condition(
                    "ema9",
                    "cross_below",
                    "ema21",
                ),
            ),

            metadata={
                "research_only":
                    True,
            },
        ),


        StrategySpec(
            strategy_id=
                "rsi_mean_reversion_v1",

            name=
                "RSI Mean Reversion",

            family=
                "mean_reversion",

            supported_asset_classes=(
                "equity",
                "index",
                "commodity",
                "currency",
            ),

            supported_instrument_types=(
                "stock",
                "spot",
                "future",
                "option",
            ),

            supported_timeframes=(
                "5m",
                "15m",
                "1h",
            ),

            required_features=(
                "rsi14",
                "close",
                "vwap",
            ),

            long_entry=(
                Condition(
                    "rsi14",
                    "lt",
                    30.0,
                ),
            ),

            short_entry=(
                Condition(
                    "rsi14",
                    "gt",
                    70.0,
                ),
            ),

            metadata={
                "research_only":
                    True,
            },
        ),
    )


class StrategyRegistry:

    def __init__(
        self,
    ):

        self._strategies = {}


        for strategy in built_in_strategies():

            self.register(
                strategy
            )


    def register(
        self,
        strategy,
    ):

        if not isinstance(
            strategy,
            StrategySpec,
        ):

            raise TypeError(
                "Strategy must be a StrategySpec."
            )


        self._strategies[
            strategy.strategy_id
        ] = strategy


        return strategy


    def get(
        self,
        strategy_id,
    ):

        return self._strategies.get(
            str(
                strategy_id
            )
        )


    def all(
        self,
    ):

        return tuple(
            self._strategies.values()
        )


    def catalog(
        self,
    ):

        return tuple(
            {
                "strategy_id":
                    item.strategy_id,

                "name":
                    item.name,

                "family":
                    item.family,

                "asset_classes":
                    item.supported_asset_classes,

                "instrument_types":
                    item.supported_instrument_types,

                "timeframes":
                    item.supported_timeframes,

                "research_only":
                    True,
            }

            for item
            in self.all()
        )


strategy_registry = StrategyRegistry()
