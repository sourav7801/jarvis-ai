"""V15 read-only extension of protected V8/V14.1 Master authority."""
from __future__ import annotations

from omni.loopback_http import exclusive_server
from workstation import jarvis_os_v141_bridge as v141


HOST = v141.HOST
PORT = v141.PORT


class V15BridgeHandler(v141.V141BridgeHandler):
    server_version = "JarvisOSV8-V15Bridge/1.0"

    def do_GET(self) -> None:
        if self.path.split("?", 1)[0] == "/api/v15/paper-authority":
            try:
                from workstation.v15_runtime_bridges import status as runtime_status
                from omni.trading_intelligence.autonomous_decision_engine_v15 import AUTONOMOUS_DECISION_ENGINE_V15
                runtime = runtime_status()
                policy = AUTONOMOUS_DECISION_ENGINE_V15.status()
            except Exception:
                runtime = {"installed": False, "v141_risk_geometry_installed": False}
                policy = {"decision_authority": "PORTFOLIO_ADJUSTED_CONTEXTUAL_UTILITY_CONTINUOUS_RISK"}
            return self.send_json({
                "success": True,
                "version": "15.0",
                "service": "JARVIS_MASTER_V15_AUTONOMOUS_MARKET_REASONING_BRIDGE",
                "protected_master_identity": "V8_UNIFIED_INTELLIGENCE",
                "v15_bridge_installed": runtime.get("installed") is True,
                "market_reasoning_ready": runtime.get("market_belief_model") is True,
                "portfolio_allocator_ready": runtime.get("portfolio_opportunity_cost") is True,
                "v141_risk_geometry_preserved": runtime.get("v141_risk_geometry_installed") is True,
                "decision_authority": policy.get("decision_authority") or "PORTFOLIO_ADJUSTED_CONTEXTUAL_UTILITY_CONTINUOUS_RISK",
                "portfolio_allocator_can_only_reduce_v14_risk": True,
                "invalid_risk_levels_hard_blocker_preserved": True,
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
    return exclusive_server(host, int(port), V15BridgeHandler)


__all__ = ["HOST", "PORT", "V15BridgeHandler", "create_server"]
