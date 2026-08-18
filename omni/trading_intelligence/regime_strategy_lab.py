from __future__ import annotations

from dataclasses import (
    replace,
)


from omni.trading_intelligence.historical_backtester import (
    historical_backtester,
)

from omni.trading_intelligence.strategy_fitness import (
    multi_regime_fitness,
)


class RegimeStrategyLab:

    def evaluate(
        self,
        genome,
        regime_datasets,
        base_config,
    ):

        if not regime_datasets:

            raise ValueError(
                "regime_datasets cannot be empty."
            )


        config = replace(
            base_config,
            **genome.config_overrides
        )


        results = {}


        for regime, bars in (
            regime_datasets.items()
        ):

            results[
                str(
                    regime
                )
            ] = (
                historical_backtester
                .run(
                    bars,
                    genome.strategy,
                    config,
                )
            )


        fitness = multi_regime_fitness(
            results
        )


        return {
            "success":
                True,

            "candidate_id":
                genome.candidate_id,

            "generation":
                genome.generation,

            "parent_ids":
                genome.parent_ids,

            "config_overrides":
                genome.config_overrides,

            "mutation_log":
                genome.mutation_log,

            "regime_results":
                results,

            "fitness":
                fitness,

            "automatic_promotion":
                False,

            "research_only":
                True,
        }


regime_strategy_lab = (
    RegimeStrategyLab()
)
