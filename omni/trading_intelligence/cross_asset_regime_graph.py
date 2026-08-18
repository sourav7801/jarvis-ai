from __future__ import annotations

from bisect import (
    bisect_left,
)

from datetime import (
    datetime,
    timezone,
)

import math


from omni.trading_intelligence.derivatives_feature_dataset import (
    derivatives_feature_dataset_builder,
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


def _pearson(
    left,
    right,
):

    if len(
        left
    ) != len(
        right
    ):

        return None


    if len(
        left
    ) < 2:

        return None


    mean_left = (
        sum(
            left
        )
        / len(
            left
        )
    )


    mean_right = (
        sum(
            right
        )
        / len(
            right
        )
    )


    numerator = sum(
        (
            x
            - mean_left
        )
        * (
            y
            - mean_right
        )

        for x, y
        in zip(
            left,
            right,
        )
    )


    left_ss = sum(
        (
            x
            - mean_left
        )
        ** 2

        for x in left
    )


    right_ss = sum(
        (
            y
            - mean_right
        )
        ** 2

        for y in right
    )


    denominator = math.sqrt(
        left_ss
        * right_ss
    )


    if denominator == 0:

        return None


    return (
        numerator
        / denominator
    )


class CrossAssetRegimeGraph:

    def __init__(
        self,
        *,
        dataset_builder=None,
    ):

        self.dataset_builder = (
            dataset_builder
            or derivatives_feature_dataset_builder
        )


    @staticmethod
    def _aligned(
        left_rows,
        right_rows,
        feature,
        max_gap_seconds,
    ):

        right_valid = [
            (
                _timestamp(
                    row[
                        "captured_at"
                    ]
                ),
                row.get(
                    feature
                ),
            )

            for row in right_rows

            if row.get(
                feature
            ) is not None
        ]


        right_valid.sort(
            key=lambda item:
                item[
                    0
                ]
        )


        right_times = [
            item[
                0
            ]

            for item in right_valid
        ]


        left_values = []

        right_values = []


        for row in left_rows:

            value = row.get(
                feature
            )


            if value is None:

                continue


            timestamp = _timestamp(
                row[
                    "captured_at"
                ]
            )


            index = bisect_left(
                right_times,
                timestamp,
            )


            candidates = []


            if index < len(
                right_valid
            ):

                candidates.append(
                    right_valid[
                        index
                    ]
                )


            if index > 0:

                candidates.append(
                    right_valid[
                        index
                        - 1
                    ]
                )


            if not candidates:

                continue


            nearest = min(
                candidates,
                key=lambda item:
                    abs(
                        (
                            item[
                                0
                            ]
                            - timestamp
                        ).total_seconds()
                    ),
            )


            gap = abs(
                (
                    nearest[
                        0
                    ]
                    - timestamp
                ).total_seconds()
            )


            if gap > float(
                max_gap_seconds
            ):

                continue


            if nearest[
                1
            ] is None:

                continue


            left_values.append(
                float(
                    value
                )
            )


            right_values.append(
                float(
                    nearest[
                        1
                    ]
                )
            )


        return (
            left_values,
            right_values,
        )


    def build(
        self,
        symbols,
        *,
        feature="atm_iv",
        lookback=252,
        min_overlap=3,
        max_gap_seconds=900,
        edge_threshold=0.40,
    ):

        symbols = tuple(
            dict.fromkeys(
                str(
                    symbol
                )

                for symbol
                in symbols
            )
        )


        if not 2 <= len(
            symbols
        ) <= 20:

            raise ValueError(
                "Cross-asset graph requires 2 to 20 symbols."
            )


        datasets = {}

        nodes = {}


        for symbol in symbols:

            dataset = (
                self.dataset_builder
                .build(
                    symbol,
                    limit=lookback,
                )
            )


            rows = dataset[
                "rows"
            ]


            datasets[
                symbol
            ] = rows


            latest = (
                rows[
                    -1
                ]

                if rows

                else None
            )


            nodes[
                symbol
            ] = {
                "snapshot_count":
                    len(
                        rows
                    ),

                "latest_feature":
                    (
                        latest.get(
                            feature
                        )
                        if latest
                        else None
                    ),

                "latest_regime":
                    (
                        latest.get(
                            "regime",
                            {}
                        ).get(
                            "regime"
                        )
                        if latest
                        else None
                    ),
            }


        edges = []


        for left_index in range(
            len(
                symbols
            )
        ):

            for right_index in range(
                left_index + 1,
                len(
                    symbols
                ),
            ):

                left_symbol = (
                    symbols[
                        left_index
                    ]
                )


                right_symbol = (
                    symbols[
                        right_index
                    ]
                )


                left_values, right_values = (
                    self._aligned(
                        datasets[
                            left_symbol
                        ],

                        datasets[
                            right_symbol
                        ],

                        feature,
                        max_gap_seconds,
                    )
                )


                correlation = _pearson(
                    left_values,
                    right_values,
                )


                edge = {
                    "left":
                        left_symbol,

                    "right":
                        right_symbol,

                    "feature":
                        feature,

                    "overlap":
                        len(
                            left_values
                        ),

                    "correlation":
                        correlation,

                    "sufficient_history":
                        (
                            len(
                                left_values
                            )
                            >= int(
                                min_overlap
                            )
                        ),
                }


                if (
                    correlation is not None
                    and len(
                        left_values
                    ) >= int(
                        min_overlap
                    )
                    and abs(
                        correlation
                    ) >= float(
                        edge_threshold
                    )
                ):

                    edge[
                        "material_edge"
                    ] = True


                else:

                    edge[
                        "material_edge"
                    ] = False


                edges.append(
                    edge
                )


        return {
            "feature":
                feature,

            "nodes":
                nodes,

            "edges":
                tuple(
                    edges
                ),

            "minimum_overlap":
                int(
                    min_overlap
                ),

            "edge_threshold":
                float(
                    edge_threshold
                ),

            "predictive_guarantee":
                False,

            "automatic_portfolio_action":
                False,

            "research_only":
                True,
        }


cross_asset_regime_graph = (
    CrossAssetRegimeGraph()
)
