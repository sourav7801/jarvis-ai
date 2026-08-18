from __future__ import annotations

import uuid

from omni.trading_intelligence.strategy_genome import (
    StrategyGenome,
)

from omni.trading_intelligence.strategy_schema import (
    StrategySpec,
)


def _intersection(
    left,
    right,
):

    return tuple(
        item

        for item in left

        if item in set(
            right
        )
    )


class StrategyCrossover:

    def crossover(
        self,
        left,
        right,
        *,
        generation=1,
    ):

        if (
            not isinstance(
                left,
                StrategySpec,
            )
            or not isinstance(
                right,
                StrategySpec,
            )
        ):

            raise TypeError(
                "Parents must be StrategySpec."
            )


        assets = _intersection(
            left.supported_asset_classes,
            right.supported_asset_classes,
        )


        instruments = _intersection(
            left.supported_instrument_types,
            right.supported_instrument_types,
        )


        timeframes = _intersection(
            left.supported_timeframes,
            right.supported_timeframes,
        )


        if (
            not assets
            or not instruments
            or not timeframes
        ):

            raise ValueError(
                "Parents have no compatible trading domain."
            )


        candidate_id = (
            "candidate-"
            + uuid.uuid4()
            .hex[:12]
        )


        required = tuple(
            dict.fromkeys(
                (
                    *left.required_features,
                    *right.required_features,
                )
            )
        )


        long_entry = tuple(
            dict.fromkeys(
                (
                    *left.long_entry,
                    *right.long_entry,
                )
            )
        )


        short_entry = tuple(
            dict.fromkeys(
                (
                    *left.short_entry,
                    *right.short_entry,
                )
            )
        )


        child = StrategySpec(
            strategy_id=
                (
                    "cross__"
                    + candidate_id
                ),

            name=
                (
                    left.name
                    + " x "
                    + right.name
                ),

            family=
                "crossover",

            supported_asset_classes=
                assets,

            supported_instrument_types=
                instruments,

            supported_timeframes=
                timeframes,

            required_features=
                required,

            long_entry=
                long_entry,

            short_entry=
                short_entry,

            exit_conditions=
                tuple(
                    dict.fromkeys(
                        (
                            *left.exit_conditions,
                            *right.exit_conditions,
                        )
                    )
                ),

            parameters={
                "parent_a":
                    left.strategy_id,

                "parent_b":
                    right.strategy_id,
            },

            metadata={
                "evolved_candidate":
                    True,

                "crossover":
                    True,

                "production_registered":
                    False,
            },
        )


        return StrategyGenome(
            candidate_id=
                candidate_id,

            strategy=
                child,

            generation=
                int(
                    generation
                ),

            parent_ids=(
                left.strategy_id,
                right.strategy_id,
            ),

            mutation_log=(
                "rule_crossover",
            ),

            metadata={
                "crossover":
                    True,

                "automatic_promotion":
                    False,
            },
        )


strategy_crossover = StrategyCrossover()
