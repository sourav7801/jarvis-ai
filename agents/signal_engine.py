# ============================================================
# JARVIS SIGNAL ENGINE
# V1
# ============================================================

from __future__ import annotations

from typing import Dict, Any


class SignalEngine:

    """
    Combines:

        Technical indicators
        Market structure
        Candlestick patterns
        Breakouts
        Support/resistance

    into a unified signal.

    Possible decisions:

        BUY
        SELL
        WAIT

    This engine NEVER executes an order.
    The Risk Engine must approve any candidate trade.
    """

    def __init__(
        self,
        minimum_signal_score: int = 60,
        minimum_confidence: int = 60,
    ):

        self.minimum_signal_score = (
            minimum_signal_score
        )

        self.minimum_confidence = (
            minimum_confidence
        )

    # ========================================================
    # SCORE TECHNICAL ANALYSIS
    # ========================================================

    def _technical_score(
        self,
        technical: Dict[str, Any],
    ):

        bullish = 0
        bearish = 0

        evidence = []

        trend = technical.get(
            "trend",
            "NEUTRAL",
        )

        momentum = technical.get(
            "momentum",
            "NEUTRAL",
        )

        trend_score = technical.get(
            "trend_score",
            0,
        )

        momentum_score = technical.get(
            "momentum_score",
            0,
        )

        rsi = technical.get(
            "rsi"
        )

        macd = technical.get(
            "macd"
        )

        # ----------------------------------------------------
        # Trend
        # ----------------------------------------------------

        if trend == "BULLISH":

            bullish += 20

            evidence.append(
                "Trend structure is bullish."
            )

        elif trend == "BEARISH":

            bearish += 20

            evidence.append(
                "Trend structure is bearish."
            )

        # ----------------------------------------------------
        # Momentum
        # ----------------------------------------------------

        if momentum == "STRONG":

            if trend == "BULLISH":

                bullish += 15

                evidence.append(
                    "Momentum confirms the bullish trend."
                )

            elif trend == "BEARISH":

                bearish += 15

                evidence.append(
                    "Momentum confirms the bearish trend."
                )

        elif momentum == "WEAK":

            evidence.append(
                "Momentum is weak."
            )

        # ----------------------------------------------------
        # Trend score
        # ----------------------------------------------------

        if trend_score >= 2:

            bullish += 10

        elif trend_score <= 0:

            bearish += 10

        # ----------------------------------------------------
        # RSI
        # ----------------------------------------------------

        if rsi is not None:

            if 50 < rsi < 70:

                bullish += 8

                evidence.append(
                    f"RSI supports bullish momentum ({rsi:.1f})."
                )

            elif 30 < rsi < 50:

                bearish += 8

                evidence.append(
                    f"RSI supports bearish momentum ({rsi:.1f})."
                )

            elif rsi >= 70:

                evidence.append(
                    f"RSI is overbought ({rsi:.1f})."
                )

            elif rsi <= 30:

                evidence.append(
                    f"RSI is oversold ({rsi:.1f})."
                )

        # ----------------------------------------------------
        # MACD
        # ----------------------------------------------------

        if macd is not None:

            signal_line = technical.get(
                "macd_signal"
            )

            if signal_line is not None:

                if macd > signal_line:

                    bullish += 7

                    evidence.append(
                        "MACD is bullish."
                    )

                elif macd < signal_line:

                    bearish += 7

                    evidence.append(
                        "MACD is bearish."
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
    # SCORE MARKET STRUCTURE
    # ========================================================

    def _structure_score(
        self,
        structure: Dict[str, Any],
    ):

        bullish = 0
        bearish = 0

        evidence = []

        bias = structure.get(
            "bias",
            "NEUTRAL",
        )

        higher_highs = len(
            structure.get(
                "higher_highs",
                [],
            )
        )

        higher_lows = len(
            structure.get(
                "higher_lows",
                [],
            )
        )

        lower_highs = len(
            structure.get(
                "lower_highs",
                [],
            )
        )

        lower_lows = len(
            structure.get(
                "lower_lows",
                [],
            )
        )

        if bias == "BULLISH":

            bullish += 20

            evidence.append(
                "Market structure is bullish."
            )

        elif bias == "BEARISH":

            bearish += 20

            evidence.append(
                "Market structure is bearish."
            )

        if higher_highs and higher_lows:

            bullish += 5

            evidence.append(
                "Higher highs and higher lows detected."
            )

        if lower_highs and lower_lows:

            bearish += 5

            evidence.append(
                "Lower highs and lower lows detected."
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
    # SCORE BREAKOUT
    # ========================================================

    def _breakout_score(
        self,
        breakout: Dict[str, Any],
    ):

        bullish = 0
        bearish = 0

        evidence = []

        signal = breakout.get(
            "signal",
            "NONE",
        )

        if signal == "BULLISH_BREAKOUT":

            bullish += 25

            evidence.append(
                "Bullish breakout detected."
            )

        elif signal == "BEARISH_BREAKDOWN":

            bearish += 25

            evidence.append(
                "Bearish breakdown detected."
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
    # SCORE CANDLESTICK PATTERNS
    # ========================================================

    def _pattern_score(
        self,
        patterns,
    ):

        bullish = 0
        bearish = 0

        evidence = []

        for pattern in patterns[-10:]:

            direction = pattern.get(
                "direction",
                "NEUTRAL",
            )

            strength = int(
                pattern.get(
                    "strength",
                    1,
                )
            )

            name = pattern.get(
                "pattern",
                "UNKNOWN",
            )

            weight = (
                4
                if strength >= 2
                else 2
            )

            if direction == "BULLISH":

                bullish += weight

                evidence.append(
                    f"Bullish pattern: {name}."
                )

            elif direction == "BEARISH":

                bearish += weight

                evidence.append(
                    f"Bearish pattern: {name}."
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
    # DETERMINE BIAS
    # ========================================================

    def _determine_action(
        self,
        bullish_score: int,
        bearish_score: int,
    ):

        difference = (
            bullish_score
            - bearish_score
        )

        total = max(
            bullish_score
            + bearish_score,
            1,
        )

        confidence = int(
            round(
                abs(difference)
                / total
                * 100
            )
        )

        if (
            bullish_score
            >= self.minimum_signal_score
            and
            bullish_score
            > bearish_score
            and
            confidence
            >= self.minimum_confidence
        ):

            action = "BUY"

        elif (
            bearish_score
            >= self.minimum_signal_score
            and
            bearish_score
            > bullish_score
            and
            confidence
            >= self.minimum_confidence
        ):

            action = "SELL"

        else:

            action = "WAIT"

        return action, confidence

    # ========================================================
    # CREATE SIGNAL
    # ========================================================

    def generate_signal(
        self,
        technical: Dict[str, Any],
        patterns: Dict[str, Any],
    ):

        if not technical.get(
            "success",
            False,
        ):

            return {

                "success":
                    False,

                "message":
                    "Technical analysis is unavailable.",

            }

        if not patterns.get(
            "success",
            False,
        ):

            return {

                "success":
                    False,

                "message":
                    "Pattern analysis is unavailable.",

            }

        technical_result = (
            self._technical_score(
                technical
            )
        )

        structure_result = (
            self._structure_score(
                patterns.get(
                    "market_structure",
                    {},
                )
            )
        )

        breakout_result = (
            self._breakout_score(
                patterns.get(
                    "breakout",
                    {},
                )
            )
        )

        pattern_result = (
            self._pattern_score(
                patterns.get(
                    "chart_patterns",
                    [],
                )
            )
        )

        bullish_score = (
            technical_result["bullish"]
            +
            structure_result["bullish"]
            +
            breakout_result["bullish"]
            +
            pattern_result["bullish"]
        )

        bearish_score = (
            technical_result["bearish"]
            +
            structure_result["bearish"]
            +
            breakout_result["bearish"]
            +
            pattern_result["bearish"]
        )

        action, confidence = (
            self._determine_action(
                bullish_score,
                bearish_score,
            )
        )

        evidence = (
            technical_result["evidence"]
            +
            structure_result["evidence"]
            +
            breakout_result["evidence"]
            +
            pattern_result["evidence"]
        )

        price = patterns.get(
            "latest_price"
        )

        atr = technical.get(
            "atr"
        )

        entry = price

        stop = None
        target = None
        risk_reward = None

        # ----------------------------------------------------
        # Candidate trade levels.
        #
        # These are NOT orders.
        # Risk Engine must approve them later.
        # ----------------------------------------------------

        if (
            action == "BUY"
            and
            price is not None
            and
            atr is not None
            and
            atr > 0
        ):

            stop = price - (
                atr * 1.5
            )

            target = price + (
                atr * 3.0
            )

        elif (
            action == "SELL"
            and
            price is not None
            and
            atr is not None
            and
            atr > 0
        ):

            stop = price + (
                atr * 1.5
            )

            target = price - (
                atr * 3.0
            )

        if (
            stop is not None
            and
            target is not None
            and
            entry is not None
        ):

            risk = abs(
                entry - stop
            )

            reward = abs(
                target - entry
            )

            if risk > 0:

                risk_reward = (
                    reward / risk
                )

        return {

            "success":
                True,

            "action":
                action,

            "confidence":
                confidence,

            "bullish_score":
                bullish_score,

            "bearish_score":
                bearish_score,

            "price":
                price,

            "entry":
                entry,

            "stop_loss":
                stop,

            "target":
                target,

            "risk_reward":
                risk_reward,

            "evidence":
                evidence,

            "technical":
                technical_result,

            "structure":
                structure_result,

            "breakout":
                breakout_result,

            "patterns":
                pattern_result,

        }


# ============================================================
# GLOBAL ENGINE
# ============================================================

signal_engine = SignalEngine()


# ============================================================
# SIMPLE FUNCTION
# ============================================================

def generate_signal(
    technical,
    patterns,
):

    return signal_engine.generate_signal(
        technical,
        patterns,
    )


# ============================================================
# TEST
# ============================================================

if __name__ == "__main__":

    print(
        "=" * 60
    )

    print(
        "JARVIS SIGNAL ENGINE"
    )

    print(
        "=" * 60
    )

    print()

    technical = {

        "success":
            True,

        "trend":
            "BULLISH",

        "momentum":
            "STRONG",

        "trend_score":
            3,

        "momentum_score":
            2,

        "rsi":
            61.5,

        "macd":
            3.0,

        "macd_signal":
            2.0,

        "atr":
            5.0,

    }

    patterns = {

        "success":
            True,

        "latest_price":
            100.0,

        "market_structure": {

            "bias":
                "BULLISH",

            "higher_highs":
                [10, 20],

            "higher_lows":
                [15, 25],

            "lower_highs":
                [],

            "lower_lows":
                [],

        },

        "breakout": {

            "signal":
                "BULLISH_BREAKOUT",

        },

        "chart_patterns": [

            {
                "pattern":
                    "BULLISH_ENGULFING",

                "direction":
                    "BULLISH",

                "strength":
                    2,
            }

        ],

    }

    result = generate_signal(
        technical,
        patterns,
    )

    print(
        "Success:",
        result.get(
            "success"
        ),
    )

    print(
        "Action:",
        result.get(
            "action"
        ),
    )

    print(
        "Confidence:",
        result.get(
            "confidence"
        ),
    )

    print(
        "Bullish Score:",
        result.get(
            "bullish_score"
        ),
    )

    print(
        "Bearish Score:",
        result.get(
            "bearish_score"
        ),
    )

    print(
        "Entry:",
        result.get(
            "entry"
        ),
    )

    print(
        "Stop:",
        result.get(
            "stop_loss"
        ),
    )

    print(
        "Target:",
        result.get(
            "target"
        ),
    )

    print(
        "Risk/Reward:",
        result.get(
            "risk_reward"
        ),
    )

    print()

    print(
        "Evidence:"
    )

    for item in result.get(
        "evidence",
        [],
    ):

        print(
            f"  - {item}"
        )