from __future__ import annotations

import json

from pathlib import (
    Path,
)


ROOT = (
    Path(__file__)
    .resolve()
    .parents[2]
)


DEFAULT_PLAN_FILE = (
    ROOT
    / "data"
    / "trading"
    / "derivatives"
    / "capture_plans.json"
)


MAX_PLANS = 50

MAX_EXPLICIT_EXPIRIES = 4


def build_capture_plan(
    plan_id,
    symbol,
    *,
    strikecount=5,
    greeks=True,
    expiry_mode="nearest",
    expiry_timestamps=(),
    interval_minutes=5,
    session_start="09:15",
    session_end="15:30",
    timezone="Asia/Kolkata",
    enabled=True,
    max_captures_per_run=1,
):

    plan_id = str(
        plan_id
    ).strip()

    symbol = str(
        symbol
    ).strip()


    if not plan_id:

        raise ValueError(
            "plan_id is required."
        )


    if not symbol:

        raise ValueError(
            "symbol is required."
        )


    strikecount = int(
        strikecount
    )


    if not 0 <= strikecount <= 50:

        raise ValueError(
            "strikecount must be between 0 and 50."
        )


    expiry_mode = str(
        expiry_mode
    ).lower()


    if expiry_mode not in {
        "nearest",
        "explicit",
    }:

        raise ValueError(
            "expiry_mode must be nearest or explicit."
        )


    expiries = tuple(
        str(
            value
        )

        for value
        in expiry_timestamps

        if str(
            value
        ).strip()
    )


    if (
        expiry_mode == "explicit"
        and not expiries
    ):

        raise ValueError(
            "Explicit expiry mode requires expiry timestamps."
        )


    if len(
        expiries
    ) > MAX_EXPLICIT_EXPIRIES:

        raise ValueError(
            "A capture plan can contain at most four explicit expiries."
        )


    interval_minutes = int(
        interval_minutes
    )


    if not 1 <= interval_minutes <= 1440:

        raise ValueError(
            "interval_minutes must be between 1 and 1440."
        )


    max_captures_per_run = int(
        max_captures_per_run
    )


    if not 1 <= max_captures_per_run <= 4:

        raise ValueError(
            "max_captures_per_run must be between 1 and 4."
        )


    return {
        "plan_id":
            plan_id,

        "symbol":
            symbol,

        "strikecount":
            strikecount,

        "greeks":
            bool(
                greeks
            ),

        "expiry_mode":
            expiry_mode,

        "expiry_timestamps":
            expiries,

        "interval_minutes":
            interval_minutes,

        "session_start":
            str(
                session_start
            ),

        "session_end":
            str(
                session_end
            ),

        "timezone":
            str(
                timezone
            ),

        "enabled":
            bool(
                enabled
            ),

        "max_captures_per_run":
            max_captures_per_run,

        "read_only":
            True,

        "persist":
            True,
    }


class CapturePlanStore:

    def __init__(
        self,
        path=None,
    ):

        self.path = Path(
            path
            or DEFAULT_PLAN_FILE
        )


    def _load(
        self,
    ):

        if not self.path.exists():

            return {
                "plans":
                    {}
            }


        value = json.loads(
            self.path.read_text(
                encoding="utf-8"
            )
        )


        if not isinstance(
            value,
            dict,
        ):

            raise ValueError(
                "Invalid capture-plan file."
            )


        plans = value.get(
            "plans",
            {}
        )


        if not isinstance(
            plans,
            dict,
        ):

            raise ValueError(
                "Invalid capture-plan structure."
            )


        return {
            "plans":
                plans
        }


    def _save(
        self,
        value,
    ):

        self.path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )


        temporary = (
            self.path
            .with_suffix(
                self.path.suffix
                + ".tmp"
            )
        )


        temporary.write_text(
            json.dumps(
                value,
                ensure_ascii=False,
                indent=2,
                default=str,
            ),
            encoding="utf-8",
        )


        temporary.replace(
            self.path
        )


    def save(
        self,
        plan,
    ):

        plan = build_capture_plan(
            plan[
                "plan_id"
            ],

            plan[
                "symbol"
            ],

            strikecount=
                plan.get(
                    "strikecount",
                    5,
                ),

            greeks=
                plan.get(
                    "greeks",
                    True,
                ),

            expiry_mode=
                plan.get(
                    "expiry_mode",
                    "nearest",
                ),

            expiry_timestamps=
                plan.get(
                    "expiry_timestamps",
                    (),
                ),

            interval_minutes=
                plan.get(
                    "interval_minutes",
                    5,
                ),

            session_start=
                plan.get(
                    "session_start",
                    "09:15",
                ),

            session_end=
                plan.get(
                    "session_end",
                    "15:30",
                ),

            timezone=
                plan.get(
                    "timezone",
                    "Asia/Kolkata",
                ),

            enabled=
                plan.get(
                    "enabled",
                    True,
                ),

            max_captures_per_run=
                plan.get(
                    "max_captures_per_run",
                    1,
                ),
        )


        value = self._load()

        plans = value[
            "plans"
        ]


        if (
            plan[
                "plan_id"
            ]
            not in plans
            and len(
                plans
            ) >= MAX_PLANS
        ):

            raise ValueError(
                "Capture-plan limit reached."
            )


        plans[
            plan[
                "plan_id"
            ]
        ] = plan


        self._save(
            value
        )


        return {
            "success":
                True,

            "plan":
                plan,

            "plan_count":
                len(
                    plans
                ),

            "background_started":
                False,

            "research_only":
                True,
        }


    def list(
        self,
    ):

        plans = (
            self._load()
            [
                "plans"
            ]
        )


        return tuple(
            plans[
                key
            ]

            for key
            in sorted(
                plans
            )
        )


    def get(
        self,
        plan_id,
    ):

        return (
            self._load()
            [
                "plans"
            ]
            .get(
                str(
                    plan_id
                )
            )
        )


    def delete(
        self,
        plan_id,
    ):

        value = self._load()

        removed = (
            value[
                "plans"
            ]
            .pop(
                str(
                    plan_id
                ),
                None,
            )
        )


        self._save(
            value
        )


        return {
            "success":
                True,

            "removed":
                removed is not None,

            "research_only":
                True,
        }


capture_plan_store = (
    CapturePlanStore()
)
