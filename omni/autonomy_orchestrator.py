"""Top-level governed autonomy orchestrator for JARVIS V10.

The orchestrator converges Executive planning, World/Context, Critic, mission
runtime, governed engineering, diagnostics and paper-trading governance. It may
queue a supervised local mission when explicitly requested, but it never starts
external consequential execution, broker orders, merges, pushes or deployment.
"""
from __future__ import annotations

from datetime import datetime, timezone
from threading import RLock
from typing import Any


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class AutonomyOrchestrator:
    def __init__(self) -> None:
        self._lock = RLock()
        self._last: dict[str, Any] | None = None
        self._plans = 0

    def plan(self, objective: str, *, enqueue_mission: bool = False) -> dict[str, Any]:
        clean = " ".join(str(objective or "").split())[:8000]
        if len(clean) < 8:
            raise ValueError("Autonomy objective is too short.")

        from omni.executive_control_plane import EXECUTIVE_CONTROL_PLANE
        executive = EXECUTIVE_CONTROL_PLANE.plan(clean, include_context=True)
        domain = str(executive.get("domain") or "GENERAL").upper()
        specialist_surface: dict[str, Any] | None = None
        surface_name = "executive"

        if domain == "ENGINEERING":
            from omni.engineering_governance import ENGINEERING_GOVERNANCE
            specialist_surface = ENGINEERING_GOVERNANCE.plan(clean)
            surface_name = "engineering_governance"
        elif domain == "SYSTEM":
            from omni.system_diagnostics import SYSTEM_DIAGNOSTICS
            specialist_surface = SYSTEM_DIAGNOSTICS.inspect()
            surface_name = "system_diagnostics"
        elif domain == "MARKETS":
            from omni.trading_intelligence.trading_governance_center import TRADING_GOVERNANCE_CENTER
            specialist_surface = TRADING_GOVERNANCE_CENTER.snapshot(days=31)
            surface_name = "trading_governance"

        evidence = [{
            "source": "executive_control_plane",
            "freshness": "FRESH",
            "provenance": {"domain": domain, "intent": (executive.get("intent") or {}).get("kind")},
            "claim": "Executive route and safety plan created",
        }]
        tool_results: list[dict[str, Any]] = []
        if specialist_surface is not None:
            evidence.append({
                "source": surface_name,
                "freshness": "FRESH",
                "provenance": {"domain": domain},
                "claim": f"{surface_name} state assembled",
            })
            tool_results.append(specialist_surface)

        from omni.critic_verifier import CRITIC_VERIFIER
        critic = CRITIC_VERIFIER.verify(
            subject=f"autonomy:{domain}:{clean[:160]}",
            domain=domain,
            evidence=evidence,
            tool_results=tool_results,
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

        queued = None
        if enqueue_mission:
            if not critic.get("progression_allowed"):
                raise RuntimeError("Critic did not verify the autonomy plan; mission queueing is blocked.")
            from omni.mission_worker import MISSION_WORKER
            queued = MISSION_WORKER.enqueue(clean, title=f"Autonomy · {domain}", priority=70)
            try:
                from omni.cognitive_event_bus import COGNITIVE_EVENT_BUS, CognitiveEventType
                COGNITIVE_EVENT_BUS.publish(
                    CognitiveEventType.MISSION_CREATED,
                    source="autonomy_orchestrator",
                    subject=str(queued.get("queue_id") or "mission"),
                    payload={"objective": clean[:1000], "domain": domain, "status": queued.get("status")},
                    provenance={"critic_verification_id": critic.get("verification_id"), "local_queue_only": True},
                )
            except Exception:
                pass

        result = {
            "success": True,
            "version": "10.0",
            "created_at": _now(),
            "objective": clean,
            "domain": domain,
            "executive": executive,
            "specialist_surface": specialist_surface,
            "specialist_surface_name": surface_name,
            "critic": critic,
            "mission_queued": queued,
            "automatic_mission_start": False,
            "external_action_executed": False,
            "merge_performed": False,
            "push_performed": False,
            "deployment_performed": False,
            "paper_only": True,
            "live_execution": False,
            "automatic_broker_order": False,
            "automatic_production_strategy_rewrite": False,
            "external_actions": "APPROVAL_GATED",
        }
        with self._lock:
            self._last = result
            self._plans += 1
        try:
            from omni.evidence_ledger import EVIDENCE_LEDGER
            EVIDENCE_LEDGER.record(
                kind="AUTONOMY_PLAN",
                subject=f"{domain}:{clean[:180]}",
                claim="Governed autonomy plan prepared",
                source="autonomy_orchestrator",
                state=str(critic.get("verdict") or "OBSERVED"),
                confidence=float(critic.get("confidence") or 0.5),
                evidence={"mission_queued": bool(queued), "surface": surface_name},
                provenance={"verification_id": critic.get("verification_id")},
                freshness="FRESH",
            )
        except Exception:
            pass
        return result

    def status(self) -> dict[str, Any]:
        with self._lock:
            last = self._last
            plans = self._plans
        return {
            "success": True,
            "version": "10.0",
            "service": "JARVIS_AUTONOMY_ORCHESTRATOR",
            "plans": plans,
            "last_plan": last,
            "capabilities": {
                "executive_planning": True,
                "context_fabric": True,
                "world_model": True,
                "cognitive_bus": True,
                "critic_verifier": True,
                "mission_queueing_explicit": True,
                "automatic_mission_start": False,
                "governed_engineering": True,
                "system_diagnostics": True,
                "trading_governance": True,
            },
            "system_plane": True,
            "permanent_agent": False,
            "external_actions": "APPROVAL_GATED",
            "paper_only": True,
            "live_execution": False,
            "automatic_broker_order": False,
            "automatic_production_strategy_rewrite": False,
        }


AUTONOMY_ORCHESTRATOR = AutonomyOrchestrator()

__all__ = ["AUTONOMY_ORCHESTRATOR", "AutonomyOrchestrator"]
