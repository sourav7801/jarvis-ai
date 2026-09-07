"""System-level Critic / Verifier for JARVIS V10.

This is a governance plane above the permanent specialist registry, not agent
#30. It evaluates evidence completeness, contradictions, freshness, tool
results and safety policy before important mission/engineering/market outputs
are treated as verified.
"""
from __future__ import annotations

from datetime import datetime, timezone
from threading import RLock
from typing import Any, Iterable, Mapping
from uuid import uuid4


VERDICTS = frozenset({
    "VERIFIED", "PARTIAL", "CONTRADICTED", "INSUFFICIENT_EVIDENCE", "FAILED",
})


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _truthy_failure(value: Any) -> bool:
    if isinstance(value, Mapping):
        if value.get("success") is False:
            return True
        status = str(value.get("status") or value.get("state") or "").upper()
        return status in {"FAILED", "ERROR", "DOWN", "TIMEOUT", "UNAVAILABLE", "REJECTED"}
    return False


def _freshness(row: Mapping[str, Any]) -> str:
    direct = str(row.get("freshness") or "").upper()
    if direct in {"FRESH", "STALE", "UNKNOWN"}:
        return direct
    if row.get("stale") is True:
        return "STALE"
    if row.get("stale") is False or row.get("fresh") is True:
        return "FRESH"
    return "UNKNOWN"


