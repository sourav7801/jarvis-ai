from __future__ import annotations


class ChampionChallenger:

    def compare(
        self,
        champion,
        challenger,
        *,
        minimum_margin=2.0,
    ):

        champion_score = float(
            champion[
                "fitness"
            ][
                "score"
            ]
        )


        challenger_score = float(
            challenger[
                "fitness"
            ][
                "score"
            ]
        )


        margin = (
            challenger_score
            - champion_score
        )


        if margin >= float(
            minimum_margin
        ):

            decision = (
                "RESEARCH_CHALLENGER_WINS"
            )


        elif margin > 0:

            decision = (
                "KEEP_TESTING"
            )


        elif margin <= -10:

            decision = (
                "CHALLENGER_DEGRADE"
            )


        else:

            decision = (
                "CHAMPION_RETAINS"
            )


        return {
            "decision":
                decision,

            "champion_score":
                champion_score,

            "challenger_score":
                challenger_score,

            "margin":
                margin,

            "production_promotion":
                False,

            "registry_mutation":
                False,

            "research_only":
                True,
        }


champion_challenger = (
    ChampionChallenger()
)
