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
    enabled = os.getenv("JARVIS_V12_AUTO_PAPER_START", "0").strip().lower() not in {"0", "false", "no", "off"}
    if not enabled:
        return {"success": True, "running": False, "reason": "V12_ADAPTIVE_AUTO_START_DISABLED", "decision_authority": "PORTFOLIO_ADJUSTED_CONTEXTUAL_UTILITY_CONTINUOUS_RISK", "paper_only": True, "live_execution": False, "automatic_broker_order": False}
    from workstation.paper_portfolio_controller import paper_portfolio_controller
    result = paper_portfolio_controller.start(intraday_profile="adaptive_intraday")
    return {**dict(result), "decision_authority": "PORTFOLIO_ADJUSTED_CONTEXTUAL_UTILITY_CONTINUOUS_RISK", "legacy_singleton_auto_start": False, "paper_only": True, "live_execution": False, "automatic_broker_order": False}


def main():
    # Acquire the exclusive listener before installing bridges or creating
    # workers. Two simultaneous launchers cannot start duplicate scan engines.
    from workstation.professional_terminal import TerminalRuntime, TerminalHTTPServer, build_handler
    from workstation import terminal_data
    try:
        server = TerminalHTTPServer((trading_app.HOST, trading_app.PORT), trading_app.Handler)
    except OSError as exc:
        print(f"Terminal port {trading_app.PORT} is already owned: {exc}")
        print(f"Open http://{trading_app.HOST}:{trading_app.PORT} or close the older terminal before upgrading.")
        return 1
    runtime = None
    try:
        install_v11_quant_bridges()
        install_v12_adaptive_bridges()
        install_v13_intelligence_bridges()
        install_v13_quant_http_bridge()
        install_v14_execution_bridges()
        install_v14_quant_http_bridge()
        install_v141_risk_geometry_bridges()
        install_v141_quant_http_bridge()
        install_v15_reasoning_bridges()
        install_v15_quant_http_bridge()
        install_v151_options_bridges()
        install_v151_quant_http_bridge()
        from workstation.paper_trading_desk import paper_desk
        from workstation.paper_portfolio_controller import paper_portfolio_controller
        terminal_data.CACHE_ENABLED = True
        runtime = TerminalRuntime(paper_desk, paper_portfolio_controller)
        server.RequestHandlerClass = build_handler(trading_app.Handler, runtime)
        runtime.start()
        # Bridge startup may wait for another Python environment. Keep it off
        # the HTTP/position-management path, and start it only once.
        import threading
        threading.Thread(target=trading_app.start_live_bridge, name="JarvisDataStartup", daemon=True).start()
        url = f"http://{trading_app.HOST}:{trading_app.PORT}"
        print("JARVIS PROFESSIONAL PAPER TERMINAL", flush=True)
        print(f"Terminal: {url}", flush=True)
        print("Intraday / Swing / Investment · paper only · live broker execution locked", flush=True)
        print("Sessions paused. Saved positions remain monitored. Start a workspace in the terminal.", flush=True)
        if os.getenv("JARVIS_NO_BROWSER", "0").lower() not in {"1", "true", "yes"}:
            import webbrowser
            webbrowser.open(url)
        server.serve_forever(poll_interval=.25)
    except KeyboardInterrupt:
        return 0
    finally:
        if runtime is not None:
            runtime.stop()
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
