"""JARVIS V14 Autonomous Execution Intelligence Center."""
from __future__ import annotations

import urllib.parse
from typing import Any, Callable

from omni.loopback_http import exclusive_server
from omni.subsystem_snapshot import SubsystemSnapshotCollector, sanitize_error
from workstation import completion_console_v13 as v13


HOST = v13.HOST
PORT = v13.PORT
STATIC = v13.STATIC
HEALTH = v13.HEALTH
V14 = SubsystemSnapshotCollector(max_inflight=5)


def _execution_policy() -> dict[str, Any]:
    from omni.trading_intelligence.continuous_execution_policy_v14 import (
        CONTINUOUS_EXECUTION_POLICY_V14,
    )
    return CONTINUOUS_EXECUTION_POLICY_V14.status()


def _runtime_bridge() -> dict[str, Any]:
    from workstation.v14_runtime_bridges import status
    return status()


def _lifecycle() -> dict[str, Any]:
    from workstation.opportunity_lifecycle_v14 import OPPORTUNITY_LIFECYCLE_V14
    return OPPORTUNITY_LIFECYCLE_V14.snapshot(limit=120)


def _sizing() -> dict[str, Any]:
    from workstation.paper_execution_sizing_v13 import status
    return status()


def _providers() -> dict[str, Callable[[], Any]]:
    return {
        "continuous_execution_policy": _execution_policy,
        "v14_runtime_bridge": _runtime_bridge,
        "opportunity_lifecycle": _lifecycle,
        "constraint_aware_fractional_sizing": _sizing,
    }


def overview_payload() -> dict[str, Any]:
    payload = v13.overview_payload()
    payload["version"] = "14.0"
    advanced = V14.collect(_providers(), timeout=2.5)
    payload.setdefault("subsystems", {}).update(advanced)
    for name, row in advanced.items():
        payload[name] = row.get("data") if row.get("healthy") else None
    if not all(row.get("healthy") for row in advanced.values()):
        payload["overall"] = "DEGRADED"
    payload.setdefault("advanced", {}).update({
        "v13_contextual_intelligence": True,
        "continuous_positive_ev_execution": True,
        "uncertainty_scaled_position_risk": True,
        "fractional_constraint_aware_sizing": True,
        "opportunity_lifecycle": True,
        "watching_is_terminal_state": False,
        "quant_runtime_authoritative": True,
    })
    payload["decision_authority"] = {
        "version": "14.0",
        "model": "POSITIVE_CONTEXTUAL_EXPECTED_VALUE_CONTINUOUS_RISK",
        "context_base": "V13_CONTEXTUAL_EXPECTED_VALUE_WITH_OUTCOME_MEMORY",
        "score_67_68_70": "OBSERVABILITY_ONLY",
        "confidence": "POSITION_SIZE_INPUT_ONLY",
        "alignment": "CONTINUOUS_EVIDENCE_ONLY",
        "static_risk_reward": "NOT_EXECUTION_AUTHORITY",
        "positive_ev_boundary_r": 0.0,
        "primary_probe_labels_are_execution_gates": False,
        "hard_data_safety_blockers_preserved": True,
    }
    payload.setdefault("safety", {}).update({
        "paper_only": True,
        "live_execution": False,
        "automatic_broker_order": False,
        "automatic_production_strategy_rewrite": False,
        "external_actions": "APPROVAL_GATED",
    })
    return payload


class CompletionHandlerV14(v13.CompletionHandlerV13):
    server_version = "JARVISCompletion/14.0"

    def do_GET(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        if path == "/v14_autonomous_execution.js":
            return self.send_file(STATIC / "v14_autonomous_execution.js", "application/javascript; charset=utf-8")
        if path == "/api/overview":
            try:
                payload = overview_payload()
                if payload.get("overall") == "READY":
                    HEALTH.mark_success()
                return self.send_json(payload)
            except Exception as exc:
                HEALTH.mark_error(exc)
                return self.send_json({
                    "success": False,
                    "message": f"{type(exc).__name__}: {sanitize_error(exc)}"[:500],
                    "paper_only": True,
                    "live_execution": False,
                }, 500)
        if path == "/api/v14/execution-authority":
            return self.send_json({
                "success": True,
                "version": "14.0",
                "service": "JARVIS_V14_CONTINUOUS_EXECUTION_AUTHORITY",
                "policy": _execution_policy(),
                "runtime": _runtime_bridge(),
                "sizing": _sizing(),
                "paper_only": True,
                "live_execution": False,
                "automatic_broker_order": False,
            })
        if path == "/api/v14/opportunity-lifecycle":
            return self.send_json(_lifecycle())
        if path == "/api/v14/status":
            bridge = _runtime_bridge()
            sizing = _sizing()
            return self.send_json({
                "success": True,
                "version": "14.0",
                "service": "JARVIS_AUTONOMOUS_EXECUTION_INTELLIGENCE_OS",
                "decision_authority": "POSITIVE_CONTEXTUAL_EXPECTED_VALUE_CONTINUOUS_RISK",
                "features": {
                    "v13_contextual_outcome_memory": True,
                    "continuous_positive_ev_execution": True,
                    "uncertainty_scales_risk_not_execution": True,
                    "arbitrary_confidence_execution_gate": False,
                    "static_score_execution_authority": False,
                    "static_alignment_execution_authority": False,
                    "static_risk_reward_execution_authority": False,
                    "fractional_constraint_aware_sizing": True,
                    "opportunity_lifecycle": True,
                    "watching_is_terminal_state": False,
                },
                "runtime_bridge_installed": bridge.get("installed") is True,
                "fractional_sizing_installed": sizing.get("installed") is True,
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
    from workstation.v14_runtime_bridges import install_v14_runtime_bridges

    bridge = install_v14_runtime_bridges()
    server = exclusive_server(HOST, PORT, CompletionHandlerV14)
    print("=" * 72)
    print("JARVIS V14 AUTONOMOUS EXECUTION INTELLIGENCE CENTER")
    print("=" * 72)
    print(f"Console: http://{HOST}:{PORT}")
    print("Decision authority: POSITIVE CONTEXTUAL EXPECTED VALUE / CONTINUOUS RISK")
    print("Confidence: POSITION SIZE INPUT / NOT EXECUTION GATE")
    print("Opportunity lifecycle: EXACT WAIT / BLOCK / ACTIONABLE / OPENED STATES")
    print("Fractional sizing: CONSTRAINT-AWARE / PAPER DESK FINAL AUTHORITY")
    print("V14 bridge:", "READY" if bridge.get("installed") else "DEGRADED")
    print("Paper trading: PERMITTED")
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
