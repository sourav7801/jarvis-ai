# ============================================================
# JARVIS MARKET REGIME DETECTOR
# V1
# ============================================================

from __future__ import annotations

from typing import Any, Dict

import pandas as pd
import numpy as np
import ta


# ============================================================
# REGIME DETECTOR
# ============================================================

class MarketRegimeDetector:

    """
    Classifies the current market regime.

    Regimes:

        TRENDING_BULL
        TRENDING_BEAR
        RANGE
        HIGH_VOLATILITY
        LOW_VOLATILITY
        TRANSITION

    This is an analytical component only.
    It never places orders.
    """

    def __init__(
        self,
        atr_window: int = 14,
        adx_window: int = 14,
        trend_window: int = 50,
        volatility_lookback: int = 100,
    ):

        self.atr_window = atr_window
        self.adx_window = adx_window
        self.trend_window = trend_window
        self.volatility_lookback = volatility_lookback

    # ========================================================
    # PREPARE DATA
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
            "high",
            "low",
            "close",
        }

        if not required.issubset(
            data.columns
        ):
            return pd.DataFrame()

        for column in [
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
                "high",
                "low",
                "close",
            ]
        )

        return data.reset_index(
            drop=True
        )

    # ========================================================
    # ANALYZE
    # ========================================================

    def analyze(
        self,
        df: pd.DataFrame,
    ) -> Dict[str, Any]:

        data = self.prepare(
            df
        )

        minimum_required = max(
            self.trend_window,
            self.volatility_lookback,
            self.adx_window * 2,
        )

        if len(data) < minimum_required:

            return {

                "success":
                    False,

                "message":
                    (
                        "Not enough data for "
                        "regime detection. "
                        f"Need at least "
                        f"{minimum_required} bars."
                    ),

            }

        close = data[
            "close"
        ]

        high = data[
            "high"
        ]

        low = data[
            "low"
        ]

        # ----------------------------------------------------
        # Moving averages
        # ----------------------------------------------------

        ema20 = (
            close.ewm(
                span=20,
                adjust=False,
            ).mean()
        )

        ema50 = (
            close.ewm(
                span=50,
                adjust=False,
            ).mean()
        )

        sma50 = (
            close.rolling(
                self.trend_window
            ).mean()
        )

        # ----------------------------------------------------
        # ADX
        # ----------------------------------------------------

        adx_indicator = (
            ta.trend.ADXIndicator(
                high=high,
                low=low,
                close=close,
                window=self.adx_window,
            )
        )

        adx = (
            adx_indicator.adx()
        )

        # ----------------------------------------------------
        # ATR
        # ----------------------------------------------------

        atr_indicator = (
            ta.volatility.AverageTrueRange(
                high=high,
                low=low,
                close=close,
                window=self.atr_window,
            )
        )

        atr = (
            atr_indicator.average_true_range()
        )

        # ----------------------------------------------------
        # Returns / realized volatility
        # ----------------------------------------------------

        returns = (
            close.pct_change()
        )

        rolling_volatility = (
            returns
            .rolling(
                self.volatility_lookback
            )
            .std()
            * np.sqrt(252)
            * 100
        )

        current_price = float(
            close.iloc[-1]
        )

        current_ema20 = float(
            ema20.iloc[-1]
        )

        current_ema50 = float(
            ema50.iloc[-1]
        )

        current_sma50 = float(
            sma50.iloc[-1]
        )

        current_adx = float(
            adx.iloc[-1]
        )

        current_atr = float(
            atr.iloc[-1]
        )

        current_volatility = float(
            rolling_volatility.iloc[-1]
        )

        # ====================================================
        # TREND SCORE
        # ====================================================

        bullish_score = 0
        bearish_score = 0

        if current_price > current_ema20:
            bullish_score += 1
        else:
            bearish_score += 1

        if current_ema20 > current_ema50:
            bullish_score += 1
        else:
            bearish_score += 1

        if current_price > current_sma50:
            bullish_score += 1
        else:
            bearish_score += 1

        # ====================================================
        # TREND STRENGTH
        # ====================================================

        trend_strength = "WEAK"

        if current_adx >= 25:
            trend_strength = "STRONG"

        elif current_adx >= 20:
            trend_strength = "MODERATE"

        # ====================================================
        # VOLATILITY REGIME
        # ====================================================

        historical_volatility = (
            rolling_volatility.dropna()
        )

        if historical_volatility.empty:

            volatility_percentile = 50.0

        else:

            volatility_percentile = (

                float(
                    (
                        historical_volatility
                        <= current_volatility
                    ).mean()
                )
                * 100.0

            )

        if volatility_percentile >= 80:

            volatility_regime = (
                "HIGH_VOLATILITY"
            )

        elif volatility_percentile <= 20:

            volatility_regime = (
                "LOW_VOLATILITY"
            )

        else:

            volatility_regime = (
                "NORMAL_VOLATILITY"
            )

        # ====================================================
        # REGIME CLASSIFICATION
        # ====================================================

        if current_adx >= 25:

            if bullish_score >= 2:

                regime = (
                    "TRENDING_BULL"
                )

            elif bearish_score >= 2:

                regime = (
                    "TRENDING_BEAR"
                )

            else:

                regime = (
                    "TRANSITION"
                )

        elif current_adx < 18:

            if (
                volatility_regime
                ==
                "HIGH_VOLATILITY"
            ):

                regime = (
                    "HIGH_VOLATILITY"
                )

            else:

                regime = (
                    "RANGE"
                )

        else:

            regime = (
                "TRANSITION"
            )

        # ====================================================
        # DISTANCE FROM MOVING AVERAGES
        # ====================================================

        ema20_distance = (
            (
                current_price
                - current_ema20
            )
            /
            current_price
            * 100
        )

        ema50_distance = (
            (
                current_price
                - current_ema50
            )
            /
            current_price
            * 100
        )

        atr_percent = (
            current_atr
            /
            current_price
            * 100
        )

        # ====================================================
        # CONFIDENCE
        # ====================================================

        confidence = 50

        if current_adx >= 30:
            confidence += 20

        elif current_adx >= 25:
            confidence += 10

        if (
            bullish_score == 3
            or
            bearish_score == 3
        ):

            confidence += 15

        elif (
            bullish_score == 2
            or
            bearish_score == 2
        ):

            confidence += 8

        if volatility_regime in {
            "HIGH_VOLATILITY",
            "LOW_VOLATILITY",
        }:

            confidence -= 5

        confidence = max(
            0,
            min(
                100,
                confidence,
            ),
        )

        # ====================================================
        # BIAS
        # ====================================================

        if bullish_score > bearish_score:

            bias = "BULLISH"

        elif bearish_score > bullish_score:

            bias = "BEARISH"

        else:

            bias = "NEUTRAL"

        # ====================================================
        # OUTPUT
        # ====================================================

        return {

            "success":
                True,

            "regime":
                regime,

            "bias":
                bias,

            "confidence":
                confidence,

            "trend_strength":
                trend_strength,

            "volatility_regime":
                volatility_regime,

            "volatility_percentile":
                round(
                    volatility_percentile,
                    2,
                ),

            "price":
                current_price,

            "ema20":
                current_ema20,

            "ema50":
                current_ema50,

            "sma50":
                current_sma50,

            "adx":
                current_adx,

            "atr":
                current_atr,

            "atr_percent":
                atr_percent,

            "ema20_distance_percent":
                ema20_distance,

            "ema50_distance_percent":
                ema50_distance,

            "bullish_score":
                bullish_score,

            "bearish_score":
                bearish_score,

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
                "REGIME DETECTION FAILED\n"
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
            "JARVIS MARKET REGIME"
        )

        lines.append(
            "--------------------------------------------------"
        )

        lines.append(
            f"Regime: "
            f"{result.get('regime')}"
        )

        lines.append(
            f"Bias: "
            f"{result.get('bias')}"
        )

        lines.append(
            f"Confidence: "
            f"{result.get('confidence')}%"
        )

        lines.append(
            f"Trend Strength: "
            f"{result.get('trend_strength')}"
        )

        lines.append(
            f"Volatility: "
            f"{result.get('volatility_regime')}"
        )

        lines.append(
            f"Volatility Percentile: "
            f"{result.get('volatility_percentile')}%"
        )

        lines.append("")

        lines.append(
            "INDICATORS"
        )

        lines.append(
            f"Price: "
            f"{result.get('price')}"
        )

        lines.append(
            f"EMA20: "
            f"{result.get('ema20')}"
        )

        lines.append(
            f"EMA50: "
            f"{result.get('ema50')}"
        )

        lines.append(
            f"SMA50: "
            f"{result.get('sma50')}"
        )

        lines.append(
            f"ADX: "
            f"{result.get('adx')}"
        )

        lines.append(
            f"ATR: "
            f"{result.get('atr')}"
        )

        lines.append(
            f"ATR %: "
            f"{result.get('atr_percent'):.2f}%"
        )

        return "\n".join(
            lines
        )