class CriticVerifier:
    def __init__(self) -> None:
        self._lock = RLock()
        self._last: dict[str, Any] | None = None
        self._verified = 0
        self._blocked = 0

    def verify(
        self,
        *,
        subject: str,
        evidence: Iterable[Mapping[str, Any]] = (),
        contradictions: Iterable[str] = (),
        tool_results: Iterable[Mapping[str, Any]] = (),
        required_evidence: int = 1,
        require_fresh: bool = False,
        require_provenance: bool = False,
        policy: Mapping[str, Any] | None = None,
        correlation_id: str | None = None,
        domain: str = "GENERAL",
    ) -> dict[str, Any]:
        rows = [dict(item) for item in evidence if isinstance(item, Mapping)][:100]
        tools = [dict(item) for item in tool_results if isinstance(item, Mapping)][:100]
        conflicts = [str(item)[:500] for item in contradictions if str(item).strip()][:50]
        required = max(0, min(int(required_evidence), 100))
        fresh = [row for row in rows if _freshness(row) == "FRESH"]
        stale = [row for row in rows if _freshness(row) == "STALE"]
        unknown_freshness = [row for row in rows if _freshness(row) == "UNKNOWN"]
        provenance_missing = [
            row for row in rows
            if not (row.get("provenance") or row.get("source") or row.get("provider"))
        ]
        failed_tools = [row for row in tools if _truthy_failure(row)]
        successful_tools = [row for row in tools if not _truthy_failure(row)]

        safety = {
            "paper_only": True,
            "live_execution": False,
            "automatic_broker_order": False,
            "automatic_production_strategy_rewrite": False,
            "external_actions": "APPROVAL_GATED",
        }
        supplied_policy = dict(policy or {})
        policy_violations: list[str] = []
        if supplied_policy.get("live_execution") is True:
            policy_violations.append("LIVE_EXECUTION_REQUESTED")
        if supplied_policy.get("automatic_broker_order") is True:
            policy_violations.append("AUTOMATIC_BROKER_ORDER_REQUESTED")
        if supplied_policy.get("automatic_production_strategy_rewrite") is True:
            policy_violations.append("AUTOMATIC_PRODUCTION_REWRITE_REQUESTED")
        if str(supplied_policy.get("external_actions") or "APPROVAL_GATED").upper() not in {
            "APPROVAL_GATED", "EXPLICIT_APPROVAL_REQUIRED", "NONE", "LOCAL_ONLY",
        }:
            policy_violations.append("EXTERNAL_ACTION_POLICY_UNSAFE")

        reasons: list[str] = []
        if policy_violations:
            verdict = "FAILED"
            reasons.extend(policy_violations)
        elif conflicts:
            verdict = "CONTRADICTED"
            reasons.append("Material contradictory evidence remains unresolved.")
        elif len(rows) < required:
            verdict = "INSUFFICIENT_EVIDENCE"
            reasons.append(f"Required at least {required} evidence items; received {len(rows)}.")
        elif require_fresh and (stale or not fresh):
            verdict = "INSUFFICIENT_EVIDENCE"
            reasons.append("Fresh evidence is required but stale/unknown evidence remains.")
        elif require_provenance and provenance_missing:
            verdict = "INSUFFICIENT_EVIDENCE"
            reasons.append("Provenance is required for every material evidence item.")
        elif failed_tools:
            verdict = "PARTIAL" if rows else "FAILED"
            reasons.append("One or more required tool/provider results failed safely.")
        elif stale or unknown_freshness:
            verdict = "PARTIAL"
            reasons.append("Evidence is usable but freshness is not fully confirmed.")
        else:
            verdict = "VERIFIED"
            reasons.append("Evidence, provenance/freshness requirements and safety checks passed.")

        confidence = 0.35
        if rows:
            confidence += min(0.35, len(rows) * 0.04)
        if fresh:
            confidence += min(0.15, len(fresh) * 0.03)
        if successful_tools:
            confidence += min(0.10, len(successful_tools) * 0.02)
        confidence -= min(0.35, len(conflicts) * 0.10)
        confidence -= min(0.25, len(failed_tools) * 0.06)
        confidence -= min(0.20, len(stale) * 0.04)
        confidence = round(max(0.05, min(confidence, 0.99)), 4)
        if verdict in {"FAILED", "CONTRADICTED", "INSUFFICIENT_EVIDENCE"}:
            confidence = min(confidence, 0.55)

        result = {
            "success": verdict in {"VERIFIED", "PARTIAL"},
            "verification_id": "verify-" + uuid4().hex[:20],
            "version": "10.0",
            "created_at": _now(),
            "subject": str(subject or "")[:500],
            "domain": str(domain or "GENERAL").upper()[:80],
            "verdict": verdict,
            "confidence": confidence,
            "reasons": reasons,
            "checks": {
                "evidence_count": len(rows),
                "required_evidence": required,
                "fresh_count": len(fresh),
                "stale_count": len(stale),
                "unknown_freshness_count": len(unknown_freshness),
                "provenance_missing": len(provenance_missing),
                "contradictions": len(conflicts),
                "tool_successes": len(successful_tools),
                "tool_failures": len(failed_tools),
                "policy_violations": list(policy_violations),
            },
            "contradictions": conflicts,
            "correlation_id": str(correlation_id or "")[:160] or None,
            "safety": safety,
            "progression_allowed": verdict == "VERIFIED",
        }
        with self._lock:
            self._last = result
            if verdict == "VERIFIED":
                self._verified += 1
            else:
                self._blocked += 1

        try:
            from omni.evidence_ledger import EVIDENCE_LEDGER
            EVIDENCE_LEDGER.record(
                kind="VERIFICATION",
                subject=result["subject"],
                claim=f"Critic verdict {verdict}",
                source="omni.critic_verifier",
                state=verdict,
                confidence=confidence,
                evidence={"checks": result["checks"], "reasons": reasons},
                provenance={"domain": result["domain"]},
                correlation_id=result["correlation_id"],
                freshness="FRESH",
            )
        except Exception:
            pass
        try:
            from omni.cognitive_event_bus import COGNITIVE_EVENT_BUS, CognitiveEventType
            event_type = CognitiveEventType.TASK_VERIFIED if verdict == "VERIFIED" else CognitiveEventType.TASK_FAILED
            COGNITIVE_EVENT_BUS.publish(
                event_type,
                source="critic_verifier",
                subject=result["subject"] or "verification",
                payload={"verdict": verdict, "confidence": confidence, "checks": result["checks"]},
                provenance={"system_plane": True, "agent_registry_member": False},
                correlation_id=result["correlation_id"],
            )
        except Exception:
            pass
        return result

    def verify_mission_packet(self, mission: Mapping[str, Any]) -> dict[str, Any]:
        critic = dict(mission.get("critic") or {})
        artifacts = list(mission.get("artifacts") or [])
        evidence = [
            {"source": "mission_control", "freshness": "FRESH", "provenance": {"mission_id": mission.get("id")}, "artifact": item}
            for item in artifacts[:20]
        ]
        contradictions = list(critic.get("gaps") or []) if critic.get("verdict") != "VERIFIED_LOCAL_PACKET" else []
        return self.verify(
            subject=f"mission:{mission.get('id') or 'unknown'}",
            domain="MISSION",
            evidence=evidence,
            contradictions=contradictions,
            required_evidence=1,
            require_fresh=True,
            require_provenance=True,
            policy={"external_actions": "APPROVAL_GATED", "live_execution": False},
            correlation_id=str(mission.get("id") or "") or None,
        )

    def verify_market_decision(self, decision: Mapping[str, Any]) -> dict[str, Any]:
        evidence = list(decision.get("evidence") or [])
        blockers = [str(item) for item in decision.get("blockers") or []]
        policy = {
            "live_execution": bool(decision.get("live_execution", False)),
            "automatic_broker_order": bool(decision.get("automatic_broker_order", False)),
            "external_actions": "APPROVAL_GATED",
        }
        return self.verify(
            subject=f"market:{decision.get('symbol') or 'unknown'}:{decision.get('profile') or ''}",
            domain="MARKETS",
            evidence=evidence,
            contradictions=blockers if decision.get("qualified") else [],
            required_evidence=1,
            require_fresh=True,
            require_provenance=True,
            policy=policy,
        )

    def status(self) -> dict[str, Any]:
        with self._lock:
            last = dict(self._last) if self._last else None
            verified = self._verified
            blocked = self._blocked
        return {
            "success": True,
            "version": "10.0",
            "service": "JARVIS_CRITIC_VERIFIER",
            "verdicts": sorted(VERDICTS),
            "last_verification": last,
            "verified_count": verified,
            "non_verified_count": blocked,
            "system_plane": True,
            "permanent_agent": False,
            "external_actions": "APPROVAL_GATED",
            "paper_only": True,
            "live_execution": False,
            "automatic_broker_order": False,
        }


CRITIC_VERIFIER = CriticVerifier()

__all__ = ["CRITIC_VERIFIER", "CriticVerifier", "VERDICTS"]
