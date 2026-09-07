from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from math import exp, isfinite
from typing import Any, Iterable, Mapping


POLICY_VERSION = "ADAPTIVE_OPPORTUNITY_POLICY_V12"

# Hard blockers are reserved for data/accounting/safety conditions.  Legacy
# score/alignment/pattern/regime gates are intentionally treated as evidence,
# not binary execution authority.
HARD_BLOCKERS = {
    "DATA_UNAVAILABLE",
    "INSUFFICIENT_TIMEFRAME_DATA",
    "INVALID_RISK_LEVELS",
    "MARKET_SESSION_CLOSED",
    "STALE_MARKET_DATA",
    "RESEARCH_ONLY_GLOBAL_FEED",
    "INSTRUMENT_SPEC_UNAVAILABLE",
    "VALUATION_FX_UNAVAILABLE",
}

SOFT_PENALTIES = {
    "SCORE_BELOW_GATE": 0.015,
    "ALIGNMENT_BELOW_GATE": 0.045,
    "INSUFFICIENT_DIRECTIONAL_CONFIRMATION": 0.055,
    "REGIME_INCOMPATIBLE_SIGNAL": 0.090,
    "STRATEGY_VOTE_CONFLICT": 0.100,
    "HIGHER_TIMEFRAME_TREND_CONFLICT": 0.110,
    "ALL_TIMEFRAMES_RANGE": 0.055,
    "PATTERN_NOT_CONFIRMED": 0.045,
    "PATTERN_OR_STRATEGY_CONFIRMATION_REQUIRED": 0.065,
    "RISK_REWARD_BELOW_GATE": 0.025,
}


def _f(value: Any, default: float = 0.0) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return float(default)
    return number if isfinite(number) else float(default)


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(float(value), high))


def _unique(values: Iterable[str]) -> list[str]:
    rows: list[str] = []
    for value in values:
        token = str(value or "").strip().upper()
        if token and token not in rows:
            rows.append(token)
    return rows


def _votes(row: Mapping[str, Any]) -> list[dict[str, Any]]:
    return [dict(item) for item in list(row.get("votes") or []) if isinstance(item, Mapping)]


def _learning_state() -> dict[str, Any]:
    try:
        from omni.trading_intelligence.trade_learning_engine import learning_engine

        value = learning_engine.status()
        return dict(value) if isinstance(value, dict) else {}
    except Exception:
        return {}


def _bucket_edge(bucket: Mapping[str, Any] | None) -> tuple[float, int]:
    if not isinstance(bucket, Mapping):
        return 0.0, 0
    trades = int(bucket.get("trades") or 0)
    if trades <= 0:
        return 0.0, 0
    wins = int(bucket.get("wins") or 0)
    r_count = int(bucket.get("r_count") or 0)
    r_sum = _f(bucket.get("r_sum"))
    posterior_win = (wins + 2.0) / (trades + 4.0)
    avg_r = (r_sum / r_count) if r_count > 0 else 0.0
    edge = 0.55 * (posterior_win - 0.5) + 0.10 * max(-2.0, min(avg_r, 2.0))
    return max(-0.18, min(edge, 0.18)), trades


def _learning_adjustment(row: Mapping[str, Any], state: Mapping[str, Any]) -> dict[str, Any]:
    votes = _votes(row)
    families = []
    strategies = []
    for vote in votes:
        family = str(vote.get("family") or "").strip().lower()
        strategy = str(vote.get("strategy") or "").strip().upper()
        if family and family not in families:
            families.append(family)
        if strategy and strategy not in strategies:
            strategies.append(strategy)

    edges: list[float] = []
    samples = 0
    family_table = state.get("families") if isinstance(state.get("families"), Mapping) else {}
    strategy_table = state.get("strategies") if isinstance(state.get("strategies"), Mapping) else {}
    regime_table = state.get("regimes") if isinstance(state.get("regimes"), Mapping) else {}
    symbol_table = state.get("symbols") if isinstance(state.get("symbols"), Mapping) else {}

    for name in families:
        edge, count = _bucket_edge(family_table.get(name) if isinstance(family_table, Mapping) else None)
        if count:
            edges.append(edge)
            samples += count
    for name in strategies:
        edge, count = _bucket_edge(strategy_table.get(name) if isinstance(strategy_table, Mapping) else None)
        if count:
            edges.append(edge)
            samples += count

    regime = str(row.get("regime") or "UNKNOWN").strip().upper()
    edge, count = _bucket_edge(regime_table.get(regime) if isinstance(regime_table, Mapping) else None)
    if count:
        edges.append(edge)
        samples += count

    symbol = str(row.get("symbol") or "").strip().upper()
    edge, count = _bucket_edge(symbol_table.get(symbol) if isinstance(symbol_table, Mapping) else None)
    if count:
        edges.append(edge)
        samples += count

    adjustment = sum(edges) / len(edges) if edges else 0.0
    confidence = _clamp(samples / 48.0)
    return {
        "probability_adjustment": adjustment * confidence,
        "samples": samples,
        "confidence": confidence,
        "families": families,
        "strategies": strategies,
    }


