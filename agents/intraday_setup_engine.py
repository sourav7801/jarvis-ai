# ============================================================
# JARVIS INTRADAY SETUP ENGINE
# V3
# ============================================================
#
# 15m = CONTEXT
# 5m  = ENTRY TRIGGER
#
# The engine calculates its own indicators directly from the
# validated pandas DataFrame supplied by the intraday router.
#
# PAPER / RESEARCH ONLY.
# NO ORDER EXECUTION.
# ============================================================

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional
import math

import pandas as pd


# ============================================================
# CONFIG
# ============================================================

MIN_SETUP_SCORE = 70.0
MIN_RISK_REWARD = 1.5

MIN_BARS = 60
ATR_PERIOD = 14
RSI_PERIOD = 14

EMA_FAST = 20
EMA_SLOW = 50

BREAKOUT_LOOKBACK = 20


# ============================================================
# ENGINE
# ============================================================

class IntradaySetupEngine:

    def __init__(self) -> None:

        self.last_result: Optional[
            Dict[str, Any]
        ] = None

    # ========================================================
    # BASIC
    # ========================================================

    @staticmethod
    def now() -> str:

        return datetime.now().isoformat(
            timespec="seconds"
        )

    @staticmethod
    def number(
        value: Any,
        default: Optional[float] = None,
    ) -> Optional[float]:

        try:

            if value is None:

                return default

            result = float(
                value
            )

            if (
                math.isnan(result)
                or
                math.isinf(result)
            ):

                return default

            return result

        except Exception:

            return default

    # ========================================================
    # DATA NORMALIZATION
    # ========================================================

    @staticmethod
    def normalize_data(
        data: Any,
    ) -> Optional[pd.DataFrame]:

        if data is None:

            return None

        if isinstance(
            data,
            pd.DataFrame,
        ):

            df = data.copy()

        else:

            try:

                df = pd.DataFrame(
                    data
                )

            except Exception:

                return None

        if df.empty:

            return None

        # ----------------------------------------------------
        # Flatten MultiIndex columns if necessary.
        # ----------------------------------------------------

        if isinstance(
            df.columns,
            pd.MultiIndex,
        ):

            flattened = []

            for col in df.columns:

                parts = [
                    str(x)
                    for x in col
                    if str(x).lower() != "nan"
                ]

                flattened.append(
                    parts[0]
                    if parts
                    else ""
                )

            df.columns = flattened

        # ----------------------------------------------------
        # Normalize names.
        # ----------------------------------------------------

        mapping = {}

        for col in df.columns:

            key = (
                str(col)
                .strip()
                .lower()
            )

            if key == "open":

                mapping[col] = "Open"

            elif key == "high":

                mapping[col] = "High"

            elif key == "low":

                mapping[col] = "Low"

            elif key == "close":

                mapping[col] = "Close"

            elif key == "volume":

                mapping[col] = "Volume"

        df = df.rename(
            columns=mapping
        )

        required = [
            "Open",
            "High",
            "Low",
            "Close",
        ]

        if not all(
            col in df.columns
            for col in required
        ):

            return None

        # ----------------------------------------------------
        # Numeric conversion.
        # ----------------------------------------------------

        for col in required:

            df[col] = pd.to_numeric(
                df[col],
                errors="coerce",
            )

        df = df.dropna(
            subset=required
        )

        if df.empty:

            return None

        # ----------------------------------------------------
        # Sort chronologically when an index exists.
        # ----------------------------------------------------

        try:

            df = df.sort_index()

        except Exception:

            pass

        return df

    # ========================================================
    # VALIDATION
    # ========================================================

    def validate_dataframe(
        self,
        df: Optional[pd.DataFrame],
        timeframe: str,
    ) -> Dict[str, Any]:

        if df is None:

            return {

                "valid":
                    False,

                "timeframe":
                    timeframe,

                "bars":
                    0,

                "message":
                    (
                        f"{timeframe} dataframe "
                        "could not be normalized."
                    ),

            }

        required = [
            "Open",
            "High",
            "Low",
            "Close",
        ]

        missing = [
            col
            for col in required
            if col not in df.columns
        ]

        if missing:

            return {

                "valid":
                    False,

                "timeframe":
                    timeframe,

                "bars":
                    len(df),

                "message":
                    (
                        "Missing columns: "
                        +
                        ", ".join(
                            missing
                        )
                    ),

            }

        if len(df) < MIN_BARS:

            return {

                "valid":
                    False,

                "timeframe":
                    timeframe,

                "bars":
                    len(df),

                "message":
                    (
                        f"{timeframe} has "
                        f"{len(df)} usable bars; "
                        f"{MIN_BARS} required."
                    ),

            }

        for col in required:

            if (
                df[col]
                .isna()
                .any()
            ):

                return {

                    "valid":
                        False,

                    "timeframe":
                        timeframe,

                    "bars":
                        len(df),

                    "message":
                        (
                            f"{timeframe} {col} "
                            "contains NaN values."
                        ),

                }

        return {

            "valid":
                True,

            "timeframe":
                timeframe,

            "bars":
                len(df),

            "message":
                "Data validation passed.",

        }

    # ========================================================
    # SERIES HELPERS
    # ========================================================

    @staticmethod
    def last(
        series: pd.Series,
    ) -> Optional[float]:

        if series is None:

            return None

        if len(series) == 0:

            return None

        try:

            return float(
                series.iloc[-1]
            )

        except Exception:

            return None

    @staticmethod
    def previous(
        series: pd.Series,
    ) -> Optional[float]:

        if series is None:

            return None

        if len(series) < 2:

            return None

        try:

            return float(
                series.iloc[-2]
            )

        except Exception:

            return None

    # ========================================================
    # EMA
    # ========================================================

    def calculate_ema(
        self,
        df: pd.DataFrame,
        period: int,
    ) -> Dict[str, Any]:

        if len(df) < period:

            return {

                "valid":
                    False,

                "value":
                    None,

                "message":
                    (
                        f"Need {period} bars "
                        "for EMA."
                    ),

            }

        series = (
            df["Close"]
            .astype(float)
            .ewm(
                span=period,
                adjust=False,
                min_periods=period,
            )
            .mean()
        )

        value = self.last(
            series
        )

        return {

            "valid":
                value is not None,

            "value":
                value,

            "message":
                (
                    "EMA calculated."
                    if value is not None
                    else
                    "EMA calculation failed."
                ),

        }

    # ========================================================
    # ATR
    # ========================================================

    def calculate_atr(
        self,
        df: pd.DataFrame,
        period: int = ATR_PERIOD,
    ) -> Dict[str, Any]:

        if len(df) < period + 1:

            return {

                "valid":
                    False,

                "value":
                    None,

                "message":
                    (
                        f"Need at least "
                        f"{period + 1} bars "
                        "for ATR."
                    ),

            }

        high = (
            df["High"]
            .astype(float)
        )

        low = (
            df["Low"]
            .astype(float)
        )

        close = (
            df["Close"]
            .astype(float)
        )

        previous_close = (
            close.shift(1)
        )

        tr1 = (
            high
            -
            low
        )

        tr2 = (
            (high - previous_close)
            .abs()
        )

        tr3 = (
            (low - previous_close)
            .abs()
        )

        true_range = pd.concat(
            [
                tr1,
                tr2,
                tr3,
            ],
            axis=1,
        ).max(
            axis=1,
            skipna=True,
        )

        atr_series = (
            true_range
            .rolling(
                period,
                min_periods=period,
            )
            .mean()
        )

        value = self.last(
            atr_series
        )

        return {

            "valid":
                value is not None,

            "value":
                value,

            "message":
                (
                    "ATR calculated."
                    if value is not None
                    else
                    "ATR calculation failed."
                ),

        }

    # ========================================================
    # RSI
    # ========================================================

    def calculate_rsi(
        self,
        df: pd.DataFrame,
        period: int = RSI_PERIOD,
    ) -> Dict[str, Any]:

        if len(df) < period + 1:

            return {

                "valid":
                    False,

                "value":
                    None,

                "message":
                    (
                        f"Need at least "
                        f"{period + 1} bars "
                        "for RSI."
                    ),

            }

        close = (
            df["Close"]
            .astype(float)
        )

        delta = close.diff()

        gain = (
            delta.clip(
                lower=0
            )
        )

        loss = (
            -delta.clip(
                upper=0
            )
        )

        avg_gain = (
            gain
            .ewm(
                alpha=1 / period,
                adjust=False,
                min_periods=period,
            )
            .mean()
        )

        avg_loss = (
            loss
            .ewm(
                alpha=1 / period,
                adjust=False,
                min_periods=period,
            )
            .mean()
        )

        rs = (
            avg_gain
            /
            avg_loss.replace(
                0,
                float("nan"),
            )
        )

        rsi = (
            100
            -
            (
                100
                /
                (
                    1
                    +
                    rs
                )
            )
        )

        # ----------------------------------------------------
        # Handle zero-loss periods correctly.
        # ----------------------------------------------------

        rsi = rsi.where(
            avg_loss != 0,
            100.0,
        )

        value = self.last(
            rsi
        )

        return {

            "valid":
                value is not None,

            "value":
                value,

            "message":
                (
                    "RSI calculated."
                    if value is not None
                    else
                    "RSI calculation failed."
                ),

        }

    # ========================================================
    # MACD
    # ========================================================

    def calculate_macd(
        self,
        df: pd.DataFrame,
    ) -> Dict[str, Any]:

        if len(df) < 35:

            return {

                "valid":
                    False,

                "macd":
                    None,

                "signal":
                    None,

                "histogram":
                    None,

                "previous_histogram":
                    None,

                "message":
                    (
                        "Need at least "
                        "35 bars for MACD."
                    ),

            }

        close = (
            df["Close"]
            .astype(float)
        )

        ema12 = (
            close
            .ewm(
                span=12,
                adjust=False,
                min_periods=12,
            )
            .mean()
        )

        ema26 = (
            close
            .ewm(
                span=26,
                adjust=False,
                min_periods=26,
            )
            .mean()
        )

        macd_line = (
            ema12
            -
            ema26
        )

        signal_line = (
            macd_line
            .ewm(
                span=9,
                adjust=False,
                min_periods=9,
            )
            .mean()
        )

        histogram = (
            macd_line
            -
            signal_line
        )

        macd_value = self.last(
            macd_line
        )

        signal_value = self.last(
            signal_line
        )

        histogram_value = self.last(
            histogram
        )

        previous_histogram = self.previous(
            histogram
        )

        valid = all(
            value is not None
            for value in [
                macd_value,
                signal_value,
                histogram_value,
            ]
        )

        return {

            "valid":
                valid,

            "macd":
                macd_value,

            "signal":
                signal_value,

            "histogram":
                histogram_value,

            "previous_histogram":
                previous_histogram,

            "message":
                (
                    "MACD calculated."
                    if valid
                    else
                    "MACD calculation failed."
                ),

        }

    # ========================================================
    # INDICATOR SNAPSHOT
    # ========================================================

    def indicator_snapshot(
        self,
        df: pd.DataFrame,
        timeframe: str,
    ) -> Dict[str, Any]:

        ema20 = (
            self.calculate_ema(
                df,
                EMA_FAST,
            )
        )

        ema50 = (
            self.calculate_ema(
                df,
                EMA_SLOW,
            )
        )

        atr = (
            self.calculate_atr(
                df,
                ATR_PERIOD,
            )
        )

        rsi = (
            self.calculate_rsi(
                df,
                RSI_PERIOD,
            )
        )

        macd = (
            self.calculate_macd(
                df
            )
        )

        close = self.last(
            df["Close"]
        )

        all_valid = all(
            [
                ema20["valid"],
                ema50["valid"],
                atr["valid"],
                rsi["valid"],
                macd["valid"],
            ]
        )

        return {

            "valid":
                all_valid,

            "timeframe":
                timeframe,

            "bars":
                len(df),

            "price":
                close,

            "ema20":
                ema20["value"],

            "ema50":
                ema50["value"],

            "atr":
                atr["value"],

            "rsi":
                rsi["value"],

            "macd":
                macd["macd"],

            "macd_signal":
                macd["signal"],

            "macd_histogram":
                macd["histogram"],

            "macd_previous_histogram":
                macd["previous_histogram"],

            "components":
                {

                    "ema20":
                        ema20,

                    "ema50":
                        ema50,

                    "atr":
                        atr,

                    "rsi":
                        rsi,

                    "macd":
                        macd,

                },

        }

    # ========================================================
    # 15M CONTEXT
    # ========================================================

    def analyze_context(
        self,
        df: pd.DataFrame,
    ) -> Dict[str, Any]:

        indicators = (
            self.indicator_snapshot(
                df,
                "15m",
            )
        )

        if not indicators[
            "valid"
        ]:

            return {

                "success":
                    False,

                "timeframe":
                    "15m",

                "message":
                    (
                        "15m indicator calculation "
                        "failed."
                    ),

                "indicators":
                    indicators,

            }

        price = indicators[
            "price"
        ]

        ema20 = indicators[
            "ema20"
        ]

        ema50 = indicators[
            "ema50"
        ]

        rsi = indicators[
            "rsi"
        ]

        histogram = indicators[
            "macd_histogram"
        ]

        bullish = 0.0
        bearish = 0.0

        evidence = []

        # ----------------------------------------------------
        # Structure
        # ----------------------------------------------------

        if (
            price > ema20
            and
            ema20 > ema50
        ):

            bullish += 40

            evidence.append(
                "15m structure is bullish: price > EMA20 > EMA50."
            )

        elif (
            price < ema20
            and
            ema20 < ema50
        ):

            bearish += 40

            evidence.append(
                "15m structure is bearish: price < EMA20 < EMA50."
            )

        elif price > ema50:

            bullish += 20

            evidence.append(
                "15m price is above EMA50."
            )

        elif price < ema50:

            bearish += 20

            evidence.append(
                "15m price is below EMA50."
            )

        # ----------------------------------------------------
        # RSI
        # ----------------------------------------------------

        if rsi >= 55:

            bullish += 15

            evidence.append(
                f"15m RSI supports bullish momentum ({rsi:.2f})."
            )

        elif rsi <= 45:

            bearish += 15

            evidence.append(
                f"15m RSI supports bearish momentum ({rsi:.2f})."
            )

        # ----------------------------------------------------
        # MACD
        # ----------------------------------------------------

        if histogram > 0:

            bullish += 15

            evidence.append(
                "15m MACD histogram is positive."
            )

        elif histogram < 0:

            bearish += 15

            evidence.append(
                "15m MACD histogram is negative."
            )

        # ----------------------------------------------------
        # Direction
        # ----------------------------------------------------

        if (
            bullish >= 45
            and
            bullish > bearish
        ):

            direction = "BULLISH"

        elif (
            bearish >= 45
            and
            bearish > bullish
        ):

            direction = "BEARISH"

        else:

            direction = "NEUTRAL"

        return {

            "success":
                True,

            "direction":
                direction,

            "strength":
                max(
                    bullish,
                    bearish,
                ),

            "bullish_score":
                bullish,

            "bearish_score":
                bearish,

            "indicators":
                indicators,

            "evidence":
                evidence,

        }

    # ========================================================
    # 5M BREAKOUT
    # ========================================================

    def detect_breakout(
        self,
        df: pd.DataFrame,
    ) -> Dict[str, Any]:

        if len(df) < (
            BREAKOUT_LOOKBACK + 1
        ):

            return {

                "valid":
                    False,

                "direction":
                    "NONE",

                "strength":
                    0.0,

                "message":
                    "Insufficient 5m bars.",

            }

        current_close = self.last(
            df["Close"]
        )

        previous_close = self.previous(
            df["Close"]
        )

        previous_high = self.number(
            df["High"]
            .iloc[
                -(
                    BREAKOUT_LOOKBACK + 1
                ):
                -1
            ]
            .max()
        )

        previous_low = self.number(
            df["Low"]
            .iloc[
                -(
                    BREAKOUT_LOOKBACK + 1
                ):
                -1
            ]
            .min()
        )

        if any(
            value is None
            for value in [
                current_close,
                previous_close,
                previous_high,
                previous_low,
            ]
        ):

            return {

                "valid":
                    False,

                "direction":
                    "NONE",

                "strength":
                    0.0,

                "message":
                    "Breakout calculation failed.",

            }

        if (
            current_close > previous_high
            and
            previous_close <= previous_high
        ):

            return {

                "valid":
                    True,

                "direction":
                    "BULLISH",

                "strength":
                    85.0,

                "level":
                    previous_high,

                "message":
                    (
                        "5m breakout above the "
                        "20-bar high."
                    ),

            }

        if (
            current_close < previous_low
            and
            previous_close >= previous_low
        ):

            return {

                "valid":
                    True,

                "direction":
                    "BEARISH",

                "strength":
                    85.0,

                "level":
                    previous_low,

                "message":
                    (
                        "5m breakdown below the "
                        "20-bar low."
                    ),

            }

        return {

            "valid":
                False,

            "direction":
                "NONE",

            "strength":
                0.0,

            "level":
                None,

            "message":
                "No confirmed breakout.",

        }

    # ========================================================
    # 5M PULLBACK
    # ========================================================

    def detect_pullback(
        self,
        df: pd.DataFrame,
        context_direction: str,
    ) -> Dict[str, Any]:

        indicators = (
            self.indicator_snapshot(
                df,
                "5m",
            )
        )

        if not indicators[
            "valid"
        ]:

            return {

                "valid":
                    False,

                "direction":
                    "NONE",

                "strength":
                    0.0,

                "message":
                    (
                        "5m indicators unavailable "
                        "for pullback."
                    ),

            }

        price = indicators[
            "price"
        ]

        ema20 = indicators[
            "ema20"
        ]

        previous_close = self.previous(
            df["Close"]
        )

        if context_direction == "BULLISH":

            if (
                previous_close <= ema20
                and
                price > ema20
            ):

                return {

                    "valid":
                        True,

                    "direction":
                        "BULLISH",

                    "strength":
                        75.0,

                    "level":
                        ema20,

                    "message":
                        (
                            "5m pullback recovered "
                            "above EMA20."
                        ),

                }

        elif context_direction == "BEARISH":

            if (
                previous_close >= ema20
                and
                price < ema20
            ):

                return {

                    "valid":
                        True,

                    "direction":
                        "BEARISH",

                    "strength":
                        75.0,

                    "level":
                        ema20,

                    "message":
                        (
                            "5m pullback rejected "
                            "below EMA20."
                        ),

                }

        return {

            "valid":
                False,

            "direction":
                "NONE",

            "strength":
                0.0,

            "level":
                None,

            "message":
                "No confirmed 5m pullback.",

        }

    # ========================================================
    # 5M MOMENTUM
    # ========================================================

    def analyze_momentum(
        self,
        df: pd.DataFrame,
        direction: str,
    ) -> Dict[str, Any]:

        indicators = (
            self.indicator_snapshot(
                df,
                "5m",
            )
        )

        if not indicators[
            "valid"
        ]:

            return {

                "valid":
                    False,

                "score":
                    0.0,

                "message":
                    (
                        "5m indicator calculation "
                        "failed."
                    ),

                "indicators":
                    indicators,

            }

        rsi = indicators[
            "rsi"
        ]

        histogram = indicators[
            "macd_histogram"
        ]

        previous_histogram = indicators[
            "macd_previous_histogram"
        ]

        score = 0.0

        evidence = []

        if direction == "BULLISH":

            if (
                rsi >= 55
                and
                rsi < 75
            ):

                score += 40

                evidence.append(
                    f"5m RSI bullish ({rsi:.2f})."
                )

            if histogram > 0:

                score += 35

                evidence.append(
                    "5m MACD histogram positive."
                )

            if (
                previous_histogram is not None
                and
                histogram
                >
                previous_histogram
            ):

                score += 25

                evidence.append(
                    "5m MACD momentum improving."
                )

        elif direction == "BEARISH":

            if (
                rsi <= 45
                and
                rsi > 25
            ):

                score += 40

                evidence.append(
                    f"5m RSI bearish ({rsi:.2f})."
                )

            if histogram < 0:

                score += 35

                evidence.append(
                    "5m MACD histogram negative."
                )

            if (
                previous_histogram is not None
                and
                histogram
                <
                previous_histogram
            ):

                score += 25

                evidence.append(
                    "5m MACD momentum weakening."
                )

        return {

            "valid":
                True,

            "score":
                min(
                    100.0,
                    score,
                ),

            "rsi":
                rsi,

            "macd_histogram":
                histogram,

            "evidence":
                evidence,

            "indicators":
                indicators,

        }

    # ========================================================
    # CANDLE
    # ========================================================

    def candle_confirmation(
        self,
        df: pd.DataFrame,
        direction: str,
    ) -> Dict[str, Any]:

        open_price = self.last(
            df["Open"]
        )

        high = self.last(
            df["High"]
        )

        low = self.last(
            df["Low"]
        )

        close = self.last(
            df["Close"]
        )

        if any(
            value is None
            for value in [
                open_price,
                high,
                low,
                close,
            ]
        ):

            return {

                "valid":
                    False,

                "score":
                    0.0,

                "message":
                    (
                        "Current 5m candle "
                        "is unavailable."
                    ),

            }

        candle_range = (
            high
            -
            low
        )

        if candle_range <= 0:

            return {

                "valid":
                    False,

                "score":
                    0.0,

                "message":
                    "Current candle has zero range.",

            }

        body = abs(
            close
            -
            open_price
        )

        body_ratio = (
            body
            /
            candle_range
        )

        if (
            direction == "BULLISH"
            and
            close > open_price
            and
            body_ratio >= 0.55
        ):

            return {

                "valid":
                    True,

                "score":
                    100.0,

                "message":
                    (
                        "Strong bullish "
                        "confirmation candle."
                    ),

            }

        if (
            direction == "BEARISH"
            and
            close < open_price
            and
            body_ratio >= 0.55
        ):

            return {

                "valid":
                    True,

                "score":
                    100.0,

                "message":
                    (
                        "Strong bearish "
                        "confirmation candle."
                    ),

            }

        return {

            "valid":
                True,

            "score":
                40.0,

            "message":
                (
                    "Candle direction is not "
                    "strongly confirmed."
                ),

        }

    # ========================================================
    # VOLATILITY
    # ========================================================

    def analyze_volatility(
        self,
        df: pd.DataFrame,
    ) -> Dict[str, Any]:

        indicators = (
            self.indicator_snapshot(
                df,
                "5m",
            )
        )

        if not indicators[
            "valid"
        ]:

            return {

                "valid":
                    False,

                "state":
                    "UNKNOWN",

                "score":
                    0.0,

                "atr":
                    indicators.get(
                        "atr"
                    ),

                "atr_percent":
                    None,

                "message":
                    "5m volatility calculation failed.",

            }

        atr = indicators[
            "atr"
        ]

        price = indicators[
            "price"
        ]

        if (
            atr is None
            or
            price is None
            or
            price <= 0
        ):

            return {

                "valid":
                    False,

                "state":
                    "UNKNOWN",

                "score":
                    0.0,

                "atr":
                    atr,

                "atr_percent":
                    None,

                "message":
                    "ATR/price unavailable.",

            }

        atr_percent = (
            atr
            /
            price
            *
            100.0
        )

        if atr_percent < 0.10:

            state = "LOW"
            score = 55.0

        elif atr_percent < 0.35:

            state = "NORMAL"
            score = 90.0

        elif atr_percent < 0.70:

            state = "HIGH"
            score = 65.0

        else:

            state = "EXTREME"
            score = 20.0

        return {

            "valid":
                True,

            "state":
                state,

            "score":
                score,

            "atr":
                atr,

            "atr_percent":
                atr_percent,

            "message":
                (
                    f"5m volatility is {state}."
                ),

        }

    # ========================================================
    # RISK REWARD
    # ========================================================

    def build_risk_reward(
        self,
        df: pd.DataFrame,
        direction: str,
        trigger: Dict[str, Any],
    ) -> Dict[str, Any]:

        indicators = (
            self.indicator_snapshot(
                df,
                "5m",
            )
        )

        if not indicators[
            "valid"
        ]:

            return {

                "valid":
                    False,

                "entry":
                    None,

                "stop":
                    None,

                "target":
                    None,

                "risk":
                    None,

                "reward":
                    None,

                "risk_reward":
                    0.0,

                "message":
                    (
                        "5m indicators unavailable "
                        "for risk/reward."
                    ),

            }

        entry = indicators[
            "price"
        ]

        atr = indicators[
            "atr"
        ]

        level = self.number(
            trigger.get(
                "level"
            ),
            entry,
        )

        if (
            entry is None
            or
            atr is None
            or
            atr <= 0
        ):

            return {

                "valid":
                    False,

                "entry":
                    entry,

                "stop":
                    None,

                "target":
                    None,

                "risk":
                    None,

                "reward":
                    None,

                "risk_reward":
                    0.0,

                "message":
                    "Entry/ATR unavailable.",

            }

        stop_distance = (
            atr
            *
            1.20
        )

        if direction == "BULLISH":

            structural_stop = (
                level
                -
                atr
                *
                0.50
            )

            stop = min(
                entry
                -
                stop_distance,

                structural_stop,
            )

            risk = (
                entry
                -
                stop
            )

            target = (
                entry
                +
                risk
                *
                2.0
            )

        elif direction == "BEARISH":

            structural_stop = (
                level
                +
                atr
                *
                0.50
            )

            stop = max(
                entry
                +
                stop_distance,

                structural_stop,
            )

            risk = (
                stop
                -
                entry
            )

            target = (
                entry
                -
                risk
                *
                2.0
            )

        else:

            return {

                "valid":
                    False,

                "entry":
                    entry,

                "stop":
                    None,

                "target":
                    None,

                "risk":
                    None,

                "reward":
                    None,

                "risk_reward":
                    0.0,

                "message":
                    "No directional setup.",

            }

        if risk <= 0:

            return {

                "valid":
                    False,

                "entry":
                    entry,

                "stop":
                    stop,

                "target":
                    target,

                "risk":
                    risk,

                "reward":
                    0.0,

                "risk_reward":
                    0.0,

                "message":
                    "Calculated risk is invalid.",

            }

        reward = abs(
            target
            -
            entry
        )

        risk_reward = (
            reward
            /
            risk
        )

        return {

            "valid":
                risk_reward
                >=
                MIN_RISK_REWARD,

            "entry":
                entry,

            "stop":
                stop,

            "target":
                target,

            "risk":
                risk,

            "reward":
                reward,

            "risk_reward":
                risk_reward,

            "message":
                (
                    "Risk/reward passed."
                    if
                    risk_reward
                    >=
                    MIN_RISK_REWARD
                    else
                    "Risk/reward below minimum."
                ),

        }

    # ========================================================
    # MAIN ANALYSIS
    # ========================================================

    def analyze(
        self,
        data_15m: Any,
        data_5m: Any,
        symbol: str = "UNKNOWN",
        market: str = "INDIA",
    ) -> Dict[str, Any]:

        df15 = self.normalize_data(
            data_15m
        )

        df5 = self.normalize_data(
            data_5m
        )

        validation15 = (
            self.validate_dataframe(
                df15,
                "15m",
            )
        )

        validation5 = (
            self.validate_dataframe(
                df5,
                "5m",
            )
        )

        if not validation15[
            "valid"
        ]:

            return {

                "success":
                    False,

                "status":
                    "BLOCKED_DATA",

                "message":
                    validation15[
                        "message"
                    ],

                "validation":
                    {

                        "15m":
                            validation15,

                        "5m":
                            validation5,

                    },

            }

        if not validation5[
            "valid"
        ]:

            return {

                "success":
                    False,

                "status":
                    "BLOCKED_DATA",

                "message":
                    validation5[
                        "message"
                    ],

                "validation":
                    {

                        "15m":
                            validation15,

                        "5m":
                            validation5,

                    },

            }

        # ====================================================
        # INDICATOR SNAPSHOTS
        # ====================================================

        indicators15 = (
            self.indicator_snapshot(
                df15,
                "15m",
            )
        )

        indicators5 = (
            self.indicator_snapshot(
                df5,
                "5m",
            )
        )

        # ----------------------------------------------------
        # HARD indicator gate.
        # ----------------------------------------------------

        if not indicators15[
            "valid"
        ]:

            return {

                "success":
                    False,

                "status":
                    "BLOCKED_INDICATORS",

                "message":
                    (
                        "15m indicators could "
                        "not be calculated."
                    ),

                "indicators":
                    {

                        "15m":
                            indicators15,

                        "5m":
                            indicators5,

                    },

            }

        if not indicators5[
            "valid"
        ]:

            return {

                "success":
                    False,

                "status":
                    "BLOCKED_INDICATORS",

                "message":
                    (
                        "5m indicators could "
                        "not be calculated."
                    ),

                "indicators":
                    {

                        "15m":
                            indicators15,

                        "5m":
                            indicators5,

                    },

            }

        # ====================================================
        # 15M CONTEXT
        # ====================================================

        context = (
            self.analyze_context(
                df15
            )
        )

        if not context.get(
            "success"
        ):

            return {

                "success":
                    False,

                "status":
                    "BLOCKED_ANALYSIS",

                "message":
                    context.get(
                        "message"
                    ),

            }

        direction = context[
            "direction"
        ]

        # ====================================================
        # 5M TRIGGERS
        # ====================================================

        breakout = (
            self.detect_breakout(
                df5
            )
        )

        pullback = (
            self.detect_pullback(

                df5,

                direction,

            )
        )

        trigger = None

        if (
            breakout.get(
                "valid"
            )
            and
            breakout.get(
                "direction"
            )
            ==
            direction
        ):

            trigger = {

                "type":
                    "BREAKOUT",

                "direction":
                    direction,

                "strength":
                    breakout.get(
                        "strength"
                    ),

                "level":
                    breakout.get(
                        "level"
                    ),

                "message":
                    breakout.get(
                        "message"
                    ),

            }

        elif (
            pullback.get(
                "valid"
            )
            and
            pullback.get(
                "direction"
            )
            ==
            direction
        ):

            trigger = {

                "type":
                    "PULLBACK",

                "direction":
                    direction,

                "strength":
                    pullback.get(
                        "strength"
                    ),

                "level":
                    pullback.get(
                        "level"
                    ),

                "message":
                    pullback.get(
                        "message"
                    ),

            }

        # ====================================================
        # NO CONTEXT
        # ====================================================

        if direction not in {
            "BULLISH",
            "BEARISH",
        }:

            result = {

                "success":
                    True,

                "status":
                    "WAIT",

                "decision":
                    "WAIT",

                "direction":
                    "NEUTRAL",

                "symbol":
                    symbol,

                "market":
                    market,

                "setup_score":
                    0.0,

                "context":
                    context,

                "trigger":
                    None,

                "indicators":
                    {

                        "15m":
                            indicators15,

                        "5m":
                            indicators5,

                    },

                "reason":
                    (
                        "15m context is not "
                        "directional."
                    ),

                "timestamp":
                    self.now(),

            }

            self.last_result = result

            return result

        # ====================================================
        # NO TRIGGER
        # ====================================================

        if trigger is None:

            result = {

                "success":
                    True,

                "status":
                    "WAIT",

                "decision":
                    "WAIT",

                "direction":
                    direction,

                "symbol":
                    symbol,

                "market":
                    market,

                "setup_score":
                    0.0,

                "context":
                    context,

                "breakout":
                    breakout,

                "pullback":
                    pullback,

                "trigger":
                    None,

                "indicators":
                    {

                        "15m":
                            indicators15,

                        "5m":
                            indicators5,

                    },

                "reason":
                    (
                        "Directional 15m context "
                        "exists, but 5m has no "
                        "matching trigger."
                    ),

                "timestamp":
                    self.now(),

            }

            self.last_result = result

            return result

        # ====================================================
        # 5M QUALITY
        # ====================================================

        momentum = (
            self.analyze_momentum(

                df5,

                direction,

            )
        )

        candle = (
            self.candle_confirmation(

                df5,

                direction,

            )
        )

        volatility = (
            self.analyze_volatility(
                df5
            )
        )

        risk_reward = (
            self.build_risk_reward(

                df5,

                direction,

                trigger,

            )
        )

        # ====================================================
        # SCORE
        # ====================================================

        context_score = float(
            context.get(
                "strength",
                0.0,
            )
            or
            0.0
        )

        trigger_score = float(
            trigger.get(
                "strength",
                0.0,
            )
            or
            0.0
        )

        momentum_score = float(
            momentum.get(
                "score",
                0.0,
            )
            or
            0.0
        )

        candle_score = float(
            candle.get(
                "score",
                0.0,
            )
            or
            0.0
        )

        volatility_score = float(
            volatility.get(
                "score",
                0.0,
            )
            or
            0.0
        )

        rr_value = float(
            risk_reward.get(
                "risk_reward",
                0.0,
            )
            or
            0.0
        )

        rr_score = min(
            100.0,
            (
                rr_value
                /
                2.0
                *
                100.0
            ),
        )

        quality_score = (
            momentum_score
            +
            candle_score
            +
            volatility_score
            +
            rr_score
        ) / 4.0

        setup_score = (

            context_score
            *
            0.40

            +

            trigger_score
            *
            0.30

            +

            quality_score
            *
            0.30

        )

        # ----------------------------------------------------
        # Hard penalties.
        # ----------------------------------------------------

        if momentum_score < 40:

            setup_score -= 10

        if candle_score < 40:

            setup_score -= 5

        if (
            not volatility.get(
                "valid"
            )
        ):

            setup_score -= 15

        if (
            volatility.get(
                "state"
            )
            ==
            "EXTREME"
        ):

            setup_score -= 15

        if (
            not risk_reward.get(
                "valid"
            )
        ):

            setup_score -= 20

        setup_score = max(
            0.0,
            min(
                100.0,
                setup_score,
            ),
        )

        # ====================================================
        # DECISION
        # ====================================================

        decision = "WAIT"
        status = "WAIT"

        if (
            setup_score
            >=
            MIN_SETUP_SCORE

            and

            risk_reward.get(
                "valid"
            )

            and

            volatility.get(
                "state"
            )
            !=
            "EXTREME"

        ):

            decision = (
                "LONG"
                if
                direction
                ==
                "BULLISH"
                else
                "SHORT"
            )

            status = "CANDIDATE"

        # ====================================================
        # EVIDENCE
        # ====================================================

        evidence = []

        evidence.extend(
            context.get(
                "evidence",
                []
            )
        )

        if trigger.get(
            "message"
        ):

            evidence.append(
                trigger[
                    "message"
                ]
            )

        evidence.extend(
            momentum.get(
                "evidence",
                []
            )
        )

        evidence.append(
            candle.get(
                "message",
                "",
            )
        )

        evidence.append(
            volatility.get(
                "message",
                "",
            )
        )

        evidence.append(
            risk_reward.get(
                "message",
                "",
            )
        )

        result = {

            "success":
                True,

            "status":
                status,

            "decision":
                decision,

            "direction":
                direction,

            "symbol":
                symbol,

            "market":
                market,

            "setup_score":
                setup_score,

            "indicators":
                {

                    "15m":
                        indicators15,

                    "5m":
                        indicators5,

                },

            "context":
                context,

            "breakout":
                breakout,

            "pullback":
                pullback,

            "trigger":
                trigger,

            "momentum":
                momentum,

            "candle":
                candle,

            "volatility":
                volatility,

            "risk_reward_plan":
                risk_reward,

            "risk_reward":
                rr_value,

            "entry":
                risk_reward.get(
                    "entry"
                ),

            "stop_loss":
                risk_reward.get(
                    "stop"
                ),

            "target":
                risk_reward.get(
                    "target"
                ),

            "evidence":
                evidence,

            "timestamp":
                self.now(),

        }

        self.last_result = result

        return result

    # ========================================================
    # FORMAT
    # ========================================================

    def format_result(
        self,
        result: Dict[str, Any],
    ) -> str:

        lines = []

        lines.append(
            "JARVIS INTRADAY SETUP ENGINE V3"
        )

        lines.append(
            "--------------------------------------------------"
        )

        lines.append(
            f"Symbol: "
            f"{result.get('symbol')}"
        )

        lines.append(
            f"Decision: "
            f"{result.get('decision')}"
        )

        lines.append(
            f"Direction: "
            f"{result.get('direction')}"
        )

        lines.append(
            f"Status: "
            f"{result.get('status')}"
        )

        lines.append(
            f"Setup Score: "
            f"{float(result.get('setup_score', 0.0) or 0.0):.1f}/100"
        )

        lines.append("")

        indicators = result.get(
            "indicators",
            {}
        )

        ind15 = indicators.get(
            "15m",
            {}
        )

        ind5 = indicators.get(
            "5m",
            {}
        )

        lines.append(
            "15M INDICATORS"
        )

        lines.append(
            f"Price: "
            f"{float(ind15.get('price', 0.0) or 0.0):.2f}"
        )

        lines.append(
            f"EMA20: "
            f"{float(ind15.get('ema20', 0.0) or 0.0):.2f}"
        )

        lines.append(
            f"EMA50: "
            f"{float(ind15.get('ema50', 0.0) or 0.0):.2f}"
        )

        lines.append(
            f"RSI: "
            f"{float(ind15.get('rsi', 0.0) or 0.0):.2f}"
        )

        lines.append(
            f"ATR: "
            f"{float(ind15.get('atr', 0.0) or 0.0):.2f}"
        )

        lines.append("")

        lines.append(
            "5M INDICATORS"
        )

        lines.append(
            f"Price: "
            f"{float(ind5.get('price', 0.0) or 0.0):.2f}"
        )

        lines.append(
            f"EMA20: "
            f"{float(ind5.get('ema20', 0.0) or 0.0):.2f}"
        )

        lines.append(
            f"EMA50: "
            f"{float(ind5.get('ema50', 0.0) or 0.0):.2f}"
        )

        lines.append(
            f"RSI: "
            f"{float(ind5.get('rsi', 0.0) or 0.0):.2f}"
        )

        lines.append(
            f"ATR: "
            f"{float(ind5.get('atr', 0.0) or 0.0):.2f}"
        )

        lines.append(
            f"MACD Histogram: "
            f"{float(ind5.get('macd_histogram', 0.0) or 0.0):.4f}"
        )

        lines.append("")

        context = result.get(
            "context",
            {}
        )

        lines.append(
            "15M CONTEXT"
        )

        lines.append(
            f"Direction: "
            f"{context.get('direction')}"
        )

        lines.append(
            f"Strength: "
            f"{float(context.get('strength', 0.0) or 0.0):.1f}/100"
        )

        lines.append("")

        trigger = result.get(
            "trigger"
        )

        lines.append(
            "5M TRIGGER"
        )

        if trigger:

            lines.append(
                f"Type: "
                f"{trigger.get('type')}"
            )

            lines.append(
                f"Direction: "
                f"{trigger.get('direction')}"
            )

            lines.append(
                f"Strength: "
                f"{float(trigger.get('strength', 0.0) or 0.0):.1f}/100"
            )

            lines.append(
                f"Message: "
                f"{trigger.get('message')}"
            )

        else:

            lines.append(
                "Type: NONE"
            )

        lines.append("")

        momentum = result.get(
            "momentum",
            {}
        )

        lines.append(
            "5M MOMENTUM"
        )

        lines.append(
            f"Score: "
            f"{float(momentum.get('score', 0.0) or 0.0):.1f}/100"
        )

        lines.append(
            f"RSI: "
            f"{float(ind5.get('rsi', 0.0) or 0.0):.2f}"
        )

        lines.append("")

        volatility = result.get(
            "volatility",
            {}
        )

        lines.append(
            "VOLATILITY"
        )

        lines.append(
            f"State: "
            f"{volatility.get('state')}"
        )

        lines.append(
            f"ATR: "
            f"{float(volatility.get('atr', 0.0) or 0.0):.2f}"
        )

        lines.append(
            f"ATR %: "
            f"{float(volatility.get('atr_percent', 0.0) or 0.0):.3f}%"
        )

        lines.append("")

        rr = result.get(
            "risk_reward_plan",
            {}
        )

        lines.append(
            "TRADE PLAN"
        )

        lines.append(
            f"Entry: "
            f"{float(rr.get('entry', 0.0) or 0.0):.2f}"
        )

        lines.append(
            f"Stop: "
            f"{float(rr.get('stop', 0.0) or 0.0):.2f}"
        )

        lines.append(
            f"Target: "
            f"{float(rr.get('target', 0.0) or 0.0):.2f}"
        )

        lines.append(
            f"Risk/Reward: "
            f"{float(rr.get('risk_reward', 0.0) or 0.0):.2f}"
        )

        lines.append("")

        lines.append(
            "EVIDENCE"
        )

        for item in result.get(
            "evidence",
            []
        ):

            if item:

                lines.append(
                    f"- {item}"
                )

        lines.append("")

        lines.append(
            "PAPER/RESEARCH ONLY — "
            "NO OPTION ORDER."
        )

        return "\n".join(
            lines
        )


