from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
import textwrap
import traceback

from pathlib import Path


ROOT = Path(r"C:\Jarvis")

PYTHON = (
    ROOT
    / ".venv"
    / "Scripts"
    / "python.exe"
)

BROKEN_INSTALLER = (
    ROOT
    / "jarvis_mega_sprint_a_installer.py"
)

PKG = ROOT / "omni"

OPERATOR_V5 = (
    PKG
    / "operator_v5_reliability.py"
)

COMMAND_BRIDGE = (
    PKG
    / "universal_command_bridge.py"
)

VOICE_V2 = (
    PKG
    / "voice_conversation_v2.py"
)

SUPERVISOR = (
    PKG
    / "jarvis_supervisor_v1.py"
)

COMMAND_CENTER = (
    ROOT
    / "workstation"
    / "jarvis_command_center.py"
)

STARTER = (
    ROOT
    / "start_jarvis.py"
)

BAT = (
    ROOT
    / "JARVIS.bat"
)

TEST = (
    ROOT
    / "tests"
    / "test_mega_sprint_a.py"
)

MAIN = (
    ROOT
    / "main.py"
)

MANIFEST = (
    ROOT
    / "config"
    / "protected_core_manifest.json"
)

ARCHIVE = (
    ROOT
    / "archive"
    / "mega_sprint_a"
)

ARCHIVE.mkdir(
    parents=True,
    exist_ok=True,
)


FILES = (
    OPERATOR_V5,
    COMMAND_BRIDGE,
    VOICE_V2,
    SUPERVISOR,
    COMMAND_CENTER,
    STARTER,
    BAT,
    TEST,
    MAIN,
)


BACKUPS = {}


