"""Executive control plane for JARVIS V8.

This module plans how JARVIS should handle a request using existing deterministic
intent routing, bounded context, specialist capability selection, verification,
and explicit safety policy.  It is an orchestration/planning layer, not a live
broker or unrestricted external-action executor.
"""

from __future__ import annotations

import re
import threading
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Any

from omni.context_fabric import snapshot as context_snapshot
from omni.unified_intent_router import IntentDecision, route_intent


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class PlanStep:
    index: int
    phase: str
    capability: str
    agent_hint: str
    description: str
    requires_approval: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ExecutiveControlPlane:
    """Bounded planner that creates one explainable route for Master JARVIS."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._last_plan: dict[str, Any] | None = None

    @staticmethod
    def _domain(text: str, intent: IntentDecision) -> str:
        lowered = " ".join(str(text or "").lower().split())
        if intent.kind == "WORKSPACE_CONTROL":
            return "OPERATING_SYSTEM"
        if intent.kind == "MARKETS":
            return "MARKETS"
        if intent.kind == "ENGINEERING":
            return "ENGINEERING"
        if intent.kind == "SYSTEM":
            return "SYSTEM"
        if intent.kind == "MISSION":
            return "MISSION"
        if any(word in lowered for word in ("company", "startup", "business", "venture", "product", "customer")):
            return "COMPANY"
        if any(word in lowered for word in ("research", "news", "source", "web", "latest")):
            return "RESEARCH"
        if any(word in lowered for word in ("memory", "remember", "recall", "forget")):
            return "MEMORY"
        return "GENERAL"

    @staticmethod
    def _agent_hints(domain: str, text: str) -> tuple[str, ...]:
        lowered = str(text or "").lower()
        base = {
            "OPERATING_SYSTEM": ("operator",),
            "MARKETS": ("trading", "data_ai", "finance", "quality"),
            "ENGINEERING": ("coding", "engineering", "security", "quality"),
            "SYSTEM": ("health", "security", "engineering"),
            "MISSION": ("operator", "strategy", "quality"),
            "COMPANY": ("strategy", "product", "finance", "operations", "quality"),
            "RESEARCH": ("research", "web_intelligence", "quality"),
            "MEMORY": ("operator",),
            "GENERAL": ("chat",),
        }.get(domain, ("chat",))
        extras: list[str] = []
        if any(word in lowered for word in ("legal", "compliance", "regulation")):
            extras.append("legal")
        if any(word in lowered for word in ("security", "privacy", "threat")):
            extras.append("security")
        if any(word in lowered for word in ("design", "ui", "ux")):
            extras.append("design")
        result: list[str] = []
        for name in (*base, *extras):
            if name not in result:
                result.append(name)
        return tuple(result[:8])

    @staticmethod
    def _steps(domain: str, intent: IntentDecision, agent_hints: tuple[str, ...]) -> tuple[PlanStep, ...]:
        if intent.kind == "WORKSPACE_CONTROL":
            return (
                PlanStep(1, "ACT", "workspace.control", "operator", "Apply the deterministic workspace action."),
                PlanStep(2, "VERIFY", "workspace.verify", "operator", "Return the exact workspace action and preserve UI state."),
            )

        if domain == "MARKETS":
            return (
                PlanStep(1, "PERCEPTION", "market.read", "data_ai", "Acquire verified, fresh market evidence; reject stale or unverified inputs."),
                PlanStep(2, "CONTEXT", "market.structure", "trading", "Build structure, regime, volatility and multi-timeframe context."),
                PlanStep(3, "REASON", "trading.research", "trading", "Evaluate strategy evidence, contradictions and reasons not to trade."),
                PlanStep(4, "RISK", "paper.risk", "finance", "Apply portfolio/risk gates and paper-only execution boundaries."),
                PlanStep(5, "VERIFY", "quality.analyze", "quality", "Verify data provenance, decision evidence and safety before returning."),
            )

        if domain == "ENGINEERING":
            return (
                PlanStep(1, "PERCEPTION", "code.index", "coding", "Inspect repository symbols and dependencies through read-only Code Intelligence."),
                PlanStep(2, "PLAN", "code.analyze", "engineering", "Produce an architecture-aware change plan that preserves protected contracts."),
                PlanStep(3, "IMPLEMENT", "code.generate", "coding", "Generate bounded code changes; repository writes remain governed."),
                PlanStep(4, "VERIFY", "quality.analyze", "quality", "Compile, test, regress and verify safety invariants before promotion."),
            )

        if domain == "MISSION":
            return (
                PlanStep(1, "PLAN", "goal.plan", "operator", "Convert the outcome into a bounded, resumable mission graph."),
                PlanStep(2, "DELEGATE", "agent.coordinate", "operator", "Select capability-matched specialists and run independent work in parallel where safe."),
                PlanStep(3, "VERIFY", "quality.analyze", "quality", "Critic-review the combined evidence and identify unresolved gaps."),
                PlanStep(4, "GOVERN", "approval.request", "operator", "Gate consequential external actions behind explicit approval.", True),
            )

        if domain == "COMPANY":
            return (
                PlanStep(1, "CONTEXT", "company.plan", "strategy", "Load venture state, evidence gaps, decisions and current workboard."),
                PlanStep(2, "DELEGATE", "agent.coordinate", "operator", "Coordinate relevant company departments through capability gates."),
                PlanStep(3, "VERIFY", "quality.analyze", "quality", "Separate evidence, hypotheses, local artifacts and actions not yet executed."),
                PlanStep(4, "GOVERN", "approval.request", "operator", "Require approval for outreach, spending, deployment, legal or production actions.", True),
            )

        if domain == "RESEARCH":
            return (
                PlanStep(1, "SEARCH", "web.search", "web_intelligence", "Discover relevant evidence sources."),
                PlanStep(2, "READ", "research.read", "research", "Read and compare sources without fabricating unavailable evidence."),
                PlanStep(3, "VERIFY", "research.cite", "quality", "Synthesize claims with provenance and expose uncertainty."),
            )

        if domain == "SYSTEM":
            return (
                PlanStep(1, "OBSERVE", "system.health", "health", "Read current service, protected-core and runtime ownership state."),
                PlanStep(2, "DIAGNOSE", "architecture.analyze", "engineering", "Trace the smallest architectural cause rather than masking symptoms."),
                PlanStep(3, "VERIFY", "quality.analyze", "quality", "Validate repair boundaries, tests and rollback before declaring recovery."),
            )

        return (
            PlanStep(1, "UNDERSTAND", "conversation", agent_hints[0] if agent_hints else "chat", "Resolve the request and relevant recent context."),
            PlanStep(2, "ANSWER", "conversation", agent_hints[0] if agent_hints else "chat", "Return one synthesized response rather than conflicting agent outputs."),
        )

    def plan(self, text: str, *, include_context: bool = True) -> dict[str, Any]:
        clean = re.sub(r"\s+", " ", str(text or "")).strip()
        intent = route_intent(clean)
        domain = self._domain(clean, intent)
        agents = self._agent_hints(domain, clean)
        steps = self._steps(domain, intent, agents)
        context = context_snapshot(clean) if include_context else None
        result = {
            "success": True,
            "version": "8.0",
            "created_at": _now(),
            "request": clean[:2000],
            "intent": intent.to_dict(),
            "domain": domain,
            "mode": "DETERMINISTIC" if intent.deterministic else "PLANNED",
            "agent_hints": list(agents),
            "steps": [step.to_dict() for step in steps],
            "workspace_actions": list(intent.workspace_actions),
            "context": context,
            "verification": {
                "critic_required": not intent.deterministic,
                "provenance_required": domain in {"MARKETS", "RESEARCH", "COMPANY"},
                "tests_required_for_code_change": domain == "ENGINEERING",
            },
            "safety": {
                "paper_only": True,
                "live_execution": False,
                "automatic_broker_order": False,
                "external_actions": "APPROVAL_GATED",
                "automatic_production_rewrite": False,
            },
        }
        with self._lock:
            self._last_plan = result
        return result

    def status(self) -> dict[str, Any]:
        with self._lock:
            last = self._last_plan
        return {
            "success": True,
            "version": "8.0",
            "service": "JARVIS_EXECUTIVE_CONTROL_PLANE",
            "last_plan": last,
            "pipeline": [
                "PERCEPTION", "CONTEXT", "INTENT", "PLAN", "DELEGATE",
                "EXECUTE_GOVERNED", "VERIFY", "MEMORY", "EVALUATE",
            ],
            "paper_only": True,
            "live_execution": False,
            "automatic_broker_order": False,
        }


EXECUTIVE_CONTROL_PLANE = ExecutiveControlPlane()


def executive(text: str) -> dict[str, Any]:
    plan = EXECUTIVE_CONTROL_PLANE.plan(text)
    intent = dict(plan.get("intent") or {})
    response = str(intent.get("response") or "Executive plan prepared.")
    return {
        "success": True,
        "type": "executive",
        "message": response,
        "plan": plan,
        "paper_only": True,
        "live_execution": False,
    }


__all__ = ["EXECUTIVE_CONTROL_PLANE", "ExecutiveControlPlane", "PlanStep", "executive"]
