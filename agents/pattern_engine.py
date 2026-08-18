# ============================================================
# JARVIS PATTERN ENGINE
# V1
# ============================================================

from __future__ import annotations

from typing import Any, Dict, List

import pandas as pd


class PatternEngine:

    def __init__(
        self,
        swing_window: int = 3,
        breakout_lookback: int = 20,
        tolerance: float = 0.01,
    ):

        self.swing_window = swing_window
        self.breakout_lookback = breakout_lookback
        self.tolerance = tolerance

    # ========================================================
    # NORMALIZE DATA
    # ========================================================

    def _prepare(
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

        else:

            data["volume"] = pd.to_numeric(
                data["volume"],
                errors="coerce",
            ).fillna(0.0)

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
    # CANDLE FEATURES
    # ========================================================

    def _candle_features(
        self,
        row,
    ) -> Dict[str, float]:

        open_price = float(
            row["open"]
        )

        high = float(
            row["high"]
        )

        low = float(
            row["low"]
        )

        close = float(
            row["close"]
        )

        body = abs(
            close - open_price
        )

        total_range = max(
            high - low,
            1e-12,
        )

        upper_wick = (
            high
            - max(
                open_price,
                close,
            )
        )

        lower_wick = (
            min(
                open_price,
                close,
            )
            - low
        )

        return {

            "body": body,

            "range": total_range,

            "upper_wick": upper_wick,

            "lower_wick": lower_wick,

            "body_ratio":
                body / total_range,

            "upper_ratio":
                upper_wick / total_range,

            "lower_ratio":
                lower_wick / total_range,

        }

    # ========================================================
    # CANDLE PATTERNS
    # ========================================================

    def candlestick_patterns(
        self,
        data: pd.DataFrame,
    ) -> List[Dict[str, Any]]:

        patterns = []

        if len(data) < 3:
            return patterns

        for index in range(
            1,
            len(data),
        ):

            previous = data.iloc[
                index - 1
            ]

            current = data.iloc[
                index
            ]

            prev_features = (
                self._candle_features(
                    previous
                )
            )

            features = (
                self._candle_features(
                    current
                )
            )

            current_open = float(
                current["open"]
            )

            current_close = float(
                current["close"]
            )

            previous_open = float(
                previous["open"]
            )

            previous_close = float(
                previous["close"]
            )

            # ------------------------------------------------
            # Bullish engulfing
            # ------------------------------------------------

            previous_bearish = (
                previous_close
                < previous_open
            )

            current_bullish = (
                current_close
                > current_open
            )

            bullish_engulfing = (

                previous_bearish

                and current_bullish

                and current_open
                <= previous_close

                and current_close
                >= previous_open

            )

            if bullish_engulfing:

                patterns.append({

                    "index":
                        index,

                    "pattern":
                        "BULLISH_ENGULFING",

                    "direction":
                        "BULLISH",

                    "strength":
                        2,

                })

            # ------------------------------------------------
            # Bearish engulfing
            # ------------------------------------------------

            previous_bullish = (
                previous_close
                > previous_open
            )

            current_bearish = (
                current_close
                < current_open
            )

            bearish_engulfing = (

                previous_bullish

                and current_bearish

                and current_open
                >= previous_close

                and current_close
                <= previous_open

            )

            if bearish_engulfing:

                patterns.append({

                    "index":
                        index,

                    "pattern":
                        "BEARISH_ENGULFING",

                    "direction":
                        "BEARISH",

                    "strength":
                        2,

                })

            # ------------------------------------------------
            # Hammer
            # ------------------------------------------------

            hammer = (

                features["lower_ratio"]
                >= 0.5

                and features["upper_ratio"]
                <= 0.2

                and features["body_ratio"]
                <= 0.4

            )

            if hammer:

                patterns.append({

                    "index":
                        index,

                    "pattern":
                        "HAMMER",

                    "direction":
                        "BULLISH",

                    "strength":
                        1,

                })

            # ------------------------------------------------
            # Shooting star
            # ------------------------------------------------

            shooting_star = (

                features["upper_ratio"]
                >= 0.5

                and features["lower_ratio"]
                <= 0.2

                and features["body_ratio"]
                <= 0.4

            )

            if shooting_star:

                patterns.append({

                    "index":
                        index,

                    "pattern":
                        "SHOOTING_STAR",

                    "direction":
                        "BEARISH",

                    "strength":
                        1,

                })

            # ------------------------------------------------
            # Inside bar
            # ------------------------------------------------

            inside_bar = (

                float(current["high"])
                <= float(previous["high"])

                and

                float(current["low"])
                >= float(previous["low"])

            )

            if inside_bar:

                patterns.append({

                    "index":
                        index,

                    "pattern":
                        "INSIDE_BAR",

                    "direction":
                        "NEUTRAL",

                    "strength":
                        1,

                })

            # ------------------------------------------------
            # Range expansion
            # ------------------------------------------------

            if index >= 5:

                previous_ranges = (

                    data.iloc[
                        index - 5:index
                    ]["high"]

                    -
                    data.iloc[
                        index - 5:index
                    ]["low"]

                )

                average_range = (
                    previous_ranges.mean()
                )

                current_range = features[
                    "range"
                ]

                if (
                    average_range > 0
                    and
                    current_range
                    >= average_range * 1.5
                ):

                    direction = (
                        "BULLISH"
                        if current_bullish
                        else
                        "BEARISH"
                        if current_bearish
                        else
                        "NEUTRAL"
                    )

                    patterns.append({

                        "index":
                            index,

                        "pattern":
                            "RANGE_EXPANSION",

                        "direction":
                            direction,

                        "strength":
                            1,

                    })

        return patterns

    # ========================================================
    # SWING POINTS
    # ========================================================

    def swing_points(
        self,
        data: pd.DataFrame,
    ) -> Dict[str, List[int]]:

        highs = []
        lows = []

        window = self.swing_window

        if len(data) < (
            window * 2 + 1
        ):

            return {
                "highs": highs,
                "lows": lows,
            }

        for index in range(
            window,
            len(data) - window,
        ):

            current_high = float(
                data.iloc[index]["high"]
            )

            current_low = float(
                data.iloc[index]["low"]
            )

            left_highs = data.iloc[
                index - window:index
            ]["high"]

            right_highs = data.iloc[
                index + 1:index + 1 + window
            ]["high"]

            left_lows = data.iloc[
                index - window:index
            ]["low"]

            right_lows = data.iloc[
                index + 1:index + 1 + window
            ]["low"]

            if (
                current_high
                >= left_highs.max()
                and
                current_high
                >= right_highs.max()
            ):

                highs.append(
                    index
                )

            if (
                current_low
                <= left_lows.min()
                and
                current_low
                <= right_lows.min()
            ):

                lows.append(
                    index
                )

        return {

            "highs":
                highs,

            "lows":
                lows,

        }

    # ========================================================
    # MARKET STRUCTURE
    # ========================================================

    def market_structure(
        self,
        data: pd.DataFrame,
    ) -> Dict[str, Any]:

        swings = self.swing_points(
            data
        )

        high_indices = swings[
            "highs"
        ]

        low_indices = swings[
            "lows"
        ]

        higher_highs = []
        lower_highs = []

        higher_lows = []
        lower_lows = []

        for current, previous in zip(
            high_indices[1:],
            high_indices[:-1],
        ):

            current_value = float(
                data.iloc[current]["high"]
            )

            previous_value = float(
                data.iloc[previous]["high"]
            )

            if current_value > previous_value:

                higher_highs.append(
                    current
                )

            elif current_value < previous_value:

                lower_highs.append(
                    current
                )

        for current, previous in zip(
            low_indices[1:],
            low_indices[:-1],
        ):

            current_value = float(
                data.iloc[current]["low"]
            )

            previous_value = float(
                data.iloc[previous]["low"]
            )

            if current_value > previous_value:

                higher_lows.append(
                    current
                )

            elif current_value < previous_value:

                lower_lows.append(
                    current
                )

        bullish_structure = (
            len(higher_highs) > 0
            and
            len(higher_lows) > 0
        )

        bearish_structure = (
            len(lower_highs) > 0
            and
            len(lower_lows) > 0
        )

        if bullish_structure and not bearish_structure:

            bias = "BULLISH"

        elif bearish_structure and not bullish_structure:

            bias = "BEARISH"

        else:

            bias = "NEUTRAL"

        return {

            "bias":
                bias,

            "swing_highs":
                high_indices,

            "swing_lows":
                low_indices,

            "higher_highs":
                higher_highs,

            "lower_highs":
                lower_highs,

            "higher_lows":
                higher_lows,

            "lower_lows":
                lower_lows,

        }

    # ========================================================
    # SUPPORT / RESISTANCE
    # ========================================================

    def support_resistance(
        self,
        data: pd.DataFrame,
    ) -> Dict[str, List[float]]:

        swings = self.swing_points(
            data
        )

        support = []

        resistance = []

        for index in swings[
            "lows"
        ]:

            support.append(
                float(
                    data.iloc[index]["low"]
                )
            )

        for index in swings[
            "highs"
        ]:

            resistance.append(
                float(
                    data.iloc[index]["high"]
                )
            )

        def cluster_levels(
            levels,
        ):

            if not levels:
                return []

            sorted_levels = sorted(
                levels
            )

            clusters = []

            for level in sorted_levels:

                if not clusters:

                    clusters.append(
                        [level]
                    )

                    continue

                previous = clusters[
                    -1
                ][-1]

                distance = (
                    abs(
                        level
                        - previous
                    )
                    / max(
                        abs(previous),
                        1e-12,
                    )
                )

                if (
                    distance
                    <= self.tolerance
                ):

                    clusters[
                        -1
                    ].append(
                        level
                    )

                else:

                    clusters.append(
                        [level]
                    )

            return [
                round(
                    sum(cluster)
                    / len(cluster),
                    4,
                )
                for cluster
                in clusters
            ]

        return {

            "support":
                cluster_levels(
                    support
                ),

            "resistance":
                cluster_levels(
                    resistance
                ),

        }

    # ========================================================
    # BREAKOUT
    # ========================================================

    def breakout_analysis(
        self,
        data: pd.DataFrame,
    ) -> Dict[str, Any]:

        if len(data) <= self.breakout_lookback:

            return {
                "signal":
                    "NONE"
            }

        latest = data.iloc[
            -1
        ]

        previous = data.iloc[
            -self.breakout_lookback:-1
        ]

        resistance = float(
            previous["high"].max()
        )

        support = float(
            previous["low"].min()
        )

        close = float(
            latest["close"]
        )

        signal = "NONE"

        if close > resistance:

            signal = "BULLISH_BREAKOUT"

        elif close < support:

            signal = "BEARISH_BREAKDOWN"

        return {

            "signal":
                signal,

            "close":
                close,

            "resistance":
                resistance,

            "support":
                support,

        }

    # ========================================================
    # DOUBLE TOP / DOUBLE BOTTOM
    # ========================================================

    def double_patterns(
        self,
        data: pd.DataFrame,
    ) -> List[Dict[str, Any]]:

        swings = self.swing_points(
            data
        )

        patterns = []

        highs = swings[
            "highs"
        ]

        lows = swings[
            "lows"
        ]

        # ----------------------------------------------------
        # Double top
        # ----------------------------------------------------

        if len(highs) >= 2:

            first = highs[-2]
            second = highs[-1]

            first_price = float(
                data.iloc[first]["high"]
            )

            second_price = float(
                data.iloc[second]["high"]
            )

            difference = (
                abs(
                    first_price
                    - second_price
                )
                / max(
                    abs(first_price),
                    1e-12,
                )
            )

            if (
                difference
                <= self.tolerance
            ):

                patterns.append({

                    "pattern":
                        "DOUBLE_TOP",

                    "direction":
                        "BEARISH",

                    "first_index":
                        first,

                    "second_index":
                        second,

                    "price_1":
                        first_price,

                    "price_2":
                        second_price,

                })

        # ----------------------------------------------------
        # Double bottom
        # ----------------------------------------------------

        if len(lows) >= 2:

            first = lows[-2]
            second = lows[-1]

            first_price = float(
                data.iloc[first]["low"]
            )

            second_price = float(
                data.iloc[second]["low"]
            )

            difference = (
                abs(
                    first_price
                    - second_price
                )
                / max(
                    abs(first_price),
                    1e-12,
                )
            )

            if (
                difference
                <= self.tolerance
            ):

                patterns.append({

                    "pattern":
                        "DOUBLE_BOTTOM",

                    "direction":
                        "BULLISH",

                    "first_index":
                        first,

                    "second_index":
                        second,

                    "price_1":
                        first_price,

                    "price_2":
                        second_price,

                })

        return patterns

    # ========================================================
    # FULL ANALYSIS
    # ========================================================

    def analyze(
        self,
        df: pd.DataFrame,
    ) -> Dict[str, Any]:

        data = self._prepare(
            df
        )

        if data.empty:

            return {

                "success":
                    False,

                "message":
                    (
                        "No valid OHLCV data "
                        "was supplied."
                    ),

            }

        candle_patterns = (
            self.candlestick_patterns(
                data
            )
        )

        structure = (
            self.market_structure(
                data
            )
        )

        levels = (
            self.support_resistance(
                data
            )
        )

        breakout = (
            self.breakout_analysis(
                data
            )
        )

        doubles = (
            self.double_patterns(
                data
            )
        )

        recent_patterns = (
            candle_patterns[-10:]
        )

        all_patterns = (
            recent_patterns
            + doubles
        )

        latest = data.iloc[
            -1
        ]

        return {

            "success":
                True,

            "bars":
                len(data),

            "latest_price":
                float(
                    latest["close"]
                ),

            "market_structure":
                structure,

            "support_resistance":
                levels,

            "breakout":
                breakout,

            "candlestick_patterns":
                recent_patterns,

            "chart_patterns":
                all_patterns,

            "bias":
                structure.get(
                    "bias",
                    "NEUTRAL",
                ),

            "data":
                data,

        }


# ============================================================
# GLOBAL ENGINE
# ============================================================

pattern_engine = PatternEngine()


# ============================================================
# SIMPLE FUNCTION
# ============================================================

def analyze_patterns(
    df: pd.DataFrame,
):

    return pattern_engine.analyze(
        df
    )


# ============================================================
# TEST
# ============================================================

if __name__ == "__main__":

    print(
        "=" * 60
    )

    print(
        "JARVIS PATTERN ENGINE"
    )

    print(
        "=" * 60
    )

    print()

    import numpy as np

    np.random.seed(
        42
    )

    rows = 250

    prices = (
        100
        +
        np.cumsum(
            np.random.normal(
                0,
                1,
                rows,
            )
        )
    )

    data = pd.DataFrame({

        "open":
            prices
            + np.random.normal(
                0,
                0.5,
                rows,
            ),

        "high":
            prices
            + np.random.uniform(
                0.2,
                1.5,
                rows,
            ),

        "low":
            prices
            - np.random.uniform(
                0.2,
                1.5,
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

    result = analyze_patterns(
        data
    )

    print(
        "Success:",
        result.get(
            "success"
        ),
    )

    print(
        "Bias:",
        result.get(
            "bias"
        ),
    )

    print(
        "Latest price:",
        result.get(
            "latest_price"
        ),
    )

    print(
        "Breakout:",
        result.get(
            "breakout"
        ),
    )

    print(
        "Recent patterns:",
        result.get(
            "candlestick_patterns"
        ),
    )