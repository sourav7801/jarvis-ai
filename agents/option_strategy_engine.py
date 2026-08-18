# ============================================================
# JARVIS OPTION STRATEGY ENGINE
# V1
# ============================================================

from __future__ import annotations

from typing import Any, Dict, List


class OptionStrategyEngine:

    """
    Ranks option strategies based on:

        market bias
        volatility
        IV
        PCR
        option-chain structure
        trend
        breakout state

    IMPORTANT:
        This engine generates candidate strategies.
        It does NOT place trades.
    """

    def __init__(self):

        self.strategies = [
            "LONG_CALL",
            "LONG_PUT",
            "BULL_CALL_SPREAD",
            "BEAR_PUT_SPREAD",
            "LONG_STRADDLE",
            "LONG_STRANGLE",
            "IRON_CONDOR",
        ]

    # ========================================================
    # HELPERS
    # ========================================================

    def _score_item(
        self,
        scores: Dict[str, int],
        strategy: str,
        points: int,
        reason: str,
        reasons: Dict[str, List[str]],
    ):

        scores[strategy] = (
            scores.get(strategy, 0)
            + points
        )

        reasons.setdefault(
            strategy,
            []
        ).append(
            reason
        )

    # ========================================================
    # RANK STRATEGIES
    # ========================================================

    def rank_strategies(
        self,
        market_bias: str,
        trend: str,
        momentum: str,
        volatility: Dict[str, Any],
        option_chain: Dict[str, Any],
        breakout: str = "NONE",
    ) -> Dict[str, Any]:

        scores = {
            strategy: 0
            for strategy
            in self.strategies
        }

        reasons = {
            strategy: []
            for strategy
            in self.strategies
        }

        market_bias = str(
            market_bias
            or "NEUTRAL"
        ).upper()

        trend = str(
            trend
            or "NEUTRAL"
        ).upper()

        momentum = str(
            momentum
            or "NEUTRAL"
        ).upper()

        breakout = str(
            breakout
            or "NONE"
        ).upper()

        atm_iv = volatility.get(
            "atm_iv"
        )

        iv_skew = volatility.get(
            "iv_skew"
        )

        pcr = option_chain.get(
            "put_call_ratio"
        )

        # ----------------------------------------------------
        # BULLISH MARKET
        # ----------------------------------------------------

        if market_bias == "BULLISH":

            self._score_item(
                scores,
                "LONG_CALL",
                25,
                "Underlying bias is bullish.",
                reasons,
            )

            self._score_item(
                scores,
                "BULL_CALL_SPREAD",
                30,
                "Bullish bias favors defined-risk bullish spreads.",
                reasons,
            )

            self._score_item(
                scores,
                "LONG_STRANGLE",
                5,
                "A strong directional move is still possible.",
                reasons,
            )

        # ----------------------------------------------------
        # BEARISH MARKET
        # ----------------------------------------------------

        elif market_bias == "BEARISH":

            self._score_item(
                scores,
                "LONG_PUT",
                25,
                "Underlying bias is bearish.",
                reasons,
            )

            self._score_item(
                scores,
                "BEAR_PUT_SPREAD",
                30,
                "Bearish bias favors defined-risk bearish spreads.",
                reasons,
            )

            self._score_item(
                scores,
                "LONG_STRANGLE",
                5,
                "A strong directional move is still possible.",
                reasons,
            )

        # ----------------------------------------------------
        # NEUTRAL MARKET
        # ----------------------------------------------------

        else:

            self._score_item(
                scores,
                "IRON_CONDOR",
                25,
                "Neutral market favors range strategies.",
                reasons,
            )

            self._score_item(
                scores,
                "LONG_STRADDLE",
                10,
                "A neutral underlying can still precede a volatility expansion.",
                reasons,
            )

        # ----------------------------------------------------
        # TREND
        # ----------------------------------------------------

        if trend == "BULLISH":

            self._score_item(
                scores,
                "LONG_CALL",
                15,
                "Trend is bullish.",
                reasons,
            )

            self._score_item(
                scores,
                "BULL_CALL_SPREAD",
                20,
                "Bullish trend supports a call spread.",
                reasons,
            )

        elif trend == "BEARISH":

            self._score_item(
                scores,
                "LONG_PUT",
                15,
                "Trend is bearish.",
                reasons,
            )

            self._score_item(
                scores,
                "BEAR_PUT_SPREAD",
                20,
                "Bearish trend supports a put spread.",
                reasons,
            )

        # ----------------------------------------------------
        # MOMENTUM
        # ----------------------------------------------------

        if momentum == "STRONG":

            if market_bias == "BULLISH":

                self._score_item(
                    scores,
                    "LONG_CALL",
                    10,
                    "Strong bullish momentum supports directional exposure.",
                    reasons,
                )

            elif market_bias == "BEARISH":

                self._score_item(
                    scores,
                    "LONG_PUT",
                    10,
                    "Strong bearish momentum supports directional exposure.",
                    reasons,
                )

        # ----------------------------------------------------
        # BREAKOUT
        # ----------------------------------------------------

        if breakout == "BULLISH_BREAKOUT":

            self._score_item(
                scores,
                "LONG_CALL",
                15,
                "Bullish breakout favors upside exposure.",
                reasons,
            )

            self._score_item(
                scores,
                "BULL_CALL_SPREAD",
                15,
                "Bullish breakout supports a defined-risk call spread.",
                reasons,
            )

        elif breakout == "BEARISH_BREAKDOWN":

            self._score_item(
                scores,
                "LONG_PUT",
                15,
                "Bearish breakdown favors downside exposure.",
                reasons,
            )

            self._score_item(
                scores,
                "BEAR_PUT_SPREAD",
                15,
                "Bearish breakdown supports a defined-risk put spread.",
                reasons,
            )

        # ----------------------------------------------------
        # VOLATILITY
        # ----------------------------------------------------

        if atm_iv is not None:

            try:

                atm_iv = float(
                    atm_iv
                )

                # These are broad heuristics.
                # We will later replace them with
                # historical IV percentile/rank.

                if atm_iv < 15:

                    self._score_item(
                        scores,
                        "LONG_STRADDLE",
                        15,
                        "Relatively low ATM IV may favor buying volatility.",
                        reasons,
                    )

                    self._score_item(
                        scores,
                        "LONG_STRANGLE",
                        15,
                        "Relatively low ATM IV may favor long-volatility structures.",
                        reasons,
                    )

                elif atm_iv > 25:

                    self._score_item(
                        scores,
                        "IRON_CONDOR",
                        15,
                        "Higher IV can make defined-risk premium-selling structures more attractive.",
                        reasons,
                    )

            except Exception:
                pass

        # ----------------------------------------------------
        # IV SKEW
        # ----------------------------------------------------

        if iv_skew is not None:

            try:

                iv_skew = float(
                    iv_skew
                )

                if iv_skew > 2:

                    self._score_item(
                        scores,
                        "BULL_CALL_SPREAD",
                        5,
                        "Higher put IV relative to call IV influences spread selection.",
                        reasons,
                    )

                elif iv_skew < -2:

                    self._score_item(
                        scores,
                        "BEAR_PUT_SPREAD",
                        5,
                        "Higher call IV relative to put IV influences spread selection.",
                        reasons,
                    )

            except Exception:
                pass

        # ----------------------------------------------------
        # PCR
        # ----------------------------------------------------

        if pcr is not None:

            try:

                pcr = float(
                    pcr
                )

                if pcr >= 1.2:

                    self._score_item(
                        scores,
                        "BULL_CALL_SPREAD",
                        8,
                        "Higher PCR provides bullish options-chain evidence.",
                        reasons,
                    )

                elif pcr <= 0.8:

                    self._score_item(
                        scores,
                        "BEAR_PUT_SPREAD",
                        8,
                        "Lower PCR provides bearish options-chain evidence.",
                        reasons,
                    )

            except Exception:
                pass

        # ----------------------------------------------------
        # Normalize to 100
        # ----------------------------------------------------

        maximum = max(
            scores.values()
        ) if scores else 1

        rankings = []

        for strategy, score in scores.items():

            normalized_score = round(
                (
                    score
                    / max(
                        maximum,
                        1,
                    )
                )
                * 100,
                1,
            )

            rankings.append({

                "strategy":
                    strategy,

                "raw_score":
                    score,

                "score":
                    normalized_score,

                "reasons":
                    reasons.get(
                        strategy,
                        [],
                    ),

            })

        rankings.sort(
            key=lambda item:
                item["score"],
            reverse=True,
        )

        return {

            "success":
                True,

            "rankings":
                rankings,

            "best_strategy":
                (
                    rankings[0]["strategy"]
                    if rankings
                    else None
                ),

        }

    # ========================================================
    # FORMAT
    # ========================================================

    def format_ranking(
        self,
        result: Dict[str, Any],
    ) -> str:

        if not result.get(
            "success",
            False,
        ):

            return (
                "OPTION STRATEGY ANALYSIS FAILED\n"
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
            "JARVIS OPTION STRATEGY ANALYSIS"
        )

        lines.append(
            "--------------------------------------------------"
        )

        lines.append(
            "STRATEGY RANKING"
        )

        rankings = result.get(
            "rankings",
            [],
        )

        for index, item in enumerate(
            rankings,
            1,
        ):

            lines.append(
                f"{index}. "
                f"{item['strategy']} "
                f"({item['score']}/100)"
            )

            for reason in item[
                "reasons"
            ][:3]:

                lines.append(
                    f"   - {reason}"
                )

        lines.append("")

        lines.append(
            "BEST CANDIDATE"
        )

        lines.append(
            str(
                result.get(
                    "best_strategy",
                    "NONE",
                )
            )
        )

        lines.append("")

        lines.append(
            "IMPORTANT: "
            "Strategy ranking is analytical only. "
            "No order was placed."
        )

        return "\n".join(
            lines
        )


# ============================================================
# GLOBAL
# ============================================================

option_strategy_engine = (
    OptionStrategyEngine()
)


# ============================================================
# SIMPLE FUNCTION
# ============================================================

def rank_option_strategies(
    market_bias,
    trend,
    momentum,
    volatility,
    option_chain,
    breakout="NONE",
):

    return (
        option_strategy_engine.rank_strategies(
            market_bias=market_bias,
            trend=trend,
            momentum=momentum,
            volatility=volatility,
            option_chain=option_chain,
            breakout=breakout,
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
        "JARVIS OPTION STRATEGY ENGINE"
    )

    print(
        "=" * 60
    )

    print()

    result = rank_option_strategies(

        market_bias="BULLISH",

        trend="BULLISH",

        momentum="STRONG",

        volatility={

            "atm_iv":
                18.5,

            "iv_skew":
                1.0,

        },

        option_chain={

            "put_call_ratio":
                0.9,

        },

        breakout="BULLISH_BREAKOUT",

    )

    print(
        option_strategy_engine.format_ranking(
            result
        )
    )