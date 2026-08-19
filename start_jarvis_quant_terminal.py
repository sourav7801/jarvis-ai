from __future__ import annotations

import socket

from workstation import quant_terminal_v2 as trading_app
from workstation.quant_v3_server_patch import install as install_quant_v3


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

    install_quant_v3(trading_app)

    print("=" * 72)
    print("JARVIS QUANT TRADING INTELLIGENCE V3")
    print("=" * 72)
    print(f"Terminal: http://{trading_app.HOST}:{trading_app.PORT}")
    print("Charts: professional interactive financial charts")
    print("Data: FYERS read-only + public crypto market data")
    print("Engine: regime-aware multi-strategy ensemble")
    print("Autopilot: autonomous PAPER execution only")
    print("Options: FYERS India + public Deribit BTC/ETH where available")
    print("Live broker execution: LOCKED")
    trading_app.main()


if __name__ == "__main__":
    main()
