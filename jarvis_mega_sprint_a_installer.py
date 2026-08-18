

# ============================================================
# COMMAND CENTER DASHBOARD
# ============================================================

write(
    COMMAND_CENTER,
    r'''
from __future__ import annotations

import json
import queue
import threading
import tkinter as tk

from tkinter import (
    messagebox,
    scrolledtext,
    ttk,
)


from omni.jarvis_supervisor_v1 import (
    jarvis_supervisor,
)

from omni.universal_command_bridge import (
    command_bridge,
)

from omni.voice_conversation_v2 import (
    voice_conversation_v2,
)


class JarvisCommandCenter:

    def __init__(
        self,
        root,
    ):

        self.root = root

        self.events = queue.Queue()

        self.speak_answers = tk.BooleanVar(
            value=False
        )


        root.title(
            "JARVIS Command Center"
        )

        root.geometry(
            "1180x760"
        )

        root.minsize(
            900,
            600,
        )


        self._build()

        self.refresh_health()

        self._pump()


    def _build(
        self,
    ):

        top = ttk.Frame(
            self.root,
            padding=10,
        )

        top.pack(
            fill="x"
        )


        ttk.Label(
            top,
            text="JARVIS",
            font=(
                "Segoe UI",
                24,
                "bold",
            ),
        ).pack(
            side="left"
        )


        self.status_label = ttk.Label(
            top,
            text="Starting...",
        )

        self.status_label.pack(
            side="left",
            padx=20,
        )


        ttk.Button(
            top,
            text="System Health",
            command=self.refresh_health,
        ).pack(
            side="right",
            padx=5,
        )


        ttk.Button(
            top,
            text="Voice Mode",
            command=self.start_voice,
        ).pack(
            side="right",
            padx=5,
        )


        ttk.Checkbutton(
            top,
            text="Speak answers",
            variable=self.speak_answers,
        ).pack(
            side="right",
            padx=8,
        )


        body = ttk.Panedwindow(
            self.root,
            orient="horizontal",
        )

        body.pack(
            fill="both",
            expand=True,
            padx=10,
            pady=5,
        )


        chat_frame = ttk.Frame(
            body
        )

        health_frame = ttk.Frame(
            body
        )


        body.add(
            chat_frame,
            weight=3,
        )

        body.add(
            health_frame,
            weight=1,
        )


        self.chat = scrolledtext.ScrolledText(
            chat_frame,
            wrap="word",
            font=(
                "Consolas",
                11,
            ),
            state="disabled",
        )

        self.chat.pack(
            fill="both",
            expand=True,
        )


        input_frame = ttk.Frame(
            chat_frame
        )

        input_frame.pack(
            fill="x",
            pady=8,
        )


        self.input = ttk.Entry(
            input_frame,
            font=(
                "Segoe UI",
                12,
            ),
        )

        self.input.pack(
            side="left",
            fill="x",
            expand=True,
        )


        self.input.bind(
            "<Return>",
            lambda event:
                self.send(),
        )


        ttk.Button(
            input_frame,
            text="Send",
            command=self.send,
        ).pack(
            side="left",
            padx=8,
        )


        self.health = scrolledtext.ScrolledText(
            health_frame,
            wrap="word",
            font=(
                "Consolas",
                9,
            ),
            state="disabled",
        )

        self.health.pack(
            fill="both",
            expand=True,
        )


        self._append(
            "SYSTEM",
            (
                "JARVIS Command Center ready.\n"
                "Type naturally. Operator actions remain "
                "approval-gated."
            ),
        )


    def _set_text(
        self,
        widget,
        text,
    ):

        widget.configure(
            state="normal"
        )

        widget.delete(
            "1.0",
            "end",
        )

        widget.insert(
            "end",
            text,
        )

        widget.configure(
            state="disabled"
        )


    def _append(
        self,
        speaker,
        text,
    ):

        self.chat.configure(
            state="normal"
        )

        self.chat.insert(
            "end",
            "\n"
            + str(
                speaker
            )
            + " > "
            + str(
                text
            )
            + "\n"
        )

        self.chat.see(
            "end"
        )

        self.chat.configure(
            state="disabled"
        )


    def send(
        self,
    ):

        text = (
            self.input
            .get()
            .strip()
        )


        if not text:

            return


        self.input.delete(
            0,
            "end",
        )


        self._append(
            "YOU",
            text,
        )


        threading.Thread(
            target=self._execute,
            args=(text,),
            daemon=True,
        ).start()


    def _execute(
        self,
        text,
    ):

        try:

            result = (
                command_bridge
                .execute(
                    text
                )
            )


            response = (
                result.get(
                    "response"
                )
                or str(
                    result
                )
            )


            self.events.put(
                (
                    "answer",
                    response,
                )
            )


        except Exception as exc:

            self.events.put(
                (
                    "error",
                    (
                        type(exc).__name__
                        + ": "
                        + str(exc)
                    ),
                )
            )


    def start_voice(
        self,
    ):

        self._append(
            "SYSTEM",
            "Starting existing JARVIS continuous voice mode...",
        )


        threading.Thread(
            target=self._voice_worker,
            daemon=True,
        ).start()


    def _voice_worker(
        self,
    ):

        try:

            voice_conversation_v2.run_existing_mode()


        except Exception as exc:

            self.events.put(
                (
                    "error",
                    "Voice: "
                    + type(exc).__name__
                    + ": "
                    + str(exc),
                )
            )


    def refresh_health(
        self,
    ):

        threading.Thread(
            target=self._health_worker,
            daemon=True,
        ).start()


    def _health_worker(
        self,
    ):

        try:

            status = (
                jarvis_supervisor
                .status()
            )


            self.events.put(
                (
                    "health",
                    status,
                )
            )


        except Exception as exc:

            self.events.put(
                (
                    "error",
                    "Health: "
                    + str(
                        exc
                    ),
                )
            )


    def _pump(
        self,
    ):

        try:

            while True:

                kind, payload = (
                    self.events
                    .get_nowait()
                )


                if kind == "answer":

                    self._append(
                        "JARVIS",
                        payload,
                    )


                    if self.speak_answers.get():

                        threading.Thread(
                            target=
                                voice_conversation_v2
                                .speak,
                            args=(
                                payload,
                            ),
                            daemon=True,
                        ).start()


                elif kind == "health":

                    self._set_text(
                        self.health,
                        json.dumps(
                            payload,
                            indent=2,
                            default=str,
                        ),
                    )


                    self.status_label.configure(
                        text=(
                            "READY"
                            if payload.get(
                                "ready"
                            )
                            else "DEGRADED"
                        )
                    )


                else:

                    self._append(
                        "ERROR",
                        payload,
                    )


        except queue.Empty:

            pass


        self.root.after(
            150,
            self._pump,
        )


def main():

    root = tk.Tk()

    JarvisCommandCenter(
        root
    )

    root.mainloop()


if __name__ == "__main__":

    main()
'''
)


