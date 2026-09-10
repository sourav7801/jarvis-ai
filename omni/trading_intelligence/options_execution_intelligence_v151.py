from __future__ import annotations

from datetime import datetime
from math import isfinite
from typing import Any, Mapping

from omni.trading_intelligence.expiry_intelligence import expiry_state
from omni.trading_intelligence.option_chain_schema import OptionChainSnapshot, OptionContractQuote


POLICY_VERSION = "OPTIONS_EXECUTION_INTELLIGENCE_V15_1"
DECISION_AUTHORITY = "V15_UNDERLYING_UTILITY_PLUS_VERIFIED_OPTION_ECONOMICS"


def _f(value: Any, default: float = 0.0) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return float(default)
    return number if isfinite(number) else float(default)


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(float(value), high))


def _ceil_to_tick(value: float, tick: float) -> float:
    if tick <= 0:
        return float(value)
    units = int(value / tick)
    if units * tick + 1e-12 < value:
        units += 1
    return round(units * tick, 10)


def _floor_to_tick(value: float, tick: float) -> float:
    if tick <= 0:
        return float(value)
    units = int(value / tick)
    return round(max(units, 0) * tick, 10)


def _verified_spec(specs: Mapping[str, Mapping[str, Any]] | None, symbol: str | None) -> dict[str, Any] | None:
    if not symbol or not isinstance(specs, Mapping):
        return None
    raw = specs.get(symbol) or specs.get(str(symbol).upper())
    if not isinstance(raw, Mapping):
        return None
    spec = dict(raw)
    lot = _f(spec.get("lot_size") or spec.get("contract_multiplier"))
    tick = _f(spec.get("tick_size"))
    if spec.get("verified") is not True or lot <= 0.0 or tick <= 0.0:
        return None
    return {
        **spec,
        "lot_size": lot,
        "contract_multiplier": lot,
        "quantity_step": 1.0,
        "tick_size": tick,
        "asset_class": "OPTION",
        "instrument_type": "OPTION",
        "native_currency": str(spec.get("native_currency") or spec.get("currency") or "INR"),
        "valuation_currency": str(spec.get("valuation_currency") or spec.get("currency") or "INR"),
    }


def _underlying_fields(decision: Mapping[str, Any]) -> dict[str, Any]:
    row = dict(decision or {})
    nested = row.get("decision") if isinstance(row.get("decision"), Mapping) else None
    if nested is not None:
        row = dict(nested)
    side = str(row.get("side") or "WAIT").upper()
    ev = _f(row.get("expected_value_r"))
    utility = _f(row.get("portfolio_adjusted_utility"), _f(row.get("utility")))
    confidence = _clamp(_f(row.get("confidence")))
    uncertainty = _clamp(_f(row.get("uncertainty"), 1.0 - confidence))
    hard = [str(value) for value in list(row.get("hard_blockers") or [])]
    executable = bool(row.get("executable") is True and side in {"LONG", "SHORT"} and ev > 0.0 and not hard)
    return {
        "side": side,
        "expected_value_r": ev,
        "portfolio_utility": utility,
        "confidence": confidence,
        "uncertainty": uncertainty,
        "hard_blockers": hard,
        "executable": executable,
        "risk_multiplier": _clamp(_f(row.get("risk_multiplier"))),
    }


def _expiry(contract: OptionContractQuote, now: datetime | None) -> dict[str, Any]:
    try:
        return dict(expiry_state(contract.expiry, now=now))
    except Exception:
        return {
            "expiry": contract.expiry,
            "days_to_expiry": None,
            "phase": "UNKNOWN",
            "theta_urgency_heuristic": 0.35,
            "research_only": True,
        }


def _contract_quality(contract: OptionContractQuote, *, spot: float, expiry: Mapping[str, Any]) -> dict[str, Any]:
    entry = _f(contract.ask or contract.ltp)
    bid = _f(contract.bid)
    ask = _f(contract.ask)
    spread_pct = contract.spread_pct
    spread = _f(spread_pct, 1.0) if spread_pct is not None else 1.0
    volume = max(_f(contract.volume), 0.0)
    oi = max(_f(contract.open_interest), 0.0)
    distance = abs(_f(contract.strike) - spot) / max(spot, 1e-9)
    delta = abs(_f(contract.delta)) if contract.delta is not None else None
    delta_quality = 0.82 if delta is None else _clamp(1.0 - abs(delta - 0.50) / 0.50, 0.25, 1.0)
    spread_quality = _clamp(1.0 - spread / 0.12, 0.0, 1.0)
    liquidity_quality = _clamp(0.35 + 0.15 * min(volume / 1000.0, 1.0) + 0.25 * min(oi / 5000.0, 1.0) + 0.25 * spread_quality)
    moneyness_quality = _clamp(1.0 - distance / 0.06, 0.20, 1.0)
    theta_urgency = _clamp(_f(expiry.get("theta_urgency_heuristic"), 0.35))
    expiry_quality = _clamp(1.0 - 0.55 * theta_urgency, 0.35, 1.0)
    quality = _clamp(0.34 * spread_quality + 0.24 * liquidity_quality + 0.18 * moneyness_quality + 0.12 * delta_quality + 0.12 * expiry_quality)
    return {
        "entry": entry,
        "bid": bid or None,
        "ask": ask or None,
        "spread_pct": spread_pct,
        "volume": contract.volume,
        "open_interest": contract.open_interest,
        "distance_from_spot_pct": round(distance * 100.0, 4),
        "delta_quality": round(delta_quality, 4),
        "spread_quality": round(spread_quality, 4),
        "liquidity_quality": round(liquidity_quality, 4),
        "moneyness_quality": round(moneyness_quality, 4),
        "expiry_quality": round(expiry_quality, 4),
        "quality": round(quality, 4),
        "verified_greeks_available": {
            "delta": contract.delta is not None,
            "gamma": contract.gamma is not None,
            "theta": contract.theta is not None,
            "vega": contract.vega is not None,
        },
    }


