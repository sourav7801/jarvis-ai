# ============================================================
# JARVIS TECHNICAL ENGINE
# ============================================================

import pandas as pd
import ta


class TechnicalEngine:

    def analyze(
        self,
        df: pd.DataFrame,
    ) -> dict:

        if df is None or df.empty:

            return {
                "success": False,
                "message": "No market data supplied.",
            }

        required = {
            "open",
            "high",
            "low",
            "close",
            "volume",
        }

        missing = (
            required
            - set(
                column.lower()
                for column in df.columns
            )
        )

        if missing:

            return {
                "success": False,
                "message": (
                    "Missing required columns: "
                    + ", ".join(
                        sorted(missing)
                    )
                ),
            }

        data = df.copy()

        data.columns = [
            str(column).lower()
            for column in data.columns
        ]

        close = pd.to_numeric(
            data["close"],
            errors="coerce",
        )

        high = pd.to_numeric(
            data["high"],
            errors="coerce",
        )

        low = pd.to_numeric(
            data["low"],
            errors="coerce",
        )

        volume = pd.to_numeric(
            data["volume"],
            errors="coerce",
        )

        data["sma20"] = close.rolling(20).mean()

        data["sma50"] = close.rolling(50).mean()

        data["sma200"] = close.rolling(200).mean()

        data["ema20"] = close.ewm(
            span=20,
            adjust=False,
        ).mean()

        data["ema50"] = close.ewm(
            span=50,
            adjust=False,
        ).mean()

        data["rsi"] = ta.momentum.RSIIndicator(
            close=close,
            window=14,
        ).rsi()

        macd = ta.trend.MACD(
            close=close,
        )

        data["macd"] = macd.macd()

        data["macd_signal"] = (
            macd.macd_signal()
        )

        data["adx"] = ta.trend.ADXIndicator(
            high=high,
            low=low,
            close=close,
            window=14,
        ).adx()

        data["atr"] = ta.volatility.AverageTrueRange(
            high=high,
            low=low,
            close=close,
            window=14,
        ).average_true_range()

        bollinger = (
            ta.volatility.BollingerBands(
                close=close,
                window=20,
            )
        )

        data["bb_high"] = (
            bollinger.bollinger_hband()
        )

        data["bb_low"] = (
            bollinger.bollinger_lband()
        )

        latest = data.iloc[-1]

        trend_score = 0

        if latest["close"] > latest["ema20"]:
            trend_score += 1

        if latest["ema20"] > latest["ema50"]:
            trend_score += 1

        if pd.notna(
            latest["sma200"]
        ):

            if latest["close"] > latest["sma200"]:
                trend_score += 1

        momentum_score = 0

        if (
            pd.notna(latest["rsi"])
            and
            latest["rsi"] > 50
        ):

            momentum_score += 1

        if (
            pd.notna(latest["macd"])
            and
            pd.notna(latest["macd_signal"])
            and
            latest["macd"]
            > latest["macd_signal"]
        ):

            momentum_score += 1

        trend = "NEUTRAL"

        if trend_score >= 2:
            trend = "BULLISH"

        elif trend_score <= 0:
            trend = "BEARISH"

        momentum = "NEUTRAL"

        if momentum_score >= 2:
            momentum = "STRONG"

        elif momentum_score == 0:
            momentum = "WEAK"

        return {

            "success": True,

            "trend": trend,

            "momentum": momentum,

            "trend_score": trend_score,

            "momentum_score": momentum_score,

            "price": float(
                latest["close"]
            ),

            "rsi": (
                float(latest["rsi"])
                if pd.notna(
                    latest["rsi"]
                )
                else None
            ),

            "macd": (
                float(latest["macd"])
                if pd.notna(
                    latest["macd"]
                )
                else None
            ),

            "adx": (
                float(latest["adx"])
                if pd.notna(
                    latest["adx"]
                )
                else None
            ),

            "atr": (
                float(latest["atr"])
                if pd.notna(
                    latest["atr"]
                )
                else None
            ),

            "data": data,

        }


technical_engine = TechnicalEngine()