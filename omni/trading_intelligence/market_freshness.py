from __future__ import annotations

from datetime import (
    datetime,
    timezone,
)


class MarketFreshnessGuard:

    def __init__(
        self,
        max_age_seconds=15.0,
        max_future_skew_seconds=5.0,
    ):

        self.max_age_seconds = float(
            max_age_seconds
        )

        self.max_future_skew_seconds = float(
            max_future_skew_seconds
        )


    def check(
        self,
        snapshot,
        *,
        now=None,
    ):

        current = (
            now
            if now is not None
            else datetime.now(
                timezone.utc
            )
        )


        if current.tzinfo is None:

            current = current.replace(
                tzinfo=timezone.utc
            )


        current = current.astimezone(
            timezone.utc
        )


        timestamp = (
            snapshot.timestamp
            .astimezone(
                timezone.utc
            )
        )


        age = (
            current
            - timestamp
        ).total_seconds()


        if age < (
            -self.max_future_skew_seconds
        ):

            return {
                "fresh":
                    False,

                "reason":
                    "future_timestamp",

                "age_seconds":
                    age,
            }


        if age > self.max_age_seconds:

            return {
                "fresh":
                    False,

                "reason":
                    "stale_quote",

                "age_seconds":
                    age,
            }


        return {
            "fresh":
                True,

            "reason":
                "fresh",

            "age_seconds":
                age,
        }