# ============================================================
# GLOBAL
# ============================================================

regime_detector = (
    MarketRegimeDetector()
)


# ============================================================
# SIMPLE FUNCTION
# ============================================================

def detect_regime(
    df: pd.DataFrame,
):

    return regime_detector.analyze(
        df
    )


# ============================================================
# TEST
# ============================================================

if __name__ == "__main__":

    import numpy as np

    print(
        "=" * 60
    )

    print(
        "JARVIS MARKET REGIME DETECTOR"
    )

    print(
        "=" * 60
    )

    np.random.seed(
        42
    )

    rows = 300

    prices = (
        100
        +
        np.cumsum(
            np.random.normal(
                0.05,
                1.0,
                rows,
            )
        )
    )

    data = pd.DataFrame({

        "open":
            prices
            + np.random.normal(
                0,
                0.4,
                rows,
            ),

        "high":
            prices
            + np.random.uniform(
                0.2,
                1.0,
                rows,
            ),

        "low":
            prices
            - np.random.uniform(
                0.2,
                1.0,
                rows,
            ),

        "close":
            prices,

        "volume":
            np.random.randint(
                10_000,
                100_000,
                rows,
            ),

    })

    result = detect_regime(
        data
    )

    print()

    print(
        regime_detector.format_result(
            result
        )
    )

    print()

    print(
        "Market Regime Detector loaded successfully."
    )