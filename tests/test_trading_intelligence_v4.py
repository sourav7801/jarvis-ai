import tempfile
import unittest

from datetime import (
    datetime,
    timedelta,
    timezone,
)

from pathlib import (
    Path,
)


import main


from omni.core_integrity import (
    verify_protected_core,
)

from omni.trading_intelligence.backtest_schema import (
    BacktestConfig,
)

from omni.trading_intelligence.champion_challenger import (
    ChampionChallenger,
)

from omni.trading_intelligence.evolution_store import (
    EvolutionStore,
)

from omni.trading_intelligence.market_schema import (
    Bar,
)

from omni.trading_intelligence.strategy_evolution_lab import (
    StrategyEvolutionLab,
)

from omni.trading_intelligence.strategy_fitness import (
    multi_regime_fitness,
    result_fitness,
)

from omni.trading_intelligence.strategy_retirement import (
    StrategyRetirementEngine,
)


def trend_up(
    count=100,
):

    start = datetime(
        2026,
        1,
        1,
        9,
        15,
        tzinfo=timezone.utc,
    )


    return [
        Bar(
            timestamp=
                start
                + timedelta(
                    minutes=index
                ),

            open=
                100
                + index
                * 0.4,

            high=
                101
                + index
                * 0.4,

            low=
                99.5
                + index
                * 0.4,

            close=
                100.5
                + index
                * 0.4,

            volume=
                1000
                + index
                * 10,
        )

        for index
        in range(
            count
        )
    ]


def trend_down(
    count=100,
):

    start = datetime(
        2026,
        2,
        1,
        9,
        15,
        tzinfo=timezone.utc,
    )


    return [
        Bar(
            timestamp=
                start
                + timedelta(
                    minutes=index
                ),

            open=
                200
                - index
                * 0.4,

            high=
                200.5
                - index
                * 0.4,

            low=
                199
                - index
                * 0.4,

            close=
                199.5
                - index
                * 0.4,

            volume=
                1000
                + index
                * 10,
        )

        for index
        in range(
            count
        )
    ]


def regimes():

    return {
        "TREND_UP":
            trend_up(),

        "TREND_DOWN":
            trend_down(),
    }


