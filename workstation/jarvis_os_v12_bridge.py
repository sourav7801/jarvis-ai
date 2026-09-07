"""V12 process-local extension of the protected V8 Master HTTP server.

The visual/command surface remains the V8 Unified Intelligence OS. V12 adds one
read-only identity endpoint so the runtime supervisor can prove that the Master
process actually installed adaptive paper-command authority rather than merely
adopting an older V8 listener. No live broker/order API exists here.
"""
from __future__ import annotations

from omni.loopback_http import exclusive_server
from workstation import jarvis_os_v8 as v8


HOST = v8.HOST
PORT = v8.PORT


class V12BridgeHandler(v8.V8Handler):
    server_version = "JarvisOSV8-V12Bridge/1.0"

    def do_GET(self) -> None:
        if self.path.split("?", 1)[0] == "/api/v12/paper-authority":
            try:
                from workstation.v12_runtime_bridges import status as bridge_status

                bridge = bridge_status()
            except Exception:
                bridge = {"installed": False}
            return self.send_json({
                "success": True,
                "version": "12.0",
                "service": "JARVIS_MASTER_V12_ADAPTIVE_BRIDGE",
                "protected_master_identity": "V8_UNIFIED_INTELLIGENCE",
                "adaptive_bridge_installed": bridge.get("installed") is True,
                "decision_authority": bridge.get("decision_authority") or "ADAPTIVE_EXPECTED_VALUE_NOT_STATIC_SCORE",
                "paper_only": True,
                "live_execution": False,
                "automatic_broker_order": False,
            })
        return super().do_GET()


def create_server(host: str = HOST, port: int = PORT):
    return exclusive_server(host, int(port), V12BridgeHandler)


__all__ = ["HOST", "PORT", "V12BridgeHandler", "create_server"]
