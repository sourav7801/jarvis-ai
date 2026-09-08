from __future__ import annotations

from math import isfinite
from typing import Any, Mapping


POSITION_INTELLIGENCE_VERSION = "POSITION_INTELLIGENCE_V15"


def _f(value: Any, default: float = 0.0) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return float(default)
    return number if isfinite(number) else float(default)


def _r_multiple(position: Mapping[str, Any], mark: float) -> float | None:
    entry = _f(position.get("entry"))
    stop = _f(position.get("initial_stop") if position.get("initial_stop") is not None else position.get("stop"))
    side = str(position.get("side") or "").upper()
    if entry <= 0.0 or stop <= 0.0 or side not in {"LONG", "SHORT"}:
        return None
    initial_risk = abs(entry - stop)
    if initial_risk <= 0.0:
        return None
    favorable = mark - entry if side == "LONG" else entry - mark
    return favorable / initial_risk


class PositionIntelligenceV15:
    """Explainable post-entry policy for synthetic paper positions.

    This module does not touch a broker. Its automatic-action contract is
    deliberately asymmetric: it may recommend or execute only risk-neutral or
    risk-reducing actions (HOLD, REDUCE, MOVE_STOP, TRAIL, PARTIAL_EXIT, EXIT,
    TIME_EXIT). ADD is reported only as eligibility and must pass a fresh normal
    V15 entry/risk allocation path; this module never increases exposure itself.
    """

    def assess(
        self,
        position: Mapping[str, Any],
        *,
        mark: float | None,
        decision: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        current_mark = _f(mark)
        side = str(position.get("side") or "").upper()
        live_decision = dict(decision or {})
        decision_side = str(live_decision.get("side") or "WAIT").upper()
        ev = _f(live_decision.get("expected_value_r"))
        confidence = max(0.0, min(_f(live_decision.get("confidence")), 1.0))
        hard = [str(item) for item in list(live_decision.get("hard_blockers") or [])]
        r_value = _r_multiple(position, current_mark) if current_mark > 0.0 else None
        action = "HOLD"
        reason = "POSITION_THESIS_STILL_ACCEPTABLE"
        reduce_fraction = 0.0
        risk_may_increase = False

        if current_mark <= 0.0:
            action = "HOLD"
            reason = "MARK_UNAVAILABLE_NO_AUTOMATIC_CHANGE"
        elif hard:
            action = "REDUCE"
            reduce_fraction = 0.50
            reason = "CURRENT_DECISION_HAS_HARD_DATA_OR_SAFETY_BLOCKER"
        elif decision_side in {"LONG", "SHORT"} and side in {"LONG", "SHORT"} and decision_side != side:
            action = "EXIT"
            reduce_fraction = 1.0
            reason = "DIRECTIONAL_THESIS_REVERSED"
        elif ev < -0.10:
            action = "EXIT"
            reduce_fraction = 1.0
            reason = "CURRENT_CONTEXTUAL_EV_MATERIALLY_NEGATIVE"
        elif ev <= 0.0:
            action = "REDUCE"
            reduce_fraction = 0.50
            reason = "CURRENT_CONTEXTUAL_EV_NON_POSITIVE"
        elif r_value is not None and r_value >= 2.0 and confidence < 0.45:
            action = "PARTIAL_EXIT"
            reduce_fraction = 0.34
            reason = "FAVORABLE_EXCURSION_WITH_WEAKENING_CONFIDENCE"
        elif r_value is not None and r_value >= 1.0:
            action = "TRAIL"
            reason = "FAVORABLE_EXCURSION_SUPPORTS_RISK_REDUCTION"
        elif ev > 0.0 and decision_side == side and confidence >= 0.65:
            action = "HOLD"
            reason = "POSITIVE_EV_AND_POSITION_THESIS_ALIGNED"

        add_eligible = bool(
            current_mark > 0.0
            and not hard
            and ev > 0.0
            and decision_side == side
            and confidence >= 0.70
        )
        # ADD requires a completely fresh entry through the normal portfolio
        # allocator and Paper Desk. This position-management policy cannot do it.
        return {
            "success": True,
            "version": "15.0",
            "service": POSITION_INTELLIGENCE_VERSION,
            "position_id": position.get("id"),
            "symbol": position.get("symbol"),
            "side": side,
            "mark": current_mark or None,
            "current_r_multiple": round(r_value, 4) if r_value is not None else None,
            "current_expected_value_r": round(ev, 4),
            "current_confidence": round(confidence, 4),
            "current_hard_blockers": hard,
            "recommended_action": action,
            "reason": reason,
            "reduce_fraction": reduce_fraction,
            "add_eligible_via_fresh_entry_path": add_eligible,
            "automatic_add_from_position_manager": False,
            "risk_may_increase": risk_may_increase,
            "paper_only": True,
            "live_execution": False,
            "automatic_broker_order": False,
        }

    def snapshot(self, *, decision_loader=None, mark_loader=None) -> dict[str, Any]:
        try:
            from workstation.paper_autonomy_engine import paper_desk

            portfolio = paper_desk.snapshot(mark_loader=mark_loader) if mark_loader is not None else paper_desk.snapshot()
        except TypeError:
            from workstation.paper_autonomy_engine import paper_desk
            portfolio = paper_desk.snapshot()
        except Exception as exc:
            return {
                "success": False,
                "version": "15.0",
                "service": POSITION_INTELLIGENCE_VERSION,
                "reason": f"{type(exc).__name__}: {exc}"[:300],
                "paper_only": True,
                "live_execution": False,
            }
        items = []
        for position in list(portfolio.get("positions") or []):
            decision = None
            if callable(decision_loader):
                try:
                    decision = decision_loader(position)
                except Exception:
                    decision = None
            mark = position.get("mark")
            items.append(self.assess(position, mark=mark, decision=decision))
        return {
            "success": True,
            "version": "15.0",
            "service": POSITION_INTELLIGENCE_VERSION,
            "open_positions": len(items),
            "actions": items,
            "automatic_actions_can_only_reduce_risk": True,
            "paper_only": True,
            "live_execution": False,
            "automatic_broker_order": False,
        }

    def status(self) -> dict[str, Any]:
        return {
            "success": True,
            "version": "15.0",
            "service": POSITION_INTELLIGENCE_VERSION,
            "actions": ["HOLD", "REDUCE", "MOVE_STOP", "TRAIL", "PARTIAL_EXIT", "EXIT", "TIME_EXIT"],
            "add_requires_fresh_normal_entry_path": True,
            "automatic_actions_can_only_reduce_risk": True,
            "paper_only": True,
            "live_execution": False,
            "automatic_broker_order": False,
        }


POSITION_INTELLIGENCE_V15 = PositionIntelligenceV15()

__all__ = ["POSITION_INTELLIGENCE_V15", "PositionIntelligenceV15", "POSITION_INTELLIGENCE_VERSION"]
