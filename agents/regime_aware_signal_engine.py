# ============================================================
# JARVIS REGIME-AWARE SIGNAL ENGINE
# V2
# ============================================================

from __future__ import annotations

from typing import Any, Dict, List

from agents.confidence_engine import (
    confidence_engine,
)


class RegimeAwareSignalEngine:

    def __init__(
        self,
        minimum_direction_score: int = 45,
        minimum_confidence: float = 60.0,
    ):

        self.minimum_direction_score = (
            minimum_direction_score
        )

        self.minimum_confidence = (
            minimum_confidence
        )

    # ========================================================
    # EVIDENCE
    # ========================================================

    def _add_evidence(
        self,
        container: List[str],
        text: str,
    ):

        if text not in container:

            container.append(
                text
            )

    # ========================================================
    # TECHNICAL SCORE
    # ========================================================

    def technical_score(
        self,
        technical: Dict[str, Any],
    ) -> Dict[str, Any]:

        bullish = 0
        bearish = 0

        evidence: List[str] = []

        trend = str(
            technical.get(
                "trend",
                "NEUTRAL",
            )
        ).upper()

        momentum = str(
            technical.get(
                "momentum",
                "NEUTRAL",
            )
        ).upper()

        rsi = technical.get(
            "rsi"
        )

        macd = technical.get(
            "macd"
        )

        macd_signal = technical.get(
            "macd_signal"
        )

        adx = technical.get(
            "adx"
        )

        if trend == "BULLISH":

            bullish += 20

            self._add_evidence(
                evidence,
                "Technical trend is bullish.",
            )

        elif trend == "BEARISH":

            bearish += 20

            self._add_evidence(
                evidence,
                "Technical trend is bearish.",
            )

        if momentum == "STRONG":

            if trend == "BULLISH":

                bullish += 15

                self._add_evidence(
                    evidence,
                    "Strong bullish momentum supports the trend.",
                )

            elif trend == "BEARISH":

                bearish += 15

                self._add_evidence(
                    evidence,
                    "Strong bearish momentum supports the trend.",
                )

        if rsi is not None:

            try:

                rsi = float(
                    rsi
                )

                if 52 <= rsi < 68:

                    bullish += 7

                    self._add_evidence(
                        evidence,
                        f"RSI supports bullish momentum ({rsi:.2f}).",
                    )

                elif 32 < rsi <= 48:

                    bearish += 7

                    self._add_evidence(
                        evidence,
                        f"RSI supports bearish momentum ({rsi:.2f}).",
                    )

                elif rsi >= 70:

                    self._add_evidence(
                        evidence,
                        f"RSI is overbought ({rsi:.2f}).",
                    )

                elif rsi <= 30:

                    self._add_evidence(
                        evidence,
                        f"RSI is oversold ({rsi:.2f}).",
                    )

            except Exception:
                pass

        if (
            macd is not None
            and
            macd_signal is not None
        ):

            try:

                if float(macd) > float(macd_signal):

                    bullish += 7

                    self._add_evidence(
                        evidence,
                        "MACD is bullish.",
                    )

                elif float(macd) < float(macd_signal):

                    bearish += 7

                    self._add_evidence(
                        evidence,
                        "MACD is bearish.",
                    )

            except Exception:
                pass

        if adx is not None:

            try:

                adx = float(
                    adx
                )

                if adx >= 25:

                    self._add_evidence(
                        evidence,
                        f"ADX indicates meaningful trend strength ({adx:.2f}).",
                    )

                elif adx < 18:

                    self._add_evidence(
                        evidence,
                        f"ADX is weak ({adx:.2f}); trend-following evidence is weak.",
                    )

            except Exception:
                pass

        return {

            "bullish":
                bullish,

            "bearish":
                bearish,

            "evidence":
                evidence,

        }

    # ========================================================
    # PATTERNS
    # ========================================================

    def pattern_score(
        self,
        patterns: Dict[str, Any],
    ) -> Dict[str, Any]:

        bullish = 0
        bearish = 0

        evidence: List[str] = []

        for item in patterns.get(
            "chart_patterns",
            [],
        )[-10:]:

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

            name = str(
                item.get(
                    "pattern",
                    "UNKNOWN",
                )
            )

            weight = (
                5
                if strength >= 2
                else
                2
            )

            if direction == "BULLISH":

                bullish += weight

                self._add_evidence(
                    evidence,
                    f"Bullish pattern: {name}.",
                )

            elif direction == "BEARISH":

                bearish += weight

                self._add_evidence(
                    evidence,
                    f"Bearish pattern: {name}.",
                )

        return {

            "bullish":
                bullish,

            "bearish":
                bearish,

            "evidence":
                evidence,

        }

    # ========================================================
    # BREAKOUT
    # ========================================================

    def breakout_score(
        self,
        patterns: Dict[str, Any],
    ) -> Dict[str, Any]:

        bullish = 0
        bearish = 0

        evidence: List[str] = []

        breakout = patterns.get(
            "breakout",
            {},
        )

        signal = str(
            breakout.get(
                "signal",
                "NONE",
            )
        ).upper()

        if signal == "BULLISH_BREAKOUT":

            bullish += 20

            self._add_evidence(
                evidence,
                "Bullish breakout detected.",
            )

        elif signal == "BEARISH_BREAKDOWN":

            bearish += 20

            self._add_evidence(
                evidence,
                "Bearish breakdown detected.",
            )

        return {

            "bullish":
                bullish,

            "bearish":
                bearish,

            "evidence":
                evidence,

        }

    # ========================================================
    # REGIME
    # ========================================================

    def regime_adjustment(
        self,
        regime: Dict[str, Any],
        bullish: int,
        bearish: int,
    ) -> Dict[str, Any]:

        regime_name = str(
            regime.get(
                "regime",
                "TRANSITION",
            )
        ).upper()

        volatility = str(
            regime.get(
                "volatility_regime",
                "NORMAL_VOLATILITY",
            )
        ).upper()

        bias = str(
            regime.get(
                "bias",
                "NEUTRAL",
            )
        ).upper()

        adjusted_bullish = bullish
        adjusted_bearish = bearish

        evidence: List[str] = []

        if regime_name == "TRENDING_BULL":

            adjusted_bullish += 20

            adjusted_bearish -= 10

            self._add_evidence(
                evidence,
                "Trending-bull regime favors long signals.",
            )

        elif regime_name == "TRENDING_BEAR":

            adjusted_bearish += 20

            adjusted_bullish -= 10

            self._add_evidence(
                evidence,
                "Trending-bear regime favors short signals.",
            )

        elif regime_name == "RANGE":

            adjusted_bullish -= 15

            adjusted_bearish -= 15

            self._add_evidence(
                evidence,
                "Range regime penalizes simple directional entries.",
            )

        elif regime_name == "TRANSITION":

            adjusted_bullish -= 12

            adjusted_bearish -= 12

            self._add_evidence(
                evidence,
                "Transition regime requires stronger confirmation.",
            )

        if volatility == "HIGH_VOLATILITY":

            adjusted_bullish -= 8

            adjusted_bearish -= 8

            self._add_evidence(
                evidence,
                "High volatility reduces directional confidence.",
            )

        elif volatility == "LOW_VOLATILITY":

            adjusted_bullish -= 3

            adjusted_bearish -= 3

            self._add_evidence(
                evidence,
                "Low volatility reduces breakout confidence.",
            )

        if bias == "BULLISH":

            adjusted_bullish += 5

        elif bias == "BEARISH":

            adjusted_bearish += 5

        return {

            "bullish":
                max(
                    0,
                    adjusted_bullish,
                ),

            "bearish":
                max(
                    0,
                    adjusted_bearish,
                ),

            "evidence":
                evidence,

        }

    # ========================================================
    # DECISION
    # ========================================================

    def decide(
        self,
        bullish_score: int,
        bearish_score: int,
        confidence: float,
        regime: Dict[str, Any],
    ) -> str:

        regime_name = str(
            regime.get(
                "regime",
                "TRANSITION",
            )
        ).upper()

        required = (
            self.minimum_confidence
        )

        if regime_name in {
            "HIGH_VOLATILITY",
            "TRANSITION",
            "RANGE",
        }:

            required += 10.0

        if (
            bullish_score
            >= self.minimum_direction_score
            and
            bullish_score > bearish_score
            and
            confidence >= required
        ):

            return "BUY"

        if (
            bearish_score
            >= self.minimum_direction_score
            and
            bearish_score > bullish_score
            and
            confidence >= required
        ):

            return "SELL"

        return "WAIT"

    # ========================================================
    # FULL SIGNAL
    # ========================================================

    def generate_signal(
        self,
        technical: Dict[str, Any],
        patterns: Dict[str, Any],
        regime: Dict[str, Any],
    ) -> Dict[str, Any]:

        if not technical.get(
            "success",
            False,
        ):

            return {

                "success":
                    False,

                "message":
                    "Technical analysis unavailable.",

            }

        if not patterns.get(
            "success",
            False,
        ):

            return {

                "success":
                    False,

                "message":
                    "Pattern analysis unavailable.",

            }

        if not regime.get(
            "success",
            False,
        ):

            return {

                "success":
                    False,

                "message":
                    "Market regime unavailable.",

            }

        technical_result = (
            self.technical_score(
                technical
            )
        )

        pattern_result = (
            self.pattern_score(
                patterns
            )
        )

        breakout_result = (
            self.breakout_score(
                patterns
            )
        )

        base_bullish = (
            technical_result["bullish"]
            +
            pattern_result["bullish"]
            +
            breakout_result["bullish"]
        )

        base_bearish = (
            technical_result["bearish"]
            +
            pattern_result["bearish"]
            +
            breakout_result["bearish"]
        )

        regime_result = (
            self.regime_adjustment(
                regime=regime,
                bullish=base_bullish,
                bearish=base_bearish,
            )
        )

        bullish_score = (
            regime_result["bullish"]
        )

        bearish_score = (
            regime_result["bearish"]
        )

        # First determine provisional direction.
        if (
            bullish_score
            > bearish_score
        ):

            provisional_action = "BUY"

        elif (
            bearish_score
            > bullish_score
        ):

            provisional_action = "SELL"

        else:

            provisional_action = "WAIT"

        confidence_result = (
            confidence_engine.calculate(

                bullish_score=bullish_score,

                bearish_score=bearish_score,

                action=provisional_action,

                regime=regime,

                technical=technical,

                patterns=patterns,

            )
        )

        confidence = (
            confidence_result[
                "confidence"
            ]
        )

        action = self.decide(

            bullish_score=bullish_score,

            bearish_score=bearish_score,

            confidence=confidence,

            regime=regime,

        )

        evidence = (
            technical_result["evidence"]
            +
            pattern_result["evidence"]
            +
            breakout_result["evidence"]
            +
            regime_result["evidence"]
        )

        if action == "WAIT":

            evidence.append(
                "Confidence is not high enough for the current regime."
            )

        price = patterns.get(
            "latest_price"
        )

        atr = technical.get(
            "atr"
        )

        entry = price
        stop_loss = None
        target = None
        risk_reward = None

        if (
            action == "BUY"
            and
            price is not None
            and
            atr is not None
            and
            float(atr) > 0
        ):

            entry = float(
                price
            )

            stop_loss = (
                entry
                -
                1.5 * float(atr)
            )

            target = (
                entry
                +
                3.0 * float(atr)
            )

        elif (
            action == "SELL"
            and
            price is not None
            and
            atr is not None
            and
            float(atr) > 0
        ):

            entry = float(
                price
            )

            stop_loss = (
                entry
                +
                1.5 * float(atr)
            )

            target = (
                entry
                -
                3.0 * float(atr)
            )

        if (
            stop_loss is not None
            and
            target is not None
            and
            entry is not None
        ):

            risk = abs(
                entry
                - stop_loss
            )

            reward = abs(
                target
                - entry
            )

            if risk > 0:

                risk_reward = (
                    reward
                    / risk
                )

        # ----------------------------------------------------
        # Risk allocation factor
        # ----------------------------------------------------

        risk_adjustment = 1.0

        if (
            str(
                regime.get(
                    "volatility_regime",
                    "",
                )
            ).upper()
            ==
            "HIGH_VOLATILITY"
        ):

            risk_adjustment = 0.50

            evidence.append(
                "Risk allocation should be reduced because volatility is high."
            )

        elif (
            str(
                regime.get(
                    "regime",
                    "",
                )
            ).upper()
            ==
            "TRANSITION"
        ):

            risk_adjustment = 0.50

        elif (
            str(
                regime.get(
                    "regime",
                    "",
                )
            ).upper()
            ==
            "RANGE"
        ):

            risk_adjustment = 0.75

        return {

            "success":
                True,

            "action":
                action,

            "confidence":
                confidence,

            "confidence_components":
                confidence_result,

            "bullish_score":
                bullish_score,

            "bearish_score":
                bearish_score,

            "base_bullish_score":
                base_bullish,

            "base_bearish_score":
                base_bearish,

            "required_confidence":
                (
                    self.minimum_confidence
                    +
                    (
                        10.0
                        if str(
                            regime.get(
                                "regime",
                                "",
                            )
                        ).upper()
                        in {
                            "HIGH_VOLATILITY",
                            "TRANSITION",
                            "RANGE",
                        }
                        else 0.0
                    )
                ),

            "risk_adjustment":
                risk_adjustment,

            "regime":
                regime.get(
                    "regime"
                ),

            "regime_bias":
                regime.get(
                    "bias"
                ),

            "volatility_regime":
                regime.get(
                    "volatility_regime"
                ),

            "entry":
                entry,

            "stop_loss":
                stop_loss,

            "target":
                target,

            "risk_reward":
                risk_reward,

            "evidence":
                evidence,

        }

    # ========================================================
    # FORMAT
    # ========================================================

    def format_signal(
        self,
        result: Dict[str, Any],
    ) -> str:

        if not result.get(
            "success",
            False,
        ):

            return (
                "REGIME-AWARE SIGNAL FAILED\n"
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
            "JARVIS REGIME-AWARE SIGNAL V2"
        )

        lines.append(
            "--------------------------------------------------"
        )

        lines.append(
            f"Decision: "
            f"{result.get('action')}"
        )

        lines.append(
            f"Confidence: "
            f"{result.get('confidence')}%"
        )

        lines.append(
            f"Required Confidence: "
            f"{result.get('required_confidence')}%"
        )

        lines.append(
            f"Regime: "
            f"{result.get('regime')}"
        )

        lines.append(
            f"Regime Bias: "
            f"{result.get('regime_bias')}"
        )

        lines.append(
            f"Volatility: "
            f"{result.get('volatility_regime')}"
        )

        lines.append(
            f"Risk Adjustment: "
            f"{result.get('risk_adjustment')}"
        )

        lines.append("")

        lines.append(
            "CONFIDENCE COMPONENTS"
        )

        components = result.get(
            "confidence_components",
            {},
        )

        for key, value in components.items():

            lines.append(
                f"{key}: {value}"
            )

        lines.append("")

        lines.append(
            "SCORES"
        )

        lines.append(
            f"Bullish: "
            f"{result.get('bullish_score')}"
        )

        lines.append(
            f"Bearish: "
            f"{result.get('bearish_score')}"
        )

        lines.append("")

        lines.append(
            "TRADE CANDIDATE"
        )

        lines.append(
            f"Entry: "
            f"{result.get('entry')}"
        )

        lines.append(
            f"Stop Loss: "
            f"{result.get('stop_loss')}"
        )

        lines.append(
            f"Target: "
            f"{result.get('target')}"
        )

        lines.append(
            f"Risk/Reward: "
            f"{result.get('risk_reward')}"
        )

        lines.append("")

        lines.append(
            "EVIDENCE"
        )

        for item in result.get(
            "evidence",
            [],
        )[:20]:

            lines.append(
                f"- {item}"
            )

        lines.append("")

        lines.append(
            "IMPORTANT: "
            "This is analytical only. "
            "No live order was placed."
        )

        return "\n".join(
            lines
        )


