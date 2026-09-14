"""Canonical V16 trading stage machine.

Blueprint section 12: replace vague "WATCHING" with an exact stage per
candidate, or an exact rejection reason. Only three things may reach a paper
order: a candidate that arrived at ACTIONABLE, a positively-sized plan, and a
Paper Desk that accepted both. Everything else must stop at a named stage with
a named reason, so the terminal can say *why* nothing traded.

This module classifies; it never decides. No stage here can open a position.
"""
from __future__ import annotations

from typing import Any, Mapping

PROGRESS_STAGES: tuple[str, ...] = (
    "DISCOVERED",
    "DATA_VALIDATED",
    "STRATEGY_EVALUATED",
    "RISK_MODEL_BUILT",
    "CONTEXTUAL_EV_CALCULATED",
    "PORTFOLIO_CHECKED",
    "SIZE_PLANNED",
    "ACTIONABLE",
    "PAPER_ORDER_CREATED",
    "PAPER_FILLED",
    "POSITION_OPEN",
    "POSITION_MANAGED",
    "POSITION_CLOSED",
    "JOURNALED",
)

REJECTION_STAGES: tuple[str, ...] = (
    "RATE_LIMITED",
    "STALE_DATA",
    "MARKET_SESSION_CLOSED",
    "NO_DIRECTION",
    "NON_POSITIVE_EV",
    "INVALID_RISK_LEVELS",
    "INSUFFICIENT_CAPITAL",
    "MAX_OPEN_RISK",
    "CORRELATION_LIMIT",
    "INSTRUMENT_SPEC_UNAVAILABLE",
    "LIVE_MARK_OUTSIDE_SETUP",
)

