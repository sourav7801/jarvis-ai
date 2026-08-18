# ============================================================
# JARVIS BREAKOUT STRATEGY
# V1
# ============================================================
#
# Independent breakout strategy.
#
# Uses:
#   - Donchian-style breakout
#   - Volume confirmation
#   - ATR expansion
#   - ADX trend filter
#   - Breakout quality filter
#   - ATR stop
#   - ATR target
#
# Research / paper trading only.
# No live orders are placed.
# ============================================================

from __future__ import annotations

from typing import Any, Dict, List

import pandas as pd

from ta.trend import ADXIndicator
from ta.volatility import AverageTrueRange


# ============================================================
# STRATEGY
# ============================================================

class BreakoutStrategy:

    name = "BREAKOUT"

    def __init__(
        self,
        breakout_window: int = 20,
        volume_window: int = 20,
        atr_window: int = 14,
        adx_window: int = 14,
        min_adx: float = 18.0,
        volume_multiplier: float = 1.20,
        atr_expansion_multiplier: float = 1.05,
        stop_atr: float = 1.50,
        target_atr: float = 3.00,
    ):

        self.breakout_window = int(
            breakout_window
        )

        self.volume_window = int(
            volume_window
        )

        self.atr_window = int(
            atr_window
        )

        self.adx_window = int(
            adx_window
        )

        self.min_adx = float(
            min_adx
        )

        self.volume_multiplier = float(
            volume_multiplier
        )

        self.atr_expansion_multiplier = float(
            atr_expansion_multiplier
        )

        self.stop_atr = float(
            stop_atr
        )

        self.target_atr = float(
            target_atr
        )

    # ========================================================
    # PREPARE
    # ========================================================

    def prepare(
        self,
        df: pd.DataFrame,
    ) -> pd.DataFrame:

        if df is None or df.empty:
            return pd.DataFrame()

        data = df.copy()

        data.columns = [
            str(column)
            .strip()
            .lower()
            for column in data.columns
        ]

        required = {
            "open",
            "high",
            "low",
            "close",
        }

        if not required.issubset(
            data.columns
        ):

            return pd.DataFrame()

        for column in [
            "open",
            "high",
            "low",
            "close",
        ]:

            data[column] = pd.to_numeric(
                data[column],
                errors="coerce",
            )

        if "volume" not in data.columns:

            data["volume"] = 0.0

        data["volume"] = pd.to_numeric(
            data["volume"],
            errors="coerce",
        ).fillna(0.0)

        data = (
            data
            .dropna(
                subset=[
                    "open",
                    "high",
                    "low",
                    "close",
                ]
            )
            .reset_index(
                drop=True
            )
        )

        return data

    # ========================================================
    # INDICATORS
    # ========================================================

    def indicators(
        self,
        data: pd.DataFrame,
    ) -> pd.DataFrame:

        result = data.copy()

        # ----------------------------------------------------
        # Previous breakout levels
        #
        # Shift(1) is critical:
        # today's candle is NOT allowed to define
        # today's breakout level.
        # ----------------------------------------------------

        result["previous_high"] = (
            result["high"]
            .rolling(
                self.breakout_window
            )
            .max()
            .shift(1)
        )

        result["previous_low"] = (
            result["low"]
            .rolling(
                self.breakout_window
            )
            .min()
            .shift(1)
        )

        # ----------------------------------------------------
        # Volume
        # ----------------------------------------------------

        result["average_volume"] = (
            result["volume"]
            .rolling(
                self.volume_window
            )
            .mean()
            .shift(1)
        )

        result["volume_ratio"] = (
            result["volume"]
            /
            result["average_volume"]
        )

        # ----------------------------------------------------
        # ATR
        # ----------------------------------------------------

        atr_indicator = (
            AverageTrueRange(
                high=result["high"],
                low=result["low"],
                close=result["close"],
                window=self.atr_window,
            )
        )

        result["atr"] = (
            atr_indicator
            .average_true_range()
        )

        result["atr_percent"] = (
            result["atr"]
            /
            result["close"]
            *
            100.0
        )

        result["atr_average"] = (
            result["atr"]
            .rolling(
                self.volume_window
            )
            .mean()
            .shift(1)
        )

        result["atr_expansion_ratio"] = (
            result["atr"]
            /
            result["atr_average"]
        )

        # ----------------------------------------------------
        # ADX
        # ----------------------------------------------------

        adx_indicator = (
            ADXIndicator(
                high=result["high"],
                low=result["low"],
                close=result["close"],
                window=self.adx_window,
            )
        )

        result["adx"] = (
            adx_indicator.adx()
        )

        result["plus_di"] = (
            adx_indicator.adx_pos()
        )

        result["minus_di"] = (
            adx_indicator.adx_neg()
        )

        # ----------------------------------------------------
        # Candle quality
        # ----------------------------------------------------

        result["candle_range"] = (
            result["high"]
            -
            result["low"]
        )

        result["body"] = (
            (
                result["close"]
                -
                result["open"]
            )
            .abs()
        )

        result["body_ratio"] = (
            result["body"]
            /
            result["candle_range"]
            .replace(
                0,
                pd.NA,
            )
        )

        # Close near high / low.

        result["close_location"] = (
            (
                result["close"]
                -
                result["low"]
            )
            /
            result["candle_range"]
            .replace(
                0,
                pd.NA,
            )
        )

        return result

    # ========================================================
    # SIGNAL
    # ========================================================

    def signal(
        self,
        df: pd.DataFrame,
    ) -> Dict[str, Any]:

        data = self.prepare(
            df
        )

        minimum_required = max(

            self.breakout_window
            + 5,

            self.volume_window
            + 5,

            self.atr_window
            * 2,

            self.adx_window
            * 2,

        )

        if len(data) < minimum_required:

            return {

                "success":
                    False,

                "message":
                    (
                        "Not enough data for "
                        "breakout analysis."
                    ),

            }

        data = self.indicators(
            data
        )

        row = data.iloc[-1]

        close = float(
            row["close"]
        )

        high = float(
            row["high"]
        )

        low = float(
            row["low"]
        )

        previous_high = row[
            "previous_high"
        ]

        previous_low = row[
            "previous_low"
        ]

        volume_ratio = row[
            "volume_ratio"
        ]

        atr = row[
            "atr"
        ]

        atr_expansion_ratio = row[
            "atr_expansion_ratio"
        ]

        adx = row[
            "adx"
        ]

        plus_di = row[
            "plus_di"
        ]

        minus_di = row[
            "minus_di"
        ]

        body_ratio = row[
            "body_ratio"
        ]

        close_location = row[
            "close_location"
        ]

        # ----------------------------------------------------
        # Safe numeric conversion
        # ----------------------------------------------------

        def number(
            value: Any,
            default: float = 0.0,
        ) -> float:

            try:

                if pd.isna(value):

                    return default

                return float(value)

            except Exception:

                return default

        previous_high = number(
            previous_high
        )

        previous_low = number(
            previous_low
        )

        volume_ratio = number(
            volume_ratio
        )

        atr = number(
            atr
        )

        atr_expansion_ratio = number(
            atr_expansion_ratio
        )

        adx = number(
            adx
        )

        plus_di = number(
            plus_di
        )

        minus_di = number(
            minus_di
        )

        body_ratio = number(
            body_ratio
        )

        close_location = number(
            close_location
        )

        # ----------------------------------------------------
        # Breakout conditions
        # ----------------------------------------------------

        bullish_breakout = (
            previous_high > 0
            and
            close > previous_high
        )

        bearish_breakdown = (
            previous_low > 0
            and
            close < previous_low
        )

        # ----------------------------------------------------
        # Confirmation conditions
        # ----------------------------------------------------

        volume_confirmed = (
            volume_ratio
            >= self.volume_multiplier
        )

        atr_expanded = (
            atr_expansion_ratio
            >= self.atr_expansion_multiplier
        )

        trend_confirmed_bull = (
            adx >= self.min_adx
            and
            plus_di > minus_di
        )

        trend_confirmed_bear = (
            adx >= self.min_adx
            and
            minus_di > plus_di
        )

        candle_confirmed_bull = (
            body_ratio >= 0.50
            and
            close_location >= 0.65
        )

        candle_confirmed_bear = (
            body_ratio >= 0.50
            and
            close_location <= 0.35
        )

        # ----------------------------------------------------
        # Scores
        # ----------------------------------------------------

        bullish_score = 0
        bearish_score = 0

        bullish_evidence: List[str] = []
        bearish_evidence: List[str] = []

        # Breakout = strongest component.

        if bullish_breakout:

            bullish_score += 35

            bullish_evidence.append(
                "Price broke above the previous "
                f"{self.breakout_window}-bar high."
            )

        if bearish_breakdown:

            bearish_score += 35

            bearish_evidence.append(
                "Price broke below the previous "
                f"{self.breakout_window}-bar low."
            )

        # Volume.

        if volume_confirmed:

            if bullish_breakout:

                bullish_score += 20

                bullish_evidence.append(
                    f"Volume confirms breakout "
                    f"({volume_ratio:.2f}x average)."
                )

            elif bearish_breakdown:

                bearish_score += 20

                bearish_evidence.append(
                    f"Volume confirms breakdown "
                    f"({volume_ratio:.2f}x average)."
                )

        # ATR expansion.

        if atr_expanded:

            if bullish_breakout:

                bullish_score += 15

                bullish_evidence.append(
                    f"ATR is expanding "
                    f"({atr_expansion_ratio:.2f}x)."
                )

            elif bearish_breakdown:

                bearish_score += 15

                bearish_evidence.append(
                    f"ATR is expanding "
                    f"({atr_expansion_ratio:.2f}x)."
                )

        # ADX + DI.

        if trend_confirmed_bull:

            bullish_score += 15

            bullish_evidence.append(
                f"ADX/+DI confirm bullish trend "
                f"(ADX {adx:.2f})."
            )

        if trend_confirmed_bear:

            bearish_score += 15

            bearish_evidence.append(
                f"ADX/-DI confirm bearish trend "
                f"(ADX {adx:.2f})."
            )

        # Candle quality.

        if (
            candle_confirmed_bull
            and
            bullish_breakout
        ):

            bullish_score += 10

            bullish_evidence.append(
                "Breakout candle closed strongly "
                "near its high."
            )

        if (
            candle_confirmed_bear
            and
            bearish_breakdown
        ):

            bearish_score += 10

            bearish_evidence.append(
                "Breakdown candle closed strongly "
                "near its low."
            )

        # ----------------------------------------------------
        # False-breakout protection
        # ----------------------------------------------------

        # A breakout without volume AND without trend
        # confirmation is treated cautiously.

        bullish_confirmations = sum([
            int(volume_confirmed),
            int(atr_expanded),
            int(trend_confirmed_bull),
            int(candle_confirmed_bull),
        ])

        bearish_confirmations = sum([
            int(volume_confirmed),
            int(atr_expanded),
            int(trend_confirmed_bear),
            int(candle_confirmed_bear),
        ])

        # Require at least two confirmations in addition
        # to the breakout itself.

        bullish_valid = (
            bullish_breakout
            and
            bullish_confirmations >= 2
        )

        bearish_valid = (
            bearish_breakdown
            and
            bearish_confirmations >= 2
        )

        # ----------------------------------------------------
        # Decision
        # ----------------------------------------------------

        action = "WAIT"

        if (
            bullish_valid
            and
            bullish_score >= 65
            and
            bullish_score > bearish_score
        ):

            action = "BUY"

        elif (
            bearish_valid
            and
            bearish_score >= 65
            and
            bearish_score > bullish_score
        ):

            action = "SELL"

        # ----------------------------------------------------
        # Candidate risk
        # ----------------------------------------------------

        entry = close

        stop_loss = None
        target = None
        risk_reward = None

        if (
            action == "BUY"
            and
            atr > 0
        ):

            stop_loss = (
                entry
                -
                self.stop_atr
                * atr
            )

            target = (
                entry
                +
                self.target_atr
                * atr
            )

        elif (
            action == "SELL"
            and
            atr > 0
        ):

            stop_loss = (
                entry
                +
                self.stop_atr
                * atr
            )

            target = (
                entry
                -
                self.target_atr
                * atr
            )

        if (
            stop_loss is not None
            and
            target is not None
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
                    /
                    risk
                )

        # ----------------------------------------------------
        # Confidence
        # ----------------------------------------------------

        total = max(
            bullish_score
            +
            bearish_score,
            1,
        )

        separation = abs(
            bullish_score
            -
            bearish_score
        )

        confidence = (
            separation
            /
            total
            *
            100.0
        )

        return {

            "success":
                True,

            "strategy":
                self.name,

            "action":
                action,

            "confidence":
                round(
                    confidence,
                    2,
                ),

            "bullish_score":
                bullish_score,

            "bearish_score":
                bearish_score,

            "entry":
                entry,

            "stop_loss":
                stop_loss,

            "target":
                target,

            "risk_reward":
                risk_reward,

            "price":
                close,

            "breakout_high":
                previous_high,

            "breakdown_low":
                previous_low,

            "volume_ratio":
                volume_ratio,

            "atr":
                atr,

            "atr_percent":
                (
                    atr
                    /
                    close
                    *
                    100.0
                    if close
                    else 0.0
                ),

            "atr_expansion_ratio":
                atr_expansion_ratio,

            "adx":
                adx,

            "plus_di":
                plus_di,

            "minus_di":
                minus_di,

            "bullish_breakout":
                bullish_breakout,

            "bearish_breakdown":
                bearish_breakdown,

            "volume_confirmed":
                volume_confirmed,

            "atr_expanded":
                atr_expanded,

            "bullish_evidence":
                bullish_evidence,

            "bearish_evidence":
                bearish_evidence,

        }

    # ========================================================
    # COMPATIBILITY METHOD
    # ========================================================

    def prepare_signal(
        self,
        technical: Dict[str, Any],
        patterns: Dict[str, Any],
        regime: Dict[str, Any],
    ) -> Dict[str, Any]:

        return {

            "success":
                True,

            "action":
                "WAIT",

            "message":
                (
                    "Use signal(df) for dedicated "
                    "historical breakout research."
                ),

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
                "BREAKOUT ANALYSIS FAILED\n"
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
            "JARVIS BREAKOUT STRATEGY"
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
            f"Bullish Score: "
            f"{result.get('bullish_score')}"
        )

        lines.append(
            f"Bearish Score: "
            f"{result.get('bearish_score')}"
        )

        lines.append("")

        lines.append(
            "BREAKOUT STATE"
        )

        lines.append(
            f"Previous High: "
            f"{result.get('breakout_high')}"
        )

        lines.append(
            f"Previous Low: "
            f"{result.get('breakdown_low')}"
        )

        lines.append(
            f"Bullish Breakout: "
            f"{result.get('bullish_breakout')}"
        )

        lines.append(
            f"Bearish Breakdown: "
            f"{result.get('bearish_breakdown')}"
        )

        lines.append("")

        lines.append(
            "CONFIRMATION"
        )

        lines.append(
            f"Volume Ratio: "
            f"{result.get('volume_ratio'):.2f}x"
        )

        lines.append(
            f"ATR Expansion: "
            f"{result.get('atr_expansion_ratio'):.2f}x"
        )

        lines.append(
            f"ADX: "
            f"{result.get('adx'):.2f}"
        )

        lines.append(
            f"+DI: "
            f"{result.get('plus_di'):.2f}"
        )

        lines.append(
            f"-DI: "
            f"{result.get('minus_di'):.2f}"
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
            "BULLISH EVIDENCE"
        )

        for item in result.get(
            "bullish_evidence",
            [],
        ):

            lines.append(
                f"- {item}"
            )

        lines.append("")

        lines.append(
            "BEARISH EVIDENCE"
        )

        for item in result.get(
            "bearish_evidence",
            [],
        ):

            lines.append(
                f"- {item}"
            )

        lines.append("")

        lines.append(
            "IMPORTANT: "
            "Research/paper-trading analysis only. "
            "No live order was placed."
        )

        return "\n".join(
            lines
        )


# ============================================================
# GLOBAL
# ============================================================

breakout_strategy = (
    BreakoutStrategy()
)


# ============================================================
# SIMPLE FUNCTION
# ============================================================

def analyze_breakout(
    df: pd.DataFrame,
):

    return (
        breakout_strategy.signal(
            df
        )
    )


# ============================================================
# TEST
# ============================================================

if __name__ == "__main__":

    from agents.market_data_agent import (
        get_market_data,
    )

    print(
        "=" * 60
    )

    print(
        "JARVIS BREAKOUT STRATEGY"
    )

    print(
        "=" * 60
    )

    result = get_market_data(

        "NIFTY",

        market="india",

        timeframe="1d",

        bars=1000,

    )

    if not result.get(
        "success",
        False,
    ):

        print(
            "Market data failed:"
        )

        print(
            result.get(
                "message"
            )
        )

    else:

        signal = (
            analyze_breakout(
                result["data"]
            )
        )

        print()

        print(
            breakout_strategy.format_result(
                signal
            )
        )

    print()

    print(
        "Breakout Strategy loaded successfully."
    )