# ============================================================
# GLOBAL
# ============================================================

regime_aware_signal_engine = (
    RegimeAwareSignalEngine()
)


# ============================================================
# SIMPLE FUNCTION
# ============================================================

def generate_regime_aware_signal(
    technical,
    patterns,
    regime,
):

    return (
        regime_aware_signal_engine.generate_signal(
            technical=technical,
            patterns=patterns,
            regime=regime,
        )
    )


# ============================================================
# TEST
# ============================================================

if __name__ == "__main__":

    technical = {

        "success":
            True,

        "trend":
            "BULLISH",

        "momentum":
            "NEUTRAL",

        "rsi":
            52.21,

        "macd":
            1.0,

        "macd_signal":
            0.5,

        "adx":
            11.89,

        "atr":
            192.14,

        "trend_strength":
            "WEAK",

    }

    patterns = {

        "success":
            True,

        "latest_price":
            24_366.0,

        "breakout": {

            "signal":
                "NONE",

        },

        "chart_patterns": [

            {
                "pattern":
                    "SHOOTING_STAR",

                "direction":
                    "BEARISH",

                "strength":
                    1,

            },

            {
                "pattern":
                    "HAMMER",

                "direction":
                    "BULLISH",

                "strength":
                    1,

            },

        ],

    }

    regime = {

        "success":
            True,

        "regime":
            "HIGH_VOLATILITY",

        "bias":
            "BULLISH",

        "volatility_regime":
            "HIGH_VOLATILITY",

        "confidence":
            60,

        "trend_strength":
            "WEAK",

    }

    result = (
        generate_regime_aware_signal(
            technical,
            patterns,
            regime,
        )
    )

    print(
        "=" * 60
    )

    print(
        "JARVIS REGIME-AWARE SIGNAL ENGINE V2"
    )

    print(
        "=" * 60
    )

    print()

    print(
        regime_aware_signal_engine.format_signal(
            result
        )
    )

    print()

    print(
        "Regime-aware Signal Engine V2 loaded successfully."
    )