REASON_ALIASES: dict[str, str] = {
    "MARKET_DATA_RATE_LIMITED": "RATE_LIMITED",
    "RATE_LIMIT": "RATE_LIMITED",
    "RATE_LIMITED": "RATE_LIMITED",
    "STALE_MARK": "STALE_DATA",
    "STALE_CANDLES": "STALE_DATA",
    "DATA_UNAVAILABLE": "STALE_DATA",
    "NO_DATA": "STALE_DATA",
    "DATA_NOT_LIVE": "STALE_DATA",
    "MARK_EXCHANGE_TIMESTAMP_MISSING": "STALE_DATA",
    "MARKET_SESSION_CLOSED": "MARKET_SESSION_CLOSED",
    "INTRADAY_ENTRY_CUTOFF": "MARKET_SESSION_CLOSED",
    "CLOSING_AUCTION_NOT_MODELLED": "MARKET_SESSION_CLOSED",
    "NO_DIRECTION": "NO_DIRECTION",
    "NO_SIGNAL": "NO_DIRECTION",
    "SIGNAL_BAR_ID_REQUIRED": "NO_DIRECTION",
    "NON_POSITIVE_EV": "NON_POSITIVE_EV",
    "EV_BELOW_THRESHOLD": "NON_POSITIVE_EV",
    "INVALID_RISK_LEVELS": "INVALID_RISK_LEVELS",
    "INVALID_STOP": "INVALID_RISK_LEVELS",
    "INSUFFICIENT_CAPITAL": "INSUFFICIENT_CAPITAL",
    "MAX_OPEN_RISK": "MAX_OPEN_RISK",
    "OPEN_RISK_LIMIT": "MAX_OPEN_RISK",
    "CORRELATION_LIMIT": "CORRELATION_LIMIT",
    "INSTRUMENT_SPEC_UNAVAILABLE": "INSTRUMENT_SPEC_UNAVAILABLE",
    "LIVE_MARK_OUTSIDE_SETUP": "LIVE_MARK_OUTSIDE_SETUP",
    "LIVE_ENTRY_VALIDATION_FAILED": "LIVE_MARK_OUTSIDE_SETUP",
    "VALUATION_FX_UNAVAILABLE": "INSTRUMENT_SPEC_UNAVAILABLE",
}


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _number(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if number == number else None


def _underlying(symbol: Any) -> str | None:
    text = str(symbol or "").upper().replace(" ", "")
    if "BANKNIFTY" in text or "NIFTYBANK" in text:
        return "BANKNIFTY"
    if "SENSEX" in text:
        return "SENSEX"
    if "NIFTY" in text:
        return "NIFTY"
    return None


def canonical_reason(raw: Any) -> str:
    """Map a provider/engine reason onto the canonical vocabulary."""

    text = str(raw or "").strip().upper()
    if not text:
        return "UNCLASSIFIED"
    if text in REASON_ALIASES:
        return REASON_ALIASES[text]
    for alias in sorted(REASON_ALIASES, key=len, reverse=True):
        if alias in text:
            return REASON_ALIASES[alias]
    return text


def classify_candidate(row: Mapping[str, Any]) -> dict[str, Any]:
    """Return the exact stage reached by one scan candidate."""

    if not isinstance(row, Mapping):
        return {"stage": "DISCOVERED", "reason": "UNCLASSIFIED", "passed": [], "rejected_at": None}

    passed: list[str] = ["DISCOVERED"]
    rejected = row.get("reason") or row.get("message") or row.get("blocker")
    certificate = _mapping(row.get("certificate"))
    data_ok = bool(row.get("verified", certificate.get("verified", True))) and not row.get("stale")
    if not data_ok:
        return {"stage": canonical_stage("STALE_DATA"), "reason": canonical_reason(rejected or "DATA_NOT_LIVE"), "passed": passed, "rejected_at": "DATA_VALIDATED"}
    passed.append("DATA_VALIDATED")

    side = str(row.get("side") or row.get("action") or row.get("adaptive_action") or "").strip().upper()
    if side in {"", "WAIT", "HOLD", "NONE", "NO_TRADE", "FLAT"}:
        return {"stage": canonical_stage("NO_DIRECTION"), "reason": canonical_reason(rejected or "NO_DIRECTION"), "passed": passed, "rejected_at": "STRATEGY_EVALUATED"}
    passed.append("STRATEGY_EVALUATED")

    entry, stop = _number(row.get("entry")), _number(row.get("stop"))
    if not (entry and stop and entry != stop):
        return {"stage": canonical_stage("INVALID_RISK_LEVELS"), "reason": canonical_reason(rejected or "INVALID_RISK_LEVELS"), "passed": passed, "rejected_at": "RISK_MODEL_BUILT"}
    passed.append("RISK_MODEL_BUILT")

    expected_value = _number(row.get("expected_value_r", row.get("ev_r")))
    if expected_value is not None and expected_value <= 0:
        return {"stage": canonical_stage("NON_POSITIVE_EV"), "reason": canonical_reason(rejected or "NON_POSITIVE_EV"), "passed": passed, "rejected_at": "CONTEXTUAL_EV_CALCULATED", "expected_value_r": expected_value}
    if expected_value is not None:
        passed.append("CONTEXTUAL_EV_CALCULATED")

    if rejected:
        reason = canonical_reason(rejected)
        return {"stage": reason if reason in REJECTION_STAGES else "PORTFOLIO_CHECKED", "reason": reason, "passed": passed, "rejected_at": "PORTFOLIO_CHECKED"}

    quantity = _number(row.get("quantity", row.get("qty")))
    if not quantity or quantity <= 0:
        return {"stage": canonical_stage("INSUFFICIENT_CAPITAL"), "reason": "SIZE_NOT_PLANNED", "passed": passed, "rejected_at": "SIZE_PLANNED"}
    passed.extend(("SIZE_PLANNED", "ACTIONABLE"))
    return {"stage": "ACTIONABLE", "reason": None, "passed": passed, "rejected_at": None, "expected_value_r": expected_value}


def canonical_stage(reason: Any) -> str:
    mapped = canonical_reason(reason)
    return mapped if mapped in REJECTION_STAGES else "UNCLASSIFIED"


def stage_order(stage: str) -> int:
    text = str(stage or "").strip().upper()
    if text in PROGRESS_STAGES:
        return PROGRESS_STAGES.index(text)
    return len(PROGRESS_STAGES) + (REJECTION_STAGES.index(text) if text in REJECTION_STAGES else 0)


def _gate(state: str, reason: Any = None) -> dict[str, Any]:
    return {"state": state, "reason": str(reason) if reason not in (None, "") else None}


def _option_decision(row: Mapping[str, Any], verdict: Mapping[str, Any]) -> dict[str, Any] | None:
    underlying = _underlying(row.get("symbol"))
    if underlying not in {"NIFTY", "BANKNIFTY", "SENSEX"}:
        return None

    proposal = _mapping(row.get("option_proposal"))
    selected = _mapping(proposal.get("selected"))
    risk_plan = _mapping(selected.get("risk_plan"))
    execution = _mapping(row.get("execution_result"))
    sizing = _mapping(execution.get("sizing") or row.get("workspace_sizing"))
    blockers = [str(item) for item in (row.get("hard_blockers") or []) if item]
    raw_reason = execution.get("reason") or proposal.get("reason") or row.get("reason") or (blockers[0] if blockers else None)
    reason = canonical_reason(raw_reason) if raw_reason else None

    candidate = selected.get("symbol") or proposal.get("selected_contract")
    option_type = str(selected.get("option_type") or proposal.get("desired_option_type") or "").upper()
    expression = "LONG CALL" if option_type in {"CALL", "CE"} else "LONG PUT" if option_type in {"PUT", "PE"} else None
    premium_entry = _number(risk_plan.get("entry"))
    premium_stop = _number(risk_plan.get("stop"))
    premium_target = _number(risk_plan.get("target"))
    geometry_ok = bool(
        premium_entry is not None and premium_stop is not None and premium_target is not None
        and 0 < premium_stop < premium_entry < premium_target
    )
    rr = ((premium_target - premium_entry) / (premium_entry - premium_stop)) if geometry_ok else None

    opened = bool(execution.get("success")) and bool(execution.get("position_id") or str(execution.get("reason") or "").upper() == "PAPER_POSITION_OPENED")
    if opened:
        status, execution_stage = "POSITION_OPEN", "POSITION_OPEN"
    elif execution and execution.get("success") is False:
        status = "BLOCKED"
        execution_stage = reason if reason in REJECTION_STAGES else str(verdict.get("stage") or "PORTFOLIO_CHECKED")
    elif proposal.get("executable") is True and candidate:
        status, execution_stage = "ACTIONABLE", "ACTIONABLE"
    elif row.get("adaptive_executable") is True:
        status, execution_stage = "QUALIFYING", "STRATEGY_EVALUATED"
    else:
        status, execution_stage = "WAIT", str(verdict.get("stage") or "DISCOVERED")

    expected_value = _number(selected.get("option_expected_value_r"))
    if expected_value is None:
        expected_value = _number(row.get("adaptive_expected_value_r"))
    confidence = _number(row.get("adaptive_confidence"))
    probability = _number(row.get("adaptive_probability_win"))
    direction = str(row.get("adaptive_side") or row.get("side") or "").upper() or None
    bias = direction if direction in {"LONG", "SHORT"} else None

    quote = _mapping(selected.get("quote"))
    economics = _mapping(selected.get("economics"))
    spec = _mapping(selected.get("instrument_spec"))
    gates: dict[str, dict[str, Any]] = {}
    gates["DATA_FRESHNESS"] = _gate("PASS" if row.get("success") is not False else "BLOCKED", row.get("message"))
    gates["DIRECTION"] = _gate("PASS" if bias else "WAIT", reason if reason == "NO_DIRECTION" else None)
    gates["EXPECTED_VALUE"] = _gate("PASS" if expected_value is not None and expected_value > 0 else "BLOCKED" if expected_value is not None else "WAIT", expected_value)
    gates["CHAIN"] = _gate("PASS" if proposal and (proposal.get("executable") is not None or candidate) else "BLOCKED" if "CHAIN" in str(raw_reason or "").upper() else "WAIT", raw_reason)
    gates["CONTRACT"] = _gate("PASS" if candidate else "BLOCKED" if any(token in str(raw_reason or "").upper() for token in ("OPTION_SYMBOL", "CONTRACT", "INSTRUMENT_SPEC")) else "WAIT", raw_reason)
    gates["LIQUIDITY"] = _gate("PASS" if candidate and economics else "WAIT")
    gates["SPREAD"] = _gate("PASS" if economics.get("spread_pct") is not None else "WAIT", economics.get("spread_pct"))
    gates["OI"] = _gate("PASS" if quote.get("open_interest") is not None else "WAIT", quote.get("open_interest"))
    gates["INSTRUMENT_SPEC"] = _gate("PASS" if spec else "BLOCKED" if "INSTRUMENT_SPEC" in str(raw_reason or "").upper() else "WAIT", raw_reason)
    gates["DUPLICATE_EXPOSURE"] = _gate("BLOCKED" if "UNDERLYING_OPTION_EXPOSURE_EXISTS" in str(raw_reason or "").upper() else "PASS" if candidate else "WAIT", raw_reason)
    gates["RISK_GEOMETRY"] = _gate("PASS" if geometry_ok else "BLOCKED" if candidate and risk_plan else "WAIT", raw_reason)
    gates["CAPITAL"] = _gate("BLOCKED" if reason == "INSUFFICIENT_CAPITAL" else "PASS" if opened else "WAIT", raw_reason)
    gates["OPEN_RISK"] = _gate("BLOCKED" if reason == "MAX_OPEN_RISK" else "PASS" if opened else "WAIT", raw_reason)
    gates["PORTFOLIO_CORRELATION"] = _gate("BLOCKED" if reason == "CORRELATION_LIMIT" else "PASS" if opened else "WAIT", raw_reason)
    fresh_quote = bool(execution.get("entry_reference") or execution.get("live_mark") or opened)
    quote_blocked = any(token in str(raw_reason or "").upper() for token in ("STALE", "MARK", "QUOTE", "SESSION_CLOSED"))
    gates["FRESH_LIVE_OPTION_QUOTE"] = _gate("PASS" if fresh_quote else "BLOCKED" if quote_blocked else "WAIT", raw_reason)

    rejections: list[str] = []
    for item in [raw_reason, *blockers]:
        if not item:
            continue
        text = canonical_reason(item)
        if text not in rejections:
            rejections.append(text)

    quantity = execution.get("quantity") or sizing.get("quantity") or sizing.get("planned_quantity") or sizing.get("lots")
    risk = execution.get("risk") or sizing.get("risk") or sizing.get("planned_risk") or sizing.get("risk_amount")
    expiry = selected.get("expiry") or _mapping(selected.get("quote")).get("expiry")
    strike = selected.get("strike")
    last_time = None
    for evidence in row.get("evidence") or []:
        if isinstance(evidence, Mapping) and evidence.get("last_candle_time"):
            last_time = evidence.get("last_candle_time")
            break

    return {
        "status": status,
        "underlying": underlying,
        "direction": direction,
        "bias": bias,
        "confidence": confidence,
        "probability_win": probability,
        "strategy": row.get("strategy") or row.get("profile"),
        "expected_value_r": expected_value,
        "expression": expression,
        "candidate_contract": candidate,
        "expiry": expiry,
        "strike": strike,
        "option_type": option_type or None,
        "entry": premium_entry,
        "stop": premium_stop,
        "target": premium_target,
        "rr": rr,
        "quantity": quantity,
        "risk": risk,
        "execution_stage": execution_stage,
        "rejection_reasons": rejections,
        "gates": gates,
        "updated_at": last_time,
        "source": "ADAPTIVE_SCANNER_OPTION_PROPOSAL",
        "paper_only": True,
        "live_execution": False,
        "automatic_broker_order": False,
    }


def summarise(rows: list[Mapping[str, Any]]) -> dict[str, Any]:
    """Classify scan rows and expose the scanner's real option decisions."""

    classified: list[dict[str, Any]] = []
    counts: dict[str, int] = {}
    autonomous_options: dict[str, dict[str, Any]] = {}
    for row in rows or ():
        verdict = classify_candidate(row)
        counts[verdict["stage"]] = counts.get(verdict["stage"], 0) + 1
        classified.append({
            "symbol": row.get("symbol"),
            "strategy": row.get("strategy") or row.get("profile"),
            "side": row.get("side") or row.get("action") or row.get("adaptive_action"),
            "entry": row.get("entry"),
            "stop": row.get("stop"),
            "target": row.get("target"),
            "expected_value_r": verdict.get("expected_value_r", row.get("expected_value_r")),
            "confidence": row.get("confidence"),
            "regime": row.get("regime"),
            **verdict,
        })
        decision = _option_decision(row, verdict)
        if decision:
            autonomous_options[decision["underlying"]] = decision

    classified.sort(key=lambda item: stage_order(item["stage"]), reverse=True)
    return {
        "candidates": classified,
        "stage_counts": counts,
        "actionable": sum(1 for c in classified if c["stage"] == "ACTIONABLE"),
        "progress_stages": list(PROGRESS_STAGES),
        "rejection_stages": list(REJECTION_STAGES),
        "autonomous_options": autonomous_options,
    }


__all__ = [
    "PROGRESS_STAGES",
    "REJECTION_STAGES",
    "REASON_ALIASES",
    "canonical_reason",
    "canonical_stage",
    "classify_candidate",
    "stage_order",
    "summarise",
]
