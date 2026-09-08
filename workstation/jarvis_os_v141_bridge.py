"""V14.1 read-only extension of the protected V8/V14 Master surface."""
from __future__ import annotations

from omni.loopback_http import exclusive_server
from workstation import jarvis_os_v14_bridge as v14


HOST = v14.HOST
PORT = v14.PORT


class V141BridgeHandler(v14.V14BridgeHandler):
    server_version = "JarvisOSV8-V14.1Bridge/1.0"

    def do_GET(self) -> None:
        if self.path.split("?", 1)[0] == "/api/v14.1/paper-authority":
            try:
                from workstation.v141_runtime_bridges import status as runtime_status
                runtime = runtime_status()
            except Exception:
                runtime = {"installed": False, "scan_wrapper_installed": False}
            return self.send_json({
                "success": True,
                "version": "14.1",
                "service": "JARVIS_MASTER_V141_RISK_GEOMETRY_BRIDGE",
                "protected_master_identity": "V8_UNIFIED_INTELLIGENCE",
                "v141_bridge_installed": runtime.get("installed") is True,
                "scan_wrapper_installed": runtime.get("scan_wrapper_installed") is True,
                "risk_geometry_service": "VERIFIED_RISK_GEOMETRY_V14_1",
                "legacy_qualification_required_for_geometry": False,
                "invalid_risk_levels_hard_blocker_preserved": True,
                "decision_authority": "POSITIVE_CONTEXTUAL_EXPECTED_VALUE_CONTINUOUS_RISK",
                "paper_only": True,
                "live_execution": False,
                "automatic_broker_order": False,
                "automatic_production_strategy_rewrite": False,
            })
        return super().do_GET()


def create_server(host: str = HOST, port: int = PORT):
    return exclusive_server(host, int(port), V141BridgeHandler)


__all__ = ["HOST", "PORT", "V141BridgeHandler", "create_server"]
