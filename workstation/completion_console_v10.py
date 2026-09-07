"""JARVIS V10 Completion Center convergence surface.

Extends V9.3 World Model/Cognitive Center with system-level Critic, Evidence
Ledger, governed Engineering, System Diagnostics and Trading Governance. No
broker-order or production-deployment surface is exposed.
"""
from __future__ import annotations

import urllib.parse
from typing import Any, Callable

from omni.loopback_http import exclusive_server
from omni.subsystem_snapshot import SubsystemSnapshotCollector, sanitize_error
from workstation import completion_console_v93 as v93

HOST = v93.HOST
PORT = v93.PORT
STATIC = v93.STATIC
HEALTH = v93.HEALTH
ADVANCED = SubsystemSnapshotCollector(max_inflight=5)


def _critic() -> Any:
    from omni.critic_verifier import CRITIC_VERIFIER
    return CRITIC_VERIFIER.status()


def _evidence() -> Any:
    from omni.evidence_ledger import EVIDENCE_LEDGER
    return EVIDENCE_LEDGER.snapshot(limit=100)


def _engineering() -> Any:
    from omni.engineering_governance import ENGINEERING_GOVERNANCE
    return {"status": ENGINEERING_GOVERNANCE.status(), "repository": ENGINEERING_GOVERNANCE.inspect()}


def _diagnostics() -> Any:
    from omni.system_diagnostics import SYSTEM_DIAGNOSTICS
    return SYSTEM_DIAGNOSTICS.inspect()


def _trading_governance() -> Any:
    from omni.trading_intelligence.trading_governance_center import TRADING_GOVERNANCE_CENTER
    return TRADING_GOVERNANCE_CENTER.snapshot(days=31)


def _advanced_providers() -> dict[str, Callable[[], Any]]:
    return {
        "critic_verifier": _critic,
        "evidence_ledger": _evidence,
        "engineering_governance": _engineering,
        "system_diagnostics": _diagnostics,
        "trading_governance": _trading_governance,
    }


def overview_payload() -> dict[str, Any]:
    payload = v93.overview_payload()
    payload["version"] = "10.0"
    advanced = ADVANCED.collect(_advanced_providers(), timeout=2.5)
    payload.setdefault("subsystems", {}).update(advanced)
    for name, row in advanced.items():
        payload[name] = row.get("data") if row.get("healthy") else None
    if not all(row.get("healthy") for row in advanced.values()):
        payload["overall"] = "DEGRADED"
    payload["advanced"] = {
        "system_critic": True,
        "evidence_ledger": True,
        "governed_engineering": True,
        "system_diagnostics": True,
        "trading_governance": True,
        "world_model": True,
        "cognitive_bus": True,
    }
    payload.setdefault("safety", {}).update({
        "paper_only": True,
        "live_execution": False,
        "automatic_broker_order": False,
        "automatic_production_strategy_rewrite": False,
        "external_actions": "APPROVAL_GATED",
    })
    return payload


class CompletionHandlerV10(v93.CompletionHandlerV93):
    server_version = "JARVISCompletion/10.0"

    def do_GET(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        params = urllib.parse.parse_qs(parsed.query)
        if path == "/v93_world.js":
            return self.send_file(STATIC / "v93_world.js", "application/javascript; charset=utf-8")
        if path == "/v10_advanced.js":
            return self.send_file(STATIC / "v10_advanced.js", "application/javascript; charset=utf-8")
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
        if path == "/api/critic":
            return self.send_json(_critic())
        if path == "/api/evidence":
            from omni.evidence_ledger import EVIDENCE_LEDGER
            kind = str((params.get("kind") or [""])[0]).strip() or None
            correlation_id = str((params.get("correlation_id") or [""])[0]).strip() or None
            return self.send_json(EVIDENCE_LEDGER.snapshot(limit=100, kind=kind, correlation_id=correlation_id))
        if path == "/api/engineering":
            return self.send_json(_engineering())
        if path == "/api/system-diagnostics":
            return self.send_json(_diagnostics())
        if path == "/api/trading-governance":
            return self.send_json(_trading_governance())
        if path == "/api/v10/status":
            return self.send_json({
                "success": True,
                "version": "10.0",
                "service": "JARVIS_ADVANCED_AUTONOMY_CONVERGENCE",
                "features": {
                    "world_model": True,
                    "cognitive_bus": True,
                    "goal_task_graph": True,
                    "mission_worker": True,
                    "critic_verifier": True,
                    "evidence_ledger": True,
                    "governed_engineering": True,
                    "system_diagnostics": True,
                    "trading_governance": True,
                },
                "permanent_agents": 29,
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
        body = self._body()
        try:
            if path == "/api/critic/verify":
                from omni.critic_verifier import CRITIC_VERIFIER
                result = CRITIC_VERIFIER.verify(
                    subject=str(body.get("subject") or "operator-verification")[:500],
                    domain=str(body.get("domain") or "GENERAL"),
                    evidence=list(body.get("evidence") or [])[:100],
                    contradictions=list(body.get("contradictions") or [])[:50],
                    tool_results=list(body.get("tool_results") or [])[:100],
                    required_evidence=int(body.get("required_evidence") or 1),
                    require_fresh=bool(body.get("require_fresh", False)),
                    require_provenance=bool(body.get("require_provenance", False)),
                    policy={
                        "paper_only": True,
                        "live_execution": False,
                        "automatic_broker_order": False,
                        "automatic_production_strategy_rewrite": False,
                        "external_actions": "APPROVAL_GATED",
                    },
                    correlation_id=str(body.get("correlation_id") or "") or None,
                )
                return self.send_json(result)
            if path == "/api/engineering/plan":
                from omni.engineering_governance import ENGINEERING_GOVERNANCE
                return self.send_json(ENGINEERING_GOVERNANCE.plan(str(body.get("request") or "")))
            if path == "/api/engineering/review":
                from omni.engineering_governance import ENGINEERING_GOVERNANCE
                packet = ENGINEERING_GOVERNANCE.review_packet(
                    request=str(body.get("request") or ""),
                    known_risks=list(body.get("known_risks") or [])[:30],
                )
                return self.send_json(packet)
            if path == "/api/system/recover":
                from omni.system_diagnostics import SYSTEM_DIAGNOSTICS
                return self.send_json(SYSTEM_DIAGNOSTICS.apply_safe_recovery(str(body.get("action") or "")))
        except (ValueError, KeyError, RuntimeError, PermissionError) as exc:
            return self.send_json({"success": False, "message": sanitize_error(exc)[:500]}, 409)
        return super().do_POST()


def main() -> int:
    server = exclusive_server(HOST, PORT, CompletionHandlerV10)
    print("=" * 72)
    print("JARVIS V10 ADVANCED AUTONOMY / GOVERNANCE CENTER")
    print("=" * 72)
    print(f"Console: http://{HOST}:{PORT}")
    print("World Model + Cognitive Bus: ENABLED")
    print("System Critic + Evidence Ledger: ENABLED")
    print("Governed Engineering + Diagnostics: ENABLED")
    print("Trading Governance: PAPER / RESEARCH ONLY")
    print("External actions: APPROVAL GATED")
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
