from __future__ import annotations


class ResearchStrategyWeighting:

    def calculate(
        self,
        evidence,
    ):

        evidence = dict(
            evidence
        )


        if not evidence:

            return {
                "weights":
                    {},

                "research_only":
                    True,

                "capital_allocation":
                    False,
            }


        raw = {}


        for strategy_id, values in (
            evidence.items()
        ):

            validation = float(
                values.get(
                    "validation_score",
                    0.0,
                )
            )


            recent = float(
                values.get(
                    "recent_score",
                    0.0,
                )
            )


            drift = max(
                0.0,
                float(
                    values.get(
                        "drift_score",
                        0.0,
                    )
                ),
            )


            score = max(
                0.05,
                (
                    1.0
                    + validation
                    / 50.0
                    + recent
                    / 50.0
                    - drift
                    / 100.0
                ),
            )


            raw[
                str(
                    strategy_id
                )
            ] = score


        total = sum(
            raw.values()
        )


        weights = {
            strategy_id:
                score
                / total

            for strategy_id, score
            in raw.items()
        }


        return {
            "weights":
                weights,

            "sum":
                sum(
                    weights.values()
                ),

            "research_only":
                True,

            "capital_allocation":
                False,

            "broker_position_sizing":
                False,

            "automatic_production_change":
                False,
        }


research_strategy_weighting = (
    ResearchStrategyWeighting()
)