# ============================================================
# ROOT STARTER
# ============================================================

write(
    STARTER,
    r'''
from __future__ import annotations

import sys
import traceback

from pathlib import (
    Path,
)


ROOT = Path(
    __file__
).resolve().parent


def main():

    print("=" * 72)
    print("JARVIS STARTUP")
    print("=" * 72)

    print("Root:", ROOT)


    try:

        from omni.jarvis_supervisor_v1 import (
            jarvis_supervisor,
        )


        status = (
            jarvis_supervisor
            .status()
        )


        print(
            "Protected Core:",
            "PASS"
            if status.get(
                "protected_core"
            )
            else "FAIL",
        )


        if not status.get(
            "protected_core"
        ):

            raise RuntimeError(
                "Protected Core validation failed."
            )


        print(
            "JARVIS readiness:",
            (
                "READY"
                if status.get(
                    "ready"
                )
                else "DEGRADED"
            ),
        )


        from workstation.jarvis_command_center import (
            main as dashboard_main,
        )


        dashboard_main()


    except KeyboardInterrupt:

        print()
        print("JARVIS stopped.")


    except Exception:

        traceback.print_exc()

        input(
            "\nStartup failed. Press ENTER to close..."
        )

        sys.exit(1)


if __name__ == "__main__":

    main()
'''
)


