from pathlib import Path
import hashlib
import inspect
import json
import shutil
import subprocess
import sys
import textwrap


ROOT = Path(r"C:\Jarvis")

MAIN_PY = (
    ROOT
    / ".venv"
    / "Scripts"
    / "python.exe"
)

PKG = (
    ROOT
    / "omni"
    / "trading_intelligence"
)

CAPTURE_PLANS = (
    PKG
    / "derivatives_capture_plans.py"
)

COLLECTOR = (
    PKG
    / "derivatives_session_collector.py"
)

DATASET = (
    PKG
    / "derivatives_feature_dataset.py"
)

V4_ADAPTER = (
    PKG
    / "derivatives_v4_adapter.py"
)

V5_ADAPTER = (
    PKG
    / "derivatives_v5_adapter.py"
)

NAUTILUS_ADAPTER = (
    PKG
    / "derivatives_nautilus_adapter.py"
)

REGIME_GRAPH = (
    PKG
    / "cross_asset_regime_graph.py"
)

OPTIMIZER = (
    PKG
    / "research_portfolio_optimizer.py"
)

STATUS = (
    PKG
    / "trading_v8_status.py"
)

MAIN = (
    ROOT
    / "main.py"
)

APP = (
    ROOT
    / "workstation"
    / "app.py"
)

TEST = (
    ROOT
    / "tests"
    / "test_trading_intelligence_v8.py"
)

MANIFEST = (
    ROOT
    / "config"
    / "protected_core_manifest.json"
)

ARCHIVE = (
    ROOT
    / "archive"
    / "trading_intelligence_v8"
)

ARCHIVE.mkdir(
    parents=True,
    exist_ok=True,
)

FILES = [
    CAPTURE_PLANS,
    COLLECTOR,
    DATASET,
    V4_ADAPTER,
    V5_ADAPTER,
    NAUTILUS_ADAPTER,
    REGIME_GRAPH,
    OPTIMIZER,
    STATUS,
    MAIN,
    APP,
    TEST,
]

BACKUPS = {}


def run(
    python,
    *args,
    capture=False,
    timeout=None,
):

    return subprocess.run(
        [
            str(python),
            *args,
        ],
        cwd=ROOT,
        capture_output=capture,
        text=True,
        timeout=timeout,
    )


def sha(
    path,
):

    return hashlib.sha256(
        path.read_bytes()
    ).hexdigest()


def write(
    path,
    source,
):

    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    path.write_text(
        textwrap.dedent(
            source
        ).lstrip(),
        encoding="utf-8",
        newline="\n",
    )


def rollback():

    print()
    print("=" * 72)
    print("ROLLBACK")
    print("=" * 72)

    for path, existed in BACKUPS.items():

        backup = (
            ARCHIVE
            / path.relative_to(
                ROOT
            )
        )

        if existed:

            shutil.copy2(
                backup,
                path,
            )

        else:

            path.unlink(
                missing_ok=True
            )

    print(
        "Trading V8 source restored."
    )


print("=" * 80)
print("JARVIS TRADING INTELLIGENCE V8")
print("HISTORICAL DERIVATIVES RESEARCH + GOVERNED COLLECTION")
print("=" * 80)


# ============================================================
# 1. VERIFY FROZEN V7 / 655 CHECKPOINT
# ============================================================

print()
print(
    "Checking frozen Trading V7 / 655 checkpoint..."
)


r = run(
    MAIN_PY,
    "-c",
    (
        "import main,inspect;"
        "from omni.core_integrity import verify_protected_core;"
        "c=verify_protected_core();"
        "assert c.ok,(c.changed,c.missing);"
        "v4=main.jarvis_trading_v4_status();"
        "v5=main.jarvis_trading_v5_status();"
        "v6=main.jarvis_trading_v6_status();"
        "v7=main.jarvis_trading_v7_status();"
        "c3=main.jarvis_nautilus_c3_status();"
        "assert v5['walk_forward_validation'];"
        "assert v6['paper_only'];"
        "assert v7['historical_chain_store'];"
        "assert c3['single_event_driven_engine'];"
        "assert v7['live_execution'] is False;"
        "assert v7['automatic_broker_order'] is False;"
        "assert c3['broker_adapter'] is False;"
        "h=main.jarvis_derivatives_history("
        "'NSE:NIFTY50-INDEX',limit=5);"
        "assert len(h)>=1;"
        "print('Protected Core: PASS');"
        "print('Trading V4: PASS');"
        "print('Trading V5: PASS');"
        "print('Trading V6: PASS');"
        "print('Trading V7: PASS');"
        "print('Nautilus C3: PASS');"
        "print('Real derivatives history: PASS');"
        "print('655 checkpoint: PASS')"
    ),
)


if r.returncode:

    print(
        "V8 BASELINE FAILURE"
    )

    sys.exit(1)


# ============================================================
# 2. VERIFY EXACT LOCAL APIs
# ============================================================

print()
print(
    "Checking exact V4 / V5 / Nautilus C3 APIs..."
)


api_probe = r'''
import inspect
import main

expected = {
    "jarvis_evolve_strategy":
        "(strategy_id, regime_datasets, base_config, candidate_count=8, random_seed=1)",

    "jarvis_walk_forward":
        "(bars, strategy, config, train_size, validation_size, test_size, step=None)",

    "jarvis_trading_validate_candidate":
        "(candidate, bars, base_config, regime_datasets=None, monte_carlo_iterations=500, random_seed=1)",

    "jarvis_nautilus_portfolio_backtest":
        "(portfolio, timeout=180)",

    "jarvis_nautilus_portfolio_walk_forward":
        "(portfolio, train_size, validation_size, test_size, step=None, timeout=180)",

    "jarvis_nautilus_c3_v5_gate":
        "(v5_report, c3_campaign)",
}


for name, signature in expected.items():

    value = getattr(
        main,
        name,
        None,
    )

    assert callable(value), name

    actual = str(
        inspect.signature(
            value
        )
    )

    assert actual == signature, (
        name,
        actual,
        signature,
    )

    print(
        name + actual + ": PASS"
    )


print(
    "Exact local research API contract: PASS"
)
'''


r = run(
    MAIN_PY,
    "-c",
    api_probe,
)


if r.returncode:

    print(
        "V8 API CONTRACT FAILURE"
    )

    sys.exit(1)


# ============================================================
# 3. BACKUP
# ============================================================

