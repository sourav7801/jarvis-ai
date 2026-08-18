# ============================================================
# JARVIS CONFIDENCE ENGINE
# V2
# ============================================================
#
# Purpose:
#   Convert market evidence into a more realistic confidence
#   score.
#
# Confidence is NOT:
#   - probability of profit
#   - guarantee of success
#   - prediction certainty
#
# It measures how well the evidence agrees with the proposed
# direction AND how suitable the current market regime is.
#
# Inputs:
#   directional separation
#   trend strength
#   regime quality
#   pattern agreement
#   volatility suitability
#
# Output:
#   0 - 100 confidence score
# ============================================================

from __future__ import annotations

from typing import Any, Dict


class ConfidenceEngine:

    def __init__(self):

        self.minimum_confidence = 0.0

    # ========================================================
    # CLAMP
    # ========================================================

    def _clamp(
        self,
        value: float,
        low: float = 0.0,
        high: float = 100.0,
    ) -> float:

        return max(
            low,
            min(
                high,
                float(value),
            ),
        )

    # ========================================================
    # DIRECTION SCORE
    # ========================================================

    def directional_component(
        self,
        bullish_score: float,
        bearish_score: float,
    ) -> float:

        bullish_score = max(
            0.0,
            float(bullish_score),
        )

        bearish_score = max(
            0.0,
            float(bearish_score),
        )

        total = (
            bullish_score
            + bearish_score
        )

        if total <= 0:

            return 0.0

        separation = abs(
            bullish_score
            - bearish_score
        )

        return self._clamp(
            separation
            / total
            * 100.0
        )

    # ========================================================
    # TREND STRENGTH
    # ========================================================

    def trend_component(
        self,
        adx: Any,
        trend_strength: str,
    ) -> float:

        strength = str(
            trend_strength
            or "WEAK"
        ).upper()

        adx_value = None

        try:

            if adx is not None:
                adx_value = float(
                    adx
                )

        except Exception:

            adx_value = None

        if adx_value is not None:

            if adx_value >= 35:

                return 100.0

            if adx_value >= 30:

                return 90.0

            if adx_value >= 25:

                return 80.0

            if adx_value >= 20:

                return 60.0

            if adx_value >= 15:

                return 40.0

            return 20.0

        mapping = {

            "STRONG": 85.0,

            "MODERATE": 60.0,

            "WEAK": 25.0,

        }

        return mapping.get(
            strength,
            25.0,
        )

    # ========================================================
    # REGIME QUALITY
    # ========================================================

    def regime_component(
        self,
        regime: str,
        volatility_regime: str,
    ) -> float:

        regime = str(
            regime
            or "TRANSITION"
        ).upper()

        volatility = str(
            volatility_regime
            or "NORMAL_VOLATILITY"
        ).upper()

        regime_scores = {

            "TRENDING_BULL": 90.0,

            "TRENDING_BEAR": 90.0,

            "RANGE": 55.0,

            "TRANSITION": 35.0,

            "HIGH_VOLATILITY": 35.0,

            "LOW_VOLATILITY": 50.0,

        }

        score = regime_scores.get(
            regime,
            35.0,
        )

        # High volatility is not automatically bad,
        # but it reduces confidence for simple directional
        # signals.

        if volatility == "HIGH_VOLATILITY":

            score -= 15.0

        elif volatility == "LOW_VOLATILITY":

            score -= 5.0

        return self._clamp(
            score
        )

    # ========================================================
    # PATTERN AGREEMENT
    # ========================================================

    def pattern_component(
        self,
        patterns: Dict[str, Any],
        action: str,
    ) -> float:

        action = str(
            action
            or "WAIT"
        ).upper()

        items = patterns.get(
            "chart_patterns",
            [],
        )

        if not items:

            return 40.0

        bullish = 0
        bearish = 0

        for item in items[-10:]:

            direction = str(
                item.get(
                    "direction",
                    "NEUTRAL",
                )
            ).upper()

            strength = int(
                item.get(
                    "strength",
                    1,
                )
            )

            weight = (
                2.0
                if strength <= 1
                else 4.0
            )

            if direction == "BULLISH":

                bullish += weight

            elif direction == "BEARISH":

                bearish += weight

        total = (
            bullish
            + bearish
        )

        if total <= 0:

            return 50.0

        if action == "BUY":

            agreement = (
                bullish
                / total
                * 100.0
            )

        elif action == "SELL":

            agreement = (
                bearish
                / total
                * 100.0
            )

        else:

            agreement = 50.0

        return self._clamp(
            agreement
        )

    # ========================================================
    # VOLATILITY SUITABILITY
    # ========================================================

    def volatility_component(
        self,
        volatility_regime: str,
        action: str,
    ) -> float:

        volatility = str(
            volatility_regime
            or "NORMAL_VOLATILITY"
        ).upper()

        action = str(
            action
            or "WAIT"
        ).upper()

        if action == "WAIT":

            return 100.0

        if volatility == "NORMAL_VOLATILITY":

            return 80.0

        if volatility == "HIGH_VOLATILITY":

            return 35.0

        if volatility == "LOW_VOLATILITY":

            return 55.0

        return 50.0

    # ========================================================
    # FINAL CONFIDENCE
    # ========================================================

    def calculate(
        self,
        bullish_score: float,
        bearish_score: float,
        action: str,
        regime: Dict[str, Any],
        technical: Dict[str, Any],
        patterns: Dict[str, Any],
    ) -> Dict[str, Any]:

        action = str(
            action
            or "WAIT"
        ).upper()

        directional = (
            self.directional_component(
                bullish_score,
                bearish_score,
            )
        )

        trend = (
            self.trend_component(
                technical.get("adx"),
                technical.get(
                    "trend_strength",
                    regime.get(
                        "trend_strength",
                        "WEAK",
                    ),
                ),
            )
        )

        regime_quality = (
            self.regime_component(
                regime.get(
                    "regime",
                    "TRANSITION",
                ),
                regime.get(
                    "volatility_regime",
                    "NORMAL_VOLATILITY",
                ),
            )
        )

        pattern_agreement = (
            self.pattern_component(
                patterns,
                action,
            )
        )

        volatility_suitability = (
            self.volatility_component(
                regime.get(
                    "volatility_regime",
                    "NORMAL_VOLATILITY",
                ),
                action,
            )
        )

        # ----------------------------------------------------
        # Weighted model
        #
        # Direction is important, but deliberately not enough.
        # ----------------------------------------------------

        raw_confidence = (

            directional * 0.30

            +

            trend * 0.20

            +

            regime_quality * 0.20

            +

            pattern_agreement * 0.15

            +

            volatility_suitability * 0.15

        )

        confidence = round(
            self._clamp(
                raw_confidence
            ),
            1,
        )

        return {

            "confidence":
                confidence,

            "directional_component":
                round(
                    directional,
                    1,
                ),

            "trend_component":
                round(
                    trend,
                    1,
                ),

            "regime_component":
                round(
                    regime_quality,
                    1,
                ),

            "pattern_component":
                round(
                    pattern_agreement,
                    1,
                ),

            "volatility_component":
                round(
                    volatility_suitability,
                    1,
                ),

        }


