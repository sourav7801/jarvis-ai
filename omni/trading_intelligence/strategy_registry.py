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


def quant_ensemble_strategies():

    """Metadata contracts for every strategy used by Quant Ensemble V2.

    Calculations remain deterministic and research/paper-only.  Keeping the
    catalog separate from evaluators makes strategy identity, required inputs
    and regime compatibility inspectable without permitting code mutation.
    """

    definitions = (
        ("EMA_9_21_TREND", "EMA 9/21 Trend", "trend", ("ema9", "ema21"), ("TRENDING", "HIGH_VOLATILITY")),
        ("EMA_20_50_TREND", "EMA 20/50 Trend", "trend", ("close", "ema20", "ema50"), ("TRENDING",)),
        ("VWAP_MOMENTUM", "VWAP Momentum", "momentum", ("close", "vwap", "ema9", "ema21"), ("TRENDING", "HIGH_VOLATILITY")),
        ("RSI_VWAP_MEAN_REVERSION", "RSI VWAP Mean Reversion", "mean_reversion", ("close", "vwap", "rsi14"), ("RANGE",)),
        ("DONCHIAN_BREAKOUT_20", "Donchian Breakout 20", "breakout", ("close", "high", "low"), ("TRENDING", "HIGH_VOLATILITY")),
        ("OPENING_RANGE_BREAKOUT_PROXY", "Opening Range Breakout Proxy", "breakout", ("close", "high", "low"), ("TRENDING", "HIGH_VOLATILITY")),
        ("ZSCORE_REVERSION_20", "Z Score Reversion 20", "mean_reversion", ("zscore20",), ("RANGE",)),
        ("FAIR_VALUE_GAP", "Fair Value Gap", "structure", ("high", "low"), ("TRENDING", "RANGE", "HIGH_VOLATILITY")),
        ("LIQUIDITY_SWEEP", "Liquidity Sweep", "structure", ("close", "high", "low"), ("RANGE", "HIGH_VOLATILITY")),
        ("RELATIVE_VOLUME_EXPANSION", "Relative Volume Expansion", "volume", ("open", "close", "relative_volume20"), ("TRENDING", "HIGH_VOLATILITY")),
        ("ATR_STRETCH_REVERSION", "ATR Stretch Reversion", "mean_reversion", ("close", "ema20", "atr14"), ("RANGE", "HIGH_VOLATILITY")),
    )

    return tuple(
        StrategySpec(
            strategy_id=strategy_id,
            name=name,
            family=family,
            supported_asset_classes=("equity", "index", "commodity", "crypto", "currency", "forex"),
            supported_instrument_types=("stock", "spot", "future", "option", "fx"),
            supported_timeframes=("1m", "3m", "5m", "15m", "1h", "4h", "1D"),
            required_features=required_features,
            version="2.0.0",
            compatible_regimes=compatible_regimes,
            metadata={
                "research_only": True,
                "paper_eligible": True,
                "live_execution": False,
                "evaluator": strategy_id.lower(),
            },
        )
        for strategy_id, name, family, required_features, compatible_regimes in definitions
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


        for strategy in quant_ensemble_strategies():

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

                "version":
                    item.version,

                "asset_classes":
                    item.supported_asset_classes,

                "instrument_types":
                    item.supported_instrument_types,

                "timeframes":
                    item.supported_timeframes,

                "required_features":
                    item.required_features,

                "compatible_regimes":
                    item.compatible_regimes,

                "research_only":
                    True,
            }

            for item
            in self.all()
        )


strategy_registry = StrategyRegistry()
