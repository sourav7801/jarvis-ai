from __future__ import annotations

import math


STATE_BONUS = {
    "PORTFOLIO_RESEARCH_ELIGIBLE":
        20.0,

    "EXTENDED_RESEARCH_ELIGIBLE":
        12.0,

    "PROMOTE":
        10.0,

    "KEEP_TESTING":
        0.0,

    "DEGRADE":
        -20.0,

    "RETIRE":
        -1000.0,
}


class ResearchPortfolioOptimizer:

    MAX_CANDIDATES = 20


    def optimize(
        self,
        candidates,
        *,
        correlation_graph=None,
        temperature=10.0,
    ):

        candidates = tuple(
            candidates
        )


        if not candidates:

            raise ValueError(
                "At least one research candidate is required."
            )


        if len(
            candidates
        ) > self.MAX_CANDIDATES:

            raise ValueError(
                "Research optimizer candidate limit exceeded."
            )


        correlations = {}


        if correlation_graph:

            for edge in correlation_graph.get(
                "edges",
                ()
            ):

                correlation = edge.get(
                    "correlation"
                )


                if correlation is None:

                    continue


                left = edge[
                    "left"
                ]

                right = edge[
                    "right"
                ]


                correlations[
                    (
                        left,
                        right,
                    )
                ] = abs(
                    float(
                        correlation
                    )
                )


                correlations[
                    (
                        right,
                        left,
                    )
                ] = abs(
                    float(
                        correlation
                    )
                )


        rows = []


        symbols = [
            str(
                candidate.get(
                    "symbol",
                    ""
                )
            )

            for candidate
            in candidates
        ]


        for index, candidate in enumerate(
            candidates
        ):

            candidate = dict(
                candidate
            )


            candidate_id = str(
                candidate.get(
                    "candidate_id",
                    "candidate_"
                    + str(
                        index
                    ),
                )
            )


            state = str(
                candidate.get(
                    "validation_state",
                    "KEEP_TESTING",
                )
            ).upper()


            quality = float(
                candidate.get(
                    "quality_score",
                    0.0,
                )
            )


            symbol = str(
                candidate.get(
                    "symbol",
                    "",
                )
            )


            peer_correlations = []


            if symbol:

                for other_symbol in symbols:

                    if (
                        not other_symbol
                        or other_symbol
                        == symbol
                    ):

                        continue


                    value = correlations.get(
                        (
                            symbol,
                            other_symbol,
                        )
                    )


                    if value is not None:

                        peer_correlations.append(
                            value
                        )


            correlation_penalty = (
                (
                    sum(
                        peer_correlations
                    )
                    / len(
                        peer_correlations
                    )
                )
                * 20.0

                if peer_correlations

                else 0.0
            )


            adjusted = (
                quality
                + STATE_BONUS.get(
                    state,
                    0.0,
                )
                - correlation_penalty
            )


            eligible = (
                state != "RETIRE"
            )


            rows.append(
                {
                    "candidate_id":
                        candidate_id,

                    "symbol":
                        symbol,

                    "validation_state":
                        state,

                    "quality_score":
                        quality,

                    "correlation_penalty":
                        correlation_penalty,

                    "adjusted_research_score":
                        adjusted,

                    "eligible":
                        eligible,
                }
            )


        eligible_rows = [
            row

            for row in rows

            if row[
                "eligible"
            ]
        ]


        if not eligible_rows:

            raise ValueError(
                "All candidates are retired."
            )


        temperature = max(
            0.001,
            float(
                temperature
            ),
        )


        maximum = max(
            row[
                "adjusted_research_score"
            ]

            for row in eligible_rows
        )


        masses = {
            row[
                "candidate_id"
            ]:
                math.exp(
                    (
                        row[
                            "adjusted_research_score"
                        ]
                        - maximum
                    )
                    / temperature
                )

            for row in eligible_rows
        }


        total = sum(
            masses.values()
        )


        weights = {
            key:
                (
                    value
                    / total
                )

            for key, value
            in masses.items()
        }


        for row in rows:

            row[
                "research_weight"
            ] = weights.get(
                row[
                    "candidate_id"
                ],
                0.0,
            )


        rows.sort(
            key=lambda row:
                row[
                    "research_weight"
                ],
            reverse=True,
        )


        hhi = sum(
            weight
            * weight

            for weight in weights.values()
        )


        return {
            "success":
                True,

            "ranking":
                tuple(
                    rows
                ),

            "research_weights":
                weights,

            "hhi":
                hhi,

            "candidate_count":
                len(
                    rows
                ),

            "v5_validation_states_respected":
                True,

            "research_weights_drive_broker_capital":
                False,

            "automatic_capital_allocation":
                False,

            "automatic_portfolio_rebalance":
                False,

            "automatic_broker_order":
                False,

            "live_execution":
                False,

            "research_only":
                True,
        }


research_portfolio_optimizer = (
    ResearchPortfolioOptimizer()
)
