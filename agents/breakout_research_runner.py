# ============================================================
# JARVIS MOMENTUM STRATEGY
# V1
# ============================================================
#
# Independent momentum strategy.
#
# Uses:
#   - RSI
#   - Rate of Change (ROC)
#   - EMA structure
#   - MACD
#   - Volume confirmation
#   - ATR risk management
#
# Research / paper trading only.
# No live orders.
# ============================================================

from __future__ import annotations

from typing import Any, Dict, List

import pandas as pd

from ta.momentum import RSIIndicator
from ta.trend import EMAIndicator, MACD
from ta.volatility import AverageTrueRange


# ============================================================
# STRATEGY
# ============================================================

class MomentumStrategy:

    name = "MOMENTUM"

    def __init__(
        self,
        fast_ema: int = 20,
        slow_ema: int = 50,
        rsi_window: int = 14,
        roc_window: int = 10,
        macd_fast: int = 12,
        macd_slow: int = 26,
        macd_signal: int = 9,
        atr_window: int = 14,
        volume_window: int = 20,
        min_volume_ratio: float = 1.0,
        stop_atr: float = 1.5,
        target_atr: float = 3.0,
    ):

        self.fast_ema = int(
            fast_ema
        )

        self.slow_ema = int(
            slow_ema
        )

        self.rsi_window = int(
            rsi_window
        )

        self.roc_window = int(
            roc_window
        )

        self.macd_fast = int(
            macd_fast
        )

        self.macd_slow = int(
            macd_slow
        )

        self.macd_signal = int(
            macd_signal
        )

        self.atr_window = int(
            atr_window
        )

        self.volume_window = int(
            volume_window
        )

        self.min_volume_ratio = float(
            min_volume_ratio
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
            str(column).strip().lower()
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
            .reset_index(drop=True)
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
        # EMA
        # ----------------------------------------------------

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

        # ----------------------------------------------------
        # RSI
        # ----------------------------------------------------

        result["rsi"] = (
            RSIIndicator(
                close=result["close"],
                window=self.rsi_window,
            ).rsi()
        )

        # ----------------------------------------------------
        # ROC
        # ----------------------------------------------------

        result["roc"] = (
            result["close"].pct_change(
                self.roc_window
            )
            * 100.0
        )

        # ----------------------------------------------------
        # MACD
        # ----------------------------------------------------

        macd = MACD(

            close=result["close"],

            window_fast=self.macd_fast,

            window_slow=self.macd_slow,

            window_sign=self.macd_signal,

        )

        result["macd"] = (
            macd.macd()
        )

        result["macd_signal"] = (
            macd.macd_signal()
        )

        result["macd_hist"] = (
            macd.macd_diff()
        )

        # ----------------------------------------------------
        # ATR
        # ----------------------------------------------------

        result["atr"] = (
            AverageTrueRange(

                high=result["high"],

                low=result["low"],

                close=result["close"],

                window=self.atr_window,

            )
            .average_true_range()
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
        # Price momentum
        # ----------------------------------------------------

        result["price_change_5"] = (
            result["close"].pct_change(5)
            * 100.0
        )

        result["price_change_20"] = (
            result["close"].pct_change(20)
            * 100.0
        )

        return result

    # ========================================================
    # SAFE NUMBER
    # ========================================================

    def number(
        self,
        value: Any,
        default: float = 0.0,
    ) -> float:

        try:

            if pd.isna(value):

                return default

            return float(
                value
            )

        except Exception:

            return default

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

            self.slow_ema + 10,

            self.macd_slow
            + self.macd_signal
            + 10,

            self.roc_window + 10,

            self.volume_window + 10,

            self.atr_window * 2,

        )

        if len(data) < minimum_required:

            return {

                "success":
                    False,

                "message":
                    (
                        "Not enough data for "
                        "momentum analysis."
                    ),

            }

        data = self.indicators(
            data
        )

        row = data.iloc[-1]

        # ----------------------------------------------------
        # Values
        # ----------------------------------------------------

        close = self.number(
            row["close"]
        )

        ema_fast = self.number(
            row["ema_fast"]
        )

        ema_slow = self.number(
            row["ema_slow"]
        )

        rsi = self.number(
            row["rsi"]
        )

        roc = self.number(
            row["roc"]
        )

        macd_value = self.number(
            row["macd"]
        )

        macd_signal = self.number(
            row["macd_signal"]
        )

        macd_hist = self.number(
            row["macd_hist"]
        )

        atr = self.number(
            row["atr"]
        )

        volume_ratio = self.number(
            row["volume_ratio"]
        )

        price_change_5 = self.number(
            row["price_change_5"]
        )

        price_change_20 = self.number(
            row["price_change_20"]
        )

        # ====================================================
        # SCORES
        # ====================================================

        bullish_score = 0

        bearish_score = 0

        bullish_evidence: List[str] = []

        bearish_evidence: List[str] = []

        # ----------------------------------------------------
        # EMA structure
        # ----------------------------------------------------

        if (
            close > ema_fast
            and
            ema_fast > ema_slow
        ):

            bullish_score += 25

            bullish_evidence.append(
                "Price and EMA structure are bullish."
            )

        elif (
            close < ema_fast
            and
            ema_fast < ema_slow
        ):

            bearish_score += 25

            bearish_evidence.append(
                "Price and EMA structure are bearish."
            )

        elif ema_fast > ema_slow:

            bullish_score += 10

            bullish_evidence.append(
                "Fast EMA remains above slow EMA."
            )

        elif ema_fast < ema_slow:

            bearish_score += 10

            bearish_evidence.append(
                "Fast EMA remains below slow EMA."
            )

        # ----------------------------------------------------
        # RSI momentum
        # ----------------------------------------------------

        if 55 <= rsi <= 70:

            bullish_score += 15

            bullish_evidence.append(
                f"RSI confirms bullish momentum ({rsi:.2f})."
            )

        elif 30 <= rsi <= 45:

            bearish_score += 15

            bearish_evidence.append(
                f"RSI confirms bearish momentum ({rsi:.2f})."
            )

        # Avoid interpreting extreme RSI as automatic entry.
        elif rsi > 70:

            bullish_score += 5

            bullish_evidence.append(
                f"RSI is very strong but extended ({rsi:.2f})."
            )

        elif rsi < 30:

            bearish_score += 5

            bearish_evidence.append(
                f"RSI is very weak but extended ({rsi:.2f})."
            )

        # ----------------------------------------------------
        # ROC
        # ----------------------------------------------------

        if roc > 1.0:

            bullish_score += 15

            bullish_evidence.append(
                f"ROC shows positive momentum ({roc:.2f}%)."
            )

        elif roc < -1.0:

            bearish_score += 15

            bearish_evidence.append(
                f"ROC shows negative momentum ({roc:.2f}%)."
            )

        # ----------------------------------------------------
        # MACD
        # ----------------------------------------------------

        if (
            macd_value > macd_signal
            and
            macd_hist > 0
        ):

            bullish_score += 20

            bullish_evidence.append(
                "MACD momentum is bullish."
            )

        elif (
            macd_value < macd_signal
            and
            macd_hist < 0
        ):

            bearish_score += 20

            bearish_evidence.append(
                "MACD momentum is bearish."
            )

        # ----------------------------------------------------
        # Volume
        # ----------------------------------------------------

        if volume_ratio >= (
            self.min_volume_ratio
        ):

            if bullish_score > bearish_score:

                bullish_score += 10

                bullish_evidence.append(
                    f"Volume confirms momentum "
                    f"({volume_ratio:.2f}x average)."
                )

            elif bearish_score > bullish_score:

                bearish_score += 10

                bearish_evidence.append(
                    f"Volume confirms momentum "
                    f"({volume_ratio:.2f}x average)."
                )

        # ----------------------------------------------------
        # Price momentum
        # ----------------------------------------------------

        if (
            price_change_5 > 0
            and
            price_change_20 > 0
        ):

            bullish_score += 10

            bullish_evidence.append(
                "Short- and medium-term price momentum "
                "are positive."
            )

        elif (
            price_change_5 < 0
            and
            price_change_20 < 0
        ):

            bearish_score += 10

            bearish_evidence.append(
                "Short- and medium-term price momentum "
                "are negative."
            )

        # ====================================================
        # DECISION
        # ====================================================

        action = "WAIT"

        if (
            bullish_score >= 60
            and
            bullish_score > bearish_score
        ):

            action = "BUY"

        elif (
            bearish_score >= 60
            and
            bearish_score > bullish_score
        ):

            action = "SELL"

        # ====================================================
        # RISK
        # ====================================================

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

        # ====================================================
        # CONFIDENCE
        # ====================================================

        total_score = max(
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
            total_score
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

            "rsi":
                rsi,

            "roc":
                roc,

            "macd":
                macd_value,

            "macd_signal":
                macd_signal,

            "macd_hist":
                macd_hist,

            "atr":
                atr,

            "volume_ratio":
                volume_ratio,

            "price_change_5":
                price_change_5,

            "price_change_20":
                price_change_20,

            "bullish_evidence":
                bullish_evidence,

            "bearish_evidence":
                bearish_evidence,

        }

    # ========================================================
    # COMPATIBILITY
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
                    "historical momentum research."
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
                "MOMENTUM ANALYSIS FAILED\n"
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
            "JARVIS MOMENTUM STRATEGY"
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
            f"RSI: "
            f"{result.get('rsi'):.2f}"
        )

        lines.append(
            f"ROC: "
            f"{result.get('roc'):.2f}%"
        )

        lines.append(
            f"MACD: "
            f"{result.get('macd'):.4f}"
        )

        lines.append(
            f"MACD Signal: "
            f"{result.get('macd_signal'):.4f}"
        )

        lines.append(
            f"MACD Histogram: "
            f"{result.get('macd_hist'):.4f}"
        )

        lines.append(
            f"Volume Ratio: "
            f"{result.get('volume_ratio'):.2f}x"
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

momentum_strategy = (
    MomentumStrategy()
)


# ============================================================
# HELPER
# ============================================================

def analyze_momentum(
    df: pd.DataFrame,
):

    return (
        momentum_strategy.signal(
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
        "JARVIS MOMENTUM STRATEGY"
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
            analyze_momentum(
                result["data"]
            )
        )

        print()

        print(
            momentum_strategy.format_result(
                signal
            )
        )

    print()

    print(
        "Momentum Strategy loaded successfully."
    )