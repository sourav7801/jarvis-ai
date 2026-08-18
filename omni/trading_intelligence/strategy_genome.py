from __future__ import annotations

from dataclasses import (
    asdict,
    dataclass,
    field,
)

from omni.trading_intelligence.strategy_schema import (
    StrategySpec,
)


@dataclass(frozen=True)
class StrategyGenome:

    candidate_id: str

    strategy: StrategySpec

    generation: int = 0

    parent_ids: tuple[str, ...] = ()

    config_overrides: dict = field(
        default_factory=dict
    )

    mutation_log: tuple[str, ...] = ()

    metadata: dict = field(
        default_factory=dict
    )


    def __post_init__(
        self,
    ):

        if not self.candidate_id:

            raise ValueError(
                "candidate_id is required."
            )


        if not isinstance(
            self.strategy,
            StrategySpec,
        ):

            raise TypeError(
                "strategy must be StrategySpec."
            )


        if self.generation < 0:

            raise ValueError(
                "generation cannot be negative."
            )


    def to_dict(
        self,
    ):

        return {
            "candidate_id":
                self.candidate_id,

            "strategy":
                self.strategy.to_dict(),

            "generation":
                self.generation,

            "parent_ids":
                self.parent_ids,

            "config_overrides":
                dict(
                    self.config_overrides
                ),

            "mutation_log":
                self.mutation_log,

            "metadata":
                dict(
                    self.metadata
                ),

            "research_only":
                True,
        }
