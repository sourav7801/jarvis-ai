from __future__ import annotations


class StrategyRetirementEngine:

    def evaluate(
        self,
        evaluation,
        *,
        retire_below=-20.0,
        degrade_below=0.0,
    ):

        score = float(
            evaluation[
                "fitness"
            ][
                "score"
            ]
        )


        if score <= retire_below:

            recommendation = (
                "RETIRE_PROPOSAL"
            )


        elif score <= degrade_below:

            recommendation = (
                "DEGRADE"
            )


        else:

            recommendation = (
                "KEEP"
            )


        return {
            "candidate_id":
                evaluation[
                    "candidate_id"
                ],

            "score":
                score,

            "recommendation":
                recommendation,

            "automatic_delete":
                False,

            "automatic_registry_change":
                False,

            "research_only":
                True,
        }


strategy_retirement_engine = (
    StrategyRetirementEngine()
)