def _regime_adjustment(row: Mapping[str, Any]) -> float:
    regime = str(row.get("regime") or "").upper()
    if "TREND" in regime:
        return 0.035
    if "HIGH VOL" in regime:
        return -0.010
    if "RANGE" in regime:
        return -0.035
    if "CONFLICT" in regime:
        return -0.060
    return 0.0


def _pattern_support(row: Mapping[str, Any], side: str) -> tuple[float, str]:
    pattern = row.get("pattern_confirmation") if isinstance(row.get("pattern_confirmation"), Mapping) else {}
    state = str(pattern.get("state") or "").upper()
    direction = str(pattern.get("direction") or "").upper()
    expected = "BULLISH" if side == "LONG" else "BEARISH"
    if state in {"CONFIRMED_BREAKOUT", "CONFIRMED_BREAKDOWN"} and direction == expected:
        return 0.055, "CONFIRMED_ALIGNED_PATTERN"
    if state in {"CONFIRMED_BREAKOUT", "CONFIRMED_BREAKDOWN"} and direction and direction != expected:
        return -0.060, "CONFIRMED_OPPOSING_PATTERN"
    return 0.0, "NO_CONFIRMED_PATTERN"


def _strategy_support(row: Mapping[str, Any], side: str) -> tuple[float, int, int]:
    supporting = 0
    opposing = 0
    compatible = 0
    for vote in _votes(row):
        vote_side = str(vote.get("side") or "").upper()
        if vote_side == side:
            supporting += 1
            if vote.get("regime_compatible") is not False:
                compatible += 1
        elif vote_side in {"LONG", "SHORT"}:
            opposing += 1
    if supporting == 0 and opposing == 0:
        return 0.0, supporting, opposing
    total = max(supporting + opposing, 1)
    directional = (supporting - opposing) / total
    compatibility = compatible / max(supporting, 1)
    return 0.045 * directional + 0.025 * compatibility, supporting, opposing


def _evidence_confidence(row: Mapping[str, Any], learning: Mapping[str, Any], pattern_label: str) -> float:
    evidence = [item for item in list(row.get("evidence") or []) if isinstance(item, Mapping)]
    decisions = [item for item in list(row.get("decisions") or []) if isinstance(item, Mapping)]
    available = [item for item in evidence if item.get("available", True)]
    fresh = [item for item in available if item.get("fresh") is not False]
    evidence_ratio = _clamp(len(available) / max(len(decisions), len(available), 1))
    fresh_ratio = _clamp(len(fresh) / max(len(available), 1)) if available else 0.0
    alignment = _clamp(_f(row.get("alignment")) / 100.0)
    pattern = 1.0 if pattern_label == "CONFIRMED_ALIGNED_PATTERN" else 0.0
    learned = _clamp(_f(learning.get("confidence")))
    return _clamp(0.22 + 0.18 * evidence_ratio + 0.16 * fresh_ratio + 0.18 * alignment + 0.10 * pattern + 0.16 * learned)


def _side(row: Mapping[str, Any]) -> str:
    candidate = str(row.get("candidate_side") or "").upper()
    if candidate in {"LONG", "SHORT"}:
        return candidate
    side = str(row.get("side") or "").upper()
    return side if side in {"LONG", "SHORT"} else "WAIT"


