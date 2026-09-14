"""Canonical V16 trading stage and autonomous-option decision contract.

This module classifies evidence already produced by the paper-only scanner.  It
never opens a position, fetches a second option chain, or invents a trade.  The
same decision object drives the Options Autopilot status, gates and rejection
reason so the UI cannot present mutually inconsistent versions of one scan.
"""
from __future__ import annotations

from datetime import datetime, timezone
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

# A deterministic primary-reason order.  Infrastructure/session blockers come
# first; then strategy/EV; then risk/portfolio admission.  The complete set is
# still preserved in rejection_reasons for diagnosis.
_REASON_PRIORITY: tuple[str, ...] = (
    "RATE_LIMITED",
    "STALE_DATA",
    "MARKET_SESSION_CLOSED",
    "NO_DIRECTION",
    "NON_POSITIVE_EV",
    "INSTRUMENT_SPEC_UNAVAILABLE",
    "LIVE_MARK_OUTSIDE_SETUP",
    "INVALID_RISK_LEVELS",
    "INSUFFICIENT_CAPITAL",
    "MAX_OPEN_RISK",
    "CORRELATION_LIMIT",
)

_OPERATIONAL_BLOCKERS = {
    "RATE_LIMITED",
    "STALE_DATA",
    "INSTRUMENT_SPEC_UNAVAILABLE",
    "LIVE_MARK_OUTSIDE_SETUP",
    "INSUFFICIENT_CAPITAL",
    "MAX_OPEN_RISK",
    "CORRELATION_LIMIT",
}


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _number(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if number == number else None


def _positive(value: Any) -> float | None:
    number = _number(value)
    return number if number is not None and number > 0 else None


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
        return {"stage": "STALE_DATA", "reason": canonical_reason(rejected or "DATA_NOT_LIVE"), "passed": passed, "rejected_at": "DATA_VALIDATED"}
    passed.append("DATA_VALIDATED")

    side = str(row.get("side") or row.get("action") or row.get("adaptive_action") or "").strip().upper()
    if side in {"", "WAIT", "HOLD", "NONE", "NO_TRADE", "FLAT"}:
        return {"stage": "NO_DIRECTION", "reason": canonical_reason(rejected or "NO_DIRECTION"), "passed": passed, "rejected_at": "STRATEGY_EVALUATED"}
    passed.append("STRATEGY_EVALUATED")

    entry, stop = _positive(row.get("entry")), _positive(row.get("stop"))
    if entry is None or stop is None or entry == stop:
        return {"stage": "INVALID_RISK_LEVELS", "reason": canonical_reason(rejected or "INVALID_RISK_LEVELS"), "passed": passed, "rejected_at": "RISK_MODEL_BUILT"}
    passed.append("RISK_MODEL_BUILT")

    expected_value = _number(row.get("expected_value_r", row.get("ev_r")))
    if expected_value is not None and expected_value <= 0:
        return {"stage": "NON_POSITIVE_EV", "reason": canonical_reason(rejected or "NON_POSITIVE_EV"), "passed": passed, "rejected_at": "CONTEXTUAL_EV_CALCULATED", "expected_value_r": expected_value}
    if expected_value is not None:
        passed.append("CONTEXTUAL_EV_CALCULATED")

    if rejected:
        reason = canonical_reason(rejected)
        return {"stage": reason if reason in REJECTION_STAGES else "PORTFOLIO_CHECKED", "reason": reason, "passed": passed, "rejected_at": "PORTFOLIO_CHECKED"}

    quantity = _number(row.get("quantity", row.get("qty")))
    if not quantity or quantity <= 0:
        return {"stage": "INSUFFICIENT_CAPITAL", "reason": "SIZE_NOT_PLANNED", "passed": passed, "rejected_at": "SIZE_PLANNED"}
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


def _append_reason(items: list[str], raw: Any) -> None:
    if raw in (None, ""):
        return
    reason = canonical_reason(raw)
    if reason not in items:
        items.append(reason)


def _primary_reason(reasons: list[str]) -> str | None:
    for wanted in _REASON_PRIORITY:
        if wanted in reasons:
            return wanted
    return reasons[0] if reasons else None


def _decision_time(row: Mapping[str, Any]) -> Any:
    # Prefer the scan decision timestamp when available.  Older scan rows only
    # carried last_candle_time; keep it as a compatibility fallback.
    for key in ("scan_at", "decision_time", "updated_at"):
        if row.get(key) not in (None, ""):
            return row.get(key)
    for evidence in row.get("evidence") or []:
        if isinstance(evidence, Mapping) and evidence.get("last_candle_time") not in (None, ""):
            return evidence.get("last_candle_time")
    return None


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
    raw_reason = execution.get("reason") or proposal.get("reason") or row.get("reason")

    candidate = selected.get("symbol") or proposal.get("selected_contract")
    option_type = str(selected.get("option_type") or proposal.get("desired_option_type") or "").upper()
    expression = "LONG CALL" if option_type in {"CALL", "CE"} else "LONG PUT" if option_type in {"PUT", "PE"} else None

    # Premium geometry is deliberately isolated from the underlying setup.  A
    # missing/zero premium plan remains None/WAIT; underlying NIFTY levels are
    # never substituted here.
    premium_entry = _positive(risk_plan.get("entry"))
    premium_stop = _positive(risk_plan.get("stop"))
    premium_target = _positive(risk_plan.get("target"))
    geometry_ok = bool(
        premium_entry is not None
        and premium_stop is not None
        and premium_target is not None
        and premium_stop < premium_entry < premium_target
    )
    rr = ((premium_target - premium_entry) / (premium_entry - premium_stop)) if geometry_ok else None

    expected_value = _number(selected.get("option_expected_value_r"))
    if expected_value is None:
        expected_value = _number(row.get("adaptive_expected_value_r"))
    confidence = _number(row.get("adaptive_confidence"))
    probability = _number(row.get("adaptive_probability_win"))
    direction = str(row.get("adaptive_side") or row.get("side") or "").upper() or None
    bias = direction if direction in {"LONG", "SHORT"} else None
    market_session = row.get("session_open")

    quote = _mapping(selected.get("quote"))
    economics = _mapping(selected.get("economics"))
    spec = _mapping(selected.get("instrument_spec"))

    reasons: list[str] = []
    if row.get("success") is False:
        _append_reason(reasons, raw_reason or row.get("message") or "STALE_DATA")
    if market_session is False:
        _append_reason(reasons, "MARKET_SESSION_CLOSED")
    if not bias:
        _append_reason(reasons, "NO_DIRECTION")
    if expected_value is not None and expected_value <= 0:
        _append_reason(reasons, "NON_POSITIVE_EV")
    _append_reason(reasons, raw_reason)
    for item in blockers:
        _append_reason(reasons, item)
    if candidate and risk_plan and not geometry_ok:
        _append_reason(reasons, "INVALID_RISK_LEVELS")
    primary_reason = _primary_reason(reasons)

    opened = bool(execution.get("success")) and bool(
        execution.get("position_id")
        or str(execution.get("reason") or "").upper() == "PAPER_POSITION_OPENED"
    )
    if opened:
        status, execution_stage = "POSITION_OPEN", "POSITION_OPEN"
    elif execution and execution.get("success") is False:
        status = "BLOCKED" if primary_reason in _OPERATIONAL_BLOCKERS else "WAIT"
        execution_stage = primary_reason or str(verdict.get("stage") or "PORTFOLIO_CHECKED")
    elif proposal.get("executable") is True and candidate and not reasons:
        status, execution_stage = "ACTIONABLE", "ACTIONABLE"
    elif row.get("adaptive_executable") is True and not reasons:
        status, execution_stage = "QUALIFYING", "STRATEGY_EVALUATED"
    else:
        status = "WAIT"
        execution_stage = primary_reason or str(verdict.get("stage") or "DISCOVERED")

    raw_reason_text = " ".join([str(raw_reason or ""), *blockers]).upper()
    gates: dict[str, dict[str, Any]] = {}
    gates["DATA_FRESHNESS"] = _gate(
        "PASS" if row.get("success") is not False else "BLOCKED",
        row.get("message") if row.get("success") is False else None,
    )
    gates["MARKET_SESSION"] = _gate(
        "PASS" if market_session is True else "BLOCKED" if market_session is False else "WAIT",
        "MARKET_SESSION_CLOSED" if market_session is False else None,
    )
    gates["DIRECTION"] = _gate("PASS" if bias else "BLOCKED", "NO_DIRECTION" if not bias else None)
    gates["EXPECTED_VALUE"] = _gate(
        "PASS" if expected_value is not None and expected_value > 0 else "BLOCKED" if expected_value is not None else "WAIT",
        expected_value,
    )

    # CHAIN/CONTRACT below describe only the chain actually consumed by the
    # autonomous proposal.  The browser's manually viewed chain is presented
    # separately by v16_option_decision_runtime.js and never changes this gate.
    chain_consumed = bool(proposal) and (candidate is not None or proposal.get("executable") is not None)
    chain_failure = "CHAIN" in raw_reason_text
    gates["AUTONOMOUS_CHAIN"] = _gate("PASS" if chain_consumed else "BLOCKED" if chain_failure else "WAIT", raw_reason)
    contract_failure = any(token in raw_reason_text for token in ("OPTION_SYMBOL", "CONTRACT", "INSTRUMENT_SPEC"))
    gates["CONTRACT"] = _gate("PASS" if candidate else "BLOCKED" if contract_failure else "WAIT", raw_reason)
    gates["LIQUIDITY"] = _gate("PASS" if candidate and economics else "WAIT")
    gates["SPREAD"] = _gate("PASS" if economics.get("spread_pct") is not None else "WAIT", economics.get("spread_pct"))
    gates["OI"] = _gate("PASS" if quote.get("open_interest") is not None else "WAIT", quote.get("open_interest"))
    gates["INSTRUMENT_SPEC"] = _gate("PASS" if spec else "BLOCKED" if "INSTRUMENT_SPEC" in raw_reason_text else "WAIT", raw_reason)
    gates["DUPLICATE_EXPOSURE"] = _gate(
        "BLOCKED" if "UNDERLYING_OPTION_EXPOSURE_EXISTS" in raw_reason_text else "PASS" if candidate else "WAIT",
        raw_reason,
    )
    gates["RISK_GEOMETRY"] = _gate("PASS" if geometry_ok else "BLOCKED" if candidate and risk_plan else "WAIT", "INVALID_RISK_LEVELS" if candidate and risk_plan and not geometry_ok else None)

    quantity = _positive(execution.get("quantity") or sizing.get("quantity") or sizing.get("planned_quantity") or sizing.get("lots"))
    risk = _positive(execution.get("risk") or sizing.get("risk") or sizing.get("planned_risk") or sizing.get("risk_amount"))
    gates["CAPITAL"] = _gate("BLOCKED" if "INSUFFICIENT_CAPITAL" in reasons else "PASS" if quantity is not None or opened else "WAIT", primary_reason)
    gates["OPEN_RISK"] = _gate("BLOCKED" if "MAX_OPEN_RISK" in reasons else "PASS" if opened else "WAIT", primary_reason)
    gates["PORTFOLIO_CORRELATION"] = _gate("BLOCKED" if "CORRELATION_LIMIT" in reasons else "PASS" if opened else "WAIT", primary_reason)

    fresh_quote = bool(execution.get("entry_reference") or execution.get("live_mark") or opened)
    exact_quote_failure = candidate and any(token in raw_reason_text for token in ("STALE_MARK", "MARK_UNAVAILABLE", "QUOTE", "LIVE_MARK_OUTSIDE_SETUP"))
    gates["FRESH_LIVE_OPTION_QUOTE"] = _gate("PASS" if fresh_quote else "BLOCKED" if exact_quote_failure else "WAIT", raw_reason)

    expiry = selected.get("expiry") or quote.get("expiry")
    strike = selected.get("strike")
    return {
        "status": status,
        "primary_reason": primary_reason,
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
        "rejection_reasons": reasons,
        "gates": gates,
        "updated_at": _decision_time(row),
        "source": "ADAPTIVE_SCANNER_OPTION_PROPOSAL",
        "paper_only": True,
        "live_execution": False,
        "automatic_broker_order": False,
    }


def _decision_rank(decision: Mapping[str, Any]) -> tuple[int, str]:
    priority = {
        "POSITION_OPEN": 5,
        "MANAGING": 5,
        "ACTIONABLE": 4,
        "QUALIFYING": 3,
        "BLOCKED": 2,
        "WAIT": 1,
    }
    return priority.get(str(decision.get("status") or "WAIT").upper(), 0), str(decision.get("updated_at") or "")


def summarise(rows: list[Mapping[str, Any]]) -> dict[str, Any]:
    """Classify scan rows and expose the scanner's real option decisions."""

    classified: list[dict[str, Any]] = []
    counts: dict[str, int] = {}
    autonomous_options: dict[str, dict[str, Any]] = {}
    for row in rows or ():
        verdict = classify_candidate(row)
        counts[verdict["stage"]] = counts.get(verdict["stage"], 0) + 1
        classified.append(
            {
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
            }
        )
        decision = _option_decision(row, verdict)
        if decision:
            existing = autonomous_options.get(decision["underlying"])
            if existing is None or _decision_rank(decision) >= _decision_rank(existing):
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