# ============================================================
# GLOBAL
# ============================================================

confidence_engine = ConfidenceEngine()


# ============================================================
# SIMPLE FUNCTION
# ============================================================

def calculate_confidence(
    bullish_score,
    bearish_score,
    action,
    regime,
    technical,
    patterns,
):

    return confidence_engine.calculate(
        bullish_score=bullish_score,
        bearish_score=bearish_score,
        action=action,
        regime=regime,
        technical=technical,
        patterns=patterns,
    )


# ============================================================
# TEST
# ============================================================

if __name__ == "__main__":

    technical = {

        "adx":
            11.89,

        "trend_strength":
            "WEAK",

    }

    patterns = {

        "chart_patterns": [

            {
                "pattern":
                    "HAMMER",

                "direction":
                    "BULLISH",

                "strength":
                    1,
            },

            {
                "pattern":
                    "SHOOTING_STAR",

                "direction":
                    "BEARISH",

                "strength":
                    1,
            },

        ],

    }

    regime = {

        "regime":
            "HIGH_VOLATILITY",

        "volatility_regime":
            "HIGH_VOLATILITY",

        "bias":
            "BULLISH",

        "trend_strength":
            "WEAK",

    }

    result = calculate_confidence(

        bullish_score=30,

        bearish_score=0,

        action="WAIT",

        regime=regime,

        technical=technical,

        patterns=patterns,

    )

    print(
        "=" * 60
    )

    print(
        "JARVIS CONFIDENCE ENGINE V2"
    )

    print(
        "=" * 60
    )

    for key, value in result.items():

        print(
            f"{key}: {value}"
        )

    print()

    print(
        "Confidence Engine loaded successfully."
    )