@dataclass(frozen=True)
class AdaptiveDecision:
    action: str
    executable: bool
    side: str
    probability_win: float
    expected_value_r: float
    confidence: float
    uncertainty: float
    required_edge_r: float
    risk_multiplier: float
    utility: float
    hard_blockers: tuple[str, ...]
    soft_evidence: tuple[str, ...]
    reasons: tuple[str, ...]
    components: Mapping[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "policy_version": POLICY_VERSION,
            "action": self.action,
            "executable": self.executable,
            "side": self.side,
            "probability_win": round(self.probability_win, 4),
            "expected_value_r": round(self.expected_value_r, 4),
            "confidence": round(self.confidence, 4),
            "uncertainty": round(self.uncertainty, 4),
            "required_edge_r": round(self.required_edge_r, 4),
            "risk_multiplier": round(self.risk_multiplier, 4),
            "utility": round(self.utility, 4),
            "hard_blockers": list(self.hard_blockers),
            "soft_evidence": list(self.soft_evidence),
            "reasons": list(self.reasons),
            "components": deepcopy(dict(self.components)),
            "legacy_static_score_gate": False,
            "legacy_static_alignment_gate": False,
            "legacy_static_risk_reward_gate": False,
            "paper_only": True,
            "live_execution": False,
            "automatic_broker_order": False,
        }


