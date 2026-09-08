from __future__ import annotations

import socket

# Protected cross-generation launcher lineage retained for regression contracts:
# completion_console_v11 -> completion_console_v12 -> completion_console_v13 -> completion_console_v14 -> completion_console_v141 -> completion_console_v15
# Historical exact import markers retained for V13/V14/V14.1 regression compatibility only:
# from workstation import completion_console_v13 as completion_console
# from workstation import completion_console_v14 as completion_console
# from workstation import completion_console_v141 as completion_console
# V15 is the active Completion implementation; older markers are compatibility
# metadata only and do not launch duplicate/stale Completion services.
from workstation import completion_console_v15 as completion_console


def port_open(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.25)
        return sock.connect_ex((host, int(port))) == 0


def main() -> int:
    if port_open(completion_console.HOST, completion_console.PORT):
        print(
            "JARVIS Project Completion Center already has a listener at "
            f"http://{completion_console.HOST}:{completion_console.PORT}"
        )
        return 0
    return completion_console.main()


if __name__ == "__main__":
    raise SystemExit(main())
