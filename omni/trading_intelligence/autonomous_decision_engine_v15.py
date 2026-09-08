from __future__ import annotations

from copy import deepcopy
from math import isfinite
from typing import Any, Iterable, Mapping

from omni.trading_intelligence.continuous_execution_policy_v14 import (
    CONTINUOUS_EXECUTION_POLICY_V14,
)
from omni.trading_intelligence.market_reasoning_v15 import AUTONOMOUS_MARKET_REASONING_V15


POLICY_VERSION = "AUTONOMOUS_DECISION_ENGINE_V15"
DECISION_AUTHORITY = "PORTFOLIO_ADJUSTED_CONTEXTUAL_UTILITY_CONTINUOUS_RISK"


def _f(value: Any, default: float = 0.0) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return float(default)
    return number if isfinite(number) else float(default)


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(float(value), high))


def _market_quality(reasoning: Mapping[str, Any]) -> float:
    belief = reasoning.get("market_belief") if isinstance(reasoning.get("market_belief"), Mapping) else {}
    uncertainty = _clamp(_f(belief.get("uncertainty"), 0.5))
    liquidity = str(belief.get("liquidity_state") or "UNKNOWN").upper()
    volatility = str(belief.get("volatility_state") or "UNKNOWN").upper()
    regime_transition = _clamp(_f(belief.get("regime_transition_probability"), 0.5))
    liquidity_factor = 1.0 if liquidity == "ACTIVE" else 0.92 if liquidity == "NORMAL" else 0.72 if liquidity == "THIN" else 0.82
    volatility_factor = 0.88 if volatility == "HIGH" else 1.0 if volatility in {"NORMAL", "LOW"} else 0.90
    transition_factor = 1.0 - 0.35 * regime_transition
    uncertainty_factor = 1.0 - 0.45 * uncertainty
    return _clamp(liquidity_factor * volatility_factor * transition_factor * uncertainty_factor, 0.20, 1.0)


def _dominant_hypothesis_alignment(reasoning: Mapping[str, Any], side: str) -> float:
    hypotheses = list(reasoning.get("hypotheses") or [])
    if not hypotheses:
        return 0.65
    desired = "BULLISH_CONTINUATION" if side == "LONG" else "BEARISH_CONTINUATION" if side == "SHORT" else ""
    aligned = next((row for row in hypotheses if str(row.get("name")) == desired), None)
    dominant = hypotheses[0] if hypotheses else None
    aligned_probability = _clamp(_f((aligned or {}).get("probability"), 0.0))
    dominant_probability = _clamp(_f((dominant or {}).get("probability"), 0.0))
    if aligned is dominant and aligned is not None:
        return _clamp(0.75 + 0.25 * aligned_probability, 0.0, 1.0)
    return _clamp(0.45 + 0.45 * aligned_probability - 0.15 * dominant_probability, 0.20, 0.95)


