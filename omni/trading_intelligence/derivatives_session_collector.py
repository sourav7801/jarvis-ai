from __future__ import annotations

import json

from datetime import (
    datetime,
    timedelta,
    timezone,
)

from pathlib import (
    Path,
)

from zoneinfo import (
    ZoneInfo,
)


from omni.trading_intelligence.derivatives_capture_plans import (
    CapturePlanStore,
    capture_plan_store,
)


ROOT = (
    Path(__file__)
    .resolve()
    .parents[2]
)


DEFAULT_STATE_FILE = (
    ROOT
    / "data"
    / "trading"
    / "derivatives"
    / "capture_state.json"
)


MAX_PLANS_PER_RUN = 10


def _utc(
    value=None,
):

    if value is None:

        return datetime.now(
            timezone.utc
        )


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


def _clock_minutes(
    value,
):

    hour, minute = (
        str(
            value
        )
        .split(
            ":",
            1,
        )
    )


    hour = int(
        hour
    )

    minute = int(
        minute
    )


    if not (
        0 <= hour <= 23
        and 0 <= minute <= 59
    ):

        raise ValueError(
            "Invalid session clock."
        )


    return (
        hour
        * 60
        + minute
    )


class CaptureStateStore:

    def __init__(
        self,
        path=None,
    ):

        self.path = Path(
            path
            or DEFAULT_STATE_FILE
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

            return {
                "plans":
                    {}
            }


        value.setdefault(
            "plans",
            {},
        )


        return value


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
                ),
                {},
            )
        )


    def mark_capture(
        self,
        plan_id,
        *,
        captured_at,
        snapshot_ids,
    ):

        value = self._load()


        value[
            "plans"
        ][
            str(
                plan_id
            )
        ] = {
            "last_capture_at":
                _utc(
                    captured_at
                ).isoformat(),

            "snapshot_ids":
                tuple(
                    snapshot_ids
                ),
        }


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
                indent=2,
                default=str,
            ),
            encoding="utf-8",
        )


        temporary.replace(
            self.path
        )