for path in FILES:

    BACKUPS[path] = (
        path.exists()
    )

    if path.exists():

        destination = (
            ARCHIVE
            / path.relative_to(
                ROOT
            )
        )

        destination.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        shutil.copy2(
            path,
            destination,
        )


manifest = json.loads(
    MANIFEST.read_text(
        encoding="utf-8"
    )
)


PROTECTED = {
    relative:
        sha(
            ROOT / relative
        )

    for relative
    in manifest.get(
        "files",
        {}
    )
}


print(
    "Protected files:",
    len(
        PROTECTED
    ),
)


# ============================================================
# 4. EXPIRY-AWARE CAPTURE PLANS
# ============================================================

write(
    CAPTURE_PLANS,
    r'''
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
'''
)


# ============================================================
# 5. GOVERNED SESSION COLLECTOR
# ============================================================

write(
    COLLECTOR,
    r'''
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
'''
)


# ============================================================
# 6. HISTORICAL FEATURE DATASET BUILDER
# ============================================================

write(
    DATASET,
    r'''
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
'''
)


# ============================================================
# 7. V4 DERIVATIVES ADAPTER
# ============================================================

write(
    V4_ADAPTER,
    r'''
from __future__ import annotations


def evolve_derivatives_strategy(
    strategy_id,
    regime_datasets,
    base_config,
    *,
    candidate_count=8,
    random_seed=1,
):

    import main


    candidate_count = max(
        1,
        min(
            int(
                candidate_count
            ),
            50,
        ),
    )


    result = main.jarvis_evolve_strategy(
        strategy_id,
        regime_datasets,
        base_config,
        candidate_count=
            candidate_count,
        random_seed=
            random_seed,
    )


    return {
        "success":
            True,

        "v4_result":
            result,

        "regime_count":
            len(
                regime_datasets
            ),

        "candidate_limit":
            50,

        "automatic_strategy_promotion":
            False,

        "automatic_registry_mutation":
            False,

        "automatic_broker_order":
            False,

        "research_only":
            True,
    }
'''
)


# ============================================================
# 8. V5 DERIVATIVES ADAPTER
# ============================================================

write(
    V5_ADAPTER,
    r'''
from __future__ import annotations


def validate_derivatives_candidate(
    candidate,
    bars,
    base_config,
    *,
    regime_datasets=None,
    monte_carlo_iterations=500,
    random_seed=1,
):

    import main


    iterations = max(
        1,
        min(
            int(
                monte_carlo_iterations
            ),
            5000,
        ),
    )


    result = (
        main
        .jarvis_trading_validate_candidate(
            candidate,
            bars,
            base_config,
            regime_datasets=
                regime_datasets,
            monte_carlo_iterations=
                iterations,
            random_seed=
                random_seed,
        )
    )


    return {
        "success":
            True,

        "v5_report":
            result,

        "v5_authoritative":
            True,

        "oos_tuning":
            False,

        "automatic_strategy_promotion":
            False,

        "automatic_broker_order":
            False,

        "research_only":
            True,
    }


def walk_forward_derivatives(
    bars,
    strategy,
    config,
    *,
    train_size,
    validation_size,
    test_size,
    step=None,
):

    import main


    result = main.jarvis_walk_forward(
        bars,
        strategy,
        config,
        train_size,
        validation_size,
        test_size,
        step=step,
    )


    return {
        "success":
            True,

        "walk_forward":
            result,

        "chronological":
            True,

        "oos_tuning":
            False,

        "automatic_parameter_selection":
            False,

        "automatic_strategy_promotion":
            False,

        "research_only":
            True,
    }
'''
)


print()
print("PART 1 SAVED")
print("Paste PART 2.")


# ============================================================
# 9. NAUTILUS C3 DERIVATIVES PORTFOLIO ADAPTER
# ============================================================

write(
    NAUTILUS_ADAPTER,
    r'''
from __future__ import annotations


def validate_derivatives_portfolio(
    portfolio,
    *,
    v5_report=None,
    train_size=None,
    validation_size=None,
    test_size=None,
    step=None,
    timeout=180,
):

    import main


    requested_walk_forward = any(
        value is not None

        for value in (
            train_size,
            validation_size,
            test_size,
        )
    )


    if requested_walk_forward:

        if (
            train_size is None
            or validation_size is None
            or test_size is None
        ):

            raise ValueError(
                "train_size, validation_size and test_size "
                "must all be supplied for Nautilus walk-forward."
            )


        evidence = (
            main
            .jarvis_nautilus_portfolio_walk_forward(
                portfolio,
                train_size,
                validation_size,
                test_size,
                step=step,
                timeout=timeout,
            )
        )


        mode = "walk_forward"


    else:

        evidence = (
            main
            .jarvis_nautilus_portfolio_backtest(
                portfolio,
                timeout=timeout,
            )
        )


        mode = "backtest"


    gate = None


    if (
        v5_report is not None
        and mode == "walk_forward"
    ):

        gate = (
            main
            .jarvis_nautilus_c3_v5_gate(
                v5_report,
                evidence,
            )
        )


    return {
        "success":
            True,

        "mode":
            mode,

        "nautilus_evidence":
            evidence,

        "v5_gate":
            gate,

        "v5_authoritative":
            True,

        "automatic_portfolio_allocation":
            False,

        "automatic_portfolio_rebalance":
            False,

        "automatic_broker_order":
            False,

        "live_execution":
            False,

        "research_only":
            True,
    }
'''
)


# ============================================================
# 10. CROSS-ASSET REGIME GRAPH
# ============================================================

write(
    REGIME_GRAPH,
    r'''
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
'''
)


# ============================================================
# 11. RESEARCH-ONLY PORTFOLIO OPTIMIZER
# ============================================================