class TradingIntelligenceV4Tests(
    unittest.TestCase
):

    def test_core(
        self,
    ):

        self.assertTrue(
            verify_protected_core().ok
        )


    def test_seed(
        self,
    ):

        lab = StrategyEvolutionLab()


        seed = lab.seed_genome(
            "rsi_mean_reversion_v1"
        )


        self.assertEqual(
            seed.generation,
            0,
        )


    def test_mutation_count(
        self,
    ):

        lab = StrategyEvolutionLab()


        candidates = lab.mutate(
            "rsi_mean_reversion_v1",
            count=5,
            random_seed=7,
        )


        self.assertEqual(
            len(
                candidates
            ),
            5,
        )


    def test_candidate_not_registered(
        self,
    ):

        from omni.trading_intelligence.strategy_registry import (
            strategy_registry,
        )


        lab = StrategyEvolutionLab()


        candidate = lab.mutate(
            "rsi_mean_reversion_v1",
            count=1,
            random_seed=5,
        )[0]


        self.assertIsNone(
            strategy_registry.get(
                candidate.strategy.strategy_id
            )
        )


    def test_mutation_has_log(
        self,
    ):

        candidate = (
            StrategyEvolutionLab()
            .mutate(
                "rsi_mean_reversion_v1",
                count=1,
                random_seed=3,
            )[0]
        )


        self.assertGreater(
            len(
                candidate.mutation_log
            ),
            0,
        )


    def test_crossover(
        self,
    ):

        child = (
            StrategyEvolutionLab()
            .crossover(
                "vwap_momentum_v1",
                "rsi_mean_reversion_v1",
            )
        )


        self.assertEqual(
            child.strategy.family,
            "crossover",
        )


        self.assertEqual(
            len(
                child.parent_ids
            ),
            2,
        )


    def test_derivatives_historical_gate(
        self,
    ):

        lab = StrategyEvolutionLab()


        genome = lab.seed_genome(
            "derivatives_confirmation_v1"
        )


        self.assertFalse(
            lab.historically_compatible(
                genome.strategy
            )
        )


        with self.assertRaises(
            ValueError
        ):

            lab.evaluate(
                genome,
                regimes(),

                BacktestConfig(
                    warmup_bars=30
                ),
            )


    def test_base_strategy_compatible(
        self,
    ):

        lab = StrategyEvolutionLab()


        genome = lab.seed_genome(
            "vwap_momentum_v1"
        )


        self.assertTrue(
            lab.historically_compatible(
                genome.strategy
            )
        )


    def test_candidate_evaluation(
        self,
    ):

        lab = StrategyEvolutionLab()


        candidate = lab.mutate(
            "rsi_mean_reversion_v1",
            count=1,
            random_seed=1,
        )[0]


        result = lab.evaluate(
            candidate,
            regimes(),

            BacktestConfig(
                warmup_bars=30,
            ),
        )


        self.assertTrue(
            result[
                "success"
            ]
        )


        self.assertIn(
            "score",
            result[
                "fitness"
            ],
        )


    def test_evolution_lab(
        self,
    ):

        result = (
            StrategyEvolutionLab()
            .evolve(
                "rsi_mean_reversion_v1",
                regimes(),

                BacktestConfig(
                    warmup_bars=30,
                ),

                candidate_count=4,
                random_seed=42,
            )
        )


        self.assertEqual(
            result[
                "candidate_count"
            ],
            4,
        )


        self.assertFalse(
            result[
                "production_promotion"
            ]
        )


        self.assertFalse(
            result[
                "registry_mutation"
            ]
        )


    def test_candidate_limit(
        self,
    ):

        with self.assertRaises(
            ValueError
        ):

            StrategyEvolutionLab().mutate(
                "rsi_mean_reversion_v1",
                count=51,
            )


    def test_fitness(
        self,
    ):

        fake = {
            "metrics": {
                "trades":
                    20,

                "return_pct":
                    0.10,

                "expectancy":
                    100,

                "avg_loss":
                    50,

                "profit_factor":
                    2.0,

                "win_rate":
                    0.60,

                "max_drawdown_pct":
                    0.08,
            }
        }


        result = result_fitness(
            fake
        )


        self.assertIn(
            "score",
            result,
        )


    def test_multiregime_penalty(
        self,
    ):

        good = {
            "metrics": {
                "trades": 20,
                "return_pct": 0.10,
                "expectancy": 50,
                "avg_loss": 50,
                "profit_factor": 1.8,
                "win_rate": 0.55,
                "max_drawdown_pct": 0.05,
            }
        }


        bad = {
            "metrics": {
                "trades": 20,
                "return_pct": -0.10,
                "expectancy": -50,
                "avg_loss": 50,
                "profit_factor": 0.7,
                "win_rate": 0.35,
                "max_drawdown_pct": 0.20,
            }
        }


        result = multi_regime_fitness(
            {
                "A":
                    good,

                "B":
                    bad,
            }
        )


        self.assertGreater(
            result[
                "stability_penalty"
            ],
            0,
        )


    def test_champion_challenger(
        self,
    ):

        comparator = (
            ChampionChallenger()
        )


        result = comparator.compare(
            {
                "fitness": {
                    "score": 10
                }
            },

            {
                "fitness": {
                    "score": 15
                }
            },
        )


        self.assertEqual(
            result[
                "decision"
            ],
            "RESEARCH_CHALLENGER_WINS",
        )


        self.assertFalse(
            result[
                "production_promotion"
            ]
        )


    def test_retirement_proposal(
        self,
    ):

        result = (
            StrategyRetirementEngine()
            .evaluate(
                {
                    "candidate_id":
                        "bad",

                    "fitness": {
                        "score":
                            -30
                    },
                }
            )
        )


        self.assertEqual(
            result[
                "recommendation"
            ],
            "RETIRE_PROPOSAL",
        )


        self.assertFalse(
            result[
                "automatic_delete"
            ]
        )


    def test_store(
        self,
    ):

        with tempfile.TemporaryDirectory() as tmp:

            store = EvolutionStore(
                Path(
                    tmp
                )
            )


            saved = store.save(
                {
                    "research_only":
                        True,

                    "candidate":
                        "x",
                }
            )


            self.assertTrue(
                Path(
                    saved[
                        "path"
                    ]
                ).exists()
            )


    def test_status(
        self,
    ):

        status = main.jarvis_trading_v4_status()


        self.assertTrue(
            status[
                "strategy_genomes"
            ]
        )


        self.assertTrue(
            status[
                "champion_challenger"
            ]
        )


        self.assertFalse(
            status[
                "automatic_strategy_promotion"
            ]
        )


        self.assertFalse(
            status[
                "production_self_modification"
            ]
        )


        self.assertFalse(
            status[
                "live_execution"
            ]
        )


    def test_v3_preserved(
        self,
    ):

        status = main.jarvis_trading_v3_status()


        self.assertTrue(
            status[
                "option_chain_schema"
            ]
        )


        self.assertFalse(
            status[
                "live_execution"
            ]
        )


    def test_public_apis(
        self,
    ):

        for name in (
            "jarvis_trading_v4_status",
            "jarvis_strategy_mutate",
            "jarvis_strategy_crossover",
            "jarvis_evaluate_strategy_candidate",
            "jarvis_evolve_strategy",
            "jarvis_compare_champion_challenger",
            "jarvis_strategy_retirement_proposal",
            "jarvis_save_evolution_artifact",
        ):

            self.assertTrue(
                callable(
                    getattr(
                        main,
                        name,
                    )
                )
            )


if __name__ == "__main__":

    unittest.main()