class AutonomousDecisionEngineV15:
    """V15 final paper decision authority.

    V14 remains the economic foundation: hard verified-data/accounting/safety
    blockers veto and positive contextual expected value is executable. V15 adds
    explicit market-state/hypothesis reasoning and bounded cross-opportunity
    allocation. Portfolio reasoning can only preserve or REDUCE V14 paper risk;
    it cannot increase risk, bypass hard blockers or access a live broker.
    """

    @staticmethod
    def _decorate(row: Mapping[str, Any], decision: Mapping[str, Any]) -> dict[str, Any]:
        base = deepcopy(dict(decision))
        reasoning = AUTONOMOUS_MARKET_REASONING_V15.reason(row, base_decision=base)
        side = str(base.get("side") or "WAIT").upper()
        expected_value = _f(base.get("expected_value_r"))
        confidence = _clamp(_f(base.get("confidence")))
        market_quality = _market_quality(reasoning)
        hypothesis_alignment = _dominant_hypothesis_alignment(reasoning, side)
        raw_utility = max(expected_value, 0.0) * (0.30 + 0.70 * confidence) * market_quality * hypothesis_alignment
        return {
            **base,
            "policy_version": POLICY_VERSION,
            "decision_authority": DECISION_AUTHORITY,
            "v14_base_decision": base,
            "market_reasoning_v15": reasoning,
            "market_quality_multiplier": round(market_quality, 4),
            "hypothesis_alignment_multiplier": round(hypothesis_alignment, 4),
            "pre_allocation_portfolio_utility": round(raw_utility, 6),
            "portfolio_adjusted_utility": round(raw_utility, 6),
            "portfolio_allocation_multiplier": 1.0,
            "opportunity_rank": None,
            "opportunity_count": 1,
            "better_opportunity_available": False,
            "portfolio_allocator_can_only_reduce_risk": True,
            "risk_multiplier": min(_clamp(_f(base.get("risk_multiplier"))), _clamp(_f(base.get("risk_multiplier")))),
            "paper_only": True,
            "live_execution": False,
            "automatic_broker_order": False,
            "automatic_production_strategy_rewrite": False,
        }

    @staticmethod
    def _allocate(items: list[tuple[int, dict[str, Any]]]) -> dict[int, dict[str, Any]]:
        executable = [
            (index, row)
            for index, row in items
            if row.get("executable") is True
            and _f(row.get("expected_value_r")) > 0.0
            and not list(row.get("hard_blockers") or [])
        ]
        executable.sort(
            key=lambda pair: (
                _f(pair[1].get("pre_allocation_portfolio_utility"), -999.0),
                _f(pair[1].get("expected_value_r"), -999.0),
                _f(pair[1].get("confidence")),
            ),
            reverse=True,
        )
        result = {index: dict(row) for index, row in items}
        if not executable:
            return result

        best_utility = max(_f(executable[0][1].get("pre_allocation_portfolio_utility")), 1e-9)
        positive_total = sum(max(_f(row.get("pre_allocation_portfolio_utility")), 0.0) for _, row in executable) or 1.0
        count = len(executable)

        for rank, (index, row) in enumerate(executable, start=1):
            current = result[index]
            raw_utility = max(_f(current.get("pre_allocation_portfolio_utility")), 0.0)
            relative = _clamp(raw_utility / best_utility, 0.0, 1.0)
            rank_decay = max(0.35, 1.0 - 0.16 * (rank - 1))
            allocation_multiplier = _clamp((0.45 + 0.55 * relative) * rank_decay, 0.20, 1.0)
            base_risk = _clamp(_f((current.get("v14_base_decision") or {}).get("risk_multiplier")))
            adjusted_risk = min(base_risk, base_risk * allocation_multiplier)
            share = raw_utility / positive_total if positive_total > 0 else 0.0
            weaker = bool(count >= 3 and rank > 1 and relative < 0.22)

            current["portfolio_allocation_multiplier"] = round(allocation_multiplier, 4)
            current["portfolio_adjusted_utility"] = round(raw_utility * allocation_multiplier, 6)
            current["opportunity_rank"] = rank
            current["opportunity_count"] = count
            current["portfolio_utility_share"] = round(share, 4)
            current["better_opportunity_available"] = rank > 1
            current["risk_multiplier"] = round(adjusted_risk, 4)
            current.setdefault("reasons", []).append("PORTFOLIO_UTILITY_ALLOCATION_APPLIED")

            if weaker:
                current["executable"] = False
                current["side"] = "WAIT"
                current["action"] = "WAIT"
                current["risk_multiplier"] = 0.0
                current["portfolio_allocation_multiplier"] = 0.0
                current["portfolio_adjusted_utility"] = 0.0
                current["better_opportunity_available"] = True
                current.setdefault("reasons", []).append("BETTER_OPPORTUNITY_AVAILABLE")
                current.setdefault("soft_evidence", []).append("PORTFOLIO_OPPORTUNITY_COST")
            elif current.get("executable") is True and adjusted_risk < 0.18:
                current["action"] = "PROBE"
                current["action_label_is_execution_gate"] = False
        return result

    def evaluate(
        self,
        row: Mapping[str, Any],
        *,
        learning_state: Mapping[str, Any] | None = None,
        allowed_sides: Iterable[str] = ("LONG", "SHORT"),
    ) -> dict[str, Any]:
        base = CONTINUOUS_EXECUTION_POLICY_V14.evaluate(
            row,
            learning_state=learning_state,
            allowed_sides=allowed_sides,
        )
        decorated = self._decorate(row, base)
        return self._allocate([(0, decorated)])[0]

    def evaluate_many(
        self,
        rows: Iterable[Mapping[str, Any]],
        *,
        learning_state: Mapping[str, Any] | None = None,
        allowed_sides: Iterable[str] = ("LONG", "SHORT"),
    ) -> list[dict[str, Any]]:
        source_rows = [dict(row) for row in rows]
        base_rows = CONTINUOUS_EXECUTION_POLICY_V14.evaluate_many(
            source_rows,
            learning_state=learning_state,
            allowed_sides=allowed_sides,
        )
        decorated_by_index: list[tuple[int, dict[str, Any]]] = []
        for index, (original, wrapper) in enumerate(zip(source_rows, base_rows)):
            base = wrapper.get("adaptive_decision") if isinstance(wrapper.get("adaptive_decision"), Mapping) else {}
            decorated_by_index.append((index, self._decorate(original, base)))
        allocated = self._allocate(decorated_by_index)

        result: list[dict[str, Any]] = []
        for index, wrapper in enumerate(base_rows):
            merged = dict(wrapper)
            decision = allocated[index]
            merged["adaptive_decision"] = decision
            merged["autonomous_decision_v15"] = decision
            merged["market_reasoning_v15"] = decision.get("market_reasoning_v15")
            result.append(merged)
        return result

    def status(self) -> dict[str, Any]:
        return {
            "success": True,
            "version": "15.0",
            "policy_version": POLICY_VERSION,
            "decision_authority": DECISION_AUTHORITY,
            "base_execution_policy": "CONTINUOUS_EXECUTION_POLICY_V14",
            "market_reasoning": "AUTONOMOUS_MARKET_REASONING_V15",
            "positive_contextual_ev_preserved": True,
            "portfolio_opportunity_cost": True,
            "multi_hypothesis_reasoning": True,
            "market_belief_model": True,
            "confidence_scales_risk_not_execution": True,
            "legacy_score_execution_authority": False,
            "static_alignment_execution_authority": False,
            "static_risk_reward_execution_authority": False,
            "portfolio_allocator_can_only_reduce_v14_risk": True,
            "holding_unused_risk_budget_allowed": True,
            "paper_only": True,
            "live_execution": False,
            "automatic_broker_order": False,
            "automatic_production_strategy_rewrite": False,
        }


AUTONOMOUS_DECISION_ENGINE_V15 = AutonomousDecisionEngineV15()

__all__ = [
    "AUTONOMOUS_DECISION_ENGINE_V15",
    "AutonomousDecisionEngineV15",
    "POLICY_VERSION",
    "DECISION_AUTHORITY",
]