write(
    OPTIMIZER,
    r'''
from __future__ import annotations

import math


STATE_BONUS = {
    "PORTFOLIO_RESEARCH_ELIGIBLE":
        20.0,

    "EXTENDED_RESEARCH_ELIGIBLE":
        12.0,

    "PROMOTE":
        10.0,

    "KEEP_TESTING":
        0.0,

    "DEGRADE":
        -20.0,

    "RETIRE":
        -1000.0,
}


class ResearchPortfolioOptimizer:

    MAX_CANDIDATES = 20


    def optimize(
        self,
        candidates,
        *,
        correlation_graph=None,
        temperature=10.0,
    ):

        candidates = tuple(
            candidates
        )


        if not candidates:

            raise ValueError(
                "At least one research candidate is required."
            )


        if len(
            candidates
        ) > self.MAX_CANDIDATES:

            raise ValueError(
                "Research optimizer candidate limit exceeded."
            )


        correlations = {}


        if correlation_graph:

            for edge in correlation_graph.get(
                "edges",
                ()
            ):

                correlation = edge.get(
                    "correlation"
                )


                if correlation is None:

                    continue


                left = edge[
                    "left"
                ]

                right = edge[
                    "right"
                ]


                correlations[
                    (
                        left,
                        right,
                    )
                ] = abs(
                    float(
                        correlation
                    )
                )


                correlations[
                    (
                        right,
                        left,
                    )
                ] = abs(
                    float(
                        correlation
                    )
                )


        rows = []


        symbols = [
            str(
                candidate.get(
                    "symbol",
                    ""
                )
            )

            for candidate
            in candidates
        ]


        for index, candidate in enumerate(
            candidates
        ):

            candidate = dict(
                candidate
            )


            candidate_id = str(
                candidate.get(
                    "candidate_id",
                    "candidate_"
                    + str(
                        index
                    ),
                )
            )


            state = str(
                candidate.get(
                    "validation_state",
                    "KEEP_TESTING",
                )
            ).upper()


            quality = float(
                candidate.get(
                    "quality_score",
                    0.0,
                )
            )


            symbol = str(
                candidate.get(
                    "symbol",
                    "",
                )
            )


            peer_correlations = []


            if symbol:

                for other_symbol in symbols:

                    if (
                        not other_symbol
                        or other_symbol
                        == symbol
                    ):

                        continue


                    value = correlations.get(
                        (
                            symbol,
                            other_symbol,
                        )
                    )


                    if value is not None:

                        peer_correlations.append(
                            value
                        )


            correlation_penalty = (
                (
                    sum(
                        peer_correlations
                    )
                    / len(
                        peer_correlations
                    )
                )
                * 20.0

                if peer_correlations

                else 0.0
            )


            adjusted = (
                quality
                + STATE_BONUS.get(
                    state,
                    0.0,
                )
                - correlation_penalty
            )


            eligible = (
                state != "RETIRE"
            )


            rows.append(
                {
                    "candidate_id":
                        candidate_id,

                    "symbol":
                        symbol,

                    "validation_state":
                        state,

                    "quality_score":
                        quality,

                    "correlation_penalty":
                        correlation_penalty,

                    "adjusted_research_score":
                        adjusted,

                    "eligible":
                        eligible,
                }
            )


        eligible_rows = [
            row

            for row in rows

            if row[
                "eligible"
            ]
        ]


        if not eligible_rows:

            raise ValueError(
                "All candidates are retired."
            )


        temperature = max(
            0.001,
            float(
                temperature
            ),
        )


        maximum = max(
            row[
                "adjusted_research_score"
            ]

            for row in eligible_rows
        )


        masses = {
            row[
                "candidate_id"
            ]:
                math.exp(
                    (
                        row[
                            "adjusted_research_score"
                        ]
                        - maximum
                    )
                    / temperature
                )

            for row in eligible_rows
        }


        total = sum(
            masses.values()
        )


        weights = {
            key:
                (
                    value
                    / total
                )

            for key, value
            in masses.items()
        }


        for row in rows:

            row[
                "research_weight"
            ] = weights.get(
                row[
                    "candidate_id"
                ],
                0.0,
            )


        rows.sort(
            key=lambda row:
                row[
                    "research_weight"
                ],
            reverse=True,
        )


        hhi = sum(
            weight
            * weight

            for weight in weights.values()
        )


        return {
            "success":
                True,

            "ranking":
                tuple(
                    rows
                ),

            "research_weights":
                weights,

            "hhi":
                hhi,

            "candidate_count":
                len(
                    rows
                ),

            "v5_validation_states_respected":
                True,

            "research_weights_drive_broker_capital":
                False,

            "automatic_capital_allocation":
                False,

            "automatic_portfolio_rebalance":
                False,

            "automatic_broker_order":
                False,

            "live_execution":
                False,

            "research_only":
                True,
        }


research_portfolio_optimizer = (
    ResearchPortfolioOptimizer()
)
'''
)


# ============================================================
# 12. V8 STATUS
# ============================================================

write(
    STATUS,
    r'''
from __future__ import annotations

from omni.core_integrity import (
    verify_protected_core,
)


def trading_v8_status():

    core = verify_protected_core()


    return {
        "protected_core":
            core.ok,

        "research_only":
            True,

        "paper_only":
            True,

        "live_execution":
            False,

        "governed_capture_plans":
            True,

        "expiry_aware_capture_plans":
            True,

        "nearest_expiry_capture":
            True,

        "explicit_expiry_capture":
            True,

        "max_expiries_per_plan":
            4,

        "session_aware_collector":
            True,

        "interval_aware_collector":
            True,

        "collector_state_persistence":
            True,

        "background_collection":
            False,

        "explicit_collector_run":
            True,

        "real_fyers_market_data":
            True,

        "v7_history_store_reused":
            True,

        "historical_feature_dataset":
            True,

        "rolling_iv_rank":
            True,

        "rolling_iv_percentile":
            True,

        "delta_oi_features":
            True,

        "pcr_change_features":
            True,

        "skew_change_features":
            True,

        "oi_imbalance_features":
            True,

        "feature_lookahead":
            False,

        "underlying_futures_options_sync":
            True,

        "derivatives_regime_datasets":
            True,

        "v4_derivatives_evolution_adapter":
            True,

        "v5_candidate_validation_adapter":
            True,

        "v5_walk_forward_adapter":
            True,

        "nautilus_c3_derivatives_adapter":
            True,

        "cross_asset_regime_graph":
            True,

        "cross_asset_minimum_history_enforced":
            True,

        "research_portfolio_optimizer":
            True,

        "research_weights_drive_broker_capital":
            False,

        "automatic_execution_profile_selection":
            False,

        "automatic_strategy_promotion":
            False,

        "automatic_registry_mutation":
            False,

        "automatic_capital_allocation":
            False,

        "automatic_portfolio_rebalance":
            False,

        "automatic_broker_order":
            False,

        "production_self_modification":
            False,

        "single_leg_naked_option_short":
            False,

        "v5_authoritative":
            True,

        "nautilus_c3_preserved":
            True,

        "trading_v7_preserved":
            True,
    }
'''
)


