from __future__ import annotations

from copy import deepcopy
from math import isfinite, tanh
from typing import Any, Iterable, Mapping

from omni.trading_intelligence.contextual_decision_engine_v13 import (
    CONTEXTUAL_DECISION_ENGINE_V13,
)


POLICY_VERSION = "CONTINUOUS_EXECUTION_POLICY_V14"
DECISION_AUTHORITY = "POSITIVE_CONTEXTUAL_EXPECTED_VALUE_CONTINUOUS_RISK"


def _f(value: Any, default: float = 0.0) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return float(default)
    return number if isfinite(number) else float(default)


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(float(value), high))


def _side(row: Mapping[str, Any], contextual: Mapping[str, Any]) -> str:
    candidates = [
        contextual.get("side"),
        (contextual.get("base_v12_decision") or {}).get("side")
        if isinstance(contextual.get("base_v12_decision"), Mapping)
        else None,
        row.get("candidate_side"),
        row.get("side"),
    ]
    for value in candidates:
        token = str(value or "").strip().upper()
        if token in {"LONG", "SHORT"}:
            return token
    return "WAIT"


class ContinuousExecutionPolicyV14:
    """Convert V13 contextual evidence into continuous paper execution risk.

    V14 deliberately removes the remaining arbitrary confidence/score/hurdle
    cutoffs from paper entry authority.  Hard data/accounting/safety blockers
    still veto.  Otherwise the economically meaningful boundary is contextual
    expected value itself: positive EV receives a continuously scaled paper
    risk budget; zero/negative EV waits.

    PRIMARY/PROBE remain descriptive labels only.  They do not decide whether
    an otherwise positive-EV paper opportunity is executable.
    """

    def _correlation(
        self,
        row: Mapping[str, Any],
        side: str,
        contextual: Mapping[str, Any],
    ) -> dict[str, Any]:
        existing = contextual.get("portfolio_correlation")
        if isinstance(existing, Mapping) and str(existing.get("state") or "") not in {
            "",
            "NOT_REQUIRED_FOR_WAIT",
        }:
            return dict(existing)
        try:
            from workstation.dynamic_correlation_risk_v13 import DYNAMIC_CORRELATION_RISK_V13

            return dict(
                DYNAMIC_CORRELATION_RISK_V13.assess(
                    symbol=str(row.get("symbol") or ""),
                    side=side,
                    profile=str(row.get("profile") or "adaptive_intraday"),
                    timeframe=str(row.get("timeframe") or ""),
                )
            )
        except Exception as exc:
            return {
                "success": False,
                "version": "14.0",
                "state": "UNKNOWN_CORRELATION_ENGINE_ERROR",
                "error": f"{type(exc).__name__}: {exc}"[:300],
                "risk_multiplier": 1.0,
                "hard_blocker": None,
                "data_fabricated": False,
                "paper_only": True,
                "live_execution": False,
            }

    def _continuous(
        self,
        row: Mapping[str, Any],
        contextual: Mapping[str, Any],
        *,
        allowed_sides: Iterable[str],
    ) -> dict[str, Any]:
        allowed = {
            str(value).strip().upper()
            for value in allowed_sides
            if str(value).strip().upper() in {"LONG", "SHORT"}
        }
        side = _side(row, contextual)
        hard = [str(item) for item in list(contextual.get("hard_blockers") or [])]
        if side not in allowed:
            hard.append("SIDE_NOT_ALLOWED" if side in {"LONG", "SHORT"} else "NO_DIRECTIONAL_EDGE")
        hard = list(dict.fromkeys(hard))

        expected_value_r = _f(contextual.get("expected_value_r"))
        confidence = _clamp(_f(contextual.get("confidence")))
        uncertainty = 1.0 - confidence
        probability_win = _clamp(_f(contextual.get("probability_win"), 0.5), 0.01, 0.99)
        soft = [str(item) for item in list(contextual.get("soft_evidence") or [])]

        correlation: dict[str, Any] = {
            "success": True,
            "version": "14.0",
            "state": "NOT_REQUIRED_FOR_WAIT",
            "risk_multiplier": 1.0,
            "paper_only": True,
            "live_execution": False,
        }
        executable = False
        action = "WAIT"
        risk_multiplier = 0.0
        reasons: list[str] = []

        if hard:
            reasons.extend(hard)
            reasons.append("HARD_DATA_ACCOUNTING_OR_SAFETY_BLOCKER")
        elif expected_value_r > 0.0:
            executable = True
            correlation = self._correlation(row, side, contextual)
            correlation_multiplier = _clamp(_f(correlation.get("risk_multiplier"), 1.0), 0.0, 1.0)

            # Continuous curve: no magic score, confidence or R:R cutoff.  EV
            # controls edge strength; uncertainty reduces size rather than
            # disabling a positive edge.  The +0.025 seed creates a very small
            # learning probe for tiny but positive edge when the verified
            # instrument quantity step can support it.
            edge_strength = _clamp(tanh(max(expected_value_r, 0.0) / 0.75))
            uncertainty_scale = 0.15 + 0.85 * confidence
            pre_correlation_risk = _clamp(
                0.025 + 0.725 * edge_strength * uncertainty_scale,
                0.0,
                0.75,
            )
            risk_multiplier = _clamp(pre_correlation_risk * correlation_multiplier, 0.0, 0.75)

            # PRIMARY/PROBE is only a human-readable intensity label. The
            # executable flag above is already determined solely by hard safety
            # and positive contextual EV.
            action = "PRIMARY" if risk_multiplier >= 0.18 else "PROBE"
            reasons.append("POSITIVE_CONTEXTUAL_EXPECTED_VALUE")
            reasons.append("UNCERTAINTY_SCALES_RISK_NOT_EXECUTION")
            if action == "PROBE":
                reasons.append("SMALL_CONTINUOUS_PAPER_RISK")
        else:
            reasons.append("NON_POSITIVE_CONTEXTUAL_EXPECTED_VALUE")

        return {
            "policy_version": POLICY_VERSION,
            "decision_authority": DECISION_AUTHORITY,
            "action": action,
            "action_label_is_execution_gate": False,
            "executable": executable,
            "side": side if executable else "WAIT",
            "probability_win": round(probability_win, 4),
            "expected_value_r": round(expected_value_r, 4),
            "confidence": round(confidence, 4),
            "uncertainty": round(uncertainty, 4),
            "required_edge_r": 0.0,
            "positive_ev_execution_boundary_r": 0.0,
            "risk_multiplier": round(risk_multiplier, 4),
            "utility": round(expected_value_r * (0.30 + 0.70 * confidence), 4),
            "hard_blockers": hard,
            "soft_evidence": soft,
            "reasons": reasons,
            "contextual_v13_decision": deepcopy(dict(contextual)),
            "portfolio_correlation": correlation,
            "legacy_static_score_gate": False,
            "legacy_static_alignment_gate": False,
            "legacy_static_risk_reward_gate": False,
            "arbitrary_confidence_execution_gate": False,
            "arbitrary_required_edge_execution_gate": False,
            "confidence_scales_position_size_only": True,
            "correlation_can_only_reduce_risk": True,
            "paper_only": True,
            "live_execution": False,
            "automatic_broker_order": False,
            "automatic_production_strategy_rewrite": False,
        }

    def evaluate(
        self,
        row: Mapping[str, Any],
        *,
        learning_state: Mapping[str, Any] | None = None,
        allowed_sides: Iterable[str] = ("LONG", "SHORT"),
    ) -> dict[str, Any]:
        contextual = CONTEXTUAL_DECISION_ENGINE_V13.evaluate(
            row,
            learning_state=learning_state,
            allowed_sides=allowed_sides,
        )
        return self._continuous(row, contextual, allowed_sides=allowed_sides)

    def evaluate_many(
        self,
        rows: Iterable[Mapping[str, Any]],
        *,
        learning_state: Mapping[str, Any] | None = None,
        allowed_sides: Iterable[str] = ("LONG", "SHORT"),
    ) -> list[dict[str, Any]]:
        source_rows = [dict(row) for row in rows]
        contextual_rows = CONTEXTUAL_DECISION_ENGINE_V13.evaluate_many(
            source_rows,
            learning_state=learning_state,
            allowed_sides=allowed_sides,
        )
        result: list[dict[str, Any]] = []
        for original, contextual_row in zip(source_rows, contextual_rows):
            contextual = (
                contextual_row.get("adaptive_decision")
                if isinstance(contextual_row.get("adaptive_decision"), Mapping)
                else {}
            )
            decision = self._continuous(original, contextual, allowed_sides=allowed_sides)
            merged = dict(contextual_row)
            merged["adaptive_decision"] = decision
            merged["contextual_decision"] = contextual
            merged["continuous_execution_decision"] = decision
            result.append(merged)
        return result

    def status(self) -> dict[str, Any]:
        return {
            "success": True,
            "version": "14.0",
            "policy_version": POLICY_VERSION,
            "decision_authority": DECISION_AUTHORITY,
            "base_contextual_policy": "CONTEXTUAL_DECISION_ENGINE_V13",
            "positive_ev_is_execution_boundary": True,
            "positive_ev_boundary_r": 0.0,
            "uncertainty_scales_risk_not_execution": True,
            "primary_probe_labels_are_execution_gates": False,
            "arbitrary_confidence_execution_gate": False,
            "static_score_execution_authority": False,
            "static_alignment_execution_authority": False,
            "static_risk_reward_execution_authority": False,
            "hard_data_safety_blockers_preserved": True,
            "fractional_constraint_aware_sizing_required": True,
            "paper_only": True,
            "live_execution": False,
            "automatic_broker_order": False,
            "automatic_production_strategy_rewrite": False,
        }


CONTINUOUS_EXECUTION_POLICY_V14 = ContinuousExecutionPolicyV14()

__all__ = [
    "CONTINUOUS_EXECUTION_POLICY_V14",
    "ContinuousExecutionPolicyV14",
    "POLICY_VERSION",
    "DECISION_AUTHORITY",
]
