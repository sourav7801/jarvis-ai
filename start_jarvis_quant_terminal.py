from __future__ import annotations

import socket

from workstation import quant_terminal_v2 as trading_app


def port_open(host: str, port: int) -> bool:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(0.25)
    try:
        return sock.connect_ex((host, int(port))) == 0
    finally:
        sock.close()


def install_v11_quant_bridges() -> dict[str, object]:
    """Install bounded V11 research/paper adapters in the Quant owner process.

    This startup hook is intentionally process-local. Quant on port 8787 owns
    scanner/controller state, so the derived 10m and governed discovery-routing
    adapters must be installed here rather than in Completion on port 8799.
    Neither adapter imports or exposes a live broker order API.
    """

    from workstation.derived_timeframe_bridge import install_derived_timeframe_bridge
    from workstation.discovery_routing_bridge import install_discovery_routing_bridge

    derived = install_derived_timeframe_bridge()
    routing = install_discovery_routing_bridge()
    return {
        "success": True,
        "derived_10m": derived,
        "discovery_routing": routing,
        "paper_only": True,
        "live_execution": False,
        "automatic_broker_order": False,
    }


def main():
    if port_open(trading_app.HOST, trading_app.PORT):
        print(
            f"JARVIS Quant Trading Intelligence already running at "
            f"http://{trading_app.HOST}:{trading_app.PORT}"
        )
        return

    bridges = install_v11_quant_bridges()
    print("=" * 72)
    print("JARVIS QUANT TRADING INTELLIGENCE V11 BRIDGED RUNTIME")
    print("=" * 72)
    print(f"Terminal: http://{trading_app.HOST}:{trading_app.PORT}")
    print("Charts: professional interactive financial charts")
    print("Data: FYERS read-only + public crypto market data")
    print("10m bars: derived from 2x contiguous COMPLETED 5m provider bars only")
    print("Discovery routing: portfolio horizon controller")
    print(f"V11 bridge state: {bool(bridges.get('success'))}")
    print("Mode: PAPER / RESEARCH")
    print("Live broker execution: LOCKED")
    trading_app.main()


if __name__ == "__main__":
    main()