# ============================================================
# 13. MAIN APIs
# ============================================================

main_source = MAIN.read_text(
    encoding="utf-8"
)


if (
    "def jarvis_trading_v8_status("
    not in main_source
):

    main_source += r'''


def jarvis_trading_v8_status():

    from omni.trading_intelligence.trading_v8_status import (
        trading_v8_status,
    )

    return trading_v8_status()


def jarvis_derivatives_capture_plan(
    plan_id,
    symbol,
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

    from omni.trading_intelligence.derivatives_capture_plans import (
        build_capture_plan,
    )

    return build_capture_plan(
        plan_id,
        symbol,
        strikecount=strikecount,
        greeks=greeks,
        expiry_mode=expiry_mode,
        expiry_timestamps=expiry_timestamps,
        interval_minutes=interval_minutes,
        session_start=session_start,
        session_end=session_end,
        timezone=timezone,
        enabled=enabled,
        max_captures_per_run=max_captures_per_run,
    )


def jarvis_save_derivatives_capture_plan(
    plan,
):

    from omni.trading_intelligence.derivatives_capture_plans import (
        capture_plan_store,
    )

    return capture_plan_store.save(
        plan
    )


def jarvis_list_derivatives_capture_plans():

    from omni.trading_intelligence.derivatives_capture_plans import (
        capture_plan_store,
    )

    return capture_plan_store.list()


def jarvis_run_derivatives_collector(
    now=None,
    dry_run=False,
    timeout=30,
    max_plans=10,
):

    from omni.trading_intelligence.derivatives_session_collector import (
        derivatives_session_collector,
    )

    return derivatives_session_collector.collect_due(
        now=now,
        dry_run=dry_run,
        timeout=timeout,
        max_plans=max_plans,
    )


def jarvis_build_derivatives_feature_dataset(
    symbol,
    limit=1000,
):

    from omni.trading_intelligence.derivatives_feature_dataset import (
        derivatives_feature_dataset_builder,
    )

    return derivatives_feature_dataset_builder.build(
        symbol,
        limit=limit,
    )


def jarvis_build_synchronized_derivatives_dataset(
    symbol,
    underlying_bars,
    futures_bars,
    limit=1000,
    max_chain_age_seconds=300,
):

    from omni.trading_intelligence.derivatives_feature_dataset import (
        derivatives_feature_dataset_builder,
    )

    return derivatives_feature_dataset_builder.synchronized(
        symbol,
        underlying_bars,
        futures_bars,
        limit=limit,
        max_chain_age_seconds=max_chain_age_seconds,
    )


def jarvis_build_derivatives_regime_datasets(
    bars,
    feature_rows,
):

    from omni.trading_intelligence.derivatives_feature_dataset import (
        derivatives_feature_dataset_builder,
    )

    return derivatives_feature_dataset_builder.regime_datasets(
        bars,
        feature_rows,
    )


def jarvis_v4_evolve_derivatives(
    strategy_id,
    regime_datasets,
    base_config,
    candidate_count=8,
    random_seed=1,
):

    from omni.trading_intelligence.derivatives_v4_adapter import (
        evolve_derivatives_strategy,
    )

    return evolve_derivatives_strategy(
        strategy_id,
        regime_datasets,
        base_config,
        candidate_count=candidate_count,
        random_seed=random_seed,
    )


def jarvis_v5_validate_derivatives(
    candidate,
    bars,
    base_config,
    regime_datasets=None,
    monte_carlo_iterations=500,
    random_seed=1,
):

    from omni.trading_intelligence.derivatives_v5_adapter import (
        validate_derivatives_candidate,
    )

    return validate_derivatives_candidate(
        candidate,
        bars,
        base_config,
        regime_datasets=regime_datasets,
        monte_carlo_iterations=monte_carlo_iterations,
        random_seed=random_seed,
    )


def jarvis_v5_walk_forward_derivatives(
    bars,
    strategy,
    config,
    train_size,
    validation_size,
    test_size,
    step=None,
):

    from omni.trading_intelligence.derivatives_v5_adapter import (
        walk_forward_derivatives,
    )

    return walk_forward_derivatives(
        bars,
        strategy,
        config,
        train_size=train_size,
        validation_size=validation_size,
        test_size=test_size,
        step=step,
    )


def jarvis_nautilus_validate_derivatives_portfolio(
    portfolio,
    v5_report=None,
    train_size=None,
    validation_size=None,
    test_size=None,
    step=None,
    timeout=180,
):

    from omni.trading_intelligence.derivatives_nautilus_adapter import (
        validate_derivatives_portfolio,
    )

    return validate_derivatives_portfolio(
        portfolio,
        v5_report=v5_report,
        train_size=train_size,
        validation_size=validation_size,
        test_size=test_size,
        step=step,
        timeout=timeout,
    )


def jarvis_cross_asset_regime_graph(
    symbols,
    feature="atm_iv",
    lookback=252,
    min_overlap=3,
    max_gap_seconds=900,
    edge_threshold=0.40,
):

    from omni.trading_intelligence.cross_asset_regime_graph import (
        cross_asset_regime_graph,
    )

    return cross_asset_regime_graph.build(
        symbols,
        feature=feature,
        lookback=lookback,
        min_overlap=min_overlap,
        max_gap_seconds=max_gap_seconds,
        edge_threshold=edge_threshold,
    )


def jarvis_research_portfolio_optimize(
    candidates,
    correlation_graph=None,
    temperature=10.0,
):

    from omni.trading_intelligence.research_portfolio_optimizer import (
        research_portfolio_optimizer,
    )

    return research_portfolio_optimizer.optimize(
        candidates,
        correlation_graph=correlation_graph,
        temperature=temperature,
    )
'''


    MAIN.write_text(
        main_source,
        encoding="utf-8",
        newline="\n",
    )


# ============================================================
# 14. WORKSTATION STATUS
# ============================================================

app_source = APP.read_text(
    encoding="utf-8"
)


if (
    "def jarvis_trading_v8_payload("
    not in app_source
):

    app_source += r'''


def jarvis_trading_v8_payload():

    from omni.trading_intelligence.trading_v8_status import (
        trading_v8_status,
    )


    try:

        return {
            "success":
                True,

            "status":
                trading_v8_status(),
        }


    except Exception as exc:

        return {
            "success":
                False,

            "error":
                (
                    type(
                        exc
                    ).__name__
                    + ": "
                    + str(
                        exc
                    )
                ),
        }
'''


    APP.write_text(
        app_source,
        encoding="utf-8",
        newline="\n",
    )


