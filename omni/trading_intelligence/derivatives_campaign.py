from __future__ import annotations


STATE_SCORE = {
    "PORTFOLIO_RESEARCH_ELIGIBLE":
        5,

    "EXTENDED_RESEARCH_ELIGIBLE":
        4,

    "PROMOTE":
        3,

    "KEEP_TESTING":
        2,

    "DEGRADE":
        1,

    "RETIRE":
        0,
}


class DerivativesResearchCampaign:

    MAX_CANDIDATES = 50


    def run(
        self,
        candidates,
    ):

        candidates = tuple(
            candidates
        )


        if not candidates:

            raise ValueError(
                "At least one candidate is required."
            )


        if len(
            candidates
        ) > self.MAX_CANDIDATES:

            raise ValueError(
                "Research campaign candidate limit exceeded."
            )


        rows = []


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


            v5 = dict(
                candidate.get(
                    "v5_report",
                    {}
                )
            )


            v5_state = (
                v5.get(
                    "recommendation",
                    {}
                ).get(
                    "recommendation"
                )
                or candidate.get(
                    "v5_recommendation"
                )
                or "KEEP_TESTING"
            )


            c3 = dict(
                candidate.get(
                    "c3_campaign",
                    {}
                )
            )


            c3_pass_rate = float(
                c3.get(
                    "oos_pass_rate",
                    0.0,
                )
            )


            if v5_state == "RETIRE":

                state = "RETIRE"


            elif v5_state == "DEGRADE":

                state = "DEGRADE"


            elif (
                v5_state == "PROMOTE"
                and c3
                and c3_pass_rate >= 0.60
            ):

                state = (
                    "PORTFOLIO_RESEARCH_ELIGIBLE"
                )


            elif v5_state == "PROMOTE":

                state = (
                    "EXTENDED_RESEARCH_ELIGIBLE"
                )


            else:

                state = "KEEP_TESTING"


            rows.append(
                {
                    "candidate_id":
                        candidate_id,

                    "state":
                        state,

                    "score":
                        STATE_SCORE.get(
                            state,
                            0,
                        ),

                    "v5_recommendation":
                        v5_state,

                    "c3_oos_pass_rate":
                        (
                            c3_pass_rate
                            if c3
                            else None
                        ),

                    "automatic_promotion":
                        False,

                    "broker_execution":
                        False,
                }
            )


        rows.sort(
            key=lambda row:
                (
                    row[
                        "score"
                    ],
                    (
                        row[
                            "c3_oos_pass_rate"
                        ]
                        or 0.0
                    ),
                ),
            reverse=True,
        )


        return {
            "success":
                True,

            "candidate_count":
                len(
                    rows
                ),

            "ranking":
                tuple(
                    rows
                ),

            "best_candidate":
                rows[
                    0
                ],

            "max_candidates":
                self.MAX_CANDIDATES,

            "v5_authoritative":
                True,

            "nautilus_evidence_supported":
                True,

            "automatic_strategy_promotion":
                False,

            "automatic_registry_mutation":
                False,

            "automatic_capital_allocation":
                False,

            "automatic_broker_order":
                False,

            "research_only":
                True,
        }


derivatives_research_campaign = (
    DerivativesResearchCampaign()
)
