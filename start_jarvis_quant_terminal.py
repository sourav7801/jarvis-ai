from __future__ import annotations

import os
import socket

# Canonical V12+ disables the legacy static-score singleton before Quant import.
# The portfolio controller owns INTRADAY/SWING/INVESTMENT paper execution;
# compatibility names are rebound process-locally by later runtime bridges.
# Protected V13 authority marker: CONTEXTUAL_EXPECTED_VALUE_NOT_STATIC_SCORE
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
    from workstation.derived_timeframe_bridge import install_derived_timeframe_bridge
    from workstation.discovery_routing_bridge import install_discovery_routing_bridge
    derived = install_derived_timeframe_bridge()
    routing = install_discovery_routing_bridge()
    return {"success": True, "derived_10m": derived, "discovery_routing": routing, "paper_only": True, "live_execution": False, "automatic_broker_order": False}


def install_v12_adaptive_bridges() -> dict[str, object]:
    from workstation.v12_runtime_bridges import install_v12_runtime_bridges
    from workstation.adaptive_discovery_bridge import install_adaptive_discovery_bridge
    runtime = install_v12_runtime_bridges()
    discovery = install_adaptive_discovery_bridge()
    return {"success": bool(runtime.get("success") and discovery.get("success")), "runtime": dict(runtime), "adaptive_discovery": dict(discovery), "paper_only": True, "live_execution": False, "automatic_broker_order": False}


def install_v13_intelligence_bridges() -> dict[str, object]:
    from workstation.v13_runtime_bridges import install_v13_runtime_bridges
    return dict(install_v13_runtime_bridges())


def install_v13_quant_http_bridge() -> dict[str, object]:
    from workstation.quant_terminal_v13_bridge import install_quant_terminal_v13_bridge
    return dict(install_quant_terminal_v13_bridge())


def install_v14_execution_bridges() -> dict[str, object]:
    from workstation.v14_runtime_bridges import install_v14_runtime_bridges
    return dict(install_v14_runtime_bridges())


def install_v14_quant_http_bridge() -> dict[str, object]:
    from workstation.quant_terminal_v14_bridge import install_quant_terminal_v14_bridge
    return dict(install_quant_terminal_v14_bridge())


def install_v141_risk_geometry_bridges() -> dict[str, object]:
    from workstation.v141_runtime_bridges import install_v141_runtime_bridges
    return dict(install_v141_runtime_bridges())


def install_v141_quant_http_bridge() -> dict[str, object]:
    from workstation.quant_terminal_v141_bridge import install_quant_terminal_v141_bridge
    return dict(install_quant_terminal_v141_bridge())


def install_v15_reasoning_bridges() -> dict[str, object]:
    from workstation.v15_runtime_bridges import install_v15_runtime_bridges
    return dict(install_v15_runtime_bridges())


def install_v15_quant_http_bridge() -> dict[str, object]:
    from workstation.quant_terminal_v15_bridge import install_quant_terminal_v15_bridge
    return dict(install_quant_terminal_v15_bridge())


def install_v151_options_bridges() -> dict[str, object]:
    from workstation.v151_runtime_bridges import install_v151_runtime_bridges
    return dict(install_v151_runtime_bridges())


def install_v151_quant_http_bridge() -> dict[str, object]:
    from workstation.quant_terminal_v151_bridge import install_quant_terminal_v151_bridge
    return dict(install_quant_terminal_v151_bridge())


def start_v12_adaptive_paper() -> dict[str, object]:
    # Function name is preserved for protected V12/V13/V14/V14.1 compatibility.
    # By V15/V15.1, verified risk geometry and portfolio-aware reasoning have
    # already rebound the canonical policy before paper workers start.
    enabled = os.getenv("JARVIS_V12_AUTO_PAPER_START", "1").strip().lower() not in {"0", "false", "no", "off"}
    if not enabled:
        return {"success": True, "running": False, "reason": "V12_ADAPTIVE_AUTO_START_DISABLED", "decision_authority": "PORTFOLIO_ADJUSTED_CONTEXTUAL_UTILITY_CONTINUOUS_RISK", "paper_only": True, "live_execution": False, "automatic_broker_order": False}
    from workstation.paper_portfolio_controller import paper_portfolio_controller
    result = paper_portfolio_controller.start(intraday_profile="adaptive_intraday")
    return {**dict(result), "decision_authority": "PORTFOLIO_ADJUSTED_CONTEXTUAL_UTILITY_CONTINUOUS_RISK", "legacy_singleton_auto_start": False, "paper_only": True, "live_execution": False, "automatic_broker_order": False}