# ============================================================
# 15. V8 TESTS
# ============================================================

write(
    TEST,
    r'''
import tempfile
import unittest

from datetime import (
    datetime,
    timedelta,
    timezone,
)

from pathlib import (
    Path,
)

from unittest.mock import (
    patch,
)


import main


from omni.core_integrity import (
    verify_protected_core,
)

from omni.trading_intelligence.cross_asset_regime_graph import (
    CrossAssetRegimeGraph,
)

from omni.trading_intelligence.derivatives_capture_plans import (
    CapturePlanStore,
    build_capture_plan,
)

from omni.trading_intelligence.derivatives_feature_dataset import (
    DerivativesFeatureDatasetBuilder,
)

from omni.trading_intelligence.derivatives_history_store import (
    DerivativesHistoryStore,
)

from omni.trading_intelligence.derivatives_session_collector import (
    CaptureStateStore,
    DerivativesSessionCollector,
)

from omni.trading_intelligence.research_portfolio_optimizer import (
    ResearchPortfolioOptimizer,
)


NOW = datetime(
    2026,
    8,
    18,
    10,
    0,
    tzinfo=timezone.utc,
)


def snapshot(
    snapshot_id,
    symbol,
    minute,
    *,
    atm_iv,
    call_oi,
    put_oi,
    pcr=None,
    skew=0.0,
):

    if pcr is None:

        pcr = (
            put_oi
            / call_oi
        )


    return {
        "snapshot_id":
            snapshot_id,

        "symbol":
            symbol,

        "captured_at":
            (
                NOW
                + timedelta(
                    minutes=minute
                )
            ).isoformat(),

        "selected_expiry":
            "1787047800",

        "strikecount":
            5,

        "greeks_requested":
            True,

        "spot":
            24000
            + minute,

        "call_oi":
            call_oi,

        "put_oi":
            put_oi,

        "pcr_oi":
            pcr,

        "atm_strike":
            24000,

        "atm_call_iv":
            atm_iv,

        "atm_put_iv":
            atm_iv,

        "atm_iv":
            atm_iv,

        "atm_skew":
            skew,

        "expiry_data":
            (),

        "raw_response":
            {
                "s":
                    "ok"
            },

        "provider":
            "test",

        "sdk_version":
            "3.1.16",

        "legs":
            (),
    }


class TradingIntelligenceV8Tests(
    unittest.TestCase
):

    def test_core(
        self,
    ):

        self.assertTrue(
            verify_protected_core().ok
        )


    def test_status(
        self,
    ):

        status = (
            main.jarvis_trading_v8_status()
        )


        self.assertTrue(
            status[
                "governed_capture_plans"
            ]
        )


        self.assertTrue(
            status[
                "historical_feature_dataset"
            ]
        )


        self.assertTrue(
            status[
                "cross_asset_regime_graph"
            ]
        )


        self.assertFalse(
            status[
                "background_collection"
            ]
        )


        self.assertFalse(
            status[
                "live_execution"
            ]
        )


    def test_plan_builder(
        self,
    ):

        plan = build_capture_plan(
            "nifty",
            "NSE:NIFTY50-INDEX",
            interval_minutes=5,
        )


        self.assertEqual(
            plan[
                "expiry_mode"
            ],
            "nearest",
        )


        self.assertTrue(
            plan[
                "read_only"
            ]
        )


    def test_explicit_expiry_limit(
        self,
    ):

        with self.assertRaises(
            ValueError
        ):

            build_capture_plan(
                "x",
                "NSE:NIFTY50-INDEX",
                expiry_mode="explicit",
                expiry_timestamps=(
                    "1",
                    "2",
                    "3",
                    "4",
                    "5",
                ),
            )


    def test_plan_store(
        self,
    ):

        with tempfile.TemporaryDirectory() as tmp:

            store = CapturePlanStore(
                Path(
                    tmp
                )
                / "plans.json"
            )


            plan = build_capture_plan(
                "nifty",
                "NSE:NIFTY50-INDEX",
            )


            result = store.save(
                plan
            )


            self.assertTrue(
                result[
                    "success"
                ]
            )


            self.assertEqual(
                len(
                    store.list()
                ),
                1,
            )


    def test_collector_dry_run_no_network(
        self,
    ):

        with tempfile.TemporaryDirectory() as tmp:

            plan_store = CapturePlanStore(
                Path(
                    tmp
                )
                / "plans.json"
            )


            state_store = CaptureStateStore(
                Path(
                    tmp
                )
                / "state.json"
            )


            plan = build_capture_plan(
                "test",
                "NSE:NIFTY50-INDEX",
                session_start="00:00",
                session_end="23:59",
                timezone="UTC",
            )


            plan_store.save(
                plan
            )


            calls = []


            def fetcher(
                *args,
                **kwargs,
            ):

                calls.append(
                    (
                        args,
                        kwargs,
                    )
                )

                raise AssertionError(
                    "Network fetcher must not run during dry-run."
                )


            collector = DerivativesSessionCollector(
                plan_store=plan_store,
                state_store=state_store,
                fetcher=fetcher,
            )


            result = collector.collect_due(
                now=NOW,
                dry_run=True,
            )


            self.assertEqual(
                len(
                    calls
                ),
                0,
            )


            self.assertEqual(
                result[
                    "results"
                ][
                    0
                ][
                    "status"
                ],
                "DRY_RUN_DUE",
            )


    def test_collector_fake_capture_and_interval(
        self,
    ):

        with tempfile.TemporaryDirectory() as tmp:

            plan_store = CapturePlanStore(
                Path(
                    tmp
                )
                / "plans.json"
            )


            state_store = CaptureStateStore(
                Path(
                    tmp
                )
                / "state.json"
            )


            plan = build_capture_plan(
                "test",
                "NSE:NIFTY50-INDEX",
                interval_minutes=5,
                session_start="00:00",
                session_end="23:59",
                timezone="UTC",
            )


            plan_store.save(
                plan
            )


            calls = []


            def fetcher(
                symbol,
                **kwargs,
            ):

                calls.append(
                    (
                        symbol,
                        kwargs,
                    )
                )


                return {
                    "success":
                        True,

                    "snapshot": {
                        "snapshot_id":
                            "fake-1",
                    },

                    "live_execution":
                        False,
                }


            collector = DerivativesSessionCollector(
                plan_store=plan_store,
                state_store=state_store,
                fetcher=fetcher,
            )


            first = collector.collect_due(
                now=NOW,
            )


            self.assertEqual(
                first[
                    "results"
                ][
                    0
                ][
                    "status"
                ],
                "CAPTURED",
            )


            second = collector.collect_due(
                now=
                    NOW
                    + timedelta(
                        minutes=2
                    ),
            )


            self.assertEqual(
                second[
                    "results"
                ][
                    0
                ][
                    "status"
                ],
                "NOT_DUE",
            )


            self.assertEqual(
                len(
                    calls
                ),
                1,
            )


    def test_feature_dataset_no_lookahead(
        self,
    ):

        with tempfile.TemporaryDirectory() as tmp:

            store = DerivativesHistoryStore(
                Path(
                    tmp
                )
                / "history.sqlite3"
            )


            store.save(
                snapshot(
                    "a",
                    "A",
                    0,
                    atm_iv=10,
                    call_oi=100,
                    put_oi=100,
                )
            )


            store.save(
                snapshot(
                    "b",
                    "A",
                    1,
                    atm_iv=20,
                    call_oi=110,
                    put_oi=130,
                )
            )


            builder = DerivativesFeatureDatasetBuilder(
                store=store
            )


            result = builder.build(
                "A"
            )


            rows = result[
                "rows"
            ]


            self.assertEqual(
                len(
                    rows
                ),
                2,
            )


            self.assertIsNone(
                rows[
                    0
                ][
                    "delta_call_oi"
                ]
            )


            self.assertEqual(
                rows[
                    1
                ][
                    "delta_call_oi"
                ],
                10,
            )


            self.assertEqual(
                rows[
                    1
                ][
                    "delta_put_oi"
                ],
                30,
            )


            self.assertFalse(
                result[
                    "future_data_leakage"
                ]
            )


    def test_regime_dataset_builder(
        self,
    ):

        builder = DerivativesFeatureDatasetBuilder()


        features = (
            {
                "captured_at":
                    NOW.isoformat(),

                "regime": {
                    "regime":
                        "R1",
                },
            },

            {
                "captured_at":
                    (
                        NOW
                        + timedelta(
                            minutes=2
                        )
                    ).isoformat(),

                "regime": {
                    "regime":
                        "R2",
                },
            },
        )


        bars = [
            {
                "timestamp":
                    NOW
                    + timedelta(
                        minutes=index
                    ),

                "close":
                    100
                    + index,
            }

            for index
            in range(
                4
            )
        ]


        result = builder.regime_datasets(
            bars,
            features,
        )


        self.assertIn(
            "R1",
            result,
        )


        self.assertIn(
            "R2",
            result,
        )


    def test_cross_asset_graph(
        self,
    ):

        with tempfile.TemporaryDirectory() as tmp:

            store = DerivativesHistoryStore(
                Path(
                    tmp
                )
                / "history.sqlite3"
            )


            for index in range(
                4
            ):

                store.save(
                    snapshot(
                        "a"
                        + str(
                            index
                        ),
                        "A",
                        index,
                        atm_iv=
                            10
                            + index,
                        call_oi=
                            100
                            + index,
                        put_oi=
                            100
                            + index,
                    )
                )


                store.save(
                    snapshot(
                        "b"
                        + str(
                            index
                        ),
                        "B",
                        index,
                        atm_iv=
                            20
                            + index * 2,
                        call_oi=
                            100
                            + index,
                        put_oi=
                            100
                            + index,
                    )
                )


            builder = DerivativesFeatureDatasetBuilder(
                store=store
            )


            graph = CrossAssetRegimeGraph(
                dataset_builder=builder
            ).build(
                (
                    "A",
                    "B",
                ),
                min_overlap=3,
                edge_threshold=0.5,
            )


            self.assertEqual(
                len(
                    graph[
                        "edges"
                    ]
                ),
                1,
            )


            self.assertTrue(
                graph[
                    "edges"
                ][
                    0
                ][
                    "material_edge"
                ]
            )


    def test_research_optimizer(
        self,
    ):

        optimizer = ResearchPortfolioOptimizer()


        result = optimizer.optimize(
            (
                {
                    "candidate_id":
                        "a",

                    "symbol":
                        "A",

                    "validation_state":
                        "PORTFOLIO_RESEARCH_ELIGIBLE",

                    "quality_score":
                        50,
                },

                {
                    "candidate_id":
                        "b",

                    "symbol":
                        "B",

                    "validation_state":
                        "KEEP_TESTING",

                    "quality_score":
                        40,
                },
            )
        )


        self.assertAlmostEqual(
            sum(
                result[
                    "research_weights"
                ].values()
            ),
            1.0,
        )


        self.assertFalse(
            result[
                "research_weights_drive_broker_capital"
            ]
        )


        self.assertFalse(
            result[
                "automatic_capital_allocation"
            ]
        )


    def test_v4_adapter_exact_passthrough(
        self,
    ):

        fake = {
            "candidate":
                "ok"
        }


        with patch.object(
            main,
            "jarvis_evolve_strategy",
            return_value=fake,
        ) as mocked:

            result = (
                main.jarvis_v4_evolve_derivatives(
                    "strategy",
                    {
                        "R":
                            ()
                    },
                    {
                        "capital":
                            100000
                    },
                    candidate_count=4,
                    random_seed=7,
                )
            )


            mocked.assert_called_once()


            self.assertEqual(
                result[
                    "v4_result"
                ],
                fake,
            )


            self.assertFalse(
                result[
                    "automatic_strategy_promotion"
                ]
            )


    def test_v5_adapter_exact_passthrough(
        self,
    ):

        fake = {
            "recommendation": {
                "recommendation":
                    "KEEP_TESTING"
            }
        }


        with patch.object(
            main,
            "jarvis_trading_validate_candidate",
            return_value=fake,
        ) as mocked:

            result = (
                main.jarvis_v5_validate_derivatives(
                    {
                        "id":
                            "c"
                    },
                    (),
                    {},
                    regime_datasets={
                        "R":
                            ()
                    },
                )
            )


            mocked.assert_called_once()


            self.assertTrue(
                result[
                    "v5_authoritative"
                ]
            )


            self.assertFalse(
                result[
                    "automatic_strategy_promotion"
                ]
            )


    def test_nautilus_adapter_exact_passthrough(
        self,
    ):

        fake = {
            "success":
                True,

            "live_execution":
                False,
        }


        with patch.object(
            main,
            "jarvis_nautilus_portfolio_backtest",
            return_value=fake,
        ) as mocked:

            result = (
                main
                .jarvis_nautilus_validate_derivatives_portfolio(
                    {
                        "strategies":
                            ()
                    }
                )
            )


            mocked.assert_called_once()


            self.assertEqual(
                result[
                    "mode"
                ],
                "backtest",
            )


            self.assertFalse(
                result[
                    "live_execution"
                ]
            )


    def test_v7_preserved(
        self,
    ):

        status = (
            main.jarvis_trading_v7_status()
        )


        self.assertTrue(
            status[
                "historical_chain_store"
            ]
        )


        self.assertFalse(
            status[
                "live_execution"
            ]
        )


    def test_c3_preserved(
        self,
    ):

        status = (
            main.jarvis_nautilus_c3_status()
        )


        self.assertTrue(
            status[
                "single_event_driven_engine"
            ]
        )


        self.assertFalse(
            status[
                "live_execution"
            ]
        )


    def test_public_apis(
        self,
    ):

        names = (
            "jarvis_trading_v8_status",
            "jarvis_derivatives_capture_plan",
            "jarvis_save_derivatives_capture_plan",
            "jarvis_list_derivatives_capture_plans",
            "jarvis_run_derivatives_collector",
            "jarvis_build_derivatives_feature_dataset",
            "jarvis_build_synchronized_derivatives_dataset",
            "jarvis_build_derivatives_regime_datasets",
            "jarvis_v4_evolve_derivatives",
            "jarvis_v5_validate_derivatives",
            "jarvis_v5_walk_forward_derivatives",
            "jarvis_nautilus_validate_derivatives_portfolio",
            "jarvis_cross_asset_regime_graph",
            "jarvis_research_portfolio_optimize",
        )


        for name in names:

            self.assertTrue(
                callable(
                    getattr(
                        main,
                        name,
                    )
                )
            )


if __name__ == "__main__":

    unittest.main()
'''
)


