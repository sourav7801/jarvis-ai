from __future__ import annotations

import math
from copy import deepcopy
from typing import Any, Iterable, Mapping

from omni.trading_intelligence.adaptive_opportunity_policy import ADAPTIVE_OPPORTUNITY_POLICY
from omni.trading_intelligence.contextual_outcome_memory import CONTEXTUAL_OUTCOME_MEMORY


DECISION_VERSION = "CONTEXTUAL_DECISION_ENGINE_V13"


def _f(value: Any, default: float = 0.0) -> float:
    try:
        number = float(value)
        return number if math.isfinite(number) else default
    except (TypeError, ValueError):
        return default


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, float(value)))


class ContextualDecisionEngineV13:
    """Second-stage paper decision intelligence built above the verified V12 policy.

    V12 remains the base evidence model. V13 adds context-conditioned realized
    paper outcomes and dynamic uncertainty. It does not promote a legacy score,
    alignment number or static R:R threshold back into execution authority.
    """

    def evaluate(
        self,
        row: Mapping[str, Any],
        *,
        allowed_sides: Iterable[str] = ("LONG", "SHORT"),
    ) -> dict[str, Any]:
        base = ADAPTIVE_OPPORTUNITY_POLICY.evaluate(row, allowed_sides=allowed_sides)
        memory = CONTEXTUAL_OUTCOME_MEMORY.lookup(row, action=str(base.get("action") or "WAIT"))
        hard = list(base.get("hard_blockers") or [])
        soft = list(base.get("soft_evidence") or [])

        base_probability = _clamp(_f(base.get("probability_win"), 0.5), 0.01, 0.99)
        base_confidence = _clamp(_f(base.get("confidence")), 0.0, 1.0)
        memory_confidence = _clamp(_f(memory.get("confidence")), 0.0, 1.0)
        posterior_win = _clamp(_f(memory.get("posterior_win_rate"), 0.5), 0.05, 0.95)
        posterior_edge_r = _f(memory.get("posterior_edge_r"))

        # Context is intentionally bounded: it can refine a V12 estimate but a
        # small historical cohort cannot overwhelm fresh market evidence.
        win_adjustment = (posterior_win - 0.5) * 0.16 * memory_confidence
        edge_adjustment = math.tanh(posterior_edge_r) * 0.08 * memory_confidence
        probability = _clamp(base_probability + win_adjustment + edge_adjustment, 0.05, 0.90)

        rr = max(0.0, _f(row.get("risk_reward")))
        expected_value_r = probability * rr - (1.0 - probability)
        confidence = _clamp(base_confidence * (0.82 + 0.08 * memory_confidence) + 0.10 * memory_confidence)
        uncertainty = 1.0 - confidence

        # The hurdle moves continuously with uncertainty and contradiction load.
        contradiction_load = min(1.0, len(soft) / 6.0)
        required_edge_r = 0.015 + 0.17 * uncertainty + 0.035 * contradiction_load
        action = "WAIT"
        executable = False
        if not hard:
            if expected_value_r >= required_edge_r and confidence >= 0.34:
                action = "PRIMARY"
                executable = True
            elif expected_value_r > 0.0 and confidence >= 0.22:
                action = "PROBE"
                executable = True

        base_risk = _f(base.get("risk_multiplier"))
        memory_risk = 0.65 + 0.35 * memory_confidence
        risk_multiplier = min(1.0, max(0.0, base_risk * memory_risk)) if executable else 0.0
        if action == "PROBE":
            risk_multiplier = min(risk_multiplier, 0.22)

        reasons = [
            f"V12 base EV {float(base.get('expected_value_r') or 0.0):+.3f}R",
            f"context posterior edge {posterior_edge_r:+.3f}R",
            f"context posterior win {posterior_win:.1%}",
            f"final EV {expected_value_r:+.3f}R vs dynamic hurdle {required_edge_r:+.3f}R",
        ]
        if not memory.get("evidence_available"):
            reasons.append("No matched closed-paper cohort; V13 did not invent historical evidence.")
        if hard:
            reasons.append("Hard data/accounting/safety blocker overrides opportunity evidence.")

        return {
            "policy_version": DECISION_VERSION,
            "action": action,
            "executable": executable,
            "side": base.get("side") if executable else "WAIT",
            "probability_win": round(probability, 4),
            "expected_value_r": round(expected_value_r, 4),
            "confidence": round(confidence, 4),
            "uncertainty": round(uncertainty, 4),
            "required_edge_r": round(required_edge_r, 4),
            "risk_multiplier": round(risk_multiplier, 4),
            "utility": round(expected_value_r * (0.5 + 0.5 * confidence), 4),
            "hard_blockers": hard,
            "soft_evidence": soft,
            "reasons": reasons,
            "base_v12_decision": deepcopy(base),
            "contextual_memory": memory,
            "decision_authority": "CONTEXTUAL_EXPECTED_VALUE_NOT_STATIC_SCORE",
            "legacy_static_score_gate": False,
            "legacy_static_alignment_gate": False,
            "legacy_static_risk_reward_gate": False,
            "paper_only": True,
            "live_execution": False,
            "automatic_broker_order": False,
        }

    def evaluate_many(
        self,
        rows: Iterable[Mapping[str, Any]],
        *,
        allowed_sides: Iterable[str] = ("LONG", "SHORT"),
    ) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        for raw in rows:
            row = dict(raw)
            row["adaptive_decision"] = self.evaluate(row, allowed_sides=allowed_sides)
            row["contextual_decision"] = row["adaptive_decision"]
            result.append(row)
        return result

    def status(self) -> dict[str, Any]:
        memory = CONTEXTUAL_OUTCOME_MEMORY.snapshot()
        return {
            "success": True,
            "version": "13.0",
            "decision_version": DECISION_VERSION,
            "base_policy": "ADAPTIVE_OPPORTUNITY_POLICY_V12",
            "decision_authority": "CONTEXTUAL_EXPECTED_VALUE_NOT_STATIC_SCORE",
            "contextual_outcome_memory": {
                "usable_r_count": memory.get("usable_r_count"),
                "cohort_count": memory.get("cohort_count"),
                "source": memory.get("source"),
                "synthetic_history": False,
            },
            "dynamic_uncertainty_hurdle": True,
            "supports_primary": True,
            "supports_low_risk_probe": True,
            "legacy_score_threshold_is_execution_authority": False,
            "legacy_alignment_threshold_is_execution_authority": False,
            "legacy_risk_reward_threshold_is_execution_authority": False,
            "paper_only": True,
            "live_execution": False,
            "automatic_broker_order": False,
            "automatic_production_strategy_rewrite": False,
        }


CONTEXTUAL_DECISION_ENGINE_V13 = ContextualDecisionEngineV13()

__all__ = ["CONTEXTUAL_DECISION_ENGINE_V13", "ContextualDecisionEngineV13", "DECISION_VERSION"]