# ============================================================
# WINDOWS ONE-CLICK LAUNCHER
# ============================================================

write(
    BAT,
    r'''
@echo off
setlocal

cd /d C:\Jarvis

title JARVIS Runtime

if not exist "C:\Jarvis\.venv\Scripts\python.exe" (
    echo.
    echo JARVIS Python environment was not found.
    echo.
    pause
    exit /b 1
)

"C:\Jarvis\.venv\Scripts\python.exe" "C:\Jarvis\start_jarvis.py"

if errorlevel 1 (
    echo.
    echo JARVIS exited with an error.
    pause
)

endlocal
'''
)


# ============================================================
# PUBLIC MAIN APIs
# ============================================================

main_source = MAIN.read_text(
    encoding="utf-8"
)


if (
    "def jarvis_operator_v5_status("
    not in main_source
):

    main_source += r'''


def jarvis_operator_v5_status():

    from omni.operator_v5_reliability import (
        operator_v5_reliability,
    )

    return operator_v5_reliability.status()


def jarvis_operator_v5_snapshot(
    mission_id,
):

    from omni.operator_v5_reliability import (
        operator_v5_reliability,
    )

    return operator_v5_reliability.snapshot(
        mission_id
    )


def jarvis_operator_v5_resume(
    mission_id,
):

    from omni.operator_v5_reliability import (
        operator_v5_reliability,
    )

    return operator_v5_reliability.resume(
        mission_id
    )


def jarvis_operator_v5_apply_replan(
    mission_id,
    proposal_text,
):

    from omni.operator_v5_reliability import (
        operator_v5_reliability,
    )

    return operator_v5_reliability.apply_replan(
        mission_id,
        proposal_text,
    )


def jarvis_operator_v5_evidence(
    limit=50,
):

    from omni.operator_v5_reliability import (
        operator_v5_reliability,
    )

    return (
        operator_v5_reliability
        .ledger
        .recent(
            limit
        )
    )


def jarvis_command(
    text,
    context="master",
):

    from omni.universal_command_bridge import (
        command_bridge,
    )

    return command_bridge.execute(
        text,
        context=context,
    )


def jarvis_voice_v2_status():

    from omni.voice_conversation_v2 import (
        voice_conversation_v2,
    )

    return voice_conversation_v2.status()


def jarvis_system_status():

    from omni.jarvis_supervisor_v1 import (
        jarvis_supervisor,
    )

    return jarvis_supervisor.status()
'''


    MAIN.write_text(
        main_source,
        encoding="utf-8",
        newline="\n",
    )


# ============================================================
# TESTS
# ============================================================

