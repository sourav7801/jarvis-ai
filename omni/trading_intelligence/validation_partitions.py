from __future__ import annotations


def chronological_split(
    bars,
    *,
    train_ratio=0.60,
    validation_ratio=0.20,
    minimum_segment_bars=32,
):

    bars = tuple(bars)

    total = len(bars)

    if total < minimum_segment_bars * 3:
        raise ValueError(
            "Insufficient data for independent "
            "train/validation/out-of-sample partitions."
        )


    train_ratio = float(train_ratio)
    validation_ratio = float(validation_ratio)

    if not 0 < train_ratio < 1:
        raise ValueError(
            "train_ratio must be between 0 and 1."
        )

    if not 0 < validation_ratio < 1:
        raise ValueError(
            "validation_ratio must be between 0 and 1."
        )

    if train_ratio + validation_ratio >= 1:
        raise ValueError(
            "A positive out-of-sample partition is required."
        )


    train_end = int(
        total * train_ratio
    )

    validation_end = train_end + int(
        total * validation_ratio
    )


    train = bars[:train_end]
    validation = bars[
        train_end:validation_end
    ]
    out_of_sample = bars[
        validation_end:
    ]


    for name, segment in (
        ("train", train),
        ("validation", validation),
        ("out_of_sample", out_of_sample),
    ):

        if len(segment) < minimum_segment_bars:
            raise ValueError(
                name
                + " partition is too small."
            )


    return {
        "train":
            train,

        "validation":
            validation,

        "out_of_sample":
            out_of_sample,

        "counts": {
            "total":
                total,

            "train":
                len(train),

            "validation":
                len(validation),

            "out_of_sample":
                len(out_of_sample),
        },

        "chronological":
            True,

        "shuffled":
            False,

        "research_only":
            True,
    }


def rolling_windows(
    bars,
    *,
    train_size,
    validation_size,
    test_size,
    step=None,
):

    bars = tuple(bars)

    train_size = int(train_size)
    validation_size = int(validation_size)
    test_size = int(test_size)

    step = int(
        step
        if step is not None
        else test_size
    )


    if min(
        train_size,
        validation_size,
        test_size,
        step,
    ) <= 0:
        raise ValueError(
            "Walk-forward window sizes must be positive."
        )


    required = (
        train_size
        + validation_size
        + test_size
    )


    if len(bars) < required:
        raise ValueError(
            "Insufficient bars for walk-forward validation."
        )


    output = []

    start = 0
    window_id = 0


    while (
        start
        + required
        <= len(bars)
    ):

        train_end = (
            start
            + train_size
        )

        validation_end = (
            train_end
            + validation_size
        )

        test_end = (
            validation_end
            + test_size
        )


        output.append(
            {
                "window_id":
                    window_id,

                "train":
                    bars[
                        start:train_end
                    ],

                "validation":
                    bars[
                        train_end:validation_end
                    ],

                "out_of_sample":
                    bars[
                        validation_end:test_end
                    ],

                "indexes": {
                    "start":
                        start,

                    "train_end":
                        train_end,

                    "validation_end":
                        validation_end,

                    "test_end":
                        test_end,
                },
            }
        )


        window_id += 1
        start += step


    return tuple(output)
