from __future__ import annotations

import os
import socket

# Canonical V12 disables the legacy static-score singleton before Quant import.
# The portfolio controller below owns adaptive INTRADAY/SWING/INVESTMENT paper
# execution; legacy HTTP names are rebound process-locally for compatibility.
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
    """Preserve verified completed-bar and discovery-routing adapters."""

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
    from workstation.v12_runtime_bridges import install_v12_runtime_bridges

    return dict(install_v12_runtime_bridges())


def start_v12_adaptive_paper() -> dict[str, object]:
    enabled = os.getenv("JARVIS_V12_AUTO_PAPER_START", "1").strip().lower() not in {
        "0", "false", "no", "off"
    }
    if not enabled:
        return {
            "success": True,
            "running": False,
            "reason": "V12_ADAPTIVE_AUTO_START_DISABLED",
            "decision_authority": "ADAPTIVE_EXPECTED_VALUE_NOT_STATIC_SCORE",
            "paper_only": True,
            "live_execution": False,
            "automatic_broker_order": False,
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

    # Bring up read-only provider state before the first adaptive scan. Failures
    # remain visible as data hard-blockers instead of being converted into fake
    # candles or forced trades.
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
    print("Decision authority: adaptive expected value + uncertainty + outcome learning")
    print("Static 67/68/70 score boundary: OBSERVABILITY ONLY")
    print("Static live R:R threshold: NOT V12 EXECUTION AUTHORITY")
    print(f"V11 bridge state: {bool(bridges.get('success'))}")
    print(f"V12 runtime bridge state: {bool(adaptive_bridges.get('success'))}")
    print(f"V12 adaptive paper state: {bool(adaptive.get('running'))}")
    print("Mode: PAPER / RESEARCH")
    print("Live broker execution: LOCKED")
    trading_app.main()


if __name__ == "__main__":
    main()