class AdaptiveOpportunityPolicy:
    """Continuous evidence policy for paper execution.

    Legacy score/alignment/R:R thresholds remain visible for compatibility and
    diagnostics, but they no longer have binary authority over V12 paper entry.
    V12 converts them into continuous evidence, estimates expected R, scales risk
    with confidence, and reserves hard vetoes for data/accounting/safety failures.
    """

    def evaluate(
        self,
        row: Mapping[str, Any],
        *,
        learning_state: Mapping[str, Any] | None = None,
        allowed_sides: Iterable[str] = ("LONG", "SHORT"),
    ) -> dict[str, Any]:
        source = dict(row)
        allowed = {str(item).upper() for item in allowed_sides if str(item).upper() in {"LONG", "SHORT"}}
        side = _side(source)
        blockers = _unique(list(source.get("blockers") or []) + list(source.get("reasons_not_to_trade") or []))
        hard = [item for item in blockers if item in HARD_BLOCKERS]
        if not source.get("success", True) and "DATA_UNAVAILABLE" not in hard:
            hard.append("DATA_UNAVAILABLE")
        if side not in allowed:
            hard.append("SIDE_NOT_ALLOWED" if side in {"LONG", "SHORT"} else "NO_DIRECTIONAL_EDGE")
        if source.get("entry") is None or source.get("stop") is None or source.get("target") is None:
            if "INVALID_RISK_LEVELS" not in hard:
                hard.append("INVALID_RISK_LEVELS")
        hard = _unique(hard)
        soft = [item for item in blockers if item not in hard]

        score = _clamp(_f(source.get("score")) / 100.0)
        alignment = _clamp(_f(source.get("alignment")) / 100.0)
        rr = max(0.0, _f(source.get("risk_reward")))
        pattern_adjustment, pattern_label = _pattern_support(source, side)
        strategy_adjustment, supporting_votes, opposing_votes = _strategy_support(source, side)
        learning = _learning_adjustment(source, learning_state or {})
        regime_adjustment = _regime_adjustment(source)
        soft_penalty = sum(SOFT_PENALTIES.get(item, 0.02) for item in soft)

        # Score is one continuous feature, not an entry boundary.  This prior is
        # deliberately conservative until alignment, structure, regime and
        # learned outcome evidence add support.
        probability = (
            0.10
            + 0.32 * score
            + 0.20 * alignment
            + pattern_adjustment
            + strategy_adjustment
            + regime_adjustment
            + _f(learning.get("probability_adjustment"))
            - soft_penalty
        )
        probability = _clamp(probability, 0.08, 0.82)
        confidence = _evidence_confidence(source, learning, pattern_label)
        uncertainty = 1.0 - confidence
        expected_value_r = probability * rr - (1.0 - probability)

        # The hurdle expands when uncertainty is high; it is not tied to a
        # magic Quant score such as 67/68/70.  Positive but uncertain edges may
        # enter as tiny paper probes so JARVIS can learn without pretending the
        # setup is high conviction.
        required_edge_r = 0.035 + 0.18 * uncertainty
        utility = expected_value_r * (0.55 + 0.45 * confidence)

        reasons: list[str] = []
        if hard:
            action = "WAIT"
            executable = False
            risk_multiplier = 0.0
            reasons.extend(hard)
        elif expected_value_r >= required_edge_r and confidence >= 0.40:
            action = "PRIMARY"
            executable = True
            edge_strength = _clamp((expected_value_r - required_edge_r + 0.10) / 0.90)
            risk_multiplier = _clamp(0.24 + 0.64 * edge_strength * confidence, 0.18, 0.88)
            reasons.append("POSITIVE_DYNAMIC_EXPECTED_VALUE")
        elif expected_value_r > 0.0 and confidence >= 0.28:
            action = "PROBE"
            executable = True
            edge_strength = _clamp(expected_value_r / max(required_edge_r, 1e-6))
            risk_multiplier = _clamp(0.07 + 0.15 * edge_strength * confidence, 0.06, 0.22)
            reasons.append("POSITIVE_EDGE_LOW_CONFIDENCE_PAPER_PROBE")
        else:
            action = "WAIT"
            executable = False
            risk_multiplier = 0.0
            reasons.append("NO_POSITIVE_ADAPTIVE_EXPECTED_VALUE")

        if soft:
            reasons.append("LEGACY_GATES_USED_AS_SOFT_EVIDENCE")
        if bool(source.get("qualified")):
            reasons.append("LEGACY_STATIC_POLICY_ALSO_QUALIFIED")

        decision = AdaptiveDecision(
            action=action,
            executable=executable,
            side=side,
            probability_win=probability,
            expected_value_r=expected_value_r,
            confidence=confidence,
            uncertainty=uncertainty,
            required_edge_r=required_edge_r,
            risk_multiplier=risk_multiplier,
            utility=utility,
            hard_blockers=tuple(hard),
            soft_evidence=tuple(soft),
            reasons=tuple(_unique(reasons)),
            components={
                "score_feature": round(score, 4),
                "alignment_feature": round(alignment, 4),
                "risk_reward": round(rr, 4),
                "pattern": pattern_label,
                "pattern_adjustment": round(pattern_adjustment, 4),
                "strategy_adjustment": round(strategy_adjustment, 4),
                "supporting_votes": supporting_votes,
                "opposing_votes": opposing_votes,
                "regime_adjustment": round(regime_adjustment, 4),
                "soft_penalty": round(soft_penalty, 4),
                "learning": learning,
                "legacy_score": _f(source.get("score")),
                "legacy_min_score": _f((source.get("profile_rules") or {}).get("minimum_score")) if isinstance(source.get("profile_rules"), Mapping) else None,
                "legacy_min_alignment": _f((source.get("profile_rules") or {}).get("minimum_alignment")) if isinstance(source.get("profile_rules"), Mapping) else None,
                "legacy_min_risk_reward": _f((source.get("profile_rules") or {}).get("minimum_risk_reward")) if isinstance(source.get("profile_rules"), Mapping) else None,
            },
        )
        return decision.to_dict()

    def evaluate_many(
        self,
        rows: Iterable[Mapping[str, Any]],
        *,
        allowed_sides: Iterable[str] = ("LONG", "SHORT"),
    ) -> list[dict[str, Any]]:
        state = _learning_state()
        result: list[dict[str, Any]] = []
        for raw in rows:
            row = dict(raw)
            row["adaptive_decision"] = self.evaluate(
                row,
                learning_state=state,
                allowed_sides=allowed_sides,
            )
            result.append(row)
        return result

    def status(self) -> dict[str, Any]:
        return {
            "success": True,
            "version": "12.0",
            "policy_version": POLICY_VERSION,
            "decision_model": "CONTINUOUS_EVIDENCE_EXPECTED_VALUE",
            "legacy_score_threshold_is_execution_authority": False,
            "legacy_alignment_threshold_is_execution_authority": False,
            "legacy_risk_reward_threshold_is_execution_authority": False,
            "hard_blockers": sorted(HARD_BLOCKERS),
            "supports_primary": True,
            "supports_low_risk_probe": True,
            "learning_calibration": True,
            "risk_scaled_by_confidence": True,
            "paper_only": True,
            "live_execution": False,
            "automatic_broker_order": False,
        }


ADAPTIVE_OPPORTUNITY_POLICY = AdaptiveOpportunityPolicy()

__all__ = [
    "ADAPTIVE_OPPORTUNITY_POLICY",
    "AdaptiveDecision",
    "AdaptiveOpportunityPolicy",
    "HARD_BLOCKERS",
    "POLICY_VERSION",
]