def main():
    if port_open(trading_app.HOST, trading_app.PORT):
        print(f"JARVIS Quant Trading Intelligence already running at http://{trading_app.HOST}:{trading_app.PORT}")
        return

    bridges = install_v11_quant_bridges()
    adaptive_bridges = install_v12_adaptive_bridges()
    v13_bridges = install_v13_intelligence_bridges()
    v13_http = install_v13_quant_http_bridge()
    v14_bridges = install_v14_execution_bridges()
    v14_http = install_v14_quant_http_bridge()
    v141_bridges = install_v141_risk_geometry_bridges()
    v141_http = install_v141_quant_http_bridge()
    v15_bridges = install_v15_reasoning_bridges()
    v15_http = install_v15_quant_http_bridge()
    v151_bridges = install_v151_options_bridges()
    v151_http = install_v151_quant_http_bridge()

    try:
        trading_app.start_live_bridge()
    except Exception:
        pass

    adaptive = start_v12_adaptive_paper()
    print("=" * 72)
    print("JARVIS QUANT TRADING INTELLIGENCE V15.1 OPTIONS EXECUTION INTELLIGENCE")
    print("=" * 72)
    print(f"Terminal: http://{trading_app.HOST}:{trading_app.PORT}")
    print("Data: FYERS read-only + public crypto market data")
    print("10m bars: derived from 2x contiguous COMPLETED 5m provider bars only")
    print("Risk geometry: V14.1 VERIFIED COMPLETED-BAR CLOSE + ATR + STRUCTURE")
    print("Market reasoning: V15 PERSISTENT BELIEF + COMPETING HYPOTHESES")
    print("Decision authority: PORTFOLIO-ADJUSTED CONTEXTUAL UTILITY / CONTINUOUS PAPER RISK")
    print("Compatibility authority lineage: POSITIVE CONTEXTUAL EXPECTED VALUE (V14 FOUNDATION); V15 PORTFOLIO UTILITY IS CURRENT")
    print("Options: VERIFIED READ-ONLY CHAIN + VERIFIED CONTRACT SPEC + OPTION ECONOMICS")
    print("Option execution: LONG PREMIUM PAPER ONLY; NAKED SHORT OPTIONS DISABLED")
    print("Option premium stop/target: RISK-PLAN ESTIMATES / NOT FUTURE MARKET QUOTES")
    print("Dealer positioning: UNAVAILABLE WITHOUT VERIFIED DEALER INVENTORY")
    print("Confidence: SCALES POSITION SIZE ONLY / NOT AN EXECUTION GATE")
    print("Static 67/68/70 score boundary: OBSERVABILITY ONLY")
    print("Static R:R / alignment boundary: NOT EXECUTION AUTHORITY")
    print("Fractional sizing: CONSTRAINT-AWARE / VERIFIED INSTRUMENT STEP")
    print("INVALID_RISK_LEVELS: HARD ONLY WHEN VERIFIED GEOMETRY CANNOT BE BUILT")
    print("Watching: NOT A TERMINAL STATE; exact pipeline reason is recorded")
    print(f"V11 bridge state: {bool(bridges.get('success'))}")
    print(f"V12 compatibility bridge state: {bool(adaptive_bridges.get('success'))}")
    print(f"V13 contextual bridge state: {bool(v13_bridges.get('installed'))}")
    print(f"V13 Quant HTTP compatibility state: {bool(v13_http.get('installed'))}")
    print(f"V14 execution bridge state: {bool(v14_bridges.get('installed'))}")
    print(f"V14 Quant HTTP compatibility state: {bool(v14_http.get('installed'))}")
    print(f"V14.1 risk geometry bridge state: {bool(v141_bridges.get('installed'))}")
    print(f"V14.1 Quant HTTP compatibility state: {bool(v141_http.get('installed'))}")
    print(f"V15 reasoning bridge state: {bool(v15_bridges.get('installed'))}")
    print(f"V15 Quant HTTP bridge state: {bool(v15_http.get('installed'))}")
    print(f"V15.1 options bridge state: {bool(v151_bridges.get('installed'))}")
    print(f"V15.1 Quant HTTP bridge state: {bool(v151_http.get('installed'))}")
    print(f"V15 paper workers running: {bool(adaptive.get('running'))}")
    print("Mode: PAPER / RESEARCH")
    print("Live broker execution: LOCKED")
    trading_app.main()


if __name__ == "__main__":
    main()
