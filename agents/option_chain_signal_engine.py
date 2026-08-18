# ============================================================
# JARVIS OPTION CHAIN SIGNAL ENGINE
# V1
# ============================================================

from __future__ import annotations

from typing import Any, Dict, List


class OptionChainSignalEngine:

    """
    Interprets option-chain information.

    Inputs:
        spot
        ATM strike
        max pain
        PCR
        call/put OI
        OI changes
        IV
        IV skew
        support/resistance

    Outputs:
        BULLISH
        BEARISH
        RANGE
        UNCERTAIN

    This engine does NOT place orders.
    """

    def __init__(
        self,
        bullish_threshold: int = 60,
        bearish_threshold: int = 60,
    ):

        self.bullish_threshold = bullish_threshold
        self.bearish_threshold = bearish_threshold

    # ========================================================
    # SCORE
    # ========================================================

    def analyze(
        self,
        chain_result: Dict[str, Any],
    ) -> Dict[str, Any]:

        if not chain_result.get(
            "success",
            False,
        ):

            return {

                "success":
                    False,

                "message":
                    chain_result.get(
                        "message",
                        "Option-chain analysis unavailable.",
                    ),

            }

        bullish = 0
        bearish = 0

        evidence: List[str] = []

        spot = chain_result.get(
            "spot"
        )

        atm = chain_result.get(
            "atm"
        )

        levels = chain_result.get(
            "levels",
            {},
        )

        oi_change = chain_result.get(
            "oi_change",
            {},
        )

        volatility = chain_result.get(
            "volatility",
            {},
        )

        pcr = chain_result.get(
            "put_call_ratio"
        )

        max_pain = chain_result.get(
            "max_pain"
        )

        # ====================================================
        # PCR
        # ====================================================

        if pcr is not None:

            try:

                pcr = float(
                    pcr
                )

                if pcr >= 1.20:

                    bullish += 20

                    evidence.append(
                        f"PCR is bullish at {pcr:.2f}."
                    )

                elif pcr >= 1.00:

                    bullish += 10

                    evidence.append(
                        f"PCR is mildly bullish at {pcr:.2f}."
                    )

                elif pcr <= 0.80:

                    bearish += 20

                    evidence.append(
                        f"PCR is bearish at {pcr:.2f}."
                    )

                elif pcr < 1.00:

                    bearish += 10

                    evidence.append(
                        f"PCR is mildly bearish at {pcr:.2f}."
                    )

            except Exception:
                pass

        # ====================================================
        # SUPPORT / RESISTANCE
        # ====================================================

        support = levels.get(
            "put_oi_support"
        )

        resistance = levels.get(
            "call_oi_resistance"
        )

        if (
            spot is not None
            and
            support is not None
            and
            resistance is not None
        ):

            try:

                spot = float(
                    spot
                )

                support = float(
                    support
                )

                resistance = float(
                    resistance
                )

                if spot > resistance:

                    bullish += 20

                    evidence.append(
                        "Spot is above the main call-OI level."
                    )

                elif spot < support:

                    bearish += 20

                    evidence.append(
                        "Spot is below the main put-OI level."
                    )

                else:

                    # Inside the OI range.
                    bullish += 5
                    bearish += 5

                    evidence.append(
                        "Spot is trading inside the main OI range."
                    )

            except Exception:
                pass

        # ====================================================
        # MAX PAIN
        # ====================================================

        if (
            spot is not None
            and
            max_pain is not None
        ):

            try:

                distance = (
                    float(spot)
                    - float(max_pain)
                )

                # Max pain is only a weak contextual signal.
                # Never use it alone to generate an order.

                if distance > 0:

                    bullish += 5

                    evidence.append(
                        "Spot is above max-pain level."
                    )

                elif distance < 0:

                    bearish += 5

                    evidence.append(
                        "Spot is below max-pain level."
                    )

            except Exception:
                pass

        # ====================================================
        # OI CHANGE
        # ====================================================

        call_change = (
            oi_change.get(
                "largest_call_oi_change"
            )
        )

        put_change = (
            oi_change.get(
                "largest_put_oi_change"
            )
        )

        if call_change:

            try:

                change = float(
                    call_change.get(
                        "change",
                        0,
                    )
                )

                if change > 0:

                    bearish += 10

                    evidence.append(
                        "Fresh call-side OI increase detected."
                    )

                elif change < 0:

                    bullish += 5

                    evidence.append(
                        "Call-side OI reduction detected."
                    )

            except Exception:
                pass

        if put_change:

            try:

                change = float(
                    put_change.get(
                        "change",
                        0,
                    )
                )

                if change > 0:

                    bullish += 10

                    evidence.append(
                        "Fresh put-side OI increase detected."
                    )

                elif change < 0:

                    bearish += 5

                    evidence.append(
                        "Put-side OI reduction detected."
                    )

            except Exception:
                pass

        # ====================================================
        # IV
        # ====================================================

        atm_iv = volatility.get(
            "atm_iv"
        )

        iv_skew = volatility.get(
            "iv_skew"
        )

        if atm_iv is not None:

            try:

                atm_iv = float(
                    atm_iv
                )

                if atm_iv > 30:

                    evidence.append(
                        f"ATM IV is elevated at {atm_iv:.2f}."
                    )

                elif atm_iv < 15:

                    evidence.append(
                        f"ATM IV is relatively low at {atm_iv:.2f}."
                    )

                else:

                    evidence.append(
                        f"ATM IV is moderate at {atm_iv:.2f}."
                    )

            except Exception:
                pass

        if iv_skew is not None:

            try:

                iv_skew = float(
                    iv_skew
                )

                if iv_skew > 2:

                    bullish += 5

                    evidence.append(
                        "Put IV is materially above call IV."
                    )

                elif iv_skew < -2:

                    bearish += 5

                    evidence.append(
                        "Call IV is materially above put IV."
                    )

            except Exception:
                pass

        # ====================================================
        # FINAL CLASSIFICATION
        # ====================================================

        total = (
            bullish
            + bearish
        )

        if total <= 0:

            bias = "UNCERTAIN"

            confidence = 0

        else:

            difference = (
                bullish
                - bearish
            )

            if (
                bullish >= self.bullish_threshold
                and
                bullish > bearish
            ):

                bias = "BULLISH"

            elif (
                bearish >= self.bearish_threshold
                and
                bearish > bullish
            ):

                bias = "BEARISH"

            elif (
                abs(
                    difference
                ) <= 15
            ):

                bias = "RANGE"

            else:

                bias = "UNCERTAIN"

            confidence = round(
                (
                    abs(
                        difference
                    )
                    / max(
                        total,
                        1,
                    )
                )
                * 100
            )

        # ====================================================
        # MARKET STATE
        # ====================================================

        market_state = "NEUTRAL"

        if (
            bias == "BULLISH"
            and
            atm is not None
            and
            spot is not None
            and
            max_pain is not None
        ):

            market_state = (
                "BULLISH_BIASED"
            )

        elif (
            bias == "BEARISH"
        ):

            market_state = (
                "BEARISH_BIASED"
            )

        elif bias == "RANGE":

            market_state = (
                "RANGE_BOUND"
            )

        return {

            "success":
                True,

            "bias":
                bias,

            "market_state":
                market_state,

            "confidence":
                confidence,

            "bullish_score":
                bullish,

            "bearish_score":
                bearish,

            "spot":
                spot,

            "atm":
                atm,

            "support":
                support,

            "resistance":
                resistance,

            "max_pain":
                max_pain,

            "pcr":
                pcr,

            "atm_iv":
                atm_iv,

            "iv_skew":
                iv_skew,

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
                "OPTION CHAIN SIGNAL FAILED\n"
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
            "JARVIS OPTION CHAIN SIGNAL"
        )

        lines.append(
            "--------------------------------------------------"
        )

        lines.append(
            f"Bias: "
            f"{result.get('bias', 'UNCERTAIN')}"
        )

        lines.append(
            f"Market State: "
            f"{result.get('market_state', 'NEUTRAL')}"
        )

        lines.append(
            f"Confidence: "
            f"{result.get('confidence', 0)}%"
        )

        lines.append("")

        lines.append(
            "KEY LEVELS"
        )

        lines.append(
            f"Spot: "
            f"{result.get('spot', 'N/A')}"
        )

        lines.append(
            f"ATM: "
            f"{result.get('atm', 'N/A')}"
        )

        lines.append(
            f"Put Support: "
            f"{result.get('support', 'N/A')}"
        )

        lines.append(
            f"Call Resistance: "
            f"{result.get('resistance', 'N/A')}"
        )

        lines.append(
            f"Max Pain: "
            f"{result.get('max_pain', 'N/A')}"
        )

        lines.append(
            f"PCR: "
            f"{result.get('pcr', 'N/A')}"
        )

        lines.append(
            f"ATM IV: "
            f"{result.get('atm_iv', 'N/A')}"
        )

        lines.append(
            f"IV Skew: "
            f"{result.get('iv_skew', 'N/A')}"
        )

        lines.append("")

        lines.append(
            "EVIDENCE"
        )

        for evidence in result.get(
            "evidence",
            [],
        ):

            lines.append(
                f"- {evidence}"
            )

        lines.append("")

        lines.append(
            "IMPORTANT: "
            "This is an analytical market-state signal. "
            "It does not place an order."
        )

        return "\n".join(
            lines
        )