def _premium_risk_plan(
    contract: OptionContractQuote,
    *,
    quality: float,
    underlying_ev: float,
    underlying_uncertainty: float,
    tick_size: float,
    spread_pct: float,
) -> dict[str, Any]:
    entry = _ceil_to_tick(_f(contract.ask or contract.ltp), tick_size)
    loss_fraction = _clamp(0.20 + 0.16 * underlying_uncertainty + 0.30 * max(spread_pct, 0.0), 0.18, 0.38)
    raw_stop = entry * (1.0 - loss_fraction)
    stop = _floor_to_tick(max(tick_size, raw_stop), tick_size)
    risk = max(entry - stop, tick_size)
    reward_r = _clamp(1.20 + 1.25 * max(underlying_ev, 0.0) + 0.55 * quality, 1.20, 2.75)
    target = _ceil_to_tick(entry + risk * reward_r, tick_size)
    rr = (target - entry) / max(entry - stop, tick_size)
    return {
        "entry": entry,
        "stop": stop,
        "target": target,
        "risk_reward": round(rr, 4),
        "premium_loss_fraction": round((entry - stop) / max(entry, tick_size), 4),
        "risk_plan_method": "LONG_PREMIUM_VERIFIED_ASK_PLUS_UNCERTAINTY_AND_LIQUIDITY",
        "premium_levels_are_risk_plan_estimates": True,
        "premium_levels_are_market_quotes": False,
        "future_option_premium_not_claimed": True,
    }