class DerivativesSessionCollector:

    def __init__(
        self,
        *,
        plan_store=None,
        state_store=None,
        fetcher=None,
    ):

        self.plan_store = (
            plan_store
            or capture_plan_store
        )


        self.state_store = (
            state_store
            or CaptureStateStore()
        )


        self.fetcher = (
            fetcher
            or self._default_fetcher
        )


    @staticmethod
    def _default_fetcher(
        symbol,
        *,
        strikecount,
        timestamp,
        greeks,
        timeout,
    ):

        import main


        return (
            main
            .jarvis_fyers_option_chain(
                symbol,
                strikecount=
                    strikecount,
                timestamp=
                    timestamp,
                greeks=
                    greeks,
                persist=
                    True,
                timeout=
                    timeout,
            )
        )


    def due_status(
        self,
        plan,
        *,
        now=None,
    ):

        now_utc = _utc(
            now
        )


        zone = ZoneInfo(
            plan[
                "timezone"
            ]
        )


        local = now_utc.astimezone(
            zone
        )


        minute = (
            local.hour
            * 60
            + local.minute
        )


        start = _clock_minutes(
            plan[
                "session_start"
            ]
        )


        end = _clock_minutes(
            plan[
                "session_end"
            ]
        )


        if start <= end:

            in_session = (
                start
                <= minute
                <= end
            )


        else:

            in_session = (
                minute >= start
                or minute <= end
            )


        state = (
            self.state_store
            .get(
                plan[
                    "plan_id"
                ]
            )
        )


        last_text = state.get(
            "last_capture_at"
        )


        clock_skew = False


        if last_text:

            last = _utc(
                last_text
            )


            if last > now_utc:

                due = False

                clock_skew = True

                next_due = last


            else:

                next_due = (
                    last
                    + timedelta(
                        minutes=
                            int(
                                plan[
                                    "interval_minutes"
                                ]
                            )
                    )
                )


                due = (
                    now_utc
                    >= next_due
                )


        else:

            due = True

            next_due = now_utc


        due = bool(
            due
            and in_session
            and plan.get(
                "enabled",
                True,
            )
        )


        return {
            "plan_id":
                plan[
                    "plan_id"
                ],

            "now_utc":
                now_utc.isoformat(),

            "local_time":
                local.isoformat(),

            "in_session":
                in_session,

            "enabled":
                bool(
                    plan.get(
                        "enabled",
                        True,
                    )
                ),

            "due":
                due,

            "clock_skew":
                clock_skew,

            "last_capture_at":
                last_text,

            "next_due_at":
                next_due.isoformat(),
        }


    @staticmethod
    def _expiries(
        plan,
    ):

        if (
            plan[
                "expiry_mode"
            ]
            == "nearest"
        ):

            return (
                None,
            )


        values = tuple(
            plan[
                "expiry_timestamps"
            ]
        )


        return values[
            :
            int(
                plan[
                    "max_captures_per_run"
                ]
            )
        ]


    def collect_plan(
        self,
        plan,
        *,
        now=None,
        dry_run=False,
        timeout=30,
    ):

        status = self.due_status(
            plan,
            now=now,
        )


        if not status[
            "due"
        ]:

            return {
                "success":
                    True,

                "plan_id":
                    plan[
                        "plan_id"
                    ],

                "status":
                    "NOT_DUE",

                "due_status":
                    status,

                "request_count":
                    0,

                "snapshot_ids":
                    (),

                "network_request":
                    False,

                "research_only":
                    True,
            }


        expiries = self._expiries(
            plan
        )


        if dry_run:

            return {
                "success":
                    True,

                "plan_id":
                    plan[
                        "plan_id"
                    ],

                "status":
                    "DRY_RUN_DUE",

                "due_status":
                    status,

                "request_count":
                    len(
                        expiries
                    ),

                "expiries":
                    expiries,

                "network_request":
                    False,

                "research_only":
                    True,
            }


        snapshot_ids = []


        for expiry in expiries:

            result = self.fetcher(
                plan[
                    "symbol"
                ],

                strikecount=
                    int(
                        plan[
                            "strikecount"
                        ]
                    ),

                timestamp=
                    expiry,

                greeks=
                    bool(
                        plan[
                            "greeks"
                        ]
                    ),

                timeout=
                    timeout,
            )


            if not result.get(
                "success"
            ):

                raise RuntimeError(
                    "Capture fetch failed."
                )


            if (
                result.get(
                    "live_execution"
                )
                is not False
            ):

                raise RuntimeError(
                    "Live execution invariant failed."
                )


            snapshot = result.get(
                "snapshot",
                {},
            )


            snapshot_id = (
                snapshot.get(
                    "snapshot_id"
                )
            )


            if not snapshot_id:

                raise RuntimeError(
                    "Collector received no snapshot ID."
                )


            snapshot_ids.append(
                snapshot_id
            )


        captured_at = _utc(
            now
        )


        self.state_store.mark_capture(
            plan[
                "plan_id"
            ],
            captured_at=
                captured_at,
            snapshot_ids=
                snapshot_ids,
        )


        return {
            "success":
                True,

            "plan_id":
                plan[
                    "plan_id"
                ],

            "status":
                "CAPTURED",

            "request_count":
                len(
                    snapshot_ids
                ),

            "snapshot_ids":
                tuple(
                    snapshot_ids
                ),

            "network_request":
                True,

            "market_data_only":
                True,

            "broker_order":
                False,

            "live_execution":
                False,

            "research_only":
                True,
        }


    def collect_due(
        self,
        *,
        now=None,
        dry_run=False,
        timeout=30,
        max_plans=10,
    ):

        max_plans = max(
            1,
            min(
                int(
                    max_plans
                ),
                MAX_PLANS_PER_RUN,
            ),
        )


        plans = (
            self.plan_store
            .list()
        )[
            :
            max_plans
        ]


        results = []


        for plan in plans:

            results.append(
                self.collect_plan(
                    plan,
                    now=now,
                    dry_run=dry_run,
                    timeout=timeout,
                )
            )


        return {
            "success":
                True,

            "plan_count":
                len(
                    plans
                ),

            "results":
                tuple(
                    results
                ),

            "dry_run":
                bool(
                    dry_run
                ),

            "background_thread":
                False,

            "automatic_broker_order":
                False,

            "research_only":
                True,
        }


derivatives_session_collector = (
    DerivativesSessionCollector()
)