# ============================================================
# 16. COMPILE V8
# ============================================================

print()
print(
    "Checking Trading Intelligence V8 syntax..."
)


r = run(
    MAIN_PY,
    "-m",
    "py_compile",

    str(
        CAPTURE_PLANS
    ),

    str(
        COLLECTOR
    ),

    str(
        DATASET
    ),

    str(
        V4_ADAPTER
    ),

    str(
        V5_ADAPTER
    ),

    str(
        NAUTILUS_ADAPTER
    ),

    str(
        REGIME_GRAPH
    ),

    str(
        OPTIMIZER
    ),

    str(
        STATUS
    ),

    str(
        MAIN
    ),

    str(
        APP
    ),

    str(
        TEST
    ),
)


if r.returncode:

    print(
        "V8 COMPILE FAILURE"
    )

    rollback()

    sys.exit(1)


print(
    "Trading V8 syntax: PASS"
)


# ============================================================
# 17. PROTECTED CORE
# ============================================================

for relative, before in (
    PROTECTED.items()
):

    if sha(
        ROOT / relative
    ) != before:

        print(
            "PROTECTED CORE MODIFIED:",
            relative,
        )

        rollback()

        sys.exit(1)


print(
    "Protected Core hashes: PASS"
)


# ============================================================
# 18. STATUS / SAFETY
# ============================================================