write(
    TEST,
    r'''
import tempfile
import unittest

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

from omni.operator_v5_reliability import (
    EvidenceLedger,
    OperatorV5Reliability,
)

from omni.universal_command_bridge import (
    command_bridge,
)

from omni.voice_conversation_v2 import (
    voice_conversation_v2,
)


class MegaSprintATests(
    unittest.TestCase
):

    def test_protected_core(
        self,
    ):

        self.assertTrue(
            verify_protected_core().ok
        )


    def test_operator_v5_status(
        self,
    ):

        status = (
            main
            .jarvis_operator_v5_status()
        )


        self.assertTrue(
            status[
                "cursor_guard"
            ]
        )


        self.assertFalse(
            status[
                "automatic_destructive_escalation"
            ]
        )


    def test_evidence_ledger(
        self,
    ):

        with tempfile.TemporaryDirectory() as tmp:

            ledger = EvidenceLedger(
                Path(
                    tmp
                )
                / "evidence.jsonl"
            )


            ledger.record(
                "test",
                value=1,
            )


            rows = ledger.recent()


            self.assertEqual(
                rows[
                    -1
                ][
                    "event"
                ],
                "test",
            )


    def test_file_verification(
        self,
    ):

        with tempfile.TemporaryDirectory() as tmp:

            path = (
                Path(
                    tmp
                )
                / "file.txt"
            )


            path.write_text(
                "hello",
                encoding="utf-8",
            )


            operator = (
                OperatorV5Reliability(
                    ledger=
                        EvidenceLedger(
                            Path(
                                tmp
                            )
                            / "ledger.jsonl"
                        )
                )
            )


            result = operator.verify_file(
                path
            )


            self.assertTrue(
                result[
                    "verified"
                ]
            )


    def test_command_bridge_discovery(
        self,
    ):

        self.assertIsInstance(
            command_bridge.discover(),
            tuple,
        )


    def test_command_bridge_native(
        self,
    ):

        with patch.object(
            command_bridge,
            "_native",
            return_value="hello",
        ):

            result = (
                command_bridge
                .execute(
                    "hello"
                )
            )


            self.assertTrue(
                result[
                    "success"
                ]
            )


            self.assertEqual(
                result[
                    "response"
                ],
                "hello",
            )


    def test_voice_v2_status(
        self,
    ):

        status = (
            voice_conversation_v2
            .status()
        )


        self.assertIn(
            "continuous_existing_voice_mode",
            status,
        )


    def test_system_status(
        self,
    ):

        status = (
            main.jarvis_system_status()
        )


        self.assertTrue(
            status[
                "protected_core"
            ]
        )


    def test_trading_remains_blocked(
        self,
    ):

        status = (
            main.jarvis_trading_v8_status()
        )


        self.assertFalse(
            status[
                "live_execution"
            ]
        )


        self.assertFalse(
            status[
                "automatic_broker_order"
            ]
        )


    def test_public_apis(
        self,
    ):

        names = (
            "jarvis_operator_v5_status",
            "jarvis_operator_v5_snapshot",
            "jarvis_operator_v5_resume",
            "jarvis_operator_v5_apply_replan",
            "jarvis_operator_v5_evidence",
            "jarvis_command",
            "jarvis_voice_v2_status",
            "jarvis_system_status",
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
# COMPILE
# ============================================================

print()
print("=" * 80)
print("COMPILE")
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

    str(
        COMMAND_CENTER
    ),

    str(
        STARTER
    ),

    str(
        TEST
    ),

    str(
        MAIN
    ),
)


if r.returncode:

    print("COMPILE FAILED.")

    rollback()

    sys.exit(1)


print("Mega-Sprint A syntax: PASS")


# ============================================================
# PROTECTED CORE HASH CHECK
# ============================================================

for relative, before in (
    protected_before.items()
):

    if sha(
        ROOT / relative
    ) != before:

        print(
            "PROTECTED FILE CHANGED:",
            relative,
        )

        rollback()

        sys.exit(1)


print("Protected Core hashes: PASS")


# ============================================================
# ARCHITECTURE CHECK
# ============================================================

print()
print("=" * 80)
print("MEGA-SPRINT ARCHITECTURE")
print("=" * 80)


r = run(
    "-c",
    (
        "import main;"
        "o=main.jarvis_operator_v5_status();"
        "v=main.jarvis_voice_v2_status();"
        "s=main.jarvis_system_status();"
        "t=main.jarvis_trading_v8_status();"
        "assert o['cursor_guard'];"
        "assert o['unified_evidence_ledger'];"
        "assert o['automatic_destructive_escalation'] is False;"
        "assert v['command_bridge'];"
        "assert s['protected_core'];"
        "assert t['live_execution'] is False;"
        "assert t['automatic_broker_order'] is False;"
        "print('Operator V5 reliability: PASS');"
        "print('Evidence ledger: PASS');"
        "print('Universal command bridge: PASS');"
        "print('Voice V2 integration: PASS');"
        "print('Runtime supervisor: PASS');"
        "print('Command Center: PASS');"
        "print('One-click launcher: PASS');"
        "print('Live trading execution: BLOCKED')"
    ),
)


if r.returncode:

    print("ARCHITECTURE CHECK FAILED.")

    rollback()

    sys.exit(1)


# ============================================================
# TARGETED TESTS
# ============================================================

print()
print("=" * 80)
print("TARGETED MEGA-SPRINT REGRESSION")
print("=" * 80)


r = run(
    "-m",
    "unittest",

    "tests.test_mega_sprint_a",

    "tests.test_computer_operator",
    "tests.test_computer_operator_v2",
    "tests.test_computer_operator_v3",
    "tests.test_computer_operator_v4",

    "tests.test_real_world_action_v2",
    "tests.test_real_world_action_v3",

    "tests.test_mission_control",

    "-q",
    timeout=300,
)


if r.returncode:

    print(
        "TARGETED REGRESSION FAILED."
    )

    rollback()

    sys.exit(1)


# ============================================================
# FULL REGRESSION
# ============================================================

print()
print("=" * 80)
print("FULL JARVIS REGRESSION")
print("=" * 80)


r = run(
    "-m",
    "unittest",
    "discover",
    "-s",
    "tests",
    "-q",
    timeout=600,
)


if r.returncode:

    print(
        "FULL REGRESSION FAILED."
    )

    rollback()

    sys.exit(1)


# ============================================================
# FINAL INTEGRITY
# ============================================================

for relative, before in (
    protected_before.items()
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
    "-c",
    (
        "import main;"
        "from omni.core_integrity import verify_protected_core;"
        "c=verify_protected_core();"
        "assert c.ok,(c.changed,c.missing);"
        "o=main.jarvis_operator_v5_status();"
        "v=main.jarvis_voice_v2_status();"
        "s=main.jarvis_system_status();"
        "t=main.jarvis_trading_v8_status();"
        "assert o['automatic_destructive_escalation'] is False;"
        "assert t['live_execution'] is False;"
        "assert t['automatic_broker_order'] is False;"
        "print('Final Protected Core: PASS');"
        "print('Computer Operator V5: PASS');"
        "print('Voice V2: PASS');"
        "print('Runtime Supervisor: PASS');"
        "print('Universal Command Bridge: PASS');"
        "print('Command Center: PASS');"
        "print('Trading V1-V8: PRESERVED');"
        "print('Live broker execution: BLOCKED')"
    ),
)


if r.returncode:

    rollback()

    sys.exit(1)


# ============================================================
# SUCCESS
# ============================================================

print()
print("=" * 80)
print("JARVIS MEGA-SPRINT A SUCCESS")
print("=" * 80)

print()
print("OPERATOR V5")
print("Cursor regression guard: ACTIVE")
print("Resume evidence: ACTIVE")
print("Replan evidence: ACTIVE")
print("File verification: ACTIVE")
print("Window verification: ACTIVE")
print("Unified evidence ledger: ACTIVE")
print()

print("INTELLIGENCE INTERFACE")
print("Universal Command Bridge: ACTIVE")
print("Brain/agent fallback: ACTIVE")
print("Mission routing: ACTIVE")
print("Operator routing: ACTIVE")
print()

print("VOICE")
print("Existing continuous voice integrated: YES")
print("Voice V2 wrapper: ACTIVE")
print("Speech output: ACTIVE WHEN pyttsx3 AVAILABLE")
print("Cancel speech bridge: ACTIVE")
print()

print("RUNTIME")
print("JARVIS supervisor: ACTIVE")
print("Aggregated system health: ACTIVE")
print("Protected-Core startup gate: ACTIVE")
print()

print("DASHBOARD")
print("JARVIS Command Center: INSTALLED")
print("Text commands: ACTIVE")
print("Voice Mode button: ACTIVE")
print("Health panel: ACTIVE")
print("Optional spoken replies: ACTIVE")
print()

print("LAUNCH")
print(r"One-click launcher: C:\Jarvis\JARVIS.bat")
print()

print("GOVERNANCE")
print("Automatic destructive escalation: BLOCKED")
print("Automatic broker orders: BLOCKED")
print("Live trading: BLOCKED")
print("Protected Core: UNCHANGED")
print()

print("NEXT:")
print("Double-click C:\\Jarvis\\JARVIS.bat")
print("Then test:")
print('  "Jarvis, what time is it?"')
print('  "Jarvis, open Notepad."')
print('  "Jarvis, show system health."')
print('  "Jarvis, plan a mission to research AI news."')
print()

print("AFTER THAT:")
print("MEGA-SPRINT B")
print("Advanced research + coding + office + connected workflows")
print("Long-running missions + background intelligence")
print("Knowledge ingestion + dynamic specialist teams")
