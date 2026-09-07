from __future__ import annotations

import os
import socket

# Canonical V12 runtime disables the legacy singleton auto-starter before the
# Quant module is imported. The portfolio controller below owns adaptive
# INTRADAY/SWING/INVESTMENT execution instead.
os.environ["JARVIS_AUTO_PAPER_START"] = "0"

from workstation import quant_terminal_v2 as trading_app


def port_open(host: str, port: int) -> bool:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(0.25)
    try:
        return sock.connect_ex((host, int(port))) == 0
    finally:
        sock.close()


def install_v11_quant_bridges() -> dict[str, object]:
    """Install bounded completed-bar/routing adapters in the Quant owner process."""

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


def install_v12_adaptive_bridges() -> dict[str, object]:
    from workstation.adaptive_direct_trade_bridge import install_adaptive_direct_trade_bridge

    direct = install_adaptive_direct_trade_bridge()
    return {
        "success": bool(direct.get("success")),
        "adaptive_direct_trade": direct,
        "paper_only": True,
        "live_execution": False,
        "automatic_broker_order": False,
    }


def start_v12_adaptive_paper() -> dict[str, object]:
    enabled = os.getenv("JARVIS_V12_AUTO_PAPER_START", "1").strip().lower() not in {
        "0", "false", "no", "off"
    }
    if not enabled:
        return {
            "success": True,
            "running": False,
            "reason": "V12_ADAPTIVE_AUTO_START_DISABLED",
            "paper_only": True,
            "live_execution": False,
        }
    from workstation.paper_portfolio_controller import paper_portfolio_controller

    result = paper_portfolio_controller.start(intraday_profile="adaptive_intraday")
    return {
        **dict(result),
        "decision_authority": "ADAPTIVE_EXPECTED_VALUE_NOT_STATIC_SCORE",
        "legacy_singleton_auto_start": False,
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
    adaptive_bridges = install_v12_adaptive_bridges()
    # Bring up the read-only market bridge before the first adaptive scan so
    # boot-time BTC/India samples have the same provider surface as later loops.
    try:
        trading_app.start_live_bridge()
    except Exception:
        pass
    adaptive = start_v12_adaptive_paper()
    print("=" * 72)
    print("JARVIS QUANT TRADING INTELLIGENCE V12 ADAPTIVE RUNTIME")
    print("=" * 72)
    print(f"Terminal: http://{trading_app.HOST}:{trading_app.PORT}")
    print("Charts: professional interactive financial charts")
    print("Data: FYERS read-only + public crypto market data")
    print("10m bars: derived from 2x contiguous COMPLETED 5m provider bars only")
    print("Discovery routing: portfolio horizon controller")
    print("Decision authority: adaptive expected value + uncertainty + learning")
    print("Static 67/68/70 score boundary: NOT EXECUTION AUTHORITY")
    print(f"V11 bridge state: {bool(bridges.get('success'))}")
    print(f"V12 direct bridge state: {bool(adaptive_bridges.get('success'))}")
    print(f"V12 adaptive paper state: {bool(adaptive.get('running'))}")
    print("Mode: PAPER / RESEARCH")
    print("Live broker execution: LOCKED")
    trading_app.main()


if __name__ == "__main__":
    main()
