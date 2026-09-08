from __future__ import annotations

from math import isfinite
from typing import Any, Mapping


REVIEW_VERSION = "CAUSAL_TRADE_REVIEW_V15"


def _f(value: Any, default: float = 0.0) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return float(default)
    return number if isfinite(number) else float(default)


def _metadata(row: Mapping[str, Any]) -> dict[str, Any]:
    value = row.get("metadata")
    return dict(value) if isinstance(value, Mapping) else {}


class CausalTradeReviewV15:
    """Separate paper decision quality from realized outcome.

    Outcome is evidence, not the label. A losing trade can be a high-quality
    decision if the entry had valid verified geometry, positive contextual EV
    and no hard blocker. Conversely, a profitable trade with invalid entry
    evidence is not automatically reinforced.
    """

    def review(self, row: Mapping[str, Any]) -> dict[str, Any]:
        metadata = _metadata(row)
        decision = metadata.get("adaptive_decision") if isinstance(metadata.get("adaptive_decision"), Mapping) else {}
        reasoning = decision.get("market_reasoning_v15") if isinstance(decision.get("market_reasoning_v15"), Mapping) else {}
        geometry = metadata.get("risk_model") if isinstance(metadata.get("risk_model"), Mapping) else {}
        realized_pnl = _f(row.get("realized_pnl"))
        realized_r = _f(metadata.get("realized_r"), 0.0)
        if realized_r == 0.0:
            initial_risk = _f(metadata.get("initial_trade_risk"))
            if initial_risk > 0.0:
                realized_r = realized_pnl / initial_risk
        ev = _f(decision.get("expected_value_r"), _f(metadata.get("adaptive_expected_value_r")))
        confidence = max(0.0, min(_f(decision.get("confidence"), _f(metadata.get("adaptive_confidence"))), 1.0))
        hard = [str(item) for item in list(decision.get("hard_blockers") or [])]
        verified_geometry = bool(
            geometry.get("derived_from_verified_completed_bar_evidence")
            or geometry.get("geometry_version")
            or (row.get("stop") is not None and row.get("target") is not None)
        )
        data_fabricated = bool(geometry.get("data_fabricated") or geometry.get("synthetic_market_data"))
        score = 0.0
        score += 0.30 if ev > 0.0 else -0.25
        score += 0.20 if verified_geometry else -0.30
        score += 0.15 if not hard else -0.35
        score += 0.10 if not data_fabricated else -0.50
        score += 0.10 * confidence
        score += 0.15 if metadata.get("legacy_numeric_gates_are_execution_authority") is False else 0.0
        score = max(-1.0, min(score, 1.0))
        if score >= 0.55:
            quality = "GOOD_DECISION"
        elif score >= 0.20:
            quality = "ACCEPTABLE_DECISION"
        elif score > -0.20:
            quality = "MIXED_DECISION"
        else:
            quality = "POOR_DECISION"

        outcome = "PROFIT" if realized_pnl > 0.0 else "LOSS" if realized_pnl < 0.0 else "FLAT"
        if quality in {"GOOD_DECISION", "ACCEPTABLE_DECISION"} and outcome == "LOSS":
            interpretation = "GOOD_PROCESS_ADVERSE_OUTCOME"
        elif quality in {"POOR_DECISION", "MIXED_DECISION"} and outcome == "PROFIT":
            interpretation = "PROFIT_DOES_NOT_VALIDATE_WEAK_PROCESS"
        elif outcome == "PROFIT":
            interpretation = "PROCESS_AND_OUTCOME_ALIGNED_POSITIVE"
        elif outcome == "LOSS":
            interpretation = "PROCESS_AND_OUTCOME_ALIGNED_NEGATIVE"
        else:
            interpretation = "FLAT_OUTCOME_REVIEW_PROCESS_ONLY"

        mae_r = _f(row.get("mae_r"), _f(metadata.get("mae_r")))
        mfe_r = _f(row.get("mfe_r"), _f(metadata.get("mfe_r")))
        entry_timing = (
            "EARLY_OR_VOLATILE" if mae_r <= -0.75 and mfe_r > 0.5
            else "LATE_OR_LOW_FOLLOW_THROUGH" if mfe_r < 0.35 and realized_r <= 0.0
            else "NORMAL"
        )
        exit_quality = (
            "LIKELY_EARLY_EXIT" if mfe_r - realized_r >= 1.0 and realized_r > 0.0
            else "CAPTURED_MOST_FAVORABLE_EXCURSION" if mfe_r > 0 and realized_r >= 0.70 * mfe_r
            else "NORMAL_OR_INDETERMINATE"
        )
        belief = reasoning.get("market_belief") if isinstance(reasoning.get("market_belief"), Mapping) else {}
        dominant = reasoning.get("dominant_hypothesis") if isinstance(reasoning.get("dominant_hypothesis"), Mapping) else None
        return {
            "success": True,
            "version": "15.0",
            "service": REVIEW_VERSION,
            "position_id": row.get("id") or row.get("position_id"),
            "symbol": row.get("symbol"),
            "side": row.get("side"),
            "decision_quality": quality,
            "decision_quality_score": round(score, 4),
            "outcome": outcome,
            "interpretation": interpretation,
            "realized_pnl": realized_pnl,
            "realized_r": round(realized_r, 4),
            "mae_r": round(mae_r, 4),
            "mfe_r": round(mfe_r, 4),
            "entry_timing_review": entry_timing,
            "exit_quality_review": exit_quality,
            "entry_expected_value_r": round(ev, 4),
            "entry_confidence": round(confidence, 4),
            "verified_risk_geometry": verified_geometry,
            "hard_blockers_at_entry": hard,
            "market_belief_at_entry": dict(belief),
            "dominant_hypothesis_at_entry": dict(dominant) if dominant else None,
            "decision_quality_separate_from_outcome": True,
            "profitable_trade_not_automatically_reinforced": True,
            "losing_trade_not_automatically_punished": True,
            "paper_only": True,
            "live_execution": False,
        }

    def status(self) -> dict[str, Any]:
        return {
            "success": True,
            "version": "15.0",
            "service": REVIEW_VERSION,
            "decision_quality_separate_from_outcome": True,
            "uses_real_closed_paper_evidence_only": True,
            "synthetic_history_created": False,
            "paper_only": True,
            "live_execution": False,
        }


CAUSAL_TRADE_REVIEW_V15 = CausalTradeReviewV15()

__all__ = ["CAUSAL_TRADE_REVIEW_V15", "CausalTradeReviewV15", "REVIEW_VERSION"]
