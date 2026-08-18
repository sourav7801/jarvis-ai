from __future__ import annotations

import hashlib
import json
import threading

from datetime import (
    datetime,
    timezone,
)

from pathlib import Path


ROOT = (
    Path(__file__)
    .resolve()
    .parents[1]
)

LEDGER = (
    ROOT
    / "data"
    / "operator"
    / "v5_evidence.jsonl"
)


SENSITIVE_KEYS = {
    "password",
    "passwd",
    "secret",
    "secret_id",
    "token",
    "access_token",
    "refresh_token",
    "authorization",
    "cookie",
    "cookies",
}


def _now():

    return datetime.now(
        timezone.utc
    ).isoformat()


def _value(
    obj,
    name,
    default=None,
):

    if isinstance(
        obj,
        dict,
    ):

        return obj.get(
            name,
            default,
        )

    return getattr(
        obj,
        name,
        default,
    )


def _safe(
    value,
):

    if value is None:

        return None


    if isinstance(
        value,
        (
            str,
            int,
            float,
            bool,
        ),
    ):

        return value


    if isinstance(
        value,
        dict,
    ):

        result = {}


        for key, item in value.items():

            key_text = str(
                key
            )


            if key_text.lower() in SENSITIVE_KEYS:

                result[
                    key_text
                ] = "<REDACTED>"

            else:

                result[
                    key_text
                ] = _safe(
                    item
                )


        return result


    if isinstance(
        value,
        (
            list,
            tuple,
            set,
        ),
    ):

        return [
            _safe(
                item
            )

            for item in value
        ]


    return str(
        value
    )


class EvidenceLedger:

    def __init__(
        self,
        path=None,
    ):

        self.path = Path(
            path
            or LEDGER
        )

        self._lock = (
            threading.Lock()
        )


    def record(
        self,
        event,
        **payload,
    ):

        row = {
            "timestamp":
                _now(),

            "event":
                str(
                    event
                ),

            **{
                str(key):
                    _safe(
                        value
                    )

                for key, value
                in payload.items()
            },
        }


        self.path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )


        with self._lock:

            with self.path.open(
                "a",
                encoding="utf-8",
            ) as handle:

                handle.write(
                    json.dumps(
                        row,
                        ensure_ascii=False,
                        default=str,
                    )
                    + "\n"
                )


        return row


    def recent(
        self,
        limit=50,
    ):

        if not self.path.exists():

            return ()


        rows = []


        for line in (
            self.path
            .read_text(
                encoding="utf-8",
                errors="ignore",
            )
            .splitlines()
            [
                -max(
                    1,
                    int(
                        limit
                    )
                ):
            ]
        ):

            try:

                rows.append(
                    json.loads(
                        line
                    )
                )

            except Exception:

                continue


        return tuple(
            rows
        )


