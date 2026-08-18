# ============================================================
# JARVIS MEAN REVERSION STRATEGY
# V1
# ============================================================

from __future__ import annotations

from typing import Any, Dict, List

import pandas as pd

from ta.momentum import RSIIndicator
from ta.volatility import (
    AverageTrueRange,
    BollingerBands,
)
from ta.trend import EMAIndicator


class MeanReversionStrategy:

    name = "MEAN_REVERSION"

    def __init__(
        self,
        bb_window: int = 20,
        bb_std: float = 2.0,
        rsi_window: int = 14,
        mean_window: int = 20,
        atr_window: int = 14,
        extreme_atr_multiple: float = 1.5,
        stop_atr: float = 1.5,
        target_atr: float = 2.25,
    ):

        self.bb_window = int(bb_window)
        self.bb_std = float(bb_std)
        self.rsi_window = int(rsi_window)
        self.mean_window = int(mean_window)
        self.atr_window = int(atr_window)
        self.extreme_atr_multiple = float(
            extreme_atr_multiple
        )
        self.stop_atr = float(stop_atr)
        self.target_atr = float(target_atr)

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

        for column in required:

            data[column] = pd.to_numeric(
                data[column],
                errors="coerce",
            )

        return (
            data
            .dropna(
                subset=list(required)
            )
            .reset_index(drop=True)
        )

    # ========================================================
    # INDICATORS
    # ========================================================

    def indicators(
        self,
        data: pd.DataFrame,
    ) -> pd.DataFrame:

        result = data.copy()

        bb = BollingerBands(
            close=result["close"],
            window=self.bb_window,
            window_dev=self.bb_std,
        )

        result["bb_middle"] = (
            bb.bollinger_mavg()
        )

        result["bb_upper"] = (
            bb.bollinger_hband()
        )

        result["bb_lower"] = (
            bb.bollinger_lband()
        )

        result["bb_percent"] = (
            bb.bollinger_pband()
        )

        result["rsi"] = (
            RSIIndicator(
                close=result["close"],
                window=self.rsi_window,
            ).rsi()
        )

        result["ema_mean"] = (
            EMAIndicator(
                close=result["close"],
                window=self.mean_window,
            ).ema_indicator()
        )

        result["atr"] = (
            AverageTrueRange(
                high=result["high"],
                low=result["low"],
                close=result["close"],
                window=self.atr_window,
            ).average_true_range()
        )

        result["distance_atr"] = (
            (
                result["close"]
                -
                result["ema_mean"]
            )
            /
            result["atr"]
        )

        return result

    # ========================================================
    # SIGNAL
    # ========================================================

    def signal(
        self,
        df: pd.DataFrame,
    ) -> Dict[str, Any]:

        data = self.prepare(df)

        minimum = max(
            self.bb_window + 10,
            self.mean_window + 10,
            self.rsi_window + 10,
            self.atr_window * 2,
        )

        if len(data) < minimum:

            return {
                "success": False,
                "message":
                    "Not enough data for mean-reversion analysis.",
            }

        data = self.indicators(
            data
        )

        row = data.iloc[-1]
        previous = data.iloc[-2]

        close = float(
            row["close"]
        )

        high = float(
            row["high"]
        )

        low = float(
            row["low"]
        )

        lower_band = float(
            row["bb_lower"]
        )

        upper_band = float(
            row["bb_upper"]
        )

        middle_band = float(
            row["bb_middle"]
        )

        rsi = float(
            row["rsi"]
        )

        ema_mean = float(
            row["ema_mean"]
        )

        atr = float(
            row["atr"]
        )

        distance_atr = float(
            row["distance_atr"]
        )

        previous_close = float(
            previous["close"]
        )

        # ----------------------------------------------------
        # Extreme conditions
        # ----------------------------------------------------

        oversold = (
            close <= lower_band
            and rsi <= 35
        )

        overbought = (
            close >= upper_band
            and rsi >= 65
        )

        # ----------------------------------------------------
        # Re-entry confirmation
        #
        # We prefer price to move back inside the band
        # rather than blindly buying the first touch.
        # ----------------------------------------------------

        bullish_reentry = (
            previous_close <= lower_band
            and close > lower_band
        )

        bearish_reentry = (
            previous_close >= upper_band
            and close < upper_band
        )

        # ----------------------------------------------------
        # Scores
        # ----------------------------------------------------

        bullish_score = 0
        bearish_score = 0

        bullish_evidence: List[str] = []
        bearish_evidence: List[str] = []

        if oversold:

            bullish_score += 35

            bullish_evidence.append(
                f"Price is near/below the lower Bollinger Band "
                f"with RSI at {rsi:.2f}."
            )

        if overbought:

            bearish_score += 35

            bearish_evidence.append(
                f"Price is near/above the upper Bollinger Band "
                f"with RSI at {rsi:.2f}."
            )

        if bullish_reentry:

            bullish_score += 25

            bullish_evidence.append(
                "Bullish re-entry inside the lower Bollinger Band."
            )

        if bearish_reentry:

            bearish_score += 25

            bearish_evidence.append(
                "Bearish re-entry inside the upper Bollinger Band."
            )

        if distance_atr <= (
            -self.extreme_atr_multiple
        ):

            bullish_score += 20

            bullish_evidence.append(
                f"Price is {abs(distance_atr):.2f} ATR "
                "below the mean."
            )

        if distance_atr >= (
            self.extreme_atr_multiple
        ):

            bearish_score += 20

            bearish_evidence.append(
                f"Price is {distance_atr:.2f} ATR "
                "above the mean."
            )

        # Mild confirmation toward the mean.

        if close < middle_band:

            bullish_score += 5

        if close > middle_band:

            bearish_score += 5

        # ----------------------------------------------------
        # Require confirmation.
        #
        # Do not buy simply because RSI is low.
        # ----------------------------------------------------

        bullish_valid = (
            bullish_score >= 60
            and
            (
                bullish_reentry
                or
                distance_atr
                <=
                -self.extreme_atr_multiple
            )
        )

        bearish_valid = (
            bearish_score >= 60
            and
            (
                bearish_reentry
                or
                distance_atr
                >=
                self.extreme_atr_multiple
            )
        )

        action = "WAIT"

        if (
            bullish_valid
            and
            bullish_score > bearish_score
        ):

            action = "BUY"

        elif (
            bearish_valid
            and
            bearish_score > bullish_score
        ):

            action = "SELL"

        # ----------------------------------------------------
        # Risk
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

            # Mean-reversion target:
            # first target is the statistical mean,
            # but never closer than a minimal risk/reward.
            target = max(
                middle_band,
                entry
                +
                self.target_atr * atr,
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

            target = min(
                middle_band,
                entry
                -
                self.target_atr * atr,
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
                    reward / risk
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

            "success": True,

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

            "bb_lower":
                lower_band,

            "bb_middle":
                middle_band,

            "bb_upper":
                upper_band,

            "rsi":
                rsi,

            "ema_mean":
                ema_mean,

            "atr":
                atr,

            "distance_atr":
                distance_atr,

            "bullish_reentry":
                bullish_reentry,

            "bearish_reentry":
                bearish_reentry,

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

            "success": True,

            "action":
                "WAIT",

            "message":
                (
                    "Use signal(df) for dedicated "
                    "mean-reversion research."
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
                "MEAN REVERSION ANALYSIS FAILED\n"
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
            "JARVIS MEAN REVERSION STRATEGY"
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
            f"Lower Band: "
            f"{result.get('bb_lower'):.2f}"
        )

        lines.append(
            f"Middle Band: "
            f"{result.get('bb_middle'):.2f}"
        )

        lines.append(
            f"Upper Band: "
            f"{result.get('bb_upper'):.2f}"
        )

        lines.append(
            f"RSI: "
            f"{result.get('rsi'):.2f}"
        )

        lines.append(
            f"Distance From Mean: "
            f"{result.get('distance_atr'):.2f} ATR"
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

mean_reversion_strategy = (
    MeanReversionStrategy()
)


# ============================================================
# HELPER
# ============================================================

def analyze_mean_reversion(
    df: pd.DataFrame,
):

    return (
        mean_reversion_strategy.signal(
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
        "JARVIS MEAN REVERSION STRATEGY"
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
            analyze_mean_reversion(
                result["data"]
            )
        )

        print()

        print(
            mean_reversion_strategy.format_result(
                signal
            )
        )

    print()

    print(
        "Mean Reversion Strategy loaded successfully."
    )