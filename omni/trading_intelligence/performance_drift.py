from __future__ import annotations


def _finite(
    value,
    default=0.0,
):

    try:
        return float(
            value
        )

    except Exception:
        return float(
            default
        )


class PerformanceDriftDetector:

    def compare(
        self,
        baseline_metrics,
        recent_metrics,
    ):

        baseline_expectancy = _finite(
            baseline_metrics.get(
                "expectancy"
            )
        )

        recent_expectancy = _finite(
            recent_metrics.get(
                "expectancy"
            )
        )


        baseline_pf = _finite(
            baseline_metrics.get(
                "profit_factor"
            ),
            1.0,
        )

        recent_pf = _finite(
            recent_metrics.get(
                "profit_factor"
            ),
            1.0,
        )


        baseline_win = _finite(
            baseline_metrics.get(
                "win_rate"
            )
        )

        recent_win = _finite(
            recent_metrics.get(
                "win_rate"
            )
        )


        baseline_dd = max(
            0.0,
            _finite(
                baseline_metrics.get(
                    "max_drawdown_pct"
                )
            ),
        )

        recent_dd = max(
            0.0,
            _finite(
                recent_metrics.get(
                    "max_drawdown_pct"
                )
            ),
        )


        expectancy_deterioration = max(
            0.0,
            (
                baseline_expectancy
                - recent_expectancy
            )
            / max(
                abs(
                    baseline_expectancy
                ),
                1.0,
            ),
        )


        pf_deterioration = max(
            0.0,
            (
                baseline_pf
                - recent_pf
            )
            / max(
                abs(
                    baseline_pf
                ),
                1.0,
            ),
        )


        win_deterioration = max(
            0.0,
            baseline_win
            - recent_win,
        )


        dd_deterioration = max(
            0.0,
            recent_dd
            - baseline_dd,
        )


        score = min(
            100.0,
            (
                expectancy_deterioration
                * 35.0
                + pf_deterioration
                * 25.0
                + win_deterioration
                * 100.0
                * 20.0
                / 100.0
                + dd_deterioration
                * 100.0
                * 20.0
                / 100.0
            ),
        )


        if score < 20:

            state = "NORMAL"


        elif score < 40:

            state = "WATCH"


        elif score < 70:

            state = "DEGRADED"


        else:

            state = "SEVERE"


        return {
            "drift_score":
                score,

            "state":
                state,

            "components": {
                "expectancy":
                    expectancy_deterioration,

                "profit_factor":
                    pf_deterioration,

                "win_rate":
                    win_deterioration,

                "drawdown":
                    dd_deterioration,
            },

            "automatic_strategy_shutdown":
                False,

            "automatic_broker_action":
                False,

            "research_only":
                True,
        }


performance_drift_detector = (
    PerformanceDriftDetector()
)
