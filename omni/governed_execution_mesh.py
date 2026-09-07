"""JARVIS V11 governed execution convergence plane.

This system plane turns a high-level objective into one bounded execution packet
that combines the V10 Autonomy Orchestrator with domain state, evidence and
critic verification. It does not become a 30th permanent agent and never gains
live broker, automatic merge/deploy, or unapproved external-action authority.
"""
from __future__ import annotations

from datetime import datetime, timezone
from threading import RLock
from typing import Any, Callable


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe(provider: Callable[[], Any], name: str) -> dict[str, Any]:
    try:
        value = provider()
        return {
            "healthy": True,
            "name": name,
            "data": value if isinstance(value, dict) else {"value": value},
            "error": None,
        }
    except Exception as exc:
        return {
            "healthy": False,
            "name": name,
            "data": {},
            "error": f"{type(exc).__name__}: {exc}"[:500],
        }


class GovernedExecutionMesh:
    """Evidence-first control packet above the permanent specialist registry."""

    def __init__(self) -> None:
        self._lock = RLock()
        self._plans = 0
        self._last: dict[str, Any] | None = None

    @staticmethod
    def _domain_surface(domain: str) -> dict[str, Any]:
        normalized = str(domain or "GENERAL").upper()
        if normalized == "MARKETS":
            return _safe(
                lambda: __import__(
                    "workstation.trading_decision_mesh",
                    fromlist=["TRADING_DECISION_MESH"],
                ).TRADING_DECISION_MESH.snapshot(limit=80),
                "trading_decision_mesh",
            )
        if normalized == "ENGINEERING":
            def engineering() -> dict[str, Any]:
                from omni.engineering_governance import ENGINEERING_GOVERNANCE
                return {
                    "status": ENGINEERING_GOVERNANCE.status(),
                    "repository": ENGINEERING_GOVERNANCE.inspect(),
                }
            return _safe(engineering, "engineering_governance")
        if normalized == "SYSTEM":
            return _safe(
                lambda: __import__(
                    "omni.system_diagnostics", fromlist=["SYSTEM_DIAGNOSTICS"]
                ).SYSTEM_DIAGNOSTICS.inspect(),
                "system_diagnostics",
            )
        if normalized == "MISSION":
            return _safe(
                lambda: __import__(
                    "omni.mission_worker", fromlist=["MISSION_WORKER"]
                ).MISSION_WORKER.status(),
                "mission_worker",
            )
        return {
            "healthy": True,
            "name": "executive_context",
            "data": {"domain": normalized},
            "error": None,
        }

    @staticmethod
    def _step_contract(executive: dict[str, Any]) -> list[dict[str, Any]]:
        plan = list(executive.get("plan") or executive.get("steps") or [])
        rows: list[dict[str, Any]] = []
        for index, raw in enumerate(plan[:40], start=1):
            if isinstance(raw, dict):
                action = str(raw.get("action") or raw.get("capability") or raw.get("name") or f"step-{index}")
                source = dict(raw)
            else:
                action = str(raw)
                source = {"value": raw}
            lowered = action.lower()
            consequential = any(
                token in lowered
                for token in (
                    "send", "publish", "deploy", "merge", "push", "purchase",
                    "external", "order", "broker", "delete", "modify",
                )
            )
            broker_related = any(token in lowered for token in ("broker", "order", "live trade", "live_execution"))
            rows.append({
                "index": index,
                "action": action[:500],
                "source": source,
                "classification": (
                    "LIVE_BROKER_LOCKED" if broker_related
                    else "APPROVAL_REQUIRED" if consequential
                    else "LOCAL_GOVERNED"
                ),
                "automatic_execution_allowed": not consequential and not broker_related,
                "approval_required": consequential,
                "live_broker_allowed": False,
            })
        return rows

    def plan(self, objective: str, *, enqueue_mission: bool = False) -> dict[str, Any]:
        clean = " ".join(str(objective or "").split())[:8000]
        if len(clean) < 8:
            raise ValueError("Execution objective is too short.")

        from omni.autonomy_orchestrator import AUTONOMY_ORCHESTRATOR
        autonomy = AUTONOMY_ORCHESTRATOR.plan(clean, enqueue_mission=enqueue_mission)
        domain = str(autonomy.get("domain") or "GENERAL").upper()
        executive = dict(autonomy.get("executive") or {})
        surface = self._domain_surface(domain)
        steps = self._step_contract(executive)

        evidence = [{
            "source": "autonomy_orchestrator",
            "freshness": "FRESH",
            "provenance": {
                "domain": domain,
                "critic_verification_id": (autonomy.get("critic") or {}).get("verification_id"),
            },
            "claim": "V10 autonomy plan prepared under locked safety policy",
        }]
        contradictions: list[str] = []
        if surface.get("healthy"):
            evidence.append({
                "source": surface.get("name"),
                "freshness": "FRESH",
                "provenance": {"domain": domain, "system_plane": True},
                "claim": "Domain execution state assembled",
            })
        else:
            contradictions.append(f"DOMAIN_SURFACE_UNAVAILABLE:{surface.get('name')}")

        blocked_steps = [row for row in steps if row["classification"] == "LIVE_BROKER_LOCKED"]
        if blocked_steps:
            contradictions.append("LIVE_BROKER_STEP_REQUESTED")

        from omni.critic_verifier import CRITIC_VERIFIER
        critic = CRITIC_VERIFIER.verify(
            subject=f"execution-mesh:{domain}:{clean[:180]}",
            domain=domain,
            evidence=evidence,
            contradictions=contradictions,
            tool_results=[surface.get("data") or {}],
            required_evidence=1,
            require_fresh=True,
            require_provenance=True,
            policy={
                "paper_only": True,
                "live_execution": False,
                "automatic_broker_order": False,
                "automatic_production_strategy_rewrite": False,
                "external_actions": "APPROVAL_GATED",
            },
        )

        approval_steps = [row for row in steps if row.get("approval_required")]
        local_steps = [
            row for row in steps
            if row.get("classification") == "LOCAL_GOVERNED"
        ]
        packet_state = (
            "BLOCKED" if blocked_steps
            else "DEGRADED" if not surface.get("healthy")
            else "APPROVAL_REQUIRED" if approval_steps
            else "READY" if critic.get("progression_allowed")
            else "CRITIC_BLOCKED"
        )
        result = {
            "success": True,
            "version": "11.0",
            "service": "JARVIS_GOVERNED_EXECUTION_MESH",
            "created_at": _now(),
            "objective": clean,
            "domain": domain,
            "state": packet_state,
            "autonomy": autonomy,
            "domain_surface": surface,
            "steps": steps,
            "local_governed_steps": local_steps,
            "approval_required_steps": approval_steps,
            "locked_steps": blocked_steps,
            "critic": critic,
            "mission_queued": autonomy.get("mission_queued"),
            "automatic_mission_start": False,
            "automatic_external_action": False,
            "automatic_merge": False,
            "automatic_deploy": False,
            "paper_only": True,
            "live_execution": False,
            "automatic_broker_order": False,
            "automatic_production_strategy_rewrite": False,
            "external_actions": "APPROVAL_GATED",
        }
        with self._lock:
            self._plans += 1
            self._last = result
        try:
            from omni.evidence_ledger import EVIDENCE_LEDGER
            EVIDENCE_LEDGER.record(
                kind="EXECUTION_MESH_PLAN",
                subject=f"{domain}:{clean[:180]}",
                claim=f"Governed execution packet state={packet_state}",
                source="governed_execution_mesh",
                state=packet_state,
                confidence=float(critic.get("confidence") or 0.5),
                evidence={
                    "local_steps": len(local_steps),
                    "approval_steps": len(approval_steps),
                    "locked_steps": len(blocked_steps),
                },
                provenance={"verification_id": critic.get("verification_id")},
                freshness="FRESH",
            )
        except Exception:
            pass
        return result

    def status(self) -> dict[str, Any]:
        with self._lock:
            plans = self._plans
            last = self._last
        return {
            "success": True,
            "version": "11.0",
            "service": "JARVIS_GOVERNED_EXECUTION_MESH",
            "plans": plans,
            "last_plan": last,
            "system_plane": True,
            "permanent_agent": False,
            "capabilities": {
                "autonomy_convergence": True,
                "domain_state_convergence": True,
                "critic_verification": True,
                "market_decision_mesh": True,
                "approval_classification": True,
                "mission_queueing_explicit": True,
                "automatic_mission_start": False,
            },
            "external_actions": "APPROVAL_GATED",
            "paper_only": True,
            "live_execution": False,
            "automatic_broker_order": False,
            "automatic_production_strategy_rewrite": False,
        }


GOVERNED_EXECUTION_MESH = GovernedExecutionMesh()

__all__ = ["GOVERNED_EXECUTION_MESH", "GovernedExecutionMesh"]
