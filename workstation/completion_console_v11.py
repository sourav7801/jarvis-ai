"""JARVIS V11 Cognitive Execution Completion Center.

Extends V10 with the Governed Execution Mesh, unified Trading Decision Mesh,
portfolio-aware discovery routing convergence and a completed-bar 10m derived
research lane. Quant owns scanner/controller execution state on port 8787;
Completion reads that authoritative state over loopback instead of creating
shadow scanner/controller singletons in the 8799 process.

All new surfaces remain system/read-only or paper-only; no live broker order or
production self-rewrite capability is introduced.
"""
from __future__ import annotations

import urllib.parse
from typing import Any, Callable

from omni.loopback_http import exclusive_server
from omni.subsystem_snapshot import SubsystemSnapshotCollector, sanitize_error
from workstation import completion_console_v10 as v10

HOST = v10.HOST
PORT = v10.PORT
STATIC = v10.STATIC
HEALTH = v10.HEALTH
V11 = SubsystemSnapshotCollector(max_inflight=5)


def _execution_mesh() -> dict[str, Any]:
    from omni.governed_execution_mesh import GOVERNED_EXECUTION_MESH
    return GOVERNED_EXECUTION_MESH.status()


def _trading_decision_mesh() -> dict[str, Any]:
    from workstation.trading_decision_mesh import TRADING_DECISION_MESH
    return TRADING_DECISION_MESH.snapshot(limit=80)


def _derived_timeframe() -> dict[str, Any]:
    """Read 10m runtime state from the authoritative Quant process."""

    from workstation.trading_decision_mesh import TRADING_DECISION_MESH, _loopback_json

    controller = _loopback_json("/api/paper/portfolio-controller", timeout=4.0)
    return TRADING_DECISION_MESH._derived_10m_runtime(controller)


def _discovery_routing() -> dict[str, Any]:
    """Read governed discovery-routing state from the authoritative scanner."""

    from workstation.trading_decision_mesh import TRADING_DECISION_MESH, _loopback_json

    scanner = _loopback_json("/api/scanner/multi", timeout=4.0)
    return TRADING_DECISION_MESH._routing_runtime(scanner)


def _v11_providers() -> dict[str, Callable[[], Any]]:
    return {
        "governed_execution_mesh": _execution_mesh,
        "trading_decision_mesh": _trading_decision_mesh,
        "derived_10m_timeframe": _derived_timeframe,
        "discovery_routing_bridge": _discovery_routing,
    }


def overview_payload() -> dict[str, Any]:
    payload = v10.overview_payload()
    payload["version"] = "11.0"
    advanced = V11.collect(_v11_providers(), timeout=3.0)
    payload.setdefault("subsystems", {}).update(advanced)
    for name, row in advanced.items():
        payload[name] = row.get("data") if row.get("healthy") else None
    if not all(row.get("healthy") for row in advanced.values()):
        payload["overall"] = "DEGRADED"
    payload.setdefault("advanced", {}).update({
        "governed_execution_mesh": True,
        "trading_decision_mesh": True,
        "portfolio_horizon_discovery_routing": True,
        "derived_10m_completed_bars": True,
        "discovery_execution_score_separation": True,
        "why_not_trade_diagnostics": True,
        "quant_runtime_authoritative": True,
    })
    payload.setdefault("safety", {}).update({
        "paper_only": True,
        "live_execution": False,
        "automatic_broker_order": False,
        "automatic_production_strategy_rewrite": False,
        "external_actions": "APPROVAL_GATED",
    })
    return payload


class CompletionHandlerV11(v10.CompletionHandlerV10):
    server_version = "JARVISCompletion/11.0"

    def do_GET(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        params = urllib.parse.parse_qs(parsed.query)
        if path == "/v11_execution_mesh.js":
            return self.send_file(STATIC / "v11_execution_mesh.js", "application/javascript; charset=utf-8")
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
                    "automatic_broker_order": False,
                }, 500)
        if path == "/api/execution-mesh":
            return self.send_json(_execution_mesh())
        if path == "/api/trading-decision-mesh":
            return self.send_json(_trading_decision_mesh())
        if path == "/api/trading-decision/explain":
            from workstation.trading_decision_mesh import TRADING_DECISION_MESH
            symbol = str((params.get("symbol") or [""])[0]).strip()
            try:
                return self.send_json(TRADING_DECISION_MESH.explain(symbol))
            except ValueError as exc:
                return self.send_json({"success": False, "message": sanitize_error(exc)[:500]}, 400)
        if path == "/api/derived-timeframe":
            return self.send_json(_derived_timeframe())
        if path == "/api/discovery-routing":
            return self.send_json(_discovery_routing())
        if path == "/api/v11/status":
            return self.send_json({
                "success": True,
                "version": "11.0",
                "service": "JARVIS_COGNITIVE_EXECUTION_CONVERGENCE",
                "features": {
                    "governed_execution_mesh": True,
                    "autonomy_orchestrator": True,
                    "world_model": True,
                    "cognitive_bus": True,
                    "critic_verifier": True,
                    "evidence_ledger": True,
                    "trading_decision_mesh": True,
                    "why_not_trade_diagnostics": True,
                    "portfolio_horizon_discovery_routing": True,
                    "derived_10m_completed_bars": True,
                    "quant_runtime_authoritative": True,
                    "governed_engineering": True,
                    "system_diagnostics": True,
                },
                "permanent_agents": 29,
                "system_planes_do_not_count_as_agents": True,
                "paper_only": True,
                "live_execution": False,
                "automatic_broker_order": False,
                "automatic_production_strategy_rewrite": False,
                "external_actions": "APPROVAL_GATED",
            })
        return super().do_GET()

    def do_POST(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        if path != "/api/execution-mesh/plan":
            return super().do_POST()
        body = self._body()
        try:
            from omni.governed_execution_mesh import GOVERNED_EXECUTION_MESH
            return self.send_json(GOVERNED_EXECUTION_MESH.plan(
                str(body.get("objective") or ""),
                enqueue_mission=bool(body.get("enqueue_mission", False)),
            ))
        except (ValueError, KeyError, RuntimeError, PermissionError) as exc:
            return self.send_json({"success": False, "message": sanitize_error(exc)[:500]}, 409)


def main() -> int:
    # Do not install scanner/controller bridges in the Completion process.
    # Quant on 8787 owns the live paper/scanner singletons; V11 reads that state
    # via bounded loopback endpoints and leaves process ownership explicit.
    server = exclusive_server(HOST, PORT, CompletionHandlerV11)
    print("=" * 72)
    print("JARVIS V11 COGNITIVE EXECUTION / MARKET DECISION CENTER")
    print("=" * 72)
    print(f"Console: http://{HOST}:{PORT}")
    print("Governed Execution Mesh: ENABLED / SYSTEM PLANE")
    print("Trading Decision Mesh: ENABLED / WHY-NOT-TRADE")
    print("Quant runtime source: http://127.0.0.1:8787")
    print("Discovery Routing: PORTFOLIO HORIZON CONTROLLER")
    print("10m Research Bars: 2x COMPLETED 5m PROVIDER BARS ONLY")
    print("External actions: APPROVAL GATED")
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
