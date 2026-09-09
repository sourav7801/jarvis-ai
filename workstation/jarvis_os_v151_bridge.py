"""V15.1 read-only extension of protected V8/V15 Master authority."""
from __future__ import annotations

from omni.loopback_http import exclusive_server
from workstation import jarvis_os_v15_bridge as v15


HOST = v15.HOST
PORT = v15.PORT


class V151BridgeHandler(v15.V15BridgeHandler):
    server_version = "JarvisOSV8-V15.1OptionsBridge/1.0"

    def do_GET(self) -> None:
        if self.path.split("?", 1)[0] == "/api/v15.1/paper-authority":
            try:
                from workstation.v151_runtime_bridges import status as runtime_status
                runtime = runtime_status()
            except Exception:
                runtime = {"installed": False, "v15_market_reasoning_preserved": False}
            return self.send_json({
                "success": True,
                "version": "15.1",
                "service": "JARVIS_MASTER_V151_OPTIONS_EXECUTION_BRIDGE",
                "protected_master_identity": "V8_UNIFIED_INTELLIGENCE",
                "v151_bridge_installed": runtime.get("installed") is True,
                "v15_market_reasoning_preserved": runtime.get("v15_market_reasoning_preserved") is True,
                "v141_risk_geometry_preserved": runtime.get("v141_risk_geometry_preserved") is True,
                "options_intelligence_ready": runtime.get("options_intelligence_ready") is True,
                "read_only_chain_provider_preserved": True,
                "long_premium_only": True,
                "naked_option_selling": False,
                "verified_option_chain_required": True,
                "verified_instrument_spec_required": True,
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


def create_server(host: str = HOST, port: int = PORT):
    return exclusive_server(host, int(port), V151BridgeHandler)


__all__ = ["HOST", "PORT", "V151BridgeHandler", "create_server"]
