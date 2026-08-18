from __future__ import annotations

from omni.trading_intelligence.strategy_fitness import (
    result_fitness,
)


class ShadowChampionChallenger:

    def compare(
        self,
        champion_metrics,
        challenger_metrics,
        *,
        margin=2.0,
    ):

        champion = result_fitness(
            {
                "metrics":
                    champion_metrics
            }
        )


        challenger = result_fitness(
            {
                "metrics":
                    challenger_metrics
            }
        )


        difference = (
            challenger[
                "score"
            ]
            - champion[
                "score"
            ]
        )


        if difference >= float(
            margin
        ):

            decision = (
                "SHADOW_CHALLENGER_LEADS"
            )


        elif difference > 0:

            decision = (
                "KEEP_OBSERVING"
            )


        elif difference <= -10:

            decision = (
                "CHALLENGER_DEGRADED"
            )


        else:

            decision = (
                "SHADOW_CHAMPION_RETAINS"
            )


        return {
            "decision":
                decision,

            "champion_fitness":
                champion,

            "challenger_fitness":
                challenger,

            "margin":
                difference,

            "automatic_production_promotion":
                False,

            "automatic_registry_mutation":
                False,

            "automatic_broker_action":
                False,

            "research_only":
                True,
        }


shadow_champion_challenger = (
    ShadowChampionChallenger()
)
