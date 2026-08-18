from __future__ import annotations

from omni.trading_intelligence.feature_engine import (
    feature_engine,
)


class MarketRegimeEngine:

    def classify(
        self,
        bars,
        *,
        trend_atr_multiple=0.75,
        high_volatility_threshold=0.015,
        high_volume_z=1.5,
    ):

        bars = list(
            bars
        )


        if len(
            bars
        ) < 21:

            return {
                "success":
                    True,

                "regime":
                    "INSUFFICIENT_DATA",

                "confidence":
                    0.0,

                "features":
                    {},
            }


        features = (
            feature_engine
            .snapshot(
                bars
            )
        )


        close = features[
            "close"
        ]

        ema9 = features[
            "ema9"
        ]

        ema21 = features[
            "ema21"
        ]

        atr = features[
            "atr14"
        ]


        trend_distance = (
            abs(
                ema9
                - ema21
            )
            if (
                ema9 is not None
                and ema21 is not None
            )
            else 0.0
        )


        trend_threshold = (
            (
                atr
                * float(
                    trend_atr_multiple
                )
            )
            if atr is not None
            else 0.0
        )


        high_volatility = bool(
            features.get(
                "realized_vol20"
            )
            is not None

            and features[
                "realized_vol20"
            ]
            >= float(
                high_volatility_threshold
            )
        )


        high_volume = bool(
            features.get(
                "volume_z20"
            )
            is not None

            and features[
                "volume_z20"
            ]
            >= float(
                high_volume_z
            )
        )


        trending = bool(
            trend_threshold > 0
            and trend_distance
            >= trend_threshold
        )


        if trending:

            if ema9 > ema21:

                regime = (
                    "TREND_UP_HIGH_VOL"
                    if high_volatility
                    else "TREND_UP"
                )

            else:

                regime = (
                    "TREND_DOWN_HIGH_VOL"
                    if high_volatility
                    else "TREND_DOWN"
                )


        elif high_volatility:

            regime = "RANGE_HIGH_VOL"


        else:

            regime = "RANGE"


        if (
            high_volume
            and "TREND" in regime
        ):

            confidence = 0.90

        elif trending:

            confidence = 0.80

        else:

            confidence = 0.70


        return {
            "success":
                True,

            "regime":
                regime,

            "confidence":
                confidence,

            "high_volatility":
                high_volatility,

            "high_volume":
                high_volume,

            "trend_distance":
                trend_distance,

            "trend_threshold":
                trend_threshold,

            "features":
                features,
        }


market_regime_engine = (
    MarketRegimeEngine()
)
