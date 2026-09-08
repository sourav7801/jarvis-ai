from __future__ import annotations

from math import isfinite
from typing import Any, Mapping


REASONING_VERSION = "AUTONOMOUS_MARKET_REASONING_V15"


def _f(value: Any, default: float = 0.0) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return float(default)
    return number if isfinite(number) else float(default)


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(float(value), high))


def _direction(row: Mapping[str, Any]) -> str:
    for value in (row.get("candidate_side"), row.get("side")):
        token = str(value or "").strip().upper()
        if token in {"LONG", "SHORT"}:
            return token
    return "WAIT"


def _available_evidence(row: Mapping[str, Any]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for raw in list(row.get("evidence") or []):
        if not isinstance(raw, Mapping) or raw.get("available") is not True:
            continue
        item = dict(raw)
        item["timeframe"] = str(item.get("timeframe") or "")
        result.append(item)
    return result


def _timeframe_state(item: Mapping[str, Any]) -> dict[str, Any]:
    trend = str(item.get("trend") or "MIXED").upper()
    close = _f(item.get("close"))
    atr = _f(item.get("atr14"))
    support = _f(item.get("support"))
    resistance = _f(item.get("resistance"))
    rsi = _f(item.get("rsi14"), 50.0)
    volume_ratio = _f(item.get("volume_ratio"), 1.0)
    atr_pct = (atr / close) if close > 0.0 and atr > 0.0 else 0.0
    near_resistance = bool(close > 0.0 and resistance > close and (resistance - close) <= max(atr, close * 0.001))
    near_support = bool(close > 0.0 and support > 0.0 and close > support and (close - support) <= max(atr, close * 0.001))
    return {
        "timeframe": item.get("timeframe"),
        "trend": trend,
        "close": close or None,
        "atr14": atr or None,
        "atr_percent": round(atr_pct, 6) if atr_pct > 0.0 else None,
        "rsi14": round(rsi, 2),
        "volume_ratio": round(volume_ratio, 3),
        "support": support or None,
        "resistance": resistance or None,
        "near_support": near_support,
        "near_resistance": near_resistance,
        "fresh": item.get("fresh") is not False,
        "source": item.get("source"),
        "data_quality": item.get("data_quality"),
        "last_candle_time": item.get("last_candle_time"),
        "complete_bars": item.get("complete_bars"),
    }


def _normalize_hypotheses(raw: list[dict[str, Any]]) -> list[dict[str, Any]]:
    total = sum(max(_f(item.get("weight")), 0.0) for item in raw)
    if total <= 0.0:
        total = float(len(raw) or 1)
        for item in raw:
            item["weight"] = 1.0
    result = []
    for item in raw:
        probability = _clamp(max(_f(item.get("weight")), 0.0) / total, 0.01, 0.97)
        result.append({
            "name": item["name"],
            "probability": round(probability, 4),
            "evidence_for": list(item.get("evidence_for") or [])[:8],
            "evidence_against": list(item.get("evidence_against") or [])[:8],
            "invalidation": item.get("invalidation"),
            "supporting_timeframes": list(item.get("supporting_timeframes") or [])[:8],
            "conflicting_timeframes": list(item.get("conflicting_timeframes") or [])[:8],
            "expected_payoff_r": item.get("expected_payoff_r"),
            "estimated_loss_r": item.get("estimated_loss_r"),
            "uncertainty": round(_clamp(_f(item.get("uncertainty"), 0.5)), 4),
            "probability_is_model_estimate": True,
        })
    result.sort(key=lambda item: item["probability"], reverse=True)
    return result


class AutonomousMarketReasoningV15:
    """Explainable market-belief and competing-hypothesis layer.

    It consumes only evidence already produced by the verified completed-bar
    Quant path. Probabilities are explicitly model estimates, not market facts.
    No candles, dealer inventory, IV history or broker state are synthesized.
    """

    def reason(
        self,
        row: Mapping[str, Any],
        *,
        base_decision: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        evidence = _available_evidence(row)
        states = [_timeframe_state(item) for item in evidence]
        fresh_states = [item for item in states if item.get("fresh")]
        total = max(len(fresh_states), 1)
        bullish = sum(1 for item in fresh_states if item.get("trend") == "BULLISH")
        bearish = sum(1 for item in fresh_states if item.get("trend") == "BEARISH")
        mixed = max(len(fresh_states) - bullish - bearish, 0)
        net = bullish - bearish
        trend_strength = abs(net) / total
        timeframe_agreement = max(bullish, bearish, mixed) / total
        timeframe_conflict = 1.0 - timeframe_agreement
        direction = "BULLISH" if net > 0 else "BEARISH" if net < 0 else "MIXED"

        atr_pcts = [_f(item.get("atr_percent")) for item in fresh_states if item.get("atr_percent") is not None]
        average_atr_pct = sum(atr_pcts) / len(atr_pcts) if atr_pcts else 0.0
        if average_atr_pct >= 0.025:
            volatility_state = "HIGH"
        elif average_atr_pct >= 0.008:
            volatility_state = "NORMAL"
        elif average_atr_pct > 0.0:
            volatility_state = "LOW"
        else:
            volatility_state = "UNKNOWN"

        volume_ratios = [_f(item.get("volume_ratio"), 1.0) for item in fresh_states]
        avg_volume_ratio = sum(volume_ratios) / len(volume_ratios) if volume_ratios else 0.0
        liquidity_state = "ACTIVE" if avg_volume_ratio >= 1.2 else "NORMAL" if avg_volume_ratio >= 0.7 else "THIN" if volume_ratios else "UNKNOWN"

        breakout_evidence = sum(
            1 for item in fresh_states
            if (direction == "BULLISH" and item.get("near_resistance"))
            or (direction == "BEARISH" and item.get("near_support"))
        )
        breakout_probability = _clamp(0.15 + 0.45 * trend_strength + 0.20 * (breakout_evidence / total) + 0.10 * _clamp(avg_volume_ratio / 2.0))
        range_probability = _clamp(0.20 + 0.55 * timeframe_conflict + 0.20 * (mixed / total))
        reversal_extremes = sum(
            1 for item in fresh_states
            if (direction == "BULLISH" and _f(item.get("rsi14"), 50.0) >= 72.0)
            or (direction == "BEARISH" and _f(item.get("rsi14"), 50.0) <= 28.0)
        )
        reversal_probability = _clamp(0.10 + 0.35 * timeframe_conflict + 0.25 * (reversal_extremes / total))

        regime = str(row.get("regime") or "UNKNOWN").upper()
        if regime in {"", "UNKNOWN", "MIXED / WAIT"}:
            regime = "TRENDING" if trend_strength >= 0.60 else "RANGE" if range_probability >= 0.55 else "MIXED"
        transition_probability = _clamp(0.10 + 0.55 * timeframe_conflict + (0.15 if volatility_state == "HIGH" else 0.0))
        uncertainty = _clamp(0.15 + 0.55 * timeframe_conflict + (0.20 if not fresh_states else 0.0) + (0.10 if volatility_state == "UNKNOWN" else 0.0))

        side = _direction(row)
        base = dict(base_decision or {})
        rr = _f(row.get("risk_reward"), 0.0)
        expected_payoff = rr if rr > 0.0 else None
        dominant_tfs = [item["timeframe"] for item in fresh_states if item.get("trend") == direction][:8]
        conflicting_tfs = [item["timeframe"] for item in fresh_states if item.get("trend") not in {direction, "MIXED"}][:8]

        bullish_weight = 0.20 + 0.55 * (bullish / total) + 0.10 * breakout_probability
        bearish_weight = 0.20 + 0.55 * (bearish / total) + 0.10 * breakout_probability
        range_weight = 0.20 + 0.60 * range_probability
        sweep_weight = 0.12 + 0.45 * reversal_probability + 0.15 * timeframe_conflict
        hypotheses = _normalize_hypotheses([
            {
                "name": "BULLISH_CONTINUATION",
                "weight": bullish_weight,
                "evidence_for": [f"{bullish}/{len(fresh_states)} fresh timeframes bullish", f"breakout estimate {breakout_probability:.2f}"],
                "evidence_against": [f"{bearish} bearish timeframes", f"timeframe conflict {timeframe_conflict:.2f}"],
                "invalidation": "verified structure turns bearish or LONG risk geometry invalidates",
                "supporting_timeframes": [item["timeframe"] for item in fresh_states if item.get("trend") == "BULLISH"],
                "conflicting_timeframes": [item["timeframe"] for item in fresh_states if item.get("trend") == "BEARISH"],
                "expected_payoff_r": expected_payoff if side == "LONG" else None,
                "estimated_loss_r": 1.0 if side == "LONG" else None,
                "uncertainty": uncertainty,
            },
            {
                "name": "BEARISH_CONTINUATION",
                "weight": bearish_weight,
                "evidence_for": [f"{bearish}/{len(fresh_states)} fresh timeframes bearish", f"breakdown estimate {breakout_probability:.2f}"],
                "evidence_against": [f"{bullish} bullish timeframes", f"timeframe conflict {timeframe_conflict:.2f}"],
                "invalidation": "verified structure turns bullish or SHORT risk geometry invalidates",
                "supporting_timeframes": [item["timeframe"] for item in fresh_states if item.get("trend") == "BEARISH"],
                "conflicting_timeframes": [item["timeframe"] for item in fresh_states if item.get("trend") == "BULLISH"],
                "expected_payoff_r": expected_payoff if side == "SHORT" else None,
                "estimated_loss_r": 1.0 if side == "SHORT" else None,
                "uncertainty": uncertainty,
            },
            {
                "name": "RANGE_CONTINUATION",
                "weight": range_weight,
                "evidence_for": [f"range estimate {range_probability:.2f}", f"mixed timeframes {mixed}"],
                "evidence_against": [f"trend strength {trend_strength:.2f}"],
                "invalidation": "verified breakout/breakdown persists across completed bars",
                "supporting_timeframes": [item["timeframe"] for item in fresh_states if item.get("trend") == "MIXED"],
                "conflicting_timeframes": dominant_tfs,
                "expected_payoff_r": None,
                "estimated_loss_r": None,
                "uncertainty": _clamp(uncertainty + 0.10),
            },
            {
                "name": "LIQUIDITY_SWEEP_REVERSAL",
                "weight": sweep_weight,
                "evidence_for": [f"reversal estimate {reversal_probability:.2f}", f"transition estimate {transition_probability:.2f}"],
                "evidence_against": [f"trend strength {trend_strength:.2f}"],
                "invalidation": "continuation hypothesis strengthens after fresh completed bars",
                "supporting_timeframes": conflicting_tfs,
                "conflicting_timeframes": dominant_tfs,
                "expected_payoff_r": None,
                "estimated_loss_r": None,
                "uncertainty": _clamp(uncertainty + 0.15),
            },
        ])
        dominant = hypotheses[0] if hypotheses else None

        provenance = [
            {
                "timeframe": item.get("timeframe"),
                "source": item.get("source"),
                "data_quality": item.get("data_quality"),
                "last_candle_time": item.get("last_candle_time"),
                "complete_bars": item.get("complete_bars"),
                "fresh": item.get("fresh"),
            }
            for item in states
        ]

        return {
            "success": bool(states),
            "version": "15.0",
            "reasoning_version": REASONING_VERSION,
            "symbol": row.get("symbol"),
            "profile": row.get("profile"),
            "market_belief": {
                "trend_direction": direction,
                "trend_strength": round(trend_strength, 4),
                "range_probability": round(range_probability, 4),
                "breakout_probability": round(breakout_probability, 4),
                "reversal_probability": round(reversal_probability, 4),
                "volatility_state": volatility_state,
                "liquidity_state": liquidity_state,
                "structure_state": "DIRECTIONAL" if trend_strength >= 0.60 else "CONFLICTED" if timeframe_conflict >= 0.45 else "BALANCED",
                "regime": regime,
                "regime_transition_probability": round(transition_probability, 4),
                "timeframe_agreement": round(timeframe_agreement, 4),
                "timeframe_conflict": round(timeframe_conflict, 4),
                "signal_freshness": "FRESH" if fresh_states and len(fresh_states) == len(states) else "PARTIAL" if fresh_states else "UNAVAILABLE",
                "uncertainty": round(uncertainty, 4),
                "current_candidate_side": side,
                "base_expected_value_r": base.get("expected_value_r"),
            },
            "timeframe_states": states,
            "hypotheses": hypotheses,
            "dominant_hypothesis": dominant,
            "data_provenance": provenance,
            "probabilities_are_model_estimates": True,
            "market_data_fabricated": False,
            "paper_only": True,
            "live_execution": False,
            "automatic_broker_order": False,
        }

    def status(self) -> dict[str, Any]:
        return {
            "success": True,
            "version": "15.0",
            "service": "JARVIS_AUTONOMOUS_MARKET_REASONING_V15",
            "reasoning_version": REASONING_VERSION,
            "persistent_belief_contract": True,
            "multi_hypothesis_reasoning": True,
            "probabilities_are_model_estimates": True,
            "verified_completed_bar_inputs_only": True,
            "market_data_fabricated": False,
            "dealer_inventory_fabricated": False,
            "paper_only": True,
            "live_execution": False,
            "automatic_broker_order": False,
        }


AUTONOMOUS_MARKET_REASONING_V15 = AutonomousMarketReasoningV15()

__all__ = ["AUTONOMOUS_MARKET_REASONING_V15", "AutonomousMarketReasoningV15", "REASONING_VERSION"]
