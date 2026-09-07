from __future__ import annotations

from threading import RLock
from typing import Any


_LOCK = RLock()
_INSTALLED = False
_ORIGINAL = None


def install_adaptive_learning_bridge() -> dict[str, Any]:
    """Remove the legacy score<70 mistake label from V12 adaptive outcomes only.

    Legacy strategies keep their historical research taxonomy. Adaptive V12
    trades are judged by realized outcome, regime, stop/target context and
    expected-value evidence rather than being called a mistake merely because
    their old compatibility score was below 70.
    """

    global _INSTALLED, _ORIGINAL
    with _LOCK:
        if _INSTALLED:
            return status()

        from omni.trading_intelligence.trade_learning_engine import TradeLearningEngine

        original = TradeLearningEngine._mistake_hypotheses
        _ORIGINAL = original

        def adaptive_mistakes(*, pnl: float, reason: str, metadata: dict[str, Any], entry: float, stop: float | None, target: float | None, score: float | None) -> list[str]:
            mistakes = list(original(
                pnl=pnl,
                reason=reason,
                metadata=metadata,
                entry=entry,
                stop=stop,
                target=target,
                score=score,
            ))
            if str(metadata.get("adaptive_policy_version") or "").startswith("ADAPTIVE_OPPORTUNITY_POLICY_V12"):
                mistakes = [item for item in mistakes if item != "MARGINAL_SIGNAL_SCORE"]
            return mistakes

        TradeLearningEngine._mistake_hypotheses = staticmethod(adaptive_mistakes)
        _INSTALLED = True
        return status()


def status() -> dict[str, Any]:
    with _LOCK:
        return {
            "success": True,
            "version": "12.0",
            "installed": _INSTALLED,
            "adaptive_score_mistake_boundary_removed": _INSTALLED,
            "legacy_strategy_taxonomy_preserved": True,
            "automatic_production_rewrite": False,
            "paper_only": True,
            "live_execution": False,
        }


__all__ = ["install_adaptive_learning_bridge", "status"]
