from __future__ import annotations

import random
import uuid

from dataclasses import (
    replace,
)


from omni.trading_intelligence.strategy_genome import (
    StrategyGenome,
)

from omni.trading_intelligence.strategy_schema import (
    Condition,
    StrategySpec,
)


CONFIG_FIELDS = (
    "stop_loss_pct",
    "target_pct",
    "trailing_stop_pct",
    "max_bars_in_trade",
)


class StrategyMutator:

    def __init__(
        self,
        seed=None,
    ):

        self.random = random.Random(
            seed
        )


    def _mutate_numeric(
        self,
        value,
    ):

        value = float(
            value
        )


        factor = self.random.choice(
            (
                0.80,
                0.90,
                0.95,
                1.05,
                1.10,
                1.20,
            )
        )


        return (
            value
            * factor
        )


    def _mutate_conditions(
        self,
        conditions,
    ):

        conditions = list(
            conditions
        )


        numeric_indexes = [
            index

            for index, condition
            in enumerate(
                conditions
            )

            if isinstance(
                condition.right,
                (
                    int,
                    float,
                ),
            )
        ]


        if not numeric_indexes:

            return (
                tuple(
                    conditions
                ),
                None,
            )


        index = self.random.choice(
            numeric_indexes
        )


        original = conditions[
            index
        ]


        mutated = Condition(
            left=
                original.left,

            operator=
                original.operator,

            right=
                self._mutate_numeric(
                    original.right
                ),
        )


        conditions[
            index
        ] = mutated


        return (
            tuple(
                conditions
            ),

            (
                original.left
                + ":"
                + str(
                    original.right
                )
                + "->"
                + str(
                    mutated.right
                )
            ),
        )


    def mutate(
        self,
        strategy,
        *,
        parent_id=None,
        generation=1,
    ):

        if not isinstance(
            strategy,
            StrategySpec,
        ):

            raise TypeError(
                "strategy must be StrategySpec."
            )


        long_entry, long_log = (
            self._mutate_conditions(
                strategy.long_entry
            )
        )


        short_entry, short_log = (
            self._mutate_conditions(
                strategy.short_entry
            )
        )


        config_overrides = {}


        config_choice = self.random.choice(
            CONFIG_FIELDS
        )


        if config_choice == "stop_loss_pct":

            value = self.random.choice(
                (
                    0.005,
                    0.01,
                    0.015,
                    0.02,
                    0.03,
                )
            )


        elif config_choice == "target_pct":

            value = self.random.choice(
                (
                    0.01,
                    0.02,
                    0.03,
                    0.04,
                    0.06,
                )
            )


        elif config_choice == "trailing_stop_pct":

            value = self.random.choice(
                (
                    None,
                    0.01,
                    0.015,
                    0.02,
                    0.03,
                )
            )


        else:

            value = self.random.choice(
                (
                    5,
                    10,
                    20,
                    30,
                    50,
                )
            )


        config_overrides[
            config_choice
        ] = value


        candidate_id = (
            "candidate-"
            + uuid.uuid4()
            .hex[:12]
        )


        child = replace(
            strategy,

            strategy_id=
                (
                    strategy.strategy_id
                    + "__"
                    + candidate_id
                ),

            name=
                (
                    strategy.name
                    + " Challenger"
                ),

            long_entry=
                long_entry,

            short_entry=
                short_entry,

            metadata={
                **strategy.metadata,

                "evolved_candidate":
                    True,

                "production_registered":
                    False,
            },
        )


        logs = [
            item

            for item in (
                long_log,
                short_log,
                (
                    "config:"
                    + config_choice
                    + "="
                    + str(
                        value
                    )
                ),
            )

            if item
        ]


        return StrategyGenome(
            candidate_id=
                candidate_id,

            strategy=
                child,

            generation=
                int(
                    generation
                ),

            parent_ids=
                (
                    (str(
                        parent_id
                    ),)
                    if parent_id
                    else (
                        strategy.strategy_id,
                    )
                ),

            config_overrides=
                config_overrides,

            mutation_log=
                tuple(
                    logs
                ),

            metadata={
                "mutation":
                    True,

                "automatic_promotion":
                    False,
            },
        )


strategy_mutator = StrategyMutator()
