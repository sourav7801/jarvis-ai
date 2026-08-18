from __future__ import annotations

from bisect import (
    bisect_right,
)

from datetime import (
    datetime,
    timezone,
)


from omni.trading_intelligence.derivatives_history_store import (
    derivatives_history_store,
)

from omni.trading_intelligence.derivatives_regime_v7 import (
    derivatives_regime,
)

from omni.trading_intelligence.derivatives_sync import (
    synchronize_derivatives,
)


def _timestamp(
    value,
):

    if isinstance(
        value,
        datetime,
    ):

        result = value


    else:

        text = str(
            value
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


    return result.astimezone(
        timezone.utc
    )


def _bar_timestamp(
    bar,
):

    if isinstance(
        bar,
        dict,
    ):

        return bar[
            "timestamp"
        ]


    return getattr(
        bar,
        "timestamp"
    )


def _rank(
    values,
    current,
):

    values = [
        float(
            value
        )

        for value in values

        if value is not None
    ]


    if (
        current is None
        or len(
            values
        ) < 2
    ):

        return None


    low = min(
        values
    )

    high = max(
        values
    )


    if high == low:

        return 50.0


    return (
        (
            float(
                current
            )
            - low
        )
        / (
            high
            - low
        )
        * 100.0
    )


def _percentile(
    values,
    current,
):

    values = [
        float(
            value
        )

        for value in values

        if value is not None
    ]


    if (
        current is None
        or not values
    ):

        return None


    return (
        sum(
            1

            for value in values

            if value <= float(
                current
            )
        )
        / len(
            values
        )
        * 100.0
    )


class DerivativesFeatureDatasetBuilder:

    def __init__(
        self,
        *,
        store=None,
    ):

        self.store = (
            store
            or derivatives_history_store
        )


    def build(
        self,
        symbol,
        *,
        limit=1000,
    ):

        history = list(
            self.store.history(
                symbol,
                limit=limit,
            )
        )


        history.reverse()


        rows = []

        iv_seen = []

        previous = None


        for source in history:

            atm_iv = source.get(
                "atm_iv"
            )


            if atm_iv is not None:

                iv_seen.append(
                    atm_iv
                )


            delta_call = None

            delta_put = None

            delta_pcr = None

            delta_iv = None

            delta_skew = None


            if previous is not None:

                if (
                    source.get(
                        "call_oi"
                    )
                    is not None
                    and previous.get(
                        "call_oi"
                    )
                    is not None
                ):

                    delta_call = (
                        source[
                            "call_oi"
                        ]
                        - previous[
                            "call_oi"
                        ]
                    )


                if (
                    source.get(
                        "put_oi"
                    )
                    is not None
                    and previous.get(
                        "put_oi"
                    )
                    is not None
                ):

                    delta_put = (
                        source[
                            "put_oi"
                        ]
                        - previous[
                            "put_oi"
                        ]
                    )


                if (
                    source.get(
                        "pcr_oi"
                    )
                    is not None
                    and previous.get(
                        "pcr_oi"
                    )
                    is not None
                ):

                    delta_pcr = (
                        source[
                            "pcr_oi"
                        ]
                        - previous[
                            "pcr_oi"
                        ]
                    )


                if (
                    atm_iv is not None
                    and previous.get(
                        "atm_iv"
                    )
                    is not None
                ):

                    delta_iv = (
                        atm_iv
                        - previous[
                            "atm_iv"
                        ]
                    )


                if (
                    source.get(
                        "atm_skew"
                    )
                    is not None
                    and previous.get(
                        "atm_skew"
                    )
                    is not None
                ):

                    delta_skew = (
                        source[
                            "atm_skew"
                        ]
                        - previous[
                            "atm_skew"
                        ]
                    )


            call_oi = source.get(
                "call_oi"
            )

            put_oi = source.get(
                "put_oi"
            )


            total_oi = (
                call_oi
                + put_oi

                if (
                    call_oi is not None
                    and put_oi is not None
                )

                else None
            )


            oi_imbalance = (
                (
                    put_oi
                    - call_oi
                )
                / total_oi

                if (
                    total_oi not in (
                        None,
                        0,
                    )
                )

                else None
            )


            feature = {
                "snapshot_id":
                    source[
                        "snapshot_id"
                    ],

                "symbol":
                    source[
                        "symbol"
                    ],

                "captured_at":
                    source[
                        "captured_at"
                    ],

                "selected_expiry":
                    source.get(
                        "selected_expiry"
                    ),

                "spot":
                    source.get(
                        "spot"
                    ),

                "atm_strike":
                    source.get(
                        "atm_strike"
                    ),

                "atm_iv":
                    atm_iv,

                "atm_iv_rank":
                    _rank(
                        iv_seen,
                        atm_iv,
                    ),

                "atm_iv_percentile":
                    _percentile(
                        iv_seen,
                        atm_iv,
                    ),

                "delta_atm_iv":
                    delta_iv,

                "atm_skew":
                    source.get(
                        "atm_skew"
                    ),

                "delta_atm_skew":
                    delta_skew,

                "pcr_oi":
                    source.get(
                        "pcr_oi"
                    ),

                "delta_pcr_oi":
                    delta_pcr,

                "call_oi":
                    call_oi,

                "put_oi":
                    put_oi,

                "delta_call_oi":
                    delta_call,

                "delta_put_oi":
                    delta_put,

                "total_oi":
                    total_oi,

                "oi_imbalance":
                    oi_imbalance,

                "feature_time":
                    source[
                        "captured_at"
                    ],

                "uses_future_snapshot":
                    False,
            }


            regime = derivatives_regime(
                {
                    "atm_iv_rank":
                        feature[
                            "atm_iv_rank"
                        ],

                    "pcr_oi":
                        feature[
                            "pcr_oi"
                        ],

                    "delta_call_oi":
                        feature[
                            "delta_call_oi"
                        ],

                    "delta_put_oi":
                        feature[
                            "delta_put_oi"
                        ],

                    "futures_basis":
                        None,
                }
            )


            feature[
                "regime"
            ] = regime


            rows.append(
                feature
            )


            previous = source


        return {
            "symbol":
                str(
                    symbol
                ),

            "rows":
                tuple(
                    rows
                ),

            "row_count":
                len(
                    rows
                ),

            "chronological":
                True,

            "rolling_features_use_only_prior_and_current_data":
                True,

            "future_data_leakage":
                False,

            "research_only":
                True,
        }


    def synchronized(
        self,
        symbol,
        underlying_bars,
        futures_bars,
        *,
        limit=1000,
        max_chain_age_seconds=300,
    ):

        chain = list(
            self.store.history(
                symbol,
                limit=limit,
            )
        )


        chain.reverse()


        result = synchronize_derivatives(
            underlying_bars,
            futures_bars,
            chain,
            max_chain_age_seconds=
                max_chain_age_seconds,
        )


        result[
            "symbol"
        ] = str(
            symbol
        )


        return result


    def regime_datasets(
        self,
        bars,
        feature_rows,
    ):

        features = sorted(
            tuple(
                feature_rows
            ),
            key=lambda row:
                _timestamp(
                    row[
                        "captured_at"
                    ]
                ),
        )


        times = [
            _timestamp(
                row[
                    "captured_at"
                ]
            )

            for row in features
        ]


        groups = {}


        for bar in bars:

            bar_time = _timestamp(
                _bar_timestamp(
                    bar
                )
            )


            index = (
                bisect_right(
                    times,
                    bar_time,
                )
                - 1
            )


            if index < 0:

                continue


            feature = features[
                index
            ]


            regime = (
                feature.get(
                    "regime",
                    {}
                ).get(
                    "regime",
                    "UNKNOWN"
                )
            )


            groups.setdefault(
                regime,
                [],
            ).append(
                bar
            )


        return {
            key:
                tuple(
                    value
                )

            for key, value
            in groups.items()
        }


derivatives_feature_dataset_builder = (
    DerivativesFeatureDatasetBuilder()
)
