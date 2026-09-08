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

    V12 still computes its learned/calibrated base EV. V13 then adds more
    specific closed-paper context, dynamic uncertainty and an evidence-only
    portfolio correlation overlay. Legacy score/alignment/R:R thresholds never
    regain binary execution authority.
    """

    def _contextualize(
        self,
        row: Mapping[str, Any],
        base: Mapping[str, Any],
    ) -> dict[str, Any]:
        memory = CONTEXTUAL_OUTCOME_MEMORY.lookup(row, action=str(base.get("action") or "WAIT"))
        hard = list(base.get("hard_blockers") or [])
        soft = list(base.get("soft_evidence") or [])

        base_probability = _clamp(_f(base.get("probability_win"), 0.5), 0.01, 0.99)
        base_confidence = _clamp(_f(base.get("confidence")), 0.0, 1.0)
        memory_confidence = _clamp(_f(memory.get("confidence")), 0.0, 1.0)
        posterior_win = _clamp(_f(memory.get("posterior_win_rate"), 0.5), 0.05, 0.95)
        posterior_edge_r = _f(memory.get("posterior_edge_r"))

        # Context can refine a V12 estimate but cannot let a tiny cohort
        # overwhelm fresh evidence. This is a bounded second-stage adjustment.
        win_adjustment = (posterior_win - 0.5) * 0.16 * memory_confidence
        edge_adjustment = math.tanh(posterior_edge_r) * 0.08 * memory_confidence
        probability = _clamp(base_probability + win_adjustment + edge_adjustment, 0.05, 0.90)

        rr = max(0.0, _f(row.get("risk_reward")))
        expected_value_r = probability * rr - (1.0 - probability)
        confidence = _clamp(base_confidence * (0.82 + 0.08 * memory_confidence) + 0.10 * memory_confidence)
        uncertainty = 1.0 - confidence

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

        correlation: dict[str, Any] = {
            "success": True,
            "version": "13.0",
            "state": "NOT_REQUIRED_FOR_WAIT",
            "risk_multiplier": 1.0,
            "hard_blocker": None,
            "paper_only": True,
            "live_execution": False,
        }
        if executable:
            try:
                from workstation.dynamic_correlation_risk_v13 import DYNAMIC_CORRELATION_RISK_V13

                correlation = DYNAMIC_CORRELATION_RISK_V13.assess(
                    symbol=str(row.get("symbol") or ""),
                    side=str(base.get("side") or row.get("candidate_side") or ""),
                    profile=str(row.get("profile") or ""),
                    timeframe=str(row.get("timeframe") or ""),
                )
                risk_multiplier *= min(1.0, max(0.0, _f(correlation.get("risk_multiplier"), 1.0)))
            except Exception as exc:
                correlation = {
                    "success": False,
                    "version": "13.0",
                    "state": "UNKNOWN_CORRELATION_ENGINE_ERROR",
                    "error": f"{type(exc).__name__}: {exc}"[:300],
                    "risk_multiplier": 1.0,
                    "hard_blocker": None,
                    "data_fabricated": False,
                    "paper_only": True,
                    "live_execution": False,
                }
        risk_multiplier = min(1.0, max(0.0, risk_multiplier)) if executable else 0.0

        reasons = [
            f"V12 learned base EV {float(base.get('expected_value_r') or 0.0):+.3f}R",
            f"context posterior edge {posterior_edge_r:+.3f}R",
            f"context posterior win {posterior_win:.1%}",
            f"final EV {expected_value_r:+.3f}R vs dynamic hurdle {required_edge_r:+.3f}R",
        ]
        if not memory.get("evidence_available"):
            reasons.append("No matched closed-paper cohort; V13 did not invent historical evidence.")
        if correlation.get("state") not in {"NOT_REQUIRED_FOR_WAIT", "NO_OPEN_PEERS", "LOW_SAME_DIRECTION_CORRELATION"}:
            reasons.append(
                "portfolio correlation state " + str(correlation.get("state") or "UNKNOWN")
                + f"; risk multiplier {float(correlation.get('risk_multiplier') or 1.0):.2f}x"
            )
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
            "base_v12_decision": deepcopy(dict(base)),
            "contextual_memory": memory,
            "portfolio_correlation": correlation,
            "decision_authority": "CONTEXTUAL_EXPECTED_VALUE_NOT_STATIC_SCORE",
            "legacy_static_score_gate": False,
            "legacy_static_alignment_gate": False,
            "legacy_static_risk_reward_gate": False,
            "paper_only": True,
            "live_execution": False,
            "automatic_broker_order": False,
        }

    def evaluate(
        self,
        row: Mapping[str, Any],
        *,
        learning_state: Mapping[str, Any] | None = None,
        allowed_sides: Iterable[str] = ("LONG", "SHORT"),
    ) -> dict[str, Any]:
        """Evaluate one row while preserving the V12 caller contract.

        Direct paper-command paths already pass an explicit V12 learning_state.
        Batch/scanner callers historically rely on V12 evaluate_many() to load
        that state once. Supporting both forms prevents V13 rebinding from
        breaking the protected V12 direct-command bridge.
        """

        if learning_state is not None:
            base = ADAPTIVE_OPPORTUNITY_POLICY.evaluate(
                row,
                learning_state=learning_state,
                allowed_sides=allowed_sides,
            )
        else:
            base_rows = ADAPTIVE_OPPORTUNITY_POLICY.evaluate_many([row], allowed_sides=allowed_sides)
            base_row = base_rows[0] if base_rows else dict(row)
            base = base_row.get("adaptive_decision") if isinstance(base_row.get("adaptive_decision"), Mapping) else {}
        return self._contextualize(row, base)

    def evaluate_many(
        self,
        rows: Iterable[Mapping[str, Any]],
        *,
        learning_state: Mapping[str, Any] | None = None,
        allowed_sides: Iterable[str] = ("LONG", "SHORT"),
    ) -> list[dict[str, Any]]:
        source_rows = [dict(raw) for raw in rows]
        # Preserve V12's batch learning behavior by default. Tests, direct
        # compatibility bridges and deterministic callers may also supply an
        # explicit learning snapshot.
        if learning_state is None:
            base_rows = ADAPTIVE_OPPORTUNITY_POLICY.evaluate_many(source_rows, allowed_sides=allowed_sides)
        else:
            base_rows = []
            for source in source_rows:
                base_rows.append(
                    {
                        **source,
                        "adaptive_decision": ADAPTIVE_OPPORTUNITY_POLICY.evaluate(
                            source,
                            learning_state=learning_state,
                            allowed_sides=allowed_sides,
                        ),
                    }
                )

        result: list[dict[str, Any]] = []
        for source, base_row in zip(source_rows, base_rows):
            base = base_row.get("adaptive_decision") if isinstance(base_row.get("adaptive_decision"), Mapping) else {}
            source["adaptive_decision"] = self._contextualize(source, base)
            source["contextual_decision"] = source["adaptive_decision"]
            result.append(source)

        # Persist a bounded high-information sample rather than every scan row.
        ranked = sorted(
            result,
            key=lambda item: (
                bool((item.get("adaptive_decision") or {}).get("executable")),
                _f((item.get("adaptive_decision") or {}).get("utility"), -999.0),
            ),
            reverse=True,
        )[:16]
        try:
            from omni.trading_intelligence.decision_forensics_v13 import DECISION_FORENSICS_V13

            for selected in ranked:
                decision = selected.get("adaptive_decision") or {}
                DECISION_FORENSICS_V13.record(
                    row=selected,
                    decision=decision,
                    correlation=decision.get("portfolio_correlation") or {},
                    phase="ADAPTIVE_SCAN",
                )
        except Exception:
            pass
        return result

    def status(self) -> dict[str, Any]:
        memory = CONTEXTUAL_OUTCOME_MEMORY.snapshot()
        return {
            "success": True,
            "version": "13.0",
            "decision_version": DECISION_VERSION,
            "base_policy": "ADAPTIVE_OPPORTUNITY_POLICY_V12",
            "base_v12_learning_preserved": True,
            "v12_direct_evaluate_signature_preserved": True,
            "decision_authority": "CONTEXTUAL_EXPECTED_VALUE_NOT_STATIC_SCORE",
            "contextual_outcome_memory": {
                "usable_r_count": memory.get("usable_r_count"),
                "cohort_count": memory.get("cohort_count"),
                "source": memory.get("source"),
                "synthetic_history": False,
            },
            "dynamic_portfolio_correlation": True,
            "correlation_can_only_reduce_risk": True,
            "decision_forensics": True,
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
