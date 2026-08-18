from __future__ import annotations

import sys
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def main():

    print("=" * 72)
    print("JARVIS STARTUP")
    print("=" * 72)
    print("Root:", ROOT)

    try:
        from omni.jarvis_supervisor_v1 import (
            jarvis_supervisor,
        )

        status = jarvis_supervisor.status()

        print(
            "Protected Core:",
            "PASS"
            if status.get("protected_core")
            else "FAIL",
        )

        if not status.get("protected_core"):
            raise RuntimeError(
                "Protected Core validation failed."
            )

        print(
            "JARVIS readiness:",
            "READY"
            if status.get("ready")
            else "DEGRADED",
        )

        print("Launching Command Center...")

        from workstation.jarvis_command_center import (
            main as dashboard_main,
        )

        dashboard_main()

        print("Command Center closed normally.")

    except KeyboardInterrupt:
        print()
        print("JARVIS stopped.")

    except BaseException:
        print()
        print("=" * 72)
        print("JARVIS STARTUP FAILURE")
        print("=" * 72)
        traceback.print_exc()

        try:
            input(
                "\nPress ENTER to close..."
            )
        except EOFError:
            pass

        sys.exit(1)


if __name__ == "__main__":
    main()