# ============================================================
# GLOBAL
# ============================================================

intraday_setup_engine = (
    IntradaySetupEngine()
)


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":

    print(
        "=" * 60
    )

    print(
        "JARVIS INTRADAY SETUP ENGINE V3"
    )

    print(
        "=" * 60
    )

    try:

        from agents.intraday_data_router import (
            intraday_data_router,
        )

    except Exception as exc:

        print(
            f"Router import failed: {exc}"
        )

        raise SystemExit(1)

    for symbol in (
        "NIFTY",
        "BANKNIFTY",
    ):

        print()
        print(
            "=" * 60
        )
        print(
            f"TEST: {symbol}"
        )
        print(
            "=" * 60
        )

        dataset = (
            intraday_data_router
            .get_required_timeframes(

                symbol=
                    symbol,

                market=
                    "india",

                bars=
                    500,

            )
        )

        if not dataset.get(
            "success"
        ):

            print(
                "DATA BLOCKED"
            )

            print(
                dataset
            )

            continue

        timeframe_map = (
            dataset[
                "timeframes"
            ]
        )

        data5 = (
            timeframe_map[
                "5m"
            ][
                "data"
            ]
        )

        data15 = (
            timeframe_map[
                "15m"
            ][
                "data"
            ]
        )

        result = (
            intraday_setup_engine
            .analyze(

                data_15m=
                    data15,

                data_5m=
                    data5,

                symbol=
                    symbol,

                market=
                    "INDIA",

            )
        )

        print()

        print(
            intraday_setup_engine
            .format_result(
                result
            )
        )

        print()

        print(
            "INDICATOR HEALTH"
        )

        print(
            result.get(
                "indicators",
                {}
            )
        )

    print()

    print(
        "Intraday Setup Engine V3 "
        "loaded successfully."
    )