print()
print(
    "Checking Trading V8 architecture..."
)


r = run(
    MAIN_PY,
    "-c",
    (
        "import main;"
        "s=main.jarvis_trading_v8_status();"
        "assert s['governed_capture_plans'];"
        "assert s['expiry_aware_capture_plans'];"
        "assert s['session_aware_collector'];"
        "assert s['historical_feature_dataset'];"
        "assert s['v4_derivatives_evolution_adapter'];"
        "assert s['v5_candidate_validation_adapter'];"
        "assert s['nautilus_c3_derivatives_adapter'];"
        "assert s['cross_asset_regime_graph'];"
        "assert s['research_portfolio_optimizer'];"
        "assert s['feature_lookahead'] is False;"
        "assert s['background_collection'] is False;"
        "assert s['research_weights_drive_broker_capital'] is False;"
        "assert s['live_execution'] is False;"
        "assert s['automatic_broker_order'] is False;"
        "print('Governed capture plans: PASS');"
        "print('Expiry-aware collector: PASS');"
        "print('Historical feature dataset: PASS');"
        "print('V4 adapter: PASS');"
        "print('V5 adapter: PASS');"
        "print('Nautilus C3 adapter: PASS');"
        "print('Cross-asset regime graph: PASS');"
        "print('Research portfolio optimizer: PASS');"
        "print('Background collection: BLOCKED');"
        "print('Broker execution: BLOCKED');"
        "print('V8 architecture: PASS')"
    ),
)


if r.returncode:

    print(
        "V8 ARCHITECTURE FAILURE"
    )

    rollback()

    sys.exit(1)


# ============================================================
# 19. VERIFY REAL STORED HISTORY — NO FYERS REQUEST
# ============================================================

print()
print(
    "Checking existing real FYERS history..."
)


r = run(
    MAIN_PY,
    "-c",
    (
        "import main;"
        "h=main.jarvis_derivatives_history("
        "'NSE:NIFTY50-INDEX',limit=10);"
        "assert len(h)>=1;"
        "d=main.jarvis_build_derivatives_feature_dataset("
        "'NSE:NIFTY50-INDEX',limit=10);"
        "assert d['row_count']>=1;"
        "assert d['future_data_leakage'] is False;"
        "assert d['rows'][-1]['atm_iv'] is not None;"
        "print('Real stored snapshot: PASS');"
        "print('Real feature conversion: PASS');"
        "print('Installer FYERS network request: NO');"
        "print('Future-data leakage: BLOCKED')"
    ),
)


if r.returncode:

    print(
        "V8 REAL-HISTORY FAILURE"
    )

    rollback()

    sys.exit(1)


# ============================================================
# 20. TARGETED REGRESSION
# ============================================================

print()
print(
    "Running Trading Intelligence V8 targeted regression..."
)


