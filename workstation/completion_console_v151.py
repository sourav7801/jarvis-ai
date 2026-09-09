"""JARVIS V15.1 Options Execution Intelligence Completion Center."""
from __future__ import annotations

import urllib.parse

from workstation import completion_console_v15 as v15


HOST = v15.HOST
PORT = v15.PORT
STATIC = v15.STATIC
HEALTH = v15.HEALTH


class CompletionHandlerV151(v15.CompletionHandlerV15):
    server_version = "JARVISCompletion/15.1"

    def do_GET(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        params = urllib.parse.parse_qs(parsed.query)
        if path == "/v151_options_execution.js":
            return self.send_file(STATIC / "v151_options_execution.js", "application/javascript; charset=utf-8")
        if path == "/api/v15.1/options/status":
            return self._proxy("/api/v15.1/options/status")
        if path == "/api/v15.1/options/plan":
            symbol = urllib.parse.quote(str((params.get("symbol") or ["NIFTY"])[0]).strip().upper() or "NIFTY")
            provider = urllib.parse.quote(str((params.get("provider") or ["fyers"])[0]).strip().lower() or "fyers")
            return self._proxy(f"/api/v15.1/options/plan?symbol={symbol}&provider={provider}", timeout=100.0)
        if path == "/api/v15.1/status":
            from workstation.v151_runtime_bridges import status as runtime_status
            runtime = runtime_status()
            quant_ready = False
            try:
                quant_status = v15._quant_json("/api/v15.1/status", timeout=8.0)
                quant_ready = (
                    quant_status.get("success") is True
                    and quant_status.get("service") == "JARVIS_QUANT_V151_OPTIONS_EXECUTION_INTELLIGENCE"
                )
            except Exception:
                quant_status = {"success": False}
            return self.send_json({
                "success": True,
                "version": "15.1",
                "service": "JARVIS_OPTIONS_EXECUTION_INTELLIGENCE_OS",
                "runtime_bridge_installed": runtime.get("installed") is True,
                "quant_options_ready": quant_ready,
                "v15_market_reasoning_preserved": runtime.get("v15_market_reasoning_preserved") is True,
                "v141_risk_geometry_preserved": runtime.get("v141_risk_geometry_preserved") is True,
                "long_premium_only": True,
                "naked_option_selling": False,
                "verified_option_chain_required": True,
                "verified_instrument_spec_required": True,
                "read_only_chain_provider_preserved": True,
                "dealer_positioning": "UNAVAILABLE_WITHOUT_VERIFIED_INVENTORY",
                "permanent_agents": 29,
                "system_planes_do_not_count_as_agents": True,
                "paper_only": True,
                "live_execution": False,
                "automatic_broker_order": False,
                "automatic_production_strategy_rewrite": False,
                "external_actions": "APPROVAL_GATED",
            })
        return super().do_GET()


def main() -> int:
    from workstation.v151_runtime_bridges import install_v151_runtime_bridges
    from omni.loopback_http import exclusive_server

    bridge = install_v151_runtime_bridges()
    server = exclusive_server(HOST, PORT, CompletionHandlerV151)
    print("=" * 72)
    print("JARVIS V15.1 OPTIONS EXECUTION INTELLIGENCE CENTER")
    print("=" * 72)
    print(f"Console: http://{HOST}:{PORT}")
    print("Underlying brain: V15 AUTONOMOUS MARKET REASONING")
    print("Option expression: VERIFIED CHAIN + VERIFIED CONTRACT ECONOMICS")
    print("Option execution: LONG PREMIUM PAPER ONLY")
    print("Naked short options: DISABLED")
    print("Dealer positioning: UNAVAILABLE WITHOUT VERIFIED DEALER INVENTORY")
    print("V15.1 bridge:", "READY" if bridge.get("installed") else "DEGRADED")
    print("Live broker execution: LOCKED")
    try:
        server.serve_forever(poll_interval=0.5)
    except KeyboardInterrupt:
        return 0
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
