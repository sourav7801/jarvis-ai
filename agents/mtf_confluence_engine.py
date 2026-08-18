# ============================================================
# JARVIS MULTI-TIMEFRAME CONFLUENCE ENGINE
# V1
# ============================================================
#
# Purpose:
#   Combine multiple timeframe analyses into one setup score.
#
# Designed for:
#   - Intraday
#   - Swing trading
#   - Options
#   - Stocks
#   - Indexes
#
# Timeframes:
#   5m
#   15m
#   30m
#   1h
#   4h
#   1d
#   1w
#
# IMPORTANT:
#   This engine does not place orders.
# ============================================================

from __future__ import annotations

from typing import Any, Dict, List


class MultiTimeframeConfluenceEngine:

    def __init__(self):

        self.weights = {

            "5m": 0.05,

            "15m": 0.10,

            "30m": 0.10,

            "1h": 0.15,

            "4h": 0.20,

            "1d": 0.25,

            "1w": 0.15,

        }

    # ========================================================
    # NORMALIZE BIAS
    # ========================================================

    def _bias(
        self,
        analysis: Dict[str, Any],
    ) -> str:

        return str(

            analysis.get(
                "bias",
                analysis.get(
                    "trend",
                    "NEUTRAL",
                ),
            )

            or "NEUTRAL"

        ).upper()

    # ========================================================
    # TIMEFRAME SCORE
    # ========================================================

    def timeframe_score(
        self,
        analysis: Dict[str, Any],
        direction: str,
    ) -> float:

        if not analysis:
            return 0.0

        direction = str(
            direction
        ).upper()

        bias = self._bias(
            analysis
        )

        regime = str(
            analysis.get(
                "regime",
                "TRANSITION",
            )
            or "TRANSITION"
        ).upper()

        confidence = float(
            analysis.get(
                "confidence",
                50.0,
            )
            or 50.0
        )

        # ----------------------------------------------------
        # Directional agreement
        # ----------------------------------------------------

        if bias == direction:

            score = 70.0

        elif bias == "NEUTRAL":

            score = 50.0

        else:

            score = 20.0

        # ----------------------------------------------------
        # Confidence
        # ----------------------------------------------------

        confidence_factor = (
            max(
                0.0,
                min(
                    100.0,
                    confidence,
                ),
            )
            / 100.0
        )

        score *= (
            0.60
            +
            0.40
            * confidence_factor
        )

        # ----------------------------------------------------
        # Regime
        # ----------------------------------------------------

        if regime in {
            "TRENDING_BULL",
            "TRENDING_BEAR",
        }:

            score += 12.0

        elif regime == "RANGE":

            score -= 8.0

        elif regime in {
            "TRANSITION",
            "HIGH_VOLATILITY",
        }:

            score -= 12.0

        return max(
            0.0,
            min(
                100.0,
                score,
            ),
        )

    # ========================================================
    # ANALYZE
    # ========================================================

    def analyze(
        self,
        timeframe_data: Dict[
            str,
            Dict[str, Any],
        ],
        preferred_direction: str = "AUTO",
    ) -> Dict[str, Any]:

        if not timeframe_data:

            return {

                "success":
                    False,

                "message":
                    "No timeframe analysis supplied.",

            }

        preferred_direction = str(
            preferred_direction
            or "AUTO"
        ).upper()

        # ----------------------------------------------------
        # Determine direction
        # ----------------------------------------------------

        bullish_weight = 0.0
        bearish_weight = 0.0

        for timeframe, analysis in (
            timeframe_data.items()
        ):

            weight = self.weights.get(
                timeframe,
                0.10,
            )

            bias = self._bias(
                analysis
            )

            if bias == "BULLISH":

                bullish_weight += weight

            elif bias == "BEARISH":

                bearish_weight += weight

        if preferred_direction == "AUTO":

            if (
                bullish_weight
                >
                bearish_weight
                + 0.10
            ):

                direction = "BULLISH"

            elif (
                bearish_weight
                >
                bullish_weight
                + 0.10
            ):

                direction = "BEARISH"

            else:

                direction = "NEUTRAL"

        else:

            direction = preferred_direction

        # ----------------------------------------------------
        # Weighted confluence
        # ----------------------------------------------------

        weighted_score = 0.0
        total_weight = 0.0

        timeframe_results = {}

        for timeframe, analysis in (
            timeframe_data.items()
        ):

            weight = self.weights.get(
                timeframe,
                0.10,
            )

            score = self.timeframe_score(
                analysis,
                direction,
            )

            weighted_score += (
                score
                * weight
            )

            total_weight += weight

            timeframe_results[
                timeframe
            ] = {

                "bias":
                    self._bias(
                        analysis
                    ),

                "score":
                    round(
                        score,
                        2,
                    ),

                "weight":
                    weight,

                "weighted_score":
                    round(
                        score * weight,
                        2,
                    ),

                "regime":
                    analysis.get(
                        "regime",
                    ),

                "confidence":
                    analysis.get(
                        "confidence",
                    ),

            }

        if total_weight > 0:

            confluence_score = (
                weighted_score
                /
                total_weight
            )

        else:

            confluence_score = 0.0

        # ----------------------------------------------------
        # Agreement
        # ----------------------------------------------------

        bullish_count = 0
        bearish_count = 0
        neutral_count = 0

        for analysis in (
            timeframe_data.values()
        ):

            bias = self._bias(
                analysis
            )

            if bias == "BULLISH":

                bullish_count += 1

            elif bias == "BEARISH":

                bearish_count += 1

            else:

                neutral_count += 1

        total_timeframes = (
            bullish_count
            +
            bearish_count
            +
            neutral_count
        )

        if total_timeframes:

            if direction == "BULLISH":

                agreement = (
                    bullish_count
                    /
                    total_timeframes
                    * 100.0
                )

            elif direction == "BEARISH":

                agreement = (
                    bearish_count
                    /
                    total_timeframes
                    * 100.0
                )

            else:

                agreement = (
                    neutral_count
                    /
                    total_timeframes
                    * 100.0
                )

        else:

            agreement = 0.0

        # ----------------------------------------------------
        # Quality classification
        # ----------------------------------------------------

        if (
            confluence_score >= 80
            and
            agreement >= 70
        ):

            quality = "A+"

        elif (
            confluence_score >= 72
            and
            agreement >= 60
        ):

            quality = "A"

        elif (
            confluence_score >= 62
            and
            agreement >= 50
        ):

            quality = "B"

        elif (
            confluence_score >= 50
        ):

            quality = "WATCH"

        else:

            quality = "AVOID"

        # ----------------------------------------------------
        # Conflicting higher timeframe
        # ----------------------------------------------------

        higher_timeframe_warning = False

        higher_timeframes = [
            "1d",
            "1w",
        ]

        for timeframe in higher_timeframes:

            analysis = timeframe_data.get(
                timeframe
            )

            if not analysis:
                continue

            bias = self._bias(
                analysis
            )

            if (
                direction == "BULLISH"
                and
                bias == "BEARISH"
            ):

                higher_timeframe_warning = True

            elif (
                direction == "BEARISH"
                and
                bias == "BULLISH"
            ):

                higher_timeframe_warning = True

        evidence: List[str] = []

        evidence.append(
            f"Directional confluence: {direction}."
        )

        evidence.append(
            f"Weighted confluence score: "
            f"{confluence_score:.1f}/100."
        )

        evidence.append(
            f"Timeframe agreement: "
            f"{agreement:.1f}%."
        )

        if higher_timeframe_warning:

            evidence.append(
                "Higher timeframe conflict detected."
            )

        else:

            evidence.append(
                "No major higher timeframe conflict detected."
            )

        # ----------------------------------------------------
        # Final trade permission
        # ----------------------------------------------------

        permission = "WAIT"

        if (
            direction in {
                "BULLISH",
                "BEARISH",
            }
            and
            confluence_score >= 70
            and
            agreement >= 60
            and
            not higher_timeframe_warning
        ):

            permission = "CANDIDATE"

        return {

            "success":
                True,

            "direction":
                direction,

            "confluence_score":
                round(
                    confluence_score,
                    2,
                ),

            "agreement":
                round(
                    agreement,
                    2,
                ),

            "quality":
                quality,

            "permission":
                permission,

            "bullish_count":
                bullish_count,

            "bearish_count":
                bearish_count,

            "neutral_count":
                neutral_count,

            "higher_timeframe_warning":
                higher_timeframe_warning,

            "timeframes":
                timeframe_results,

            "evidence":
                evidence,

        }

    # ========================================================
    # FORMAT
    # ========================================================

    def format_result(
        self,
        result: Dict[str, Any],
    ) -> str:

        if not result.get(
            "success",
            False,
        ):

            return (
                "MULTI-TIMEFRAME ANALYSIS FAILED\n"
                "--------------------------------------------------\n"
                +
                str(
                    result.get(
                        "message",
                        "Unknown error.",
                    )
                )
            )

        lines = []

        lines.append(
            "JARVIS MULTI-TIMEFRAME CONFLUENCE"
        )

        lines.append(
            "--------------------------------------------------"
        )

        lines.append(
            f"Direction: "
            f"{result.get('direction')}"
        )

        lines.append(
            f"Confluence Score: "
            f"{result.get('confluence_score')}/100"
        )

        lines.append(
            f"Agreement: "
            f"{result.get('agreement')}%"
        )

        lines.append(
            f"Setup Quality: "
            f"{result.get('quality')}"
        )

        lines.append(
            f"Permission: "
            f"{result.get('permission')}"
        )

        lines.append("")

        lines.append(
            "TIMEFRAME BREAKDOWN"
        )

        for timeframe, item in (
            result.get(
                "timeframes",
                {},
            ).items()
        ):

            lines.append(

                f"{timeframe}: "
                f"{item.get('bias')} | "
                f"score={item.get('score')} | "
                f"regime={item.get('regime')}"

            )

        lines.append("")

        lines.append(
            "EVIDENCE"
        )

        for item in result.get(
            "evidence",
            [],
        ):

            lines.append(
                f"- {item}"
            )

        lines.append("")

        lines.append(
            "IMPORTANT: "
            "Confluence is a setup-quality measure, "
            "not a probability of profit."
        )

        return "\n".join(
            lines
        )