class OptionsExecutionIntelligenceV151:
    """Selects a verified long-premium option expression for a V15 opportunity.

    This service cannot write to a broker. A bullish underlying may consider calls
    and a bearish underlying may consider puts, but an option is rejected when its
    verified chain economics or instrument specification are not good enough.
    Missing Greeks remain explicitly unavailable rather than being fabricated.
    """

    def evaluate(
        self,
        snapshot: OptionChainSnapshot,
        underlying_decision: Mapping[str, Any],
        *,
        verified_snapshot: bool = False,
        verified_specs: Mapping[str, Mapping[str, Any]] | None = None,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        under = _underlying_fields(underlying_decision)
        common = {
            "success": True,
            "version": "15.1",
            "policy_version": POLICY_VERSION,
            "decision_authority": DECISION_AUTHORITY,
            "underlying": snapshot.underlying,
            "spot": snapshot.spot,
            "chain_timestamp": snapshot.timestamp,
            "underlying_decision": under,
            "long_premium_only": True,
            "naked_option_selling": False,
            "dealer_positioning": "UNAVAILABLE_WITHOUT_VERIFIED_INVENTORY",
            "paper_only": True,
            "live_execution": False,
            "automatic_broker_order": False,
        }
        if not verified_snapshot:
            return {**common, "action": "NO_OPTION_TRADE", "executable": False, "reason": "OPTION_CHAIN_NOT_VERIFIED", "candidates": []}
        if not under["executable"]:
            reason = under["hard_blockers"][0] if under["hard_blockers"] else "UNDERLYING_NOT_ACTIONABLE"
            return {**common, "action": "NO_OPTION_TRADE", "executable": False, "reason": reason, "candidates": []}

        desired_type = "call" if under["side"] == "LONG" else "put"
        candidates: list[dict[str, Any]] = []
        rejected: dict[str, int] = {}
        for contract in snapshot.contracts:
            if contract.option_type != desired_type:
                continue
            reason = None
            spec = _verified_spec(verified_specs, contract.symbol)
            exp = _expiry(contract, now)
            quality = _contract_quality(contract, spot=snapshot.spot, expiry=exp)
            entry = _f(quality.get("entry"))
            spread_pct = quality.get("spread_pct")
            if not contract.symbol:
                reason = "OPTION_SYMBOL_UNAVAILABLE"
            elif spec is None:
                reason = "OPTION_INSTRUMENT_SPEC_UNVERIFIED"
            elif entry <= 0.0 or contract.ask is None or contract.bid is None:
                reason = "OPTION_EXECUTABLE_QUOTE_UNAVAILABLE"
            elif spread_pct is None or _f(spread_pct, 1.0) > 0.12:
                reason = "OPTION_SPREAD_TOO_WIDE"
            elif str(exp.get("phase")) == "EXPIRED":
                reason = "OPTION_EXPIRED"
            elif str(exp.get("phase")) == "EXPIRY_DAY":
                reason = "ZERO_DTE_LONG_PREMIUM_DISABLED"

            if reason:
                rejected[reason] = rejected.get(reason, 0) + 1
                candidates.append({
                    "symbol": contract.symbol,
                    "expiry": contract.expiry,
                    "strike": contract.strike,
                    "option_type": contract.option_type,
                    "executable": False,
                    "reason": reason,
                    "quote": contract.to_dict(),
                    "expiry_state": exp,
                    "economics": quality,
                    "greeks_fabricated": False,
                })
                continue

            plan = _premium_risk_plan(
                contract,
                quality=_f(quality.get("quality")),
                underlying_ev=under["expected_value_r"],
                underlying_uncertainty=under["uncertainty"],
                tick_size=_f(spec.get("tick_size")),
                spread_pct=_f(spread_pct),
            )
            theta_urgency = _clamp(_f(exp.get("theta_urgency_heuristic"), 0.35))
            option_quality = _f(quality.get("quality")) * (1.0 - 0.35 * theta_urgency)
            option_ev = under["expected_value_r"] * option_quality - 0.08 * _f(spread_pct)
            option_utility = max(under["portfolio_utility"], under["expected_value_r"], 0.0) * max(option_quality, 0.0)
            risk_multiplier = min(under["risk_multiplier"], under["risk_multiplier"] * _clamp(option_quality, 0.15, 1.0))
            executable = option_ev > 0.0 and risk_multiplier > 0.0
            row_reason = "OPTION_READY_FOR_PAPER_DESK" if executable else "OPTION_ECONOMICS_NON_POSITIVE"
            if not executable:
                rejected[row_reason] = rejected.get(row_reason, 0) + 1
            candidates.append({
                "symbol": contract.symbol,
                "expiry": contract.expiry,
                "strike": contract.strike,
                "option_type": contract.option_type,
                "executable": executable,
                "reason": row_reason,
                "option_expected_value_r": round(option_ev, 4),
                "option_utility": round(option_utility, 6),
                "risk_multiplier": round(risk_multiplier, 4),
                "quote": contract.to_dict(),
                "expiry_state": exp,
                "economics": quality,
                "risk_plan": plan,
                "instrument_spec": spec,
                "greeks_fabricated": False,
                "iv_fabricated": False,
                "dealer_inventory_fabricated": False,
            })

        ranked = sorted(
            [row for row in candidates if row.get("executable") is True],
            key=lambda row: (_f(row.get("option_utility")), _f(row.get("option_expected_value_r"))),
            reverse=True,
        )
        best = ranked[0] if ranked else None
        if best is None:
            top_reason = max(rejected.items(), key=lambda item: item[1])[0] if rejected else "NO_MATCHING_OPTION_CONTRACT"
            return {
                **common,
                "action": "NO_OPTION_TRADE",
                "executable": False,
                "reason": top_reason,
                "desired_option_type": desired_type,
                "candidate_count": len(candidates),
                "rejection_counts": rejected,
                "candidates": candidates,
                "selected": None,
            }
        return {
            **common,
            "action": "PAPER_BUY_CALL" if desired_type == "call" else "PAPER_BUY_PUT",
            "executable": True,
            "reason": "OPTION_READY_FOR_PAPER_DESK",
            "desired_option_type": desired_type,
            "candidate_count": len(candidates),
            "rejection_counts": rejected,
            "candidates": candidates,
            "selected": best,
            "selected_contract": best.get("symbol"),
            "option_expected_value_r": best.get("option_expected_value_r"),
            "option_utility": best.get("option_utility"),
            "risk_multiplier": best.get("risk_multiplier"),
        }

    def status(self) -> dict[str, Any]:
        return {
            "success": True,
            "version": "15.1",
            "service": POLICY_VERSION,
            "decision_authority": DECISION_AUTHORITY,
            "requires_verified_option_chain": True,
            "requires_verified_lot_size_and_tick_size": True,
            "long_premium_only": True,
            "naked_option_selling": False,
            "call_for_bullish_underlying": True,
            "put_for_bearish_underlying": True,
            "underlying_direction_does_not_force_option_trade": True,
            "option_specific_economics_required": True,
            "zero_dte_long_premium_enabled": False,
            "verified_greeks_only": True,
            "greeks_fabricated": False,
            "dealer_positioning": "UNAVAILABLE_WITHOUT_VERIFIED_INVENTORY",
            "paper_only": True,
            "live_execution": False,
            "automatic_broker_order": False,
        }


OPTIONS_EXECUTION_INTELLIGENCE_V151 = OptionsExecutionIntelligenceV151()

__all__ = [
    "OPTIONS_EXECUTION_INTELLIGENCE_V151",
    "OptionsExecutionIntelligenceV151",
    "POLICY_VERSION",
    "DECISION_AUTHORITY",
]
