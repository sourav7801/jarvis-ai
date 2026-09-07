"""V13 process-local extension of the protected V8/V12 Master surface.

The visible Master remains V8 Unified Intelligence. V13 adds a read-only
identity endpoint proving contextual paper-command authority is installed in
this exact process. No live broker/order API is exposed.
"""
from __future__ import annotations

from omni.loopback_http import exclusive_server
from workstation import jarvis_os_v12_bridge as v12


HOST = v12.HOST
PORT = v12.PORT


class V13BridgeHandler(v12.V12BridgeHandler):
    server_version = "JarvisOSV8-V13Bridge/1.0"

    def do_GET(self) -> None:
        if self.path.split("?", 1)[0] == "/api/v13/paper-authority":
            try:
                from workstation.v13_runtime_bridges import status as bridge_status
                bridge = bridge_status()
            except Exception:
                bridge = {"installed": False}
            return self.send_json({
                "success": True,
                "version": "13.0",
                "service": "JARVIS_MASTER_V13_CONTEXTUAL_BRIDGE",
                "protected_master_identity": "V8_UNIFIED_INTELLIGENCE",
                "contextual_bridge_installed": bridge.get("installed") is True,
                "decision_authority": bridge.get("decision_authority") or "CONTEXTUAL_EXPECTED_VALUE_NOT_STATIC_SCORE",
                "static_score_execution_authority": False,
                "static_discovery_score_gate": False if bridge.get("installed") else None,
                "paper_only": True,
                "live_execution": False,
                "automatic_broker_order": False,
                "automatic_production_strategy_rewrite": False,
            })
        return super().do_GET()


def create_server(host: str = HOST, port: int = PORT):
    return exclusive_server(host, int(port), V13BridgeHandler)


__all__ = ["HOST", "PORT", "V13BridgeHandler", "create_server"]
