from __future__ import annotations

from datetime import (
    datetime,
    timezone,
)


from omni.trading_intelligence.market_schema import (
    Bar,
)


def normalize_timestamp(
    value,
):

    if isinstance(
        value,
        datetime,
    ):

        if value.tzinfo is None:

            return value.replace(
                tzinfo=timezone.utc
            )


        return value


    if isinstance(
        value,
        (
            int,
            float,
        ),
    ):

        numeric = float(
            value
        )


        if numeric > 100000000000:

            numeric = (
                numeric
                / 1000.0
            )


        return datetime.fromtimestamp(
            numeric,
            tz=timezone.utc,
        )


    text = str(
        value
    ).strip()


    if text.isdigit():

        return normalize_timestamp(
            int(
                text
            )
        )


    if text.endswith(
        "Z"
    ):

        text = (
            text[:-1]
            + "+00:00"
        )


    result = datetime.fromisoformat(
        text
    )


    if result.tzinfo is None:

        result = result.replace(
            tzinfo=timezone.utc
        )


    return result


def _records(
    value,
):

    if value is None:

        return []


    # pandas-like DataFrame without importing pandas.
    if (
        hasattr(
            value,
            "to_dict",
        )
        and hasattr(
            value,
            "columns",
        )
    ):

        try:

            return list(
                value.to_dict(
                    "records"
                )
            )

        except Exception:

            pass


    if isinstance(
        value,
        (list, tuple),
    ):

        return list(
            value
        )


    if isinstance(
        value,
        dict,
    ):

        # Column-oriented dictionary.
        keys = {
            str(
                key
            ).lower()

            for key in value
        }


        if {
            "open",
            "high",
            "low",
            "close",
        }.issubset(
            keys
        ):

            lengths = [
                len(
                    child
                )

                for child in value.values()

                if isinstance(
                    child,
                    (
                        list,
                        tuple,
                    ),
                )
            ]


            if lengths:

                count = min(
                    lengths
                )

                rows = []


                for index in range(
                    count
                ):

                    rows.append(
                        {
                            key:
                                (
                                    child[
                                        index
                                    ]
                                    if isinstance(
                                        child,
                                        (
                                            list,
                                            tuple,
                                        ),
                                    )
                                    else child
                                )

                            for key, child
                            in value.items()
                        }
                    )


                return rows


    raise ValueError(
        "Unsupported historical-data payload shape."
    )


def _candidate_payload(
    payload,
):

    if isinstance(
        payload,
        dict
    ):

        if (
            payload.get(
                "success"
            )
            is False
        ):

            raise RuntimeError(
                str(
                    payload.get(
                        "message"
                    )
                    or payload.get(
                        "error"
                    )
                    or "Historical provider returned failure."
                )
            )


        for key in (
            "data",
            "candles",
            "rows",
            "history",
            "ohlcv",
            "frame",
        ):

            if key in payload:

                return payload[
                    key
                ]


    return payload


def _mapping_value(
    row,
    names,
    default=None,
):

    normalized = {
        str(
            key
        ).strip().lower():
            value

        for key, value
        in row.items()
    }


    for name in names:

        if name in normalized:

            return normalized[
                name
            ]


    return default


def normalize_history_payload(
    payload,
    *,
    symbol=None,
):

    candidate = _candidate_payload(
        payload
    )


    rows = _records(
        candidate
    )


    bars = []


    for row in rows:

        if isinstance(
            row,
            Bar,
        ):

            bars.append(
                row
            )

            continue


        if isinstance(
            row,
            (
                list,
                tuple,
            ),
        ):

            if len(
                row
            ) < 6:

                raise ValueError(
                    "Candle row requires at least "
                    "timestamp/O/H/L/C/volume."
                )


            timestamp = row[
                0
            ]

            open_price = row[
                1
            ]

            high = row[
                2
            ]

            low = row[
                3
            ]

            close = row[
                4
            ]

            volume = row[
                5
            ]

            oi = (
                row[
                    6
                ]
                if len(
                    row
                ) > 6
                else None
            )


        elif isinstance(
            row,
            dict,
        ):

            timestamp = _mapping_value(
                row,
                (
                    "timestamp",
                    "datetime",
                    "date",
                    "time",
                    "ts",
                    "epoch",
                ),
            )


            open_price = _mapping_value(
                row,
                (
                    "open",
                    "o",
                ),
            )


            high = _mapping_value(
                row,
                (
                    "high",
                    "h",
                ),
            )


            low = _mapping_value(
                row,
                (
                    "low",
                    "l",
                ),
            )


            close = _mapping_value(
                row,
                (
                    "close",
                    "c",
                ),
            )


            volume = _mapping_value(
                row,
                (
                    "volume",
                    "v",
                    "vol",
                ),
                0.0,
            )


            oi = _mapping_value(
                row,
                (
                    "open_interest",
                    "oi",
                ),
                None,
            )


        else:

            raise ValueError(
                "Unsupported candle row."
            )


        if timestamp is None:

            raise ValueError(
                "Historical row has no timestamp."
            )


        bars.append(
            Bar(
                timestamp=
                    normalize_timestamp(
                        timestamp
                    ),

                open=
                    float(
                        open_price
                    ),

                high=
                    float(
                        high
                    ),

                low=
                    float(
                        low
                    ),

                close=
                    float(
                        close
                    ),

                volume=
                    float(
                        volume
                        or 0.0
                    ),

                open_interest=
                    (
                        float(
                            oi
                        )
                        if oi
                        not in (
                            None,
                            "",
                        )
                        else None
                    ),

                symbol=
                    symbol,
            )
        )


    bars.sort(
        key=lambda bar:
            bar.timestamp
    )


    if len(
        bars
    ) < 2:

        raise ValueError(
            "Historical payload contains too few candles."
        )


    return tuple(
        bars
    )
