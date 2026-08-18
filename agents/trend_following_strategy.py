# ============================================================
# JARVIS TREND FOLLOWING STRATEGY
# V1
# ============================================================
#
# Independent strategy:
#   - EMA structure
#   - ADX trend filter
#   - DI direction
#   - Pullback confirmation
#   - ATR stop/target
#   - Momentum confirmation
#
# IMPORTANT:
#   Research/paper trading only.
#   No live orders.
# ============================================================

from __future__ import annotations

from typing import Any, Dict, List

import pandas as pd
import numpy as np

from ta.trend import (
    EMAIndicator,
    ADXIndicator,
)

from ta.momentum import RSIIndicator

from ta.volatility import AverageTrueRange


# ============================================================
# STRATEGY
# ============================================================

class TrendFollowingStrategy:

    name = "TREND_FOLLOWING"

    def __init__(
        self,
        fast_ema: int = 20,
        slow_ema: int = 50,
        trend_ema: int = 200,
        adx_window: int = 14,
        atr_window: int = 14,
        min_adx: float = 20.0,
        stop_atr: float = 1.5,
        target_atr: float = 3.0,
    ):

        self.fast_ema = fast_ema
        self.slow_ema = slow_ema
        self.trend_ema = trend_ema

        self.adx_window = adx_window
        self.atr_window = atr_window

        self.min_adx = min_adx

        self.stop_atr = stop_atr
        self.target_atr = target_atr

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
            str(c).strip().lower()
            for c in data.columns
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

        data = data.dropna(
            subset=[
                "open",
                "high",
                "low",
                "close",
            ]
        )

        return data.reset_index(
            drop=True
        )

    # ========================================================
    # INDICATORS
    # ========================================================

    def indicators(
        self,
        data: pd.DataFrame,
    ) -> pd.DataFrame:

        result = data.copy()

        result["ema_fast"] = (
            EMAIndicator(
                close=result["close"],
                window=self.fast_ema,
            ).ema_indicator()
        )

        result["ema_slow"] = (
            EMAIndicator(
                close=result["close"],
                window=self.slow_ema,
            ).ema_indicator()
        )

        result["ema_trend"] = (
            EMAIndicator(
                close=result["close"],
                window=self.trend_ema,
            ).ema_indicator()
        )

        adx_indicator = ADXIndicator(
            high=result["high"],
            low=result["low"],
            close=result["close"],
            window=self.adx_window,
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

        result["rsi"] = (
            RSIIndicator(
                close=result["close"],
                window=14,
            ).rsi()
        )

        result["atr"] = (
            AverageTrueRange(
                high=result["high"],
                low=result["low"],
                close=result["close"],
                window=self.atr_window,
            ).average_true_range()
        )

        result["atr_percent"] = (
            result["atr"]
            /
            result["close"]
            *
            100.0
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

        minimum = max(
            self.trend_ema,
            self.slow_ema,
            self.adx_window * 2,
            self.atr_window * 2,
        )

        if len(data) < minimum:

            return {

                "success":
                    False,

                "message":
                    (
                        "Not enough data for "
                        "trend-following analysis."
                    ),

            }

        data = self.indicators(
            data
        )

        row = data.iloc[-1]

        previous = data.iloc[-2]

        close = float(
            row["close"]
        )

        ema_fast = float(
            row["ema_fast"]
        )

        ema_slow = float(
            row["ema_slow"]
        )

        ema_trend = float(
            row["ema_trend"]
        )

        adx = float(
            row["adx"]
        )

        plus_di = float(
            row["plus_di"]
        )

        minus_di = float(
            row["minus_di"]
        )

        rsi = float(
            row["rsi"]
        )

        atr = float(
            row["atr"]
        )

        previous_close = float(
            previous["close"]
        )

        previous_fast = float(
            previous["ema_fast"]
        )

        # ----------------------------------------------------
        # Bullish conditions
        # ----------------------------------------------------

        bullish = []

        if close > ema_trend:

            bullish.append(
                "Price is above the long-term EMA."
            )

        if ema_fast > ema_slow:

            bullish.append(
                "Fast EMA is above slow EMA."
            )

        if (
            adx >= self.min_adx
            and
            plus_di > minus_di
        ):

            bullish.append(
                "ADX and +DI confirm bullish trend strength."
            )

        if (
            previous_close
            <=
            previous_fast
            and
            close
            >
            ema_fast
        ):

            bullish.append(
                "Bullish pullback/reclaim detected."
            )

        if 50 <= rsi <= 70:

            bullish.append(
                f"RSI confirms healthy bullish momentum ({rsi:.2f})."
            )

        # ----------------------------------------------------
        # Bearish conditions
        # ----------------------------------------------------

        bearish = []

        if close < ema_trend:

            bearish.append(
                "Price is below the long-term EMA."
            )

        if ema_fast < ema_slow:

            bearish.append(
                "Fast EMA is below slow EMA."
            )

        if (
            adx >= self.min_adx
            and
            minus_di > plus_di
        ):

            bearish.append(
                "ADX and -DI confirm bearish trend strength."
            )

        if (
            previous_close
            >=
            previous_fast
            and
            close
            <
            ema_fast
        ):

            bearish.append(
                "Bearish pullback/rejection detected."
            )

        if 30 <= rsi <= 50:

            bearish.append(
                f"RSI confirms bearish momentum ({rsi:.2f})."
            )

        # ----------------------------------------------------
        # Score
        # ----------------------------------------------------

        bullish_score = 0
        bearish_score = 0

        # Trend structure.
        if close > ema_trend:
            bullish_score += 25

        if close < ema_trend:
            bearish_score += 25

        # EMA alignment.
        if ema_fast > ema_slow:
            bullish_score += 20

        if ema_fast < ema_slow:
            bearish_score += 20

        # ADX direction.
        if (
            adx >= self.min_adx
            and
            plus_di > minus_di
        ):
            bullish_score += 20

        if (
            adx >= self.min_adx
            and
            minus_di > plus_di
        ):
            bearish_score += 20

        # Pullback.
        if (
            previous_close
            <=
            previous_fast
            and
            close
            >
            ema_fast
        ):
            bullish_score += 15

        if (
            previous_close
            >=
            previous_fast
            and
            close
            <
            ema_fast
        ):
            bearish_score += 15

        # RSI.
        if 50 <= rsi <= 70:
            bullish_score += 10

        if 30 <= rsi <= 50:
            bearish_score += 10

        # ----------------------------------------------------
        # Decision
        # ----------------------------------------------------

        action = "WAIT"

        if (
            bullish_score >= 65
            and
            bullish_score > bearish_score
        ):

            action = "BUY"

        elif (
            bearish_score >= 65
            and
            bearish_score > bullish_score
        ):

            action = "SELL"

        # ----------------------------------------------------
        # Entry / risk
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
                self.stop_atr * atr
            )

            target = (
                entry
                +
                self.target_atr * atr
            )

        elif (
            action == "SELL"
            and
            atr > 0
        ):

            stop_loss = (
                entry
                +
                self.stop_atr * atr
            )

            target = (
                entry
                -
                self.target_atr * atr
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
                    / risk
                )

        # ----------------------------------------------------
        # Confidence
        # ----------------------------------------------------

        total = max(
            bullish_score
            + bearish_score,
            1,
        )

        separation = abs(
            bullish_score
            - bearish_score
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

            "ema_fast":
                ema_fast,

            "ema_slow":
                ema_slow,

            "ema_trend":
                ema_trend,

            "adx":
                adx,

            "plus_di":
                plus_di,

            "minus_di":
                minus_di,

            "rsi":
                rsi,

            "atr":
                atr,

            "atr_percent":
                float(
                    row["atr_percent"]
                ),

            "bullish_evidence":
                bullish,

            "bearish_evidence":
                bearish,

        }

    # ========================================================
    # ADAPTER COMPATIBILITY
    # ========================================================

    def prepare_signal(
        self,
        technical: Dict[str, Any],
        patterns: Dict[str, Any],
        regime: Dict[str, Any],
    ) -> Dict[str, Any]:

        """
        Compatibility interface for future strategy
        research architecture.

        A full historical strategy run should use
        signal(df) because this strategy owns its indicators.
        """

        return {

            "success":
                True,

            "action":
                "WAIT",

            "message":
                (
                    "Use signal(df) for the dedicated "
                    "trend-following historical backtest."
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
                "TREND FOLLOWING ANALYSIS FAILED\n"
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
            "JARVIS TREND FOLLOWING STRATEGY"
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
            "INDICATORS"
        )

        lines.append(
            f"Price: "
            f"{result.get('price'):.2f}"
        )

        lines.append(
            f"EMA {self.fast_ema}: "
            f"{result.get('ema_fast'):.2f}"
        )

        lines.append(
            f"EMA {self.slow_ema}: "
            f"{result.get('ema_slow'):.2f}"
        )

        lines.append(
            f"EMA {self.trend_ema}: "
            f"{result.get('ema_trend'):.2f}"
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

        lines.append(
            f"RSI: "
            f"{result.get('rsi'):.2f}"
        )

        lines.append(
            f"ATR: "
            f"{result.get('atr'):.2f}"
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

trend_following_strategy = (
    TrendFollowingStrategy()
)


# ============================================================
# SIMPLE FUNCTION
# ============================================================

def analyze_trend_following(
    df: pd.DataFrame,
):

    return (
        trend_following_strategy.signal(
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
        "JARVIS TREND FOLLOWING STRATEGY"
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
            analyze_trend_following(
                result["data"]
            )
        )

        print()

        print(
            trend_following_strategy.format_result(
                signal
            )
        )

    print()

    print(
        "Trend Following Strategy loaded successfully."
    )