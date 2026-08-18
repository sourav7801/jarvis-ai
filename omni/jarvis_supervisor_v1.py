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