class OperatorV5Reliability:

    def __init__(
        self,
        ledger=None,
    ):

        self.ledger = (
            ledger
            or EvidenceLedger()
        )


    @staticmethod
    def _cursor(
        mission,
    ):

        cursor = _value(
            mission,
            "cursor",
            None,
        )


        if isinstance(
            cursor,
            int,
        ):

            return cursor


        state = _value(
            mission,
            "state",
            None,
        )


        cursor = _value(
            state,
            "cursor",
            None,
        )


        return (
            cursor
            if isinstance(
                cursor,
                int,
            )
            else None
        )


    @staticmethod
    def _status(
        mission,
    ):

        status = _value(
            mission,
            "status",
            None,
        )


        if hasattr(
            status,
            "value",
        ):

            status = status.value


        return (
            str(
                status
            )
            if status is not None
            else None
        )


    def snapshot(
        self,
        mission_id,
    ):

        import main


        mission = (
            main
            .jarvis_v4_get_mission(
                mission_id
            )
        )


        result = {
            "mission_id":
                str(
                    mission_id
                ),

            "cursor":
                self._cursor(
                    mission
                ),

            "status":
                self._status(
                    mission
                ),

            "goal":
                _value(
                    mission,
                    "goal",
                    None,
                ),
        }


        self.ledger.record(
            "mission.snapshot",
            **result,
        )


        return result


    def _assert_cursor(
        self,
        before,
        after,
    ):

        left = before.get(
            "cursor"
        )

        right = after.get(
            "cursor"
        )


        regressed = bool(
            isinstance(
                left,
                int,
            )
            and isinstance(
                right,
                int,
            )
            and right < left
        )


        if regressed:

            raise RuntimeError(
                "Mission cursor regression detected."
            )


        return False


    def resume(
        self,
        mission_id,
    ):

        import main


        before = self.snapshot(
            mission_id
        )


        result = (
            main
            .jarvis_v4_resume_mission(
                mission_id
            )
        )


        after = self.snapshot(
            mission_id
        )


        self._assert_cursor(
            before,
            after,
        )


        evidence = self.ledger.record(
            "mission.resume",
            mission_id=
                mission_id,
            cursor_before=
                before.get(
                    "cursor"
                ),
            cursor_after=
                after.get(
                    "cursor"
                ),
            cursor_regressed=
                False,
        )


        return {
            "success":
                True,

            "result":
                result,

            "before":
                before,

            "after":
                after,

            "cursor_regressed":
                False,

            "evidence":
                evidence,
        }


    def apply_replan(
        self,
        mission_id,
        proposal_text,
    ):

        import main


        before = self.snapshot(
            mission_id
        )


        result = (
            main
            .jarvis_v4_apply_replan(
                mission_id,
                proposal_text,
            )
        )


        after = self.snapshot(
            mission_id
        )


        self._assert_cursor(
            before,
            after,
        )


        self.ledger.record(
            "mission.replan",
            mission_id=
                mission_id,
            cursor_before=
                before.get(
                    "cursor"
                ),
            cursor_after=
                after.get(
                    "cursor"
                ),
            cursor_regressed=
                False,
        )


        return {
            "success":
                True,

            "result":
                result,

            "cursor_before":
                before.get(
                    "cursor"
                ),

            "cursor_after":
                after.get(
                    "cursor"
                ),

            "cursor_regressed":
                False,
        }


    def run_goal(
        self,
        goal,
        *,
        hints=None,
        approval_batch_id=None,
    ):

        import main


        self.ledger.record(
            "goal.started",
            goal=
                goal,
        )


        try:

            result = (
                main
                .jarvis_operator_run(
                    goal,
                    hints=hints,
                    approval_batch_id=
                        approval_batch_id,
                )
            )


            self.ledger.record(
                "goal.finished",
                goal=
                    goal,
                result=
                    result,
            )


            return result


        except Exception as exc:

            self.ledger.record(
                "goal.failed",
                goal=
                    goal,
                error=
                    (
                        type(
                            exc
                        ).__name__
                        + ": "
                        + str(
                            exc
                        )
                    ),
            )

            raise


    def verify_file(
        self,
        path,
        *,
        min_bytes=1,
        expected_sha256=None,
    ):

        path = Path(
            path
        )


        exists = path.is_file()


        size = (
            path.stat().st_size
            if exists
            else 0
        )


        digest = None


        if exists:

            digest = hashlib.sha256(
                path.read_bytes()
            ).hexdigest()


        verified = bool(
            exists
            and size
            >= int(
                min_bytes
            )
            and (
                expected_sha256 is None
                or digest
                == str(
                    expected_sha256
                ).lower()
            )
        )


        result = {
            "verified":
                verified,

            "path":
                str(
                    path
                ),

            "exists":
                exists,

            "size":
                size,

            "sha256":
                digest,
        }


        self.ledger.record(
            "verification.file",
            **result,
        )


        return result


    def verify_window(
        self,
        title,
    ):

        from omni.desktop_automation import (
            DesktopAutomation,
        )


        windows = (
            DesktopAutomation()
            .windows()
        )


        needle = str(
            title
        ).lower()


        matches = []


        for window in windows:

            if isinstance(
                window,
                dict,
            ):

                rendered = " ".join(
                    str(
                        value
                    )

                    for value
                    in window.values()
                )

            else:

                rendered = str(
                    window
                )


            if needle in rendered.lower():

                matches.append(
                    rendered
                )


        result = {
            "verified":
                bool(
                    matches
                ),

            "title":
                str(
                    title
                ),

            "matches":
                tuple(
                    matches[
                        :10
                    ]
                ),
        }


        self.ledger.record(
            "verification.window",
            **result,
        )


        return result


    def status(
        self,
    ):

        return {
            "available":
                True,

            "version":
                "5.0",

            "cursor_guard":
                True,

            "resume_evidence":
                True,

            "replan_evidence":
                True,

            "unified_evidence_ledger":
                True,

            "file_verification":
                True,

            "window_verification":
                True,

            "automatic_destructive_escalation":
                False,

            "automatic_replan_execution":
                False,

            "live_trading_execution":
                False,
        }


operator_v5_reliability = (
    OperatorV5Reliability()
)
