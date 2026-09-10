from __future__ import annotations

"""Isolated V16 professional paper-terminal launcher.

This launcher intentionally does not replace JARVIS.bat yet. It lets the V16
convergence branch exercise the pushed professional terminal while preserving
the verified V15 runtime as the rollback/default daily launcher until the full
V16 regression and Windows acceptance gate passes.
"""

import os
import threading

# Professional sessions are explicit. Existing positions remain managed by the
# canonical Paper Desk, but no workspace begins entry scanning on process boot.
os.environ["JARVIS_AUTO_PAPER_START"] = "0"
os.environ["JARVIS_V12_AUTO_PAPER_START"] = "0"

from workstation import quant_terminal_v2 as trading_app
from workstation import terminal_data
from workstation.professional_terminal import TerminalHTTPServer, TerminalRuntime, build_handler

import start_jarvis_quant_terminal as lineage


def install_verified_reasoning_lineage() -> dict[str, object]:
    """Install only the V11 -> verified V15 reasoning chain.

    V15.1 options work is deliberately not activated here until it is migrated
    into V16 with its failed safety contract corrected and re-verified.
    """

    states = {
        "v11": lineage.install_v11_quant_bridges(),
        "v12": lineage.install_v12_adaptive_bridges(),
        "v13": lineage.install_v13_intelligence_bridges(),
        "v13_http": lineage.install_v13_quant_http_bridge(),
        "v14": lineage.install_v14_execution_bridges(),
        "v14_http": lineage.install_v14_quant_http_bridge(),
        "v141": lineage.install_v141_risk_geometry_bridges(),
        "v141_http": lineage.install_v141_quant_http_bridge(),
        "v15": lineage.install_v15_reasoning_bridges(),
        "v15_http": lineage.install_v15_quant_http_bridge(),
    }
    return {
        "success": True,
        "states": states,
        "decision_authority": "PORTFOLIO_ADJUSTED_CONTEXTUAL_UTILITY_CONTINUOUS_RISK",
        "paper_only": True,
        "live_execution": False,
        "automatic_broker_order": False,
    }


def main() -> int:
    # Acquire 8787 before constructing workers. A second launcher cannot create
    # duplicate scanners, sessions or Paper Desk actions behind an existing UI.
    try:
        server = TerminalHTTPServer((trading_app.HOST, trading_app.PORT), trading_app.Handler)
    except OSError as exc:
        print(f"Professional terminal port {trading_app.PORT} is already owned: {exc}")
        print(f"Open http://{trading_app.HOST}:{trading_app.PORT} or stop the owned JARVIS Quant runtime first.")
        return 1

    runtime: TerminalRuntime | None = None
    try:
        install_verified_reasoning_lineage()

        from workstation.paper_trading_desk import paper_desk
        from workstation.paper_portfolio_controller import paper_portfolio_controller

        terminal_data.CACHE_ENABLED = True
        runtime = TerminalRuntime(paper_desk, paper_portfolio_controller)
        server.RequestHandlerClass = build_handler(trading_app.Handler, runtime)
        runtime.start()

        # FYERS/public-data bridge startup is isolated from the HTTP and
        # position-management path. The data-side governor/caches remain the
        # canonical protection against provider fan-out and verified 429s.
        threading.Thread(
            target=trading_app.start_live_bridge,
            name="JarvisV16DataStartup",
            daemon=True,
        ).start()

        url = f"http://{trading_app.HOST}:{trading_app.PORT}"
        print("=" * 72)
        print("JARVIS V16 PROFESSIONAL PAPER TERMINAL CONVERGENCE")
        print("=" * 72)
        print(f"Terminal: {url}")
        print("Workspaces: INTRADAY / SWING / INVESTMENT")
        print("Sessions: explicit START/PAUSE; saved positions remain monitored")
        print("Data: verified provider data only; invalid/stale data blocks new entries")
        print("Decision authority: V15 PORTFOLIO-ADJUSTED CONTEXTUAL UTILITY")
        print("Risk geometry: V14.1 VERIFIED COMPLETED-BAR GEOMETRY")
        print("Ledger: one canonical Paper Desk with workspace capital partitions")
        print("Live broker execution: LOCKED")

        if os.getenv("JARVIS_NO_BROWSER", "0").strip().lower() not in {"1", "true", "yes", "on"}:
            import webbrowser
            webbrowser.open(url)

        server.serve_forever(poll_interval=0.25)
        return 0
    except KeyboardInterrupt:
        return 0
    finally:
        if runtime is not None:
            runtime.stop()
        server.server_close()


if __name__ == "__main__":
    raise SystemExit(main())
