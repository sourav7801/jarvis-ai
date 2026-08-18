from __future__ import annotations

import csv
import json

from datetime import (
    datetime,
)

from pathlib import (
    Path,
)


from omni.trading_intelligence.market_schema import (
    Bar,
)


def parse_timestamp(
    value,
):

    if isinstance(
        value,
        datetime,
    ):

        return value


    text = str(
        value
    ).strip()


    if text.endswith(
        "Z"
    ):

        text = (
            text[:-1]
            + "+00:00"
        )


    return datetime.fromisoformat(
        text
    )


class TradingDataset:

    def __init__(
        self,
        bars,
    ):

        self.bars = tuple(
            sorted(
                bars,
                key=lambda bar:
                    bar.timestamp,
            )
        )


        self.validate()


    @staticmethod
    def _bar(
        row,
    ):

        if isinstance(
            row,
            Bar,
        ):

            return row


        row = dict(
            row
        )


        return Bar(
            timestamp=
                parse_timestamp(
                    row[
                        "timestamp"
                    ]
                ),

            open=
                float(
                    row[
                        "open"
                    ]
                ),

            high=
                float(
                    row[
                        "high"
                    ]
                ),

            low=
                float(
                    row[
                        "low"
                    ]
                ),

            close=
                float(
                    row[
                        "close"
                    ]
                ),

            volume=
                float(
                    row.get(
                        "volume",
                        0.0,
                    )
                    or 0.0
                ),

            open_interest=
                (
                    float(
                        row[
                            "open_interest"
                        ]
                    )
                    if row.get(
                        "open_interest"
                    )
                    not in (
                        None,
                        "",
                    )
                    else None
                ),

            symbol=
                row.get(
                    "symbol"
                ),
        )


    @classmethod
    def from_rows(
        cls,
        rows,
    ):

        return cls(
            cls._bar(
                row
            )

            for row in rows
        )


    @classmethod
    def from_csv(
        cls,
        path,
    ):

        with Path(
            path
        ).open(
            "r",
            encoding="utf-8-sig",
            newline="",
        ) as handle:

            return cls.from_rows(
                csv.DictReader(
                    handle
                )
            )


    @classmethod
    def from_jsonl(
        cls,
        path,
    ):

        rows = []


        with Path(
            path
        ).open(
            "r",
            encoding="utf-8",
        ) as handle:

            for line in handle:

                line = line.strip()

                if line:

                    rows.append(
                        json.loads(
                            line
                        )
                    )


        return cls.from_rows(
            rows
        )


    def validate(
        self,
    ):

        previous = None


        for bar in self.bars:

            if (
                previous is not None
                and bar.timestamp
                < previous
            ):

                raise ValueError(
                    "Dataset timestamps are not ordered."
                )


            previous = bar.timestamp


        return {
            "success":
                True,

            "bars":
                len(
                    self.bars
                ),
        }


    def slice(
        self,
        start=None,
        end=None,
    ):

        bars = self.bars


        if start is not None:

            start = parse_timestamp(
                start
            )

            bars = tuple(
                bar

                for bar in bars

                if bar.timestamp
                >= start
            )


        if end is not None:

            end = parse_timestamp(
                end
            )

            bars = tuple(
                bar

                for bar in bars

                if bar.timestamp
                <= end
            )


        return TradingDataset(
            bars
        )
