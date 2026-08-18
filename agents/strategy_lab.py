# ============================================================
# JARVIS STRATEGY LAB
# V1
# ============================================================
#
# Purpose:
#   Research and rank strategy families.
#
# Strategies:
#   - TREND_FOLLOWING
#   - BREAKOUT
#   - MOMENTUM
#   - MEAN_REVERSION
#   - SWING_PULLBACK
#   - OPTIONS_DIRECTIONAL
#   - OPTIONS_DEFINED_RISK
#   - OPTIONS_RANGE
#   - OPTIONS_LONG_VOLATILITY
#
# This is a research/ranking layer.
# It does NOT place trades.
# ============================================================

from __future__ import annotations

from typing import Any, Dict, List


class StrategyLab:

    def __init__(self):

        self.strategies = [

            "TREND_FOLLOWING",

            "BREAKOUT",

            "MOMENTUM",

            "MEAN_REVERSION",

            "SWING_PULLBACK",

            "OPTIONS_DIRECTIONAL",

            "OPTIONS_DEFINED_RISK",

            "OPTIONS_RANGE",

            "OPTIONS_LONG_VOLATILITY",

        ]

    # ========================================================
    # REGIME COMPATIBILITY
    # ========================================================

    def regime_score(
        self,
        strategy: str,
        regime: str,
        volatility: str,
    ) -> float:

        regime = str(
            regime
            or "TRANSITION"
        ).upper()

        volatility = str(
            volatility
            or "NORMAL_VOLATILITY"
        ).upper()

        table = {

            "TREND_FOLLOWING": {

                "TRENDING_BULL": 90,

                "TRENDING_BEAR": 90,

                "RANGE": 25,

                "TRANSITION": 35,

                "HIGH_VOLATILITY": 45,

            },

            "BREAKOUT": {

                "TRENDING_BULL": 85,

                "TRENDING_BEAR": 85,

                "RANGE": 40,

                "TRANSITION": 45,

                "HIGH_VOLATILITY": 50,

            },

            "MOMENTUM": {

                "TRENDING_BULL": 85,

                "TRENDING_BEAR": 85,

                "RANGE": 35,

                "TRANSITION": 40,

                "HIGH_VOLATILITY": 50,

            },

            "MEAN_REVERSION": {

                "TRENDING_BULL": 30,

                "TRENDING_BEAR": 30,

                "RANGE": 90,

                "TRANSITION": 65,

                "HIGH_VOLATILITY": 45,

            },

            "SWING_PULLBACK": {

                "TRENDING_BULL": 90,

                "TRENDING_BEAR": 90,

                "RANGE": 35,

                "TRANSITION": 50,

                "HIGH_VOLATILITY": 45,

            },

            "OPTIONS_DIRECTIONAL": {

                "TRENDING_BULL": 85,

                "TRENDING_BEAR": 85,

                "RANGE": 25,

                "TRANSITION": 30,

                "HIGH_VOLATILITY": 40,

            },

            "OPTIONS_DEFINED_RISK": {

                "TRENDING_BULL": 80,

                "TRENDING_BEAR": 80,

                "RANGE": 65,

                "TRANSITION": 45,

                "HIGH_VOLATILITY": 70,

            },

            "OPTIONS_RANGE": {

                "TRENDING_BULL": 25,

                "TRENDING_BEAR": 25,

                "RANGE": 90,

                "TRANSITION": 65,

                "HIGH_VOLATILITY": 75,

            },

            "OPTIONS_LONG_VOLATILITY": {

                "TRENDING_BULL": 55,

                "TRENDING_BEAR": 55,

                "RANGE": 45,

                "TRANSITION": 70,

                "HIGH_VOLATILITY": 35,

            },

        }

        base = table.get(
            strategy,
            {},
        ).get(
            regime,
            40,
        )

        # Extra volatility adjustment.

        if (
            volatility
            == "HIGH_VOLATILITY"
        ):

            if strategy in {
                "OPTIONS_DEFINED_RISK",
                "OPTIONS_RANGE",
            }:

                base += 8

            elif strategy in {
                "TREND_FOLLOWING",
                "SWING_PULLBACK",
            }:

                base -= 8

        elif (
            volatility
            == "LOW_VOLATILITY"
        ):

            if strategy == (
                "OPTIONS_LONG_VOLATILITY"
            ):

                base += 12

        return max(
            0,
            min(
                100,
                base,
            ),
        )

    # ========================================================
    # DIRECTION COMPATIBILITY
    # ========================================================

    def direction_score(
        self,
        strategy: str,
        bias: str,
    ) -> float:

        bias = str(
            bias
            or "NEUTRAL"
        ).upper()

        if strategy in {
            "MEAN_REVERSION",
            "OPTIONS_RANGE",
        }:

            if bias == "NEUTRAL":
                return 90

            return 65

        if bias in {
            "BULLISH",
            "BEARISH",
        }:

            return 85

        return 45

    # ========================================================
    # MOMENTUM
    # ========================================================

    def momentum_score(
        self,
        strategy: str,
        momentum: str,
    ) -> float:

        momentum = str(
            momentum
            or "NEUTRAL"
        ).upper()

        if strategy in {
            "MOMENTUM",
            "BREAKOUT",
            "TREND_FOLLOWING",
            "OPTIONS_DIRECTIONAL",
        }:

            if momentum == "STRONG":
                return 95

            if momentum == "BULLISH":
                return 75

            if momentum == "BEARISH":
                return 75

            return 40

        if strategy in {
            "MEAN_REVERSION",
            "OPTIONS_RANGE",
        }:

            if momentum == "NEUTRAL":
                return 85

            return 55

        return 60

    # ========================================================
    # TREND SCORE
    # ========================================================

    def trend_score(
        self,
        strategy: str,
        trend: str,
    ) -> float:

        trend = str(
            trend
            or "NEUTRAL"
        ).upper()

        if strategy in {
            "TREND_FOLLOWING",
            "BREAKOUT",
            "MOMENTUM",
            "SWING_PULLBACK",
            "OPTIONS_DIRECTIONAL",
            "OPTIONS_DEFINED_RISK",
        }:

            if trend in {
                "BULLISH",
                "BEARISH",
            }:

                return 90

            return 40

        if strategy in {
            "MEAN_REVERSION",
            "OPTIONS_RANGE",
        }:

            if trend == "NEUTRAL":
                return 90

            return 45

        return 60

    # ========================================================
    # SCORE ONE STRATEGY
    # ========================================================

    def score_strategy(
        self,
        strategy: str,
        technical: Dict[str, Any],
        regime: Dict[str, Any],
        confluence: Dict[str, Any],
        option_context: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:

        option_context = (
            option_context
            or {}
        )

        regime_name = regime.get(
            "regime",
            "TRANSITION",
        )

        volatility = regime.get(
            "volatility_regime",
            "NORMAL_VOLATILITY",
        )

        bias = regime.get(
            "bias",
            "NEUTRAL",
        )

        trend = technical.get(
            "trend",
            "NEUTRAL",
        )

        momentum = technical.get(
            "momentum",
            "NEUTRAL",
        )

        regime_score = (
            self.regime_score(
                strategy,
                regime_name,
                volatility,
            )
        )

        direction_score = (
            self.direction_score(
                strategy,
                bias,
            )
        )

        momentum_score = (
            self.momentum_score(
                strategy,
                momentum,
            )
        )

        trend_score = (
            self.trend_score(
                strategy,
                trend,
            )
        )

        confluence_score = float(
            confluence.get(
                "confluence_score",
                50,
            )
        )

        # ----------------------------------------------------
        # Option-specific context
        # ----------------------------------------------------

        option_bonus = 0.0

        if strategy.startswith(
            "OPTIONS_"
        ):

            iv = option_context.get(
                "atm_iv"
            )

            pcr = option_context.get(
                "pcr"
            )

            if iv is not None:

                try:

                    iv = float(
                        iv
                    )

                    if (
                        strategy
                        ==
                        "OPTIONS_LONG_VOLATILITY"
                        and
                        iv < 18
                    ):

                        option_bonus += 15

                    elif (
                        strategy
                        ==
                        "OPTIONS_RANGE"
                        and
                        iv >= 25
                    ):

                        option_bonus += 15

                    elif (
                        strategy
                        ==
                        "OPTIONS_DEFINED_RISK"
                        and
                        iv >= 20
                    ):

                        option_bonus += 10

                except Exception:
                    pass

            if pcr is not None:

                try:

                    pcr = float(
                        pcr
                    )

                    if (
                        strategy
                        in {
                            "OPTIONS_DIRECTIONAL",
                            "OPTIONS_DEFINED_RISK",
                        }
                        and
                        pcr > 1.1
                        and
                        bias == "BULLISH"
                    ):

                        option_bonus += 10

                    elif (
                        strategy
                        in {
                            "OPTIONS_DIRECTIONAL",
                            "OPTIONS_DEFINED_RISK",
                        }
                        and
                        pcr < 0.85
                        and
                        bias == "BEARISH"
                    ):

                        option_bonus += 10

                except Exception:
                    pass

        # ----------------------------------------------------
        # Final score
        # ----------------------------------------------------

        final_score = (

            regime_score * 0.30

            +

            confluence_score * 0.25

            +

            trend_score * 0.15

            +

            momentum_score * 0.15

            +

            direction_score * 0.10

            +

            option_bonus

            * 0.05

        )

        final_score = max(
            0,
            min(
                100,
                final_score,
            ),
        )

        return {

            "strategy":
                strategy,

            "score":
                round(
                    final_score,
                    2,
                ),

            "regime_score":
                round(
                    regime_score,
                    2,
                ),

            "confluence_score":
                round(
                    confluence_score,
                    2,
                ),

            "trend_score":
                round(
                    trend_score,
                    2,
                ),

            "momentum_score":
                round(
                    momentum_score,
                    2,
                ),

            "direction_score":
                round(
                    direction_score,
                    2,
                ),

            "option_bonus":
                round(
                    option_bonus,
                    2,
                ),

        }

    # ========================================================
    # RANK
    # ========================================================

    def rank(
        self,
        technical: Dict[str, Any],
        regime: Dict[str, Any],
        confluence: Dict[str, Any],
        option_context: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:

        rankings = []

        for strategy in (
            self.strategies
        ):

            rankings.append(

                self.score_strategy(

                    strategy=strategy,

                    technical=technical,

                    regime=regime,

                    confluence=confluence,

                    option_context=option_context,

                )

            )

        rankings.sort(
            key=lambda item:
                item["score"],
            reverse=True,
        )

        # ----------------------------------------------------
        # Setup permission
        # ----------------------------------------------------

        quality = confluence.get(
            "quality",
            "WATCH",
        )

        permission = confluence.get(
            "permission",
            "WAIT",
        )

        if (
            permission
            != "CANDIDATE"
        ):

            recommendation = "WAIT"

        elif not rankings:

            recommendation = "WAIT"

        elif rankings[0]["score"] < 70:

            recommendation = "WAIT"

        else:

            recommendation = (
                rankings[0]["strategy"]
            )

        return {

            "success":
                True,

            "recommendation":
                recommendation,

            "setup_quality":
                quality,

            "permission":
                permission,

            "rankings":
                rankings,

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
                "STRATEGY LAB FAILED\n"
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
            "JARVIS STRATEGY LAB"
        )

        lines.append(
            "--------------------------------------------------"
        )

        lines.append(
            f"Setup Quality: "
            f"{result.get('setup_quality')}"
        )

        lines.append(
            f"Permission: "
            f"{result.get('permission')}"
        )

        lines.append(
            f"Recommendation: "
            f"{result.get('recommendation')}"
        )

        lines.append("")

        lines.append(
            "STRATEGY RANKING"
        )

        for index, item in enumerate(
            result.get(
                "rankings",
                [],
            ),
            start=1,
        ):

            lines.append(

                f"{index}. "
                f"{item['strategy']} "
                f"{item['score']}/100"

            )

        lines.append("")

        lines.append(
            "IMPORTANT: "
            "These are research scores, "
            "not probabilities of profit."
        )

        return "\n".join(
            lines
        )


# ============================================================
# GLOBAL
# ============================================================

strategy_lab = StrategyLab()


# ============================================================
# SIMPLE FUNCTION
# ============================================================

def rank_strategies(
    technical,
    regime,
    confluence,
    option_context=None,
):

    return strategy_lab.rank(
        technical=technical,
        regime=regime,
        confluence=confluence,
        option_context=option_context,
    )


# ============================================================
# TEST
# ============================================================

if __name__ == "__main__":

    technical = {

        "trend":
            "BULLISH",

        "momentum":
            "STRONG",

    }

    regime = {

        "regime":
            "TRENDING_BULL",

        "bias":
            "BULLISH",

        "volatility_regime":
            "NORMAL_VOLATILITY",

    }

    confluence = {

        "confluence_score":
            84,

        "agreement":
            80,

        "quality":
            "A+",

        "permission":
            "CANDIDATE",

    }

    option_context = {

        "atm_iv":
            18.0,

        "pcr":
            1.18,

    }

    result = rank_strategies(

        technical=technical,

        regime=regime,

        confluence=confluence,

        option_context=option_context,

    )

    print(
        "=" * 60
    )

    print(
        "JARVIS STRATEGY LAB"
    )

    print(
        "=" * 60
    )

    print()

    print(
        strategy_lab.format_result(
            result
        )
    )

    print()

    print(
        "Strategy Lab loaded successfully."
    )