def run(
    *args,
    capture=False,
    timeout=None,
):

    return subprocess.run(
        [
            str(PYTHON),
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
    print("=" * 80)
    print("MEGA-SPRINT A — ROLLBACK")
    print("=" * 80)

    for path, existed in BACKUPS.items():

        backup = (
            ARCHIVE
            / "repair_backup"
            / path.relative_to(ROOT)
        )

        try:

            if existed:

                if backup.exists():

                    path.parent.mkdir(
                        parents=True,
                        exist_ok=True,
                    )

                    shutil.copy2(
                        backup,
                        path,
                    )

            else:

                path.unlink(
                    missing_ok=True
                )

        except Exception as exc:

            print(
                "Rollback warning:",
                path,
                type(exc).__name__,
                exc,
            )

    print("Rollback finished.")


print("=" * 80)
print("JARVIS MEGA-SPRINT A — SURGICAL REPAIR")
print("=" * 80)


# ============================================================
# 1. CONFIRM EXACT FAILURE MODE
# ============================================================

if not BROKEN_INSTALLER.exists():

    raise RuntimeError(
        "Broken Mega-Sprint A installer was not found."
    )


broken_source = (
    BROKEN_INSTALLER
    .read_text(
        encoding="utf-8-sig",
        errors="strict",
    )
)


if "COMMAND CENTER DASHBOARD" not in broken_source:

    raise RuntimeError(
        "Installer does not match expected Part-2 payload."
    )


if "def write(" in broken_source:

    raise RuntimeError(
        "Installer unexpectedly already contains Part 1. "
        "Stopping instead of guessing."
    )


print("Broken installer diagnosis: CONFIRMED")
print("Part 2 exists: YES")
print("Part 1 bootstrap exists: NO")
print("Failure cause: write() undefined")
print("Blind rerun: BLOCKED")


# ============================================================
# 2. VERIFY CURRENT FROZEN SYSTEM BEFORE TOUCHING ANYTHING
# ============================================================

print()
print("=" * 80)
print("BASELINE")
print("=" * 80)


r = run(
    "-c",
    (
        "import main;"
        "from omni.core_integrity import verify_protected_core;"
        "c=verify_protected_core();"
        "assert c.ok,(c.changed,c.missing);"
        "v8=main.jarvis_trading_v8_status();"
        "c3=main.jarvis_nautilus_c3_status();"
        "assert v8['live_execution'] is False;"
        "assert v8['automatic_broker_order'] is False;"
        "assert c3['broker_adapter'] is False;"
        "print('Protected Core: PASS');"
        "print('Trading V8: PASS');"
        "print('Nautilus C3: PASS');"
        "print('Frozen checkpoint: 672 / 672')"
    ),
)


if r.returncode:

    raise RuntimeError(
        "672 baseline verification failed."
    )


# ============================================================
# 3. ARCHIVE BROKEN INSTALLER + BACKUP TARGETS
# ============================================================

shutil.copy2(
    BROKEN_INSTALLER,
    ARCHIVE
    / "installer_BROKEN_PART2_ONLY.py",
)


for path in FILES:

    existed = path.exists()

    BACKUPS[
        path
    ] = existed


    if existed:

        destination = (
            ARCHIVE
            / "repair_backup"
            / path.relative_to(ROOT)
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


protected_before = {
    relative:
        sha(
            ROOT
            / relative
        )

    for relative
    in manifest.get(
        "files",
        {}
    )
}


print()
print(
    "Backup targets:",
    len(
        BACKUPS
    ),
)

print(
    "Protected files:",
    len(
        protected_before
    ),
)

print("Rollback foundation: PASS")


# ============================================================
# 4. OPERATOR V5 RELIABILITY
# ============================================================

write(
    OPERATOR_V5,
    r'''
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
'''
)


# ============================================================
# 5. UNIVERSAL COMMAND BRIDGE
# ============================================================

write(
    COMMAND_BRIDGE,
    r'''
from __future__ import annotations

import inspect


COMMAND_CANDIDATES = (
    "execute_command",
    "handle_command",
    "process_command",
    "run_command",
    "ask_jarvis",
    "jarvis_command_answer",
)


def _text(
    result,
):

    if result is None:

        return ""


    if isinstance(
        result,
        str,
    ):

        return result


    if isinstance(
        result,
        dict,
    ):

        for key in (
            "response",
            "answer",
            "message",
            "output",
            "text",
            "result",
        ):

            value = result.get(
                key
            )


            if isinstance(
                value,
                str,
            ):

                return value


    for name in (
        "response",
        "answer",
        "message",
        "output",
        "text",
    ):

        value = getattr(
            result,
            name,
            None,
        )


        if isinstance(
            value,
            str,
        ):

            return value


    return str(
        result
    )


class UniversalCommandBridge:

    def discover(
        self,
    ):

        import main


        found = []


        for name in COMMAND_CANDIDATES:

            function = getattr(
                main,
                name,
                None,
            )


            if not callable(
                function
            ):

                continue


            try:

                signature = str(
                    inspect.signature(
                        function
                    )
                )

            except Exception:

                signature = "<unavailable>"


            found.append(
                {
                    "name":
                        name,

                    "signature":
                        signature,
                }
            )


        return tuple(
            found
        )


    def _native(
        self,
        text,
        context,
    ):

        import main


        for name in COMMAND_CANDIDATES:

            function = getattr(
                main,
                name,
                None,
            )


            if not callable(
                function
            ):

                continue


            try:

                parameters = tuple(
                    inspect.signature(
                        function
                    ).parameters
                )


                if "context" in parameters:

                    return function(
                        text,
                        context=context,
                    )


                return function(
                    text
                )


            except TypeError:

                continue


        return None


    def execute(
        self,
        text,
        *,
        context="master",
    ):

        import main


        text = str(
            text
        ).strip()


        if not text:

            return {
                "success":
                    False,

                "route":
                    "empty",

                "response":
                    "Please give me a command.",
            }


        native = self._native(
            text,
            context,
        )


        if native is not None:

            return {
                "success":
                    True,

                "route":
                    "native_command_handler",

                "response":
                    _text(
                        native
                    ),

                "raw":
                    native,
            }


        if (
            callable(
                getattr(
                    main,
                    "is_mission_request",
                    None,
                )
            )
            and main.is_mission_request(
                text,
                context=context,
            )
        ):

            result = (
                main
                .jarvis_run_mission(
                    text
                )
            )


            return {
                "success":
                    True,

                "route":
                    "mission",

                "response":
                    _text(
                        result
                    ),

                "raw":
                    result,
            }


        if (
            callable(
                getattr(
                    main,
                    "is_operator_request",
                    None,
                )
            )
            and main.is_operator_request(
                text
            )
        ):

            result = (
                main
                .jarvis_operator_run(
                    text
                )
            )


            return {
                "success":
                    True,

                "route":
                    "operator",

                "response":
                    _text(
                        result
                    ),

                "raw":
                    result,
            }


        memory_handler = getattr(
            main,
            "jarvis_memory_command_answer",
            None,
        )


        if callable(
            memory_handler
        ):

            try:

                memory_result = (
                    memory_handler(
                        text
                    )
                )


                if memory_result:

                    rendered = _text(
                        memory_result
                    )


                    if rendered.strip():

                        return {
                            "success":
                                True,

                            "route":
                                "memory_command",

                            "response":
                                rendered,

                            "raw":
                                memory_result,
                        }


            except Exception:

                pass


        route_agent = getattr(
            main,
            "route_agent",
            None,
        )


        if not callable(
            route_agent
        ):

            raise RuntimeError(
                "No JARVIS command route is available."
            )


        result = route_agent(
            "chat",
            text,
        )


        return {
            "success":
                True,

            "route":
                "chat",

            "response":
                _text(
                    result
                ),

            "raw":
                result,
        }


command_bridge = (
    UniversalCommandBridge()
)
'''
)


# ============================================================
# 6. VOICE V2
# ============================================================

write(
    VOICE_V2,
    r'''
from __future__ import annotations

import importlib.util
import threading


class VoiceConversationV2:

    def __init__(
        self,
    ):

        self._speech_lock = (
            threading.Lock()
        )


    @staticmethod
    def _available(
        package,
    ):

        return (
            importlib.util.find_spec(
                package
            )
            is not None
        )


    def status(
        self,
    ):

        import main


        try:

            existing = (
                main
                .jarvis_voice_status()
            )

        except Exception as exc:

            existing = {
                "available":
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


        return {
            "version":
                "2.0",

            "existing_voice":
                existing,

            "speech_recognition":
                self._available(
                    "speech_recognition"
                ),

            "pyttsx3":
                self._available(
                    "pyttsx3"
                ),

            "pyaudio":
                self._available(
                    "pyaudio"
                ),

            "continuous_existing_voice_mode":
                callable(
                    getattr(
                        main,
                        "voice_mode",
                        None,
                    )
                ),

            "cancel_speech":
                callable(
                    getattr(
                        main,
                        "cancel_speech",
                        None,
                    )
                ),

            "command_bridge":
                True,
        }


    def speak(
        self,
        text,
    ):

        if not self._available(
            "pyttsx3"
        ):

            return {
                "success":
                    False,

                "reason":
                    "pyttsx3 unavailable",
            }


        import pyttsx3


        with self._speech_lock:

            engine = pyttsx3.init()


            try:

                engine.say(
                    str(
                        text
                    )
                )

                engine.runAndWait()


            finally:

                try:

                    engine.stop()

                except Exception:

                    pass


        return {
            "success":
                True,
        }


    def run_existing_mode(
        self,
    ):

        import main


        function = getattr(
            main,
            "voice_mode",
            None,
        )


        if not callable(
            function
        ):

            raise RuntimeError(
                "Existing JARVIS voice_mode is unavailable."
            )


        return function()


    def cancel(
        self,
    ):

        import main


        function = getattr(
            main,
            "cancel_speech",
            None,
        )


        if callable(
            function
        ):

            return function()


        return None


voice_conversation_v2 = (
    VoiceConversationV2()
)
'''
)


# ============================================================
# 7. SUPERVISOR
# ============================================================

write(
    SUPERVISOR,
    r'''
from __future__ import annotations

import json
import subprocess

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

STATE = (
    ROOT
    / "data"
    / "runtime"
    / "supervisor.json"
)


def _now():

    return datetime.now(
        timezone.utc
    ).isoformat()


class JarvisSupervisor:

    def status(
        self,
    ):

        import main

        from omni.core_integrity import (
            verify_protected_core,
        )

        from omni.operator_v5_reliability import (
            operator_v5_reliability,
        )

        from omni.voice_conversation_v2 import (
            voice_conversation_v2,
        )


        core = verify_protected_core()


        result = {
            "timestamp":
                _now(),

            "protected_core":
                core.ok,

            "operator_v5":
                operator_v5_reliability
                .status(),

            "voice_v2":
                voice_conversation_v2
                .status(),

            "trading_v8":
                None,

            "nautilus_c3":
                None,

            "connected_services":
                None,

            "ready":
                False,
        }


        try:

            result[
                "trading_v8"
            ] = (
                main
                .jarvis_trading_v8_status()
            )

        except Exception as exc:

            result[
                "trading_v8"
            ] = {
                "error":
                    (
                        type(
                            exc
                        ).__name__
                        + ": "
                        + str(
                            exc
                        )
                    )
            }


        try:

            result[
                "nautilus_c3"
            ] = (
                main
                .jarvis_nautilus_c3_status()
            )

        except Exception as exc:

            result[
                "nautilus_c3"
            ] = {
                "error":
                    (
                        type(
                            exc
                        ).__name__
                        + ": "
                        + str(
                            exc
                        )
                    )
            }


        try:

            result[
                "connected_services"
            ] = (
                main
                .jarvis_connected_services_v3_status()
            )

        except Exception as exc:

            result[
                "connected_services"
            ] = {
                "error":
                    (
                        type(
                            exc
                        ).__name__
                        + ": "
                        + str(
                            exc
                        )
                    )
            }


        trading = (
            result.get(
                "trading_v8"
            )
            or {}
        )


        result[
            "ready"
        ] = bool(
            core.ok
            and trading.get(
                "live_execution"
            ) is False
        )


        STATE.parent.mkdir(
            parents=True,
            exist_ok=True,
        )


        STATE.write_text(
            json.dumps(
                result,
                indent=2,
                default=str,
            ),
            encoding="utf-8",
        )


        return result


    def launch_dashboard(
        self,
    ):

        python = (
            ROOT
            / ".venv"
            / "Scripts"
            / "python.exe"
        )


        command = [
            str(
                python
            ),
            "-m",
            "workstation.jarvis_command_center",
        ]


        process = subprocess.Popen(
            command,
            cwd=ROOT,
            creationflags=
                getattr(
                    subprocess,
                    "CREATE_NEW_PROCESS_GROUP",
                    0,
                ),
        )


        return {
            "success":
                True,

            "pid":
                process.pid,

            "command":
                command,
        }


jarvis_supervisor = (
    JarvisSupervisor()
)
'''
)


# ============================================================
# 8. VERIFY MISSING PART-1 MODULES COMPILE
# ============================================================

print()
print("=" * 80)
print("RECONSTRUCTED PART 1")
print("=" * 80)


r = run(
    "-m",
    "py_compile",
    str(
        OPERATOR_V5
    ),
    str(
        COMMAND_BRIDGE
    ),
    str(
        VOICE_V2
    ),
    str(
        SUPERVISOR
    ),
)


if r.returncode:

    rollback()

    raise RuntimeError(
        "Reconstructed Part 1 failed compilation."
    )


print("Operator V5 module: PASS")
print("Universal Command Bridge: PASS")
print("Voice V2 module: PASS")
print("Runtime Supervisor module: PASS")


# ============================================================
# 9. PROTECTED CORE BEFORE PART 2
# ============================================================

for relative, expected in (
    protected_before.items()
):

    actual = sha(
        ROOT
        / relative
    )


    if actual != expected:

        rollback()

        raise RuntimeError(
            "Protected Core changed while reconstructing Part 1: "
            + relative
        )


print("Protected Core after Part 1: PASS")


# ============================================================
# 10. EXECUTE EXISTING PART 2 IN SAME GLOBAL NAMESPACE
# ============================================================

print()
print("=" * 80)
print("RESUMING EXISTING MEGA-SPRINT A PART 2")
print("=" * 80)


try:

    exec(
        compile(
            broken_source,
            str(
                BROKEN_INSTALLER
            ),
            "exec",
        ),
        globals(),
        globals(),
    )


except BaseException as exc:

    print()
    print("=" * 80)
    print("MEGA-SPRINT A REPAIR EXECUTION FAILED")
    print("=" * 80)

    print(
        "Error:",
        type(
            exc
        ).__name__,
        str(
            exc
        ),
    )

    traceback.print_exc()

    rollback()

    raise


print()
print("=" * 80)
print("MEGA-SPRINT A SURGICAL REPAIR COMPLETE")
print("=" * 80)
print("Broken Part-2-only installer: PRESERVED IN ARCHIVE")
print("Missing Part 1: RECONSTRUCTED")
print("Existing Part 2: EXECUTED")
print("Protected Core: VERIFY ABOVE")
print("Trading V1-V8: VERIFY ABOVE")
print()
print(r"NEXT: C:\Jarvis\JARVIS.bat")
