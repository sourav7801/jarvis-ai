"""V14 process-local extension of protected V8/V13 Master paper authority."""
from __future__ import annotations

from omni.loopback_http import exclusive_server
from workstation import jarvis_os_v13_bridge as v13


HOST = v13.HOST
PORT = v13.PORT


class V14BridgeHandler(v13.V13BridgeHandler):
    server_version = "JarvisOSV8-V14Bridge/1.0"

    def do_GET(self) -> None:
        if self.path.split("?", 1)[0] == "/api/v14/paper-authority":
            try:
                from workstation.v14_runtime_bridges import status as runtime_status
                from omni.trading_intelligence.continuous_execution_policy_v14 import (
                    CONTINUOUS_EXECUTION_POLICY_V14,
                )
                from workstation.opportunity_lifecycle_v14 import OPPORTUNITY_LIFECYCLE_V14

                runtime = runtime_status()
                policy = CONTINUOUS_EXECUTION_POLICY_V14.status()
                lifecycle = OPPORTUNITY_LIFECYCLE_V14.snapshot(limit=20)
            except Exception:
                runtime = {"installed": False}
                policy = {"decision_authority": "POSITIVE_CONTEXTUAL_EXPECTED_VALUE_CONTINUOUS_RISK"}
                lifecycle = {"active_count": 0}
            return self.send_json({
                "success": True,
                "version": "14.0",
                "service": "JARVIS_MASTER_V14_AUTONOMOUS_EXECUTION_BRIDGE",
                "protected_master_identity": "V8_UNIFIED_INTELLIGENCE",
                "v14_bridge_installed": runtime.get("installed") is True,
                "decision_authority": policy.get("decision_authority") or "POSITIVE_CONTEXTUAL_EXPECTED_VALUE_CONTINUOUS_RISK",
                "positive_ev_execution_boundary_r": 0.0,
                "uncertainty_scales_risk_not_execution": True,
                "arbitrary_confidence_execution_gate": False,
                "static_score_execution_authority": False,
                "fractional_constraint_aware_sizing": runtime.get("fractional_constraint_aware_sizing") is True,
                "watching_is_terminal_state": False,
                "opportunity_lifecycle_active": lifecycle.get("active_count", 0),
                "paper_only": True,
                "live_execution": False,
                "automatic_broker_order": False,
                "automatic_production_strategy_rewrite": False,
            })
        return super().do_GET()


def create_server(host: str = HOST, port: int = PORT):
    return exclusive_server(host, int(port), V14BridgeHandler)


__all__ = ["HOST", "PORT", "V14BridgeHandler", "create_server"]
