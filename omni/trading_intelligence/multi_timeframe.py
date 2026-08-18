from __future__ import annotations

from collections import (
    OrderedDict,
)

from datetime import (
    timedelta,
)


from omni.trading_intelligence.feature_engine import (
    feature_engine,
)

from omni.trading_intelligence.market_schema import (
    Bar,
)


def _bucket_start(
    timestamp,
    minutes,
):

    minutes = int(
        minutes
    )


    midnight = timestamp.replace(
        hour=0,
        minute=0,
        second=0,
        microsecond=0,
    )


    elapsed = int(
        (
            timestamp
            - midnight
        ).total_seconds()
        // 60
    )


    bucket = (
        elapsed
        // minutes
        * minutes
    )


    return (
        midnight
        + timedelta(
            minutes=bucket
        )
    )


def resample_bars(
    bars,
    timeframe_minutes,
    *,
    base_timeframe_minutes=1,
    closed_only=True,
):

    bars = list(
        bars
    )


    timeframe_minutes = int(
        timeframe_minutes
    )

    base_timeframe_minutes = int(
        base_timeframe_minutes
    )


    if (
        timeframe_minutes
        <= base_timeframe_minutes
    ):

        raise ValueError(
            "Resampled timeframe must exceed base timeframe."
        )


    if (
        timeframe_minutes
        % base_timeframe_minutes
        != 0
    ):

        raise ValueError(
            "Higher timeframe must be an integer "
            "multiple of base timeframe."
        )


    required_count = (
        timeframe_minutes
        // base_timeframe_minutes
    )


    buckets = OrderedDict()


    for bar in bars:

        key = _bucket_start(
            bar.timestamp,
            timeframe_minutes,
        )


        bucket = buckets.setdefault(
            key,
            [],
        )


        bucket.append(
            bar
        )


    output = []


    for timestamp, items in buckets.items():

        if (
            closed_only
            and len(
                items
            ) < required_count
        ):

            continue


        oi_values = [
            item.open_interest

            for item in items

            if item.open_interest
            is not None
        ]


        output.append(
            Bar(
                timestamp=
                    timestamp,

                open=
                    float(
                        items[
                            0
                        ].open
                    ),

                high=
                    max(
                        float(
                            item.high
                        )
                        for item
                        in items
                    ),

                low=
                    min(
                        float(
                            item.low
                        )
                        for item
                        in items
                    ),

                close=
                    float(
                        items[
                            -1
                        ].close
                    ),

                volume=
                    sum(
                        float(
                            item.volume
                        )
                        for item
                        in items
                    ),

                open_interest=
                    (
                        oi_values[
                            -1
                        ]
                        if oi_values
                        else None
                    ),

                symbol=
                    items[
                        -1
                    ].symbol,
            )
        )


    return tuple(
        output
    )


def multitimeframe_features(
    bars,
    higher_timeframes,
    *,
    base_timeframe_minutes=1,
):

    context = {}


    for timeframe in higher_timeframes:

        resampled = resample_bars(
            bars,
            timeframe,
            base_timeframe_minutes=
                base_timeframe_minutes,
            closed_only=True,
        )


        if len(
            resampled
        ) < 21:

            continue


        snapshot = feature_engine.snapshot(
            resampled
        )


        prefix = (
            "tf"
            + str(
                timeframe
            )
            + "_"
        )


        for key, value in snapshot.items():

            context[
                prefix
                + key
            ] = value


    return context
