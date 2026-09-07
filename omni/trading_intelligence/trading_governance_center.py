"""Unified paper-trading learning and strategy-governance observability for V10.

This module composes existing Paper Desk, learning, self-improvement and
champion/challenger systems. It proposes research actions but cannot change
production strategy code or enable live execution.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class TradingGovernanceCenter:
    def snapshot(self, *, days: int = 31) -> dict[str, Any]:
        from omni.trading_intelligence.trade_learning_engine import learning_engine
        from omni.trading_intelligence.self_improvement_coordinator import self_improvement_coordinator
        from omni.trading_intelligence.champion_challenger import CHAMPION_CHALLENGER
        from workstation.paper_trading_desk import paper_desk
        from workstation.paper_portfolio_controller import paper_portfolio_controller

        review = paper_desk.performance_review(days=max(1, min(int(days), 365)))
        learning = learning_engine.status()
        mistakes = learning_engine.mistake_report()
        research = self_improvement_coordinator.status()
        governance = CHAMPION_CHALLENGER.snapshot(limit=100)
        portfolio = paper_portfolio_controller.status()

        proposals: list[dict[str, Any]] = []
        ranked_mistakes = list(mistakes.get("ranked_mistakes") or [])[:12]
        for row in ranked_mistakes[:5]:
            name = str(row.get("mistake") or row.get("name") or "").strip()
            count = int(row.get("count") or row.get("occurrences") or 0)
            if name:
                proposals.append({
                    "kind": "RESEARCH_HYPOTHESIS",
                    "topic": name,
                    "priority": "HIGH" if count >= 5 else "MEDIUM",
                    "evidence_count": count,
                    "action": "Validate a paper-only strategy/filter hypothesis with robust out-of-sample, bootstrap and cost gates.",
                    "automatic_production_change": False,
                })

        recent = list(learning.get("recent_outcomes") or [])[-100:]
        if recent:
            losing = [row for row in recent if float(row.get("pnl") or 0.0) < 0]
            if len(losing) / max(len(recent), 1) >= 0.60:
                proposals.append({
                    "kind": "RISK_REVIEW",
                    "topic": "RECENT_LOSS_CONCENTRATION",
                    "priority": "HIGH",
                    "evidence_count": len(losing),
                    "action": "Review regime/timeframe/strategy concentration before relaxing any paper-entry gate.",
                    "automatic_production_change": False,
                })

        evidence = [
            {
                "source": "paper_trading_desk",
                "freshness": "FRESH",
                "provenance": {"days": days},
                "claim": "Paper performance review loaded",
            },
            {
                "source": "trade_learning_engine",
                "freshness": "FRESH",
                "provenance": {"recent_outcomes": len(recent)},
                "claim": "Bounded paper learning state loaded",
            },
            {
                "source": "champion_challenger",
                "freshness": "FRESH",
                "provenance": {"records": len(governance.get("records") or [])},
                "claim": "Strategy governance registry loaded",
            },
        ]
        from omni.critic_verifier import CRITIC_VERIFIER
        critic = CRITIC_VERIFIER.verify(
            subject="trading-governance:snapshot",
            domain="MARKETS",
            evidence=evidence,
            required_evidence=3,
            require_fresh=True,
            require_provenance=True,
            policy={
                "live_execution": False,
                "automatic_broker_order": False,
                "automatic_production_strategy_rewrite": False,
                "external_actions": "APPROVAL_GATED",
            },
        )

        result = {
            "success": True,
            "version": "10.0",
            "generated_at": _now(),
            "paper_review": review,
            "learning": learning,
            "mistakes": mistakes,
            "self_improvement": research,
            "strategy_governance": governance,
            "portfolio": portfolio,
            "research_proposals": proposals,
            "critic": critic,
            "governance": {
                "automatic_production_strategy_rewrite": False,
                "automatic_live_promotion": False,
                "paper_challenger_only": True,
                "robust_validation_required": True,
                "external_actions": "APPROVAL_GATED",
            },
            "paper_only": True,
            "live_execution": False,
            "automatic_broker_order": False,
        }
        try:
            from omni.evidence_ledger import EVIDENCE_LEDGER
            EVIDENCE_LEDGER.record(
                kind="TRADING_GOVERNANCE",
                subject="paper-trading-learning",
                claim="Unified paper-learning and strategy-governance snapshot",
                source="trading_governance_center",
                state=critic.get("verdict") or "OBSERVED",
                confidence=float(critic.get("confidence") or 0.5),
                evidence={"proposal_count": len(proposals), "recent_outcomes": len(recent)},
                provenance={"paper_only": True},
                freshness="FRESH",
            )
        except Exception:
            pass
        return result

    def status(self) -> dict[str, Any]:
        result = self.snapshot(days=31)
        return {
            "success": True,
            "version": "10.0",
            "service": "JARVIS_TRADING_GOVERNANCE_CENTER",
            "proposal_count": len(result.get("research_proposals") or []),
            "critic": result.get("critic"),
            "paper_only": True,
            "live_execution": False,
            "automatic_broker_order": False,
            "automatic_production_strategy_rewrite": False,
        }


TRADING_GOVERNANCE_CENTER = TradingGovernanceCenter()

__all__ = ["TRADING_GOVERNANCE_CENTER", "TradingGovernanceCenter"]
