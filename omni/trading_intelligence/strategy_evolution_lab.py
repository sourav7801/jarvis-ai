from __future__ import annotations

from omni.trading_intelligence.champion_challenger import (
    champion_challenger,
)

from omni.trading_intelligence.derivatives_strategy_registry import (
    ensure_derivatives_strategies,
)

from omni.trading_intelligence.regime_strategy_lab import (
    regime_strategy_lab,
)

from omni.trading_intelligence.strategy_crossover import (
    strategy_crossover,
)

from omni.trading_intelligence.strategy_genome import (
    StrategyGenome,
)

from omni.trading_intelligence.strategy_mutation import (
    StrategyMutator,
)

from omni.trading_intelligence.strategy_registry import (
    strategy_registry,
)

from omni.trading_intelligence.strategy_retirement import (
    strategy_retirement_engine,
)


HISTORICAL_FEATURES = {
    "close",
    "sma20",
    "ema9",
    "ema21",
    "ema50",
    "rsi14",
    "atr14",
    "atr_pct",
    "vwap",
    "volume_z20",
    "return_1",
    "realized_vol20",
}


class StrategyEvolutionLab:

    MAX_CANDIDATES = 50


    @staticmethod
    def _ensure_registry():

        ensure_derivatives_strategies()


    @classmethod
    def historically_compatible(
        cls,
        strategy,
    ):

        required = set(
            strategy.required_features
        )


        return required.issubset(
            HISTORICAL_FEATURES
        )


    def seed_genome(
        self,
        strategy_id,
    ):

        self._ensure_registry()


        strategy = strategy_registry.get(
            strategy_id
        )


        if strategy is None:

            raise ValueError(
                "Unknown seed strategy: "
                + str(
                    strategy_id
                )
            )


        return StrategyGenome(
            candidate_id=
                (
                    "seed:"
                    + strategy.strategy_id
                ),

            strategy=
                strategy,

            generation=
                0,

            parent_ids=(),

            metadata={
                "seed":
                    True,

                "production_registered":
                    True,

                "automatic_promotion":
                    False,
            },
        )


    def mutate(
        self,
        strategy_id,
        *,
        count=5,
        random_seed=1,
        generation=1,
    ):

        count = int(
            count
        )


        if (
            count <= 0
            or count > self.MAX_CANDIDATES
        ):

            raise ValueError(
                "count must be between 1 and "
                + str(
                    self.MAX_CANDIDATES
                )
            )


        seed_genome = self.seed_genome(
            strategy_id
        )


        mutator = StrategyMutator(
            random_seed
        )


        output = []


        for _ in range(
            count
        ):

            output.append(
                mutator.mutate(
                    seed_genome.strategy,
                    parent_id=
                        seed_genome.candidate_id,
                    generation=
                        generation,
                )
            )


        return tuple(
            output
        )


    def crossover(
        self,
        left_strategy_id,
        right_strategy_id,
        *,
        generation=1,
    ):

        left = self.seed_genome(
            left_strategy_id
        )


        right = self.seed_genome(
            right_strategy_id
        )


        return strategy_crossover.crossover(
            left.strategy,
            right.strategy,
            generation=generation,
        )


    def evaluate(
        self,
        genome,
        regime_datasets,
        base_config,
    ):

        if not self.historically_compatible(
            genome.strategy
        ):

            raise ValueError(
                "Candidate requires features unavailable "
                "in the V2 historical backtester. "
                "Use snapshot research until V5/V6 provides "
                "historical derivatives feature streams."
            )


        return regime_strategy_lab.evaluate(
            genome,
            regime_datasets,
            base_config,
        )


    def evolve(
        self,
        strategy_id,
        regime_datasets,
        base_config,
        *,
        candidate_count=8,
        random_seed=1,
    ):

        seed = self.seed_genome(
            strategy_id
        )


        if not self.historically_compatible(
            seed.strategy
        ):

            raise ValueError(
                "Seed is not compatible with current "
                "historical feature stream."
            )


        champion_evaluation = (
            self.evaluate(
                seed,
                regime_datasets,
                base_config,
            )
        )


        challengers = self.mutate(
            strategy_id,
            count=candidate_count,
            random_seed=random_seed,
            generation=1,
        )


        evaluated = []


        for challenger in challengers:

            evaluation = self.evaluate(
                challenger,
                regime_datasets,
                base_config,
            )


            comparison = (
                champion_challenger
                .compare(
                    champion_evaluation,
                    evaluation,
                )
            )


            retirement = (
                strategy_retirement_engine
                .evaluate(
                    evaluation
                )
            )


            evaluated.append(
                {
                    "genome":
                        challenger.to_dict(),

                    "evaluation":
                        evaluation,

                    "comparison":
                        comparison,

                    "retirement":
                        retirement,
                }
            )


        evaluated.sort(
            key=lambda item:
                item[
                    "evaluation"
                ][
                    "fitness"
                ][
                    "score"
                ],
            reverse=True,
        )


        return {
            "success":
                True,

            "seed_strategy_id":
                strategy_id,

            "champion":
                champion_evaluation,

            "challengers":
                tuple(
                    evaluated
                ),

            "best_challenger":
                (
                    evaluated[
                        0
                    ]
                    if evaluated
                    else None
                ),

            "candidate_count":
                len(
                    evaluated
                ),

            "production_promotion":
                False,

            "registry_mutation":
                False,

            "automatic_retirement":
                False,

            "research_only":
                True,
        }


strategy_evolution_lab = (
    StrategyEvolutionLab()
)