# ============================================================
# GLOBAL ENGINE
# ============================================================

option_chain_signal_engine = (
    OptionChainSignalEngine()
)


# ============================================================
# COMPATIBILITY FUNCTION
# ============================================================

def analyze_chain_signal(
    chain_result:
    Dict[str, Any],
):

    return (
        option_chain_signal_engine.analyze(
            chain_result
        )
    )


# ============================================================
# TEST
# ============================================================

if __name__ == "__main__":

    print(
        "=" * 60
    )

    print(
        "JARVIS OPTION CHAIN SIGNAL ENGINE"
    )

    print(
        "=" * 60
    )

    print()

    example = {

        "success":
            True,

        "spot":
            24366.0,

        "atm":
            24400.0,

        "levels": {

            "put_oi_support":
                24200.0,

            "call_oi_resistance":
                24700.0,

        },

        "oi_change": {

            "largest_call_oi_change": {

                "strike":
                    24700.0,

                "change":
                    15000,

            },

            "largest_put_oi_change": {

                "strike":
                    24200.0,

                "change":
                    25000,

            },

        },

        "max_pain":
            24300.0,

        "put_call_ratio":
            1.15,

        "volatility": {

            "atm_iv":
                18.5,

            "iv_skew":
                1.5,

        },

    }

    result = (
        analyze_chain_signal(
            example
        )
    )

    print(
        option_chain_signal_engine.format_signal(
            result
        )
    )