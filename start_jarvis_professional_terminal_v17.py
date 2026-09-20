from __future__ import annotations

"""JARVIS V17 professional autonomous-options PAPER terminal launcher.

V17 converges the verified V16 runtime rather than creating another trading
stack. One scanner, one canonical Paper Desk, one workspace ledger and one
option-admission authority remain in force.
"""

import os
import threading

# Entry sessions remain explicit. Once INTRADAY/SWING is started, the scanner
# can select verified option contracts without manual strike/lot/BUY clicks.
os.environ["JARVIS_AUTO_PAPER_START"] = "0"
os.environ["JARVIS_V12_AUTO_PAPER_START"] = "0"
os.environ["JARVIS_V17_AUTONOMOUS_OPTIONS"] = "1"
os.environ["JARVIS_LIVE_EXECUTION"] = "0"

from workstation import quant_terminal_v2 as trading_app
from workstation import terminal_data
from workstation.professional_terminal import TerminalHTTPServer, TerminalRuntime
from workstation.v17_terminal_http import build_handler

from start_jarvis_professional_terminal_v16 import install_verified_reasoning_lineage


def main() -> int:
    try:
        server = TerminalHTTPServer((trading_app.HOST, trading_app.PORT), trading_app.Handler)
    except OSError as exc:
        print(f"Professional terminal port {trading_app.PORT} is already owned: {exc}")
        print(f"Open http://{trading_app.HOST}:{trading_app.PORT} or stop the owned JARVIS runtime first.")
        return 1

    runtime: TerminalRuntime | None = None
    try:
        install_verified_reasoning_lineage()

        from workstation.paper_trading_desk import paper_desk
        from workstation.paper_portfolio_controller import paper_portfolio_controller
        from workstation.v17_autonomous_options import install_v17_autonomous_options

        # Shared/single-flight market reads are mandatory in V17. This reduces
        # duplicate FYERS calls from chart, scanner, strategy and option views.
        terminal_data.CACHE_ENABLED = True

        runtime = TerminalRuntime(paper_desk, paper_portfolio_controller)
        autonomy = install_v17_autonomous_options(runtime)
        server.RequestHandlerClass = build_handler(trading_app.Handler, runtime)
        runtime.start()

        # Existing provider bridge remains the single data ingress. It is kept
        # off the HTTP thread so provider delays/rate limits do not freeze UI or
        # position management.
        threading.Thread(
            target=trading_app.start_live_bridge,
            name="JarvisV17DataStartup",
            daemon=True,
        ).start()

        # V17.3 durable PAPER intent is reconciled at process boot, not only
        # after a browser status request.  A fresh install defaults DISARMED;
        # only an explicit prior START JARVIS can persist armed=True.
        from workstation.v17_autopilot_preferences import load_preferences
        from workstation.v17_cross_market_control_plane import cross_market_control_plane
        from workstation.v17_crypto_paper_lane import crypto_paper_lane

        boot_preferences = load_preferences()
        boot_control = cross_market_control_plane.reconcile(
            runtime,
            preferences=boot_preferences,
            force=True,
            crypto_lane=crypto_paper_lane,
        )

        url = f"http://{trading_app.HOST}:{trading_app.PORT}"
        status = autonomy.status("INTRADAY")
        print("=" * 76)
        print("JARVIS V17 - AUTONOMOUS OPTIONS PAPER RUNTIME")
        print("=" * 76)
        print(f"Terminal: {url}")
        print(f"V17 status: {url}/api/v17/trading/status?workspace=INTRADAY")
        print(f"Canonical state: {url}/api/v16/trading/workspace-state?workspace=INTRADAY")
        print("Workspaces: INTRADAY / SWING / INVESTMENT")
        print("Flow: live provider data -> completed bars -> scanner -> strategy -> option selector -> risk -> Paper Desk -> journal")
        print("Manual option selection: NOT REQUIRED for verified autonomous option plans")
        print("Verified automatic option underlyings: " + ", ".join(status["verified_auto_option_underlyings"]))
        print("Broader futures/commodity/crypto markets: scan/research enabled where provider data exists; option entry fails closed until an exact contract provider is verified")
        print("Frequency: broad continuous opportunity scanning; NO forced trade quota")
        print("Shared market-data cache: ENABLED")
        print("Visible terminal identity: V17 AUTONOMOUS OPTIONS")
        print(
            "Cross-market PAPER control: "
            + ("ARMED / AUTO-RESUME" if boot_control.get("armed") else "DISARMED")
            + f" · {boot_control.get('last_action') or 'UNKNOWN'}"
        )
        print("Live broker execution: LOCKED")
        print("Mode: PAPER ONLY")

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