# ============================================================
# GLOBAL
# ============================================================

mtf_confluence_engine = (
    MultiTimeframeConfluenceEngine()
)


# ============================================================
# SIMPLE FUNCTION
# ============================================================

def analyze_mtf(
    timeframe_data,
    preferred_direction="AUTO",
):

    return (
        mtf_confluence_engine.analyze(
            timeframe_data=timeframe_data,
            preferred_direction=preferred_direction,
        )
    )


# ============================================================
# TEST
# ============================================================

if __name__ == "__main__":

    example = {

        "15m": {

            "bias":
                "BULLISH",

            "regime":
                "TRENDING_BULL",

            "confidence":
                75,

        },

        "1h": {

            "bias":
                "BULLISH",

            "regime":
                "TRENDING_BULL",

            "confidence":
                78,

        },

        "4h": {

            "bias":
                "BULLISH",

            "regime":
                "TRENDING_BULL",

            "confidence":
                80,

        },

        "1d": {

            "bias":
                "BULLISH",

            "regime":
                "TRENDING_BULL",

            "confidence":
                82,

        },

        "1w": {

            "bias":
                "BULLISH",

            "regime":
                "TRENDING_BULL",

            "confidence":
                76,

        },

    }

    result = analyze_mtf(
        example
    )

    print(
        "=" * 60
    )

    print(
        "JARVIS MULTI-TIMEFRAME CONFLUENCE ENGINE"
    )

    print(
        "=" * 60
    )

    print()

    print(
        mtf_confluence_engine.format_result(
            result
        )
    )

    print()

    print(
        "Multi-Timeframe Confluence Engine loaded successfully."
    )