r = run(
    MAIN_PY,
    "-m",
    "unittest",

    "tests.test_trading_intelligence_v8",
    "tests.test_trading_intelligence_v7",

    "tests.test_nautilus_phase_c3",
    "tests.test_nautilus_phase_c2",
    "tests.test_nautilus_research_kernel",

    "tests.test_trading_intelligence_v6",
    "tests.test_trading_intelligence_v5",
    "tests.test_trading_intelligence_v4",
    "tests.test_trading_intelligence_v3",
    "tests.test_trading_intelligence_v2",
    "tests.test_trading_v1_1_fyers_bridge",
    "tests.test_trading_intelligence_v1",

    "-q",
    timeout=480,
)


if r.returncode:

    print(
        "TARGETED REGRESSION FAILURE"
    )

    rollback()

    sys.exit(1)


# ============================================================
# 21. FULL REGRESSION
# ============================================================

print()
print(
    "Running full JARVIS regression..."
)


r = run(
    MAIN_PY,
    "-m",
    "unittest",
    "discover",
    "-s",
    "tests",
    "-q",
    timeout=540,
)


if r.returncode:

    print(
        "FULL REGRESSION FAILURE"
    )

    rollback()

    sys.exit(1)


# ============================================================
# 22. FINAL PROTECTED CORE
# ============================================================

for relative, before in (
    PROTECTED.items()
):

    if sha(
        ROOT / relative
    ) != before:

        print(
            "FINAL PROTECTED CORE CHANGE:",
            relative,
        )

        rollback()

        sys.exit(1)


r = run(
    MAIN_PY,
    "-c",
    (
        "import main;"
        "from omni.core_integrity import verify_protected_core;"
        "c=verify_protected_core();"
        "assert c.ok,(c.changed,c.missing);"
        "v5=main.jarvis_trading_v5_status();"
        "v6=main.jarvis_trading_v6_status();"
        "v7=main.jarvis_trading_v7_status();"
        "v8=main.jarvis_trading_v8_status();"
        "c3=main.jarvis_nautilus_c3_status();"
        "assert v5['walk_forward_validation'];"
        "assert v6['paper_only'];"
        "assert v7['historical_chain_store'];"
        "assert v8['historical_feature_dataset'];"
        "assert c3['single_event_driven_engine'];"
        "assert v8['live_execution'] is False;"
        "assert v8['automatic_broker_order'] is False;"
        "print('Final Protected Core: PASS');"
        "print('Trading V5: PRESERVED');"
        "print('Trading V6: PRESERVED');"
        "print('Trading V7: PRESERVED');"
        "print('Nautilus C3: PRESERVED');"
        "print('Trading V8: PASS')"
    ),
)


if r.returncode:

    rollback()

    sys.exit(1)


r = run(
    MAIN_PY,
    "-m",
    "unittest",
    (
        "tests.test_computer_operator_v2."
        "ComputerOperatorV2Tests.test_dom_provider"
    ),
    "-q",
)


if r.returncode:

    print(
        "FINAL BROWSER TEST FAILURE"
    )

    rollback()

    sys.exit(1)


print(
    "Final browser DOM test: PASS"
)


# ============================================================
# 23. SUCCESS
# ============================================================

status = run(
    MAIN_PY,
    "-c",
    (
        "import main,pprint;"
        "pprint.pp(main.jarvis_trading_v8_status())"
    ),
    capture=True,
)


print()
print("=" * 80)
print("JARVIS TRADING INTELLIGENCE V8 SUCCESS")
print("=" * 80)

print()
print("HISTORICAL COLLECTION")
print("Governed capture plans: ACTIVE")
print("Nearest-expiry capture: ACTIVE")
print("Explicit-expiry capture: ACTIVE")
print("Maximum explicit expiries per plan: 4")
print("Session windows: ACTIVE")
print("Interval due logic: ACTIVE")
print("Collector state persistence: ACTIVE")
print("Manual/explicit collector run: ACTIVE")
print("Background market polling: DISABLED")
print()

print("HISTORICAL FEATURE ENGINE")
print("Real V7 SQLite history: REUSED")
print("Rolling ATM IV rank: ACTIVE")
print("Rolling ATM IV percentile: ACTIVE")
print("ATM IV change: ACTIVE")
print("PCR change: ACTIVE")
print("Call/Put delta-OI: ACTIVE")
print("Skew change: ACTIVE")
print("OI imbalance: ACTIVE")
print("Chronological feature generation: ACTIVE")
print("Future-data leakage: BLOCKED")
print()

print("RESEARCH INTEGRATION")
print("V4 derivatives evolution adapter: ACTIVE")
print("V5 candidate validation adapter: ACTIVE")
print("V5 derivatives walk-forward adapter: ACTIVE")
print("Nautilus C3 derivatives portfolio adapter: ACTIVE")
print("V5 remains authoritative: YES")
print()

print("CROSS-ASSET RESEARCH")
print("Cross-asset regime graph: ACTIVE")
print("Timestamp-tolerance alignment: ACTIVE")
print("Minimum-overlap requirement: ACTIVE")
print("Correlation edges: ACTIVE")
print("Predictive guarantee: NONE")
print()

print("PORTFOLIO RESEARCH")
print("Research optimizer: ACTIVE")
print("Validation-state weighting: ACTIVE")
print("Correlation penalty: ACTIVE")
print("Research HHI: ACTIVE")
print("Research weights -> broker capital: BLOCKED")
print("Automatic allocation: BLOCKED")
print("Automatic rebalance: BLOCKED")
print()

print("GOVERNANCE")
print("Single-leg naked option short: BLOCKED")
print("Automatic strategy promotion: BLOCKED")
print("Automatic registry mutation: BLOCKED")
print("Automatic broker orders: BLOCKED")
print("Live execution: BLOCKED")
print("Production self-modification: BLOCKED")
print()

print("PRESERVED")
print("Trading V1-V7: YES")
print("Nautilus Phase B/C2/C3: YES")
print("Real FYERS history: YES")
print("Browser lock repair: YES")
print("Protected Core: UNCHANGED")
print("Full regression: PASS")
print()

print("STATUS:")
print(
    status.stdout.strip()
)
print()

print("NEXT AFTER V8:")
print("Create first governed NIFTY capture plan")
print("Begin accumulating intraday option-chain history")
print("Add BANKNIFTY / FINNIFTY / SENSEX / commodities")
print("Build cross-asset derivatives history")
print("Then Trading V9:")
print("Historical research campaign orchestration")
print("Derivatives feature backtests at scale")
print("V4 candidate evolution -> V5 validation -> Nautilus C3")
print("Research ensemble portfolio campaigns")
print("Still NO live broker execution")
