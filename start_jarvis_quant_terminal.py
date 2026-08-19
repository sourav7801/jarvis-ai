from __future__ import annotations

import socket

from workstation.jarvis_trading_workstation_v7 import app as trading_app


def port_open(host: str, port: int) -> bool:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(0.25)
    try:
        return sock.connect_ex((host, int(port))) == 0
    finally:
        sock.close()


def main():
    if port_open(trading_app.HOST, trading_app.PORT):
        print(
            f"JARVIS Quant Trading Intelligence already running at "
            f"http://{trading_app.HOST}:{trading_app.PORT}"
        )
        return

    print("=" * 72)
    print("JARVIS QUANT TRADING INTELLIGENCE")
    print("=" * 72)
    print(f"Terminal: http://{trading_app.HOST}:{trading_app.PORT}")
    print("Mode: PAPER / RESEARCH")
    print("Live broker execution: LOCKED")
    trading_app.main()


if __name__ == "__main__":
    main()
