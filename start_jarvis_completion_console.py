from __future__ import annotations

import socket

from workstation import completion_console_v12 as completion_console


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
