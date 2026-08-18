from __future__ import annotations

from statistics import (
    fmean,
)


from omni.trading_intelligence.nautilus_c3_bridge import (
    nautilus_c3_portfolio_bridge,
)


class NautilusC3WalkForward:

    @staticmethod
    def _aligned_length(
        portfolio,
    ):

        strategies = list(
            portfolio[
                "strategies"
            ]
        )


        lengths = {
            len(
                slot[
                    "bars"
                ]
            )

            for slot in strategies
        }


        signal_lengths = {
            len(
                slot[
                    "signals"
                ]
            )

            for slot in strategies
        }


        if (
            len(
                lengths
            ) != 1
            or lengths
            != signal_lengths
        ):

            raise ValueError(
                "C3 walk-forward currently requires "
                "aligned equal-length strategy datasets."
            )


        total = next(
            iter(
                lengths
            )
        )


        timestamps = None


        for slot in strategies:

            current = tuple(
                str(
                    (
                        bar.get(
                            "timestamp"
                        )
                        if isinstance(
                            bar,
                            dict,
                        )
                        else getattr(
                            bar,
                            "timestamp",
                        )
                    )
                )

                for bar
                in slot[
                    "bars"
                ]
            )


            if timestamps is None:

                timestamps = current


            elif current != timestamps:

                raise ValueError(
                    "Walk-forward timestamps are not aligned."
                )


        return total


    @staticmethod
    def _slice(
        portfolio,
        start,
        end,
    ):

        result = dict(
            portfolio
        )


        strategies = []


        for slot in portfolio[
            "strategies"
        ]:

            child = dict(
                slot
            )


            child[
                "bars"
            ] = tuple(
                slot[
                    "bars"
                ][
                    start:end
                ]
            )


            child[
                "signals"
            ] = tuple(
                slot[
                    "signals"
                ][
                    start:end
                ]
            )


            strategies.append(
                child
            )


        result[
            "strategies"
        ] = tuple(
            strategies
        )


        return result


    @staticmethod
    def _research_pnl(
        result,
    ):

        engine = result.get(
            "realized_pnl_numeric"
        )


        if engine is not None:

            return (
                float(
                    engine
                ),
                "engine_realized_pnl",
            )


        return (
            float(
                result[
                    "drawdown_attribution"
                ][
                    "portfolio_total_proxy_pnl"
                ]
            ),
            "signal_proxy_pnl",
        )


    def run(
        self,
        portfolio,
        *,
        train_size,
        validation_size,
        test_size,
        step=None,
        timeout=180,
    ):

        total = self._aligned_length(
            portfolio
        )


        train_size = int(
            train_size
        )

        validation_size = int(
            validation_size
        )

        test_size = int(
            test_size
        )


        step = int(
            step
            if step is not None
            else test_size
        )


        if min(
            train_size,
            validation_size,
            test_size,
            step,
        ) < 10:

            raise ValueError(
                "Each C3 walk-forward segment "
                "must contain at least 10 bars."
            )


        required = (
            train_size
            + validation_size
            + test_size
        )


        if total < required:

            raise ValueError(
                "Insufficient aligned data for C3 walk-forward."
            )


        windows = []

        start = 0

        window_id = 0


        while (
            start
            + required
            <= total
        ):

            train_end = (
                start
                + train_size
            )


            validation_end = (
                train_end
                + validation_size
            )


            test_end = (
                validation_end
                + test_size
            )


            train_result = (
                nautilus_c3_portfolio_bridge
                .run(
                    self._slice(
                        portfolio,
                        start,
                        train_end,
                    ),
                    timeout=timeout,
                )
            )


            validation_result = (
                nautilus_c3_portfolio_bridge
                .run(
                    self._slice(
                        portfolio,
                        train_end,
                        validation_end,
                    ),
                    timeout=timeout,
                )
            )


            oos_result = (
                nautilus_c3_portfolio_bridge
                .run(
                    self._slice(
                        portfolio,
                        validation_end,
                        test_end,
                    ),
                    timeout=timeout,
                )
            )


            train_pnl, train_source = (
                self._research_pnl(
                    train_result
                )
            )


            validation_pnl, validation_source = (
                self._research_pnl(
                    validation_result
                )
            )


            oos_pnl, oos_source = (
                self._research_pnl(
                    oos_result
                )
            )


            windows.append(
                {
                    "window_id":
                        window_id,

                    "indexes": {
                        "start":
                            start,

                        "train_end":
                            train_end,

                        "validation_end":
                            validation_end,

                        "test_end":
                            test_end,
                    },

                    "train": {
                        "pnl":
                            train_pnl,

                        "source":
                            train_source,

                        "fill_count":
                            train_result[
                                "fill_count"
                            ],
                    },

                    "validation": {
                        "pnl":
                            validation_pnl,

                        "source":
                            validation_source,

                        "fill_count":
                            validation_result[
                                "fill_count"
                            ],
                    },

                    "out_of_sample": {
                        "pnl":
                            oos_pnl,

                        "source":
                            oos_source,

                        "fill_count":
                            oos_result[
                                "fill_count"
                            ],

                        "profitable":
                            oos_pnl
                            > 0,
                    },
                }
            )


            start += step

            window_id += 1


        profitable = sum(
            1

            for row in windows

            if row[
                "out_of_sample"
            ][
                "profitable"
            ]
        )


        oos_pnls = [
            row[
                "out_of_sample"
            ][
                "pnl"
            ]

            for row in windows
        ]


        return {
            "success":
                True,

            "window_count":
                len(
                    windows
                ),

            "windows":
                tuple(
                    windows
                ),

            "oos_profitable_windows":
                profitable,

            "oos_pass_rate":
                (
                    profitable
                    / len(
                        windows
                    )

                    if windows

                    else 0.0
                ),

            "average_oos_pnl":
                (
                    fmean(
                        oos_pnls
                    )

                    if oos_pnls

                    else 0.0
                ),

            "chronological":
                True,

            "precomputed_signal_replay":
                True,

            "candidate_reoptimized_on_oos":
                False,

            "oos_tuning":
                False,

            "automatic_strategy_promotion":
                False,

            "research_only":
                True,
        }


nautilus_c3_walk_forward = (
    NautilusC3WalkForward()
)


def nautilus_c3_v5_gate(
    v5_report,
    c3_campaign,
):

    recommendation = (
        v5_report.get(
            "recommendation",
            {}
        ).get(
            "recommendation"
        )
    )


    pass_rate = float(
        c3_campaign.get(
            "oos_pass_rate",
            0.0,
        )
    )


    safe = (
        c3_campaign.get(
            "success"
        )
        is True

        and c3_campaign.get(
            "oos_tuning"
        )
        is False

        and c3_campaign.get(
            "candidate_reoptimized_on_oos"
        )
        is False
    )


    if not safe:

        state = "REJECT"


    elif recommendation == "RETIRE":

        state = "RETIRE"


    elif recommendation == "DEGRADE":

        state = "DEGRADE"


    elif (
        recommendation == "PROMOTE"
        and pass_rate >= 0.60
    ):

        state = (
            "PORTFOLIO_RESEARCH_ELIGIBLE"
        )


    else:

        state = "KEEP_TESTING"


    return {
        "state":
            state,

        "v5_recommendation":
            recommendation,

        "c3_oos_pass_rate":
            pass_rate,

        "oos_tuning":
            False,

        "production_promotion":
            False,

        "automatic_registry_mutation":
            False,

        "automatic_portfolio_allocation":
            False,

        "automatic_broker_order":
            False,

        "research_only":
            True,
    }
