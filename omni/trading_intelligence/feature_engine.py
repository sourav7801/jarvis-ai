from __future__ import annotations

from math import (
    sqrt,
)

from statistics import (
    fmean,
    pstdev,
)


class FeatureEngine:

    @staticmethod
    def _value(
        bar,
        field,
    ):

        if isinstance(
            bar,
            dict,
        ):

            return float(
                bar[
                    field
                ]
            )


        return float(
            getattr(
                bar,
                field,
            )
        )


    @classmethod
    def series(
        cls,
        bars,
        field,
    ):

        return [
            cls._value(
                bar,
                field,
            )

            for bar in bars
        ]


    @staticmethod
    def sma(
        values,
        period,
    ):

        values = list(
            map(
                float,
                values,
            )
        )

        period = int(
            period
        )


        if (
            period <= 0
            or len(
                values
            ) < period
        ):

            return None


        return fmean(
            values[
                -period:
            ]
        )


    @staticmethod
    def ema_series(
        values,
        period,
    ):

        values = list(
            map(
                float,
                values,
            )
        )

        period = int(
            period
        )


        if (
            period <= 0
            or not values
        ):

            return []


        alpha = (
            2.0
            / (
                period
                + 1.0
            )
        )


        output = [
            values[
                0
            ]
        ]


        for value in values[
            1:
        ]:

            output.append(
                (
                    alpha
                    * value
                )
                + (
                    (
                        1.0
                        - alpha
                    )
                    * output[
                        -1
                    ]
                )
            )


        return output


    @classmethod
    def ema(
        cls,
        values,
        period,
    ):

        result = cls.ema_series(
            values,
            period,
        )


        return (
            result[
                -1
            ]
            if result
            else None
        )


    @staticmethod
    def returns(
        values,
    ):

        values = list(
            map(
                float,
                values,
            )
        )


        output = []


        for previous, current in zip(
            values,
            values[
                1:
            ],
        ):

            if previous == 0:

                output.append(
                    0.0
                )

            else:

                output.append(
                    (
                        current
                        / previous
                    )
                    - 1.0
                )


        return output


    @classmethod
    def rsi(
        cls,
        values,
        period=14,
    ):

        values = list(
            map(
                float,
                values,
            )
        )

        period = int(
            period
        )


        if len(
            values
        ) < (
            period
            + 1
        ):

            return None


        changes = [
            current - previous

            for previous, current
            in zip(
                values,
                values[
                    1:
                ],
            )
        ]


        recent = changes[
            -period:
        ]


        gains = [
            max(
                change,
                0.0,
            )

            for change in recent
        ]


        losses = [
            max(
                -change,
                0.0,
            )

            for change in recent
        ]


        avg_gain = fmean(
            gains
        )

        avg_loss = fmean(
            losses
        )


        if avg_loss == 0:

            return 100.0


        rs = (
            avg_gain
            / avg_loss
        )


        return (
            100.0
            - (
                100.0
                / (
                    1.0
                    + rs
                )
            )
        )


    @classmethod
    def atr(
        cls,
        bars,
        period=14,
    ):

        bars = list(
            bars
        )

        period = int(
            period
        )


        if len(
            bars
        ) < (
            period
            + 1
        ):

            return None


        tr = []


        for previous, current in zip(
            bars,
            bars[
                1:
            ],
        ):

            high = cls._value(
                current,
                "high",
            )

            low = cls._value(
                current,
                "low",
            )

            previous_close = cls._value(
                previous,
                "close",
            )


            tr.append(
                max(
                    high - low,
                    abs(
                        high
                        - previous_close
                    ),
                    abs(
                        low
                        - previous_close
                    ),
                )
            )


        return fmean(
            tr[
                -period:
            ]
        )


    @classmethod
    def vwap(
        cls,
        bars,
    ):

        bars = list(
            bars
        )


        numerator = 0.0

        denominator = 0.0


        for bar in bars:

            volume = cls._value(
                bar,
                "volume",
            )


            if volume <= 0:

                continue


            typical = (
                cls._value(
                    bar,
                    "high",
                )
                + cls._value(
                    bar,
                    "low",
                )
                + cls._value(
                    bar,
                    "close",
                )
            ) / 3.0


            numerator += (
                typical
                * volume
            )

            denominator += volume


        if denominator == 0:

            return None


        return (
            numerator
            / denominator
        )


    @staticmethod
    def zscore(
        values,
        period=20,
    ):

        values = list(
            map(
                float,
                values,
            )
        )


        if len(
            values
        ) < period:

            return None


        recent = values[
            -period:
        ]


        mean = fmean(
            recent
        )

        sigma = pstdev(
            recent
        )


        if sigma == 0:

            return 0.0


        return (
            (
                recent[
                    -1
                ]
                - mean
            )
            / sigma
        )


    @classmethod
    def snapshot(
        cls,
        bars,
    ):

        bars = list(
            bars
        )


        if not bars:

            raise ValueError(
                "At least one bar is required."
            )


        closes = cls.series(
            bars,
            "close",
        )

        volumes = cls.series(
            bars,
            "volume",
        )


        atr14 = cls.atr(
            bars,
            14,
        )


        close = closes[
            -1
        ]


        returns = cls.returns(
            closes
        )


        return {
            "close":
                close,

            "sma20":
                cls.sma(
                    closes,
                    20,
                ),

            "ema9":
                cls.ema(
                    closes,
                    9,
                ),

            "ema21":
                cls.ema(
                    closes,
                    21,
                ),

            "ema50":
                cls.ema(
                    closes,
                    50,
                ),

            "rsi14":
                cls.rsi(
                    closes,
                    14,
                ),

            "atr14":
                atr14,

            "atr_pct":
                (
                    atr14
                    / close
                    if (
                        atr14 is not None
                        and close != 0
                    )
                    else None
                ),

            "vwap":
                cls.vwap(
                    bars
                ),

            "volume_z20":
                cls.zscore(
                    volumes,
                    20,
                ),

            "return_1":
                (
                    returns[
                        -1
                    ]
                    if returns
                    else None
                ),

            "realized_vol20":
                (
                    pstdev(
                        returns[
                            -20:
                        ]
                    )
                    if len(
                        returns
                    ) >= 2
                    else None
                ),
        }


feature_engine = FeatureEngine()
