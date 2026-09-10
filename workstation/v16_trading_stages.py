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

# Ordered pipeline. A candidate's stage is the furthest point it provably
# reached, so the terminal can show real progress rather than a binary verdict.
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

# Exact rejection reasons. A rejection is terminal for this candidate/cycle.
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

# Engine/provider reasons that already carry precise meaning are mapped onto
# the canonical vocabulary instead of being renamed away. Anything unmapped
# still surfaces verbatim; it is never silently dropped.
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


def canonical_reason(raw: Any) -> str:
    """Map a provider/engine reason onto the canonical vocabulary."""

    text = str(raw or "").strip().upper()
    if not text:
        return "UNCLASSIFIED"
    if text in REASON_ALIASES:
        return REASON_ALIASES[text]
    # Reasons are frequently namespaced, e.g. "BLOCKED:STALE_MARK" or
    # "MARK_UNAVAILABLE:TimeoutError". Match the longest known token present.
    for alias in sorted(REASON_ALIASES, key=len, reverse=True):
        if alias in text:
            return REASON_ALIASES[alias]
    return text


def classify_candidate(row: Mapping[str, Any]) -> dict[str, Any]:
    """Return the exact stage reached by one scan candidate.

    ``stage`` is always a member of PROGRESS_STAGES or REJECTION_STAGES. The
    row's own evidence determines how far it travelled; nothing is assumed.
    """

    if not isinstance(row, Mapping):
        return {"stage": "DISCOVERED", "reason": "UNCLASSIFIED", "passed": [], "rejected_at": None}

    passed: list[str] = ["DISCOVERED"]
    rejected = row.get("reason") or row.get("message") or row.get("blocker")

    # Data certificate must have been valid before any strategy work counted.
    certificate = row.get("certificate") if isinstance(row.get("certificate"), Mapping) else {}
    data_ok = bool(row.get("verified", certificate.get("verified", True))) and not row.get("stale")
    if not data_ok:
        return {
            "stage": canonical_stage("STALE_DATA"),
            "reason": canonical_reason(rejected or "DATA_NOT_LIVE"),
            "passed": passed,
            "rejected_at": "DATA_VALIDATED",
        }
    passed.append("DATA_VALIDATED")

    side = str(row.get("side") or row.get("action") or row.get("adaptive_action") or "").strip().upper()
    if side in {"", "WAIT", "HOLD", "NONE", "NO_TRADE", "FLAT"}:
        return {
            "stage": canonical_stage("NO_DIRECTION"),
            "reason": canonical_reason(rejected or "NO_DIRECTION"),
            "passed": passed,
            "rejected_at": "STRATEGY_EVALUATED",
        }
    passed.append("STRATEGY_EVALUATED")

    entry, stop = row.get("entry"), row.get("stop")
    try:
        entry, stop = float(entry), float(stop)
        geometry_ok = entry > 0 and stop > 0 and entry != stop
    except (TypeError, ValueError):
        geometry_ok = False
    if not geometry_ok:
        return {
            "stage": canonical_stage("INVALID_RISK_LEVELS"),
            "reason": canonical_reason(rejected or "INVALID_RISK_LEVELS"),
            "passed": passed,
            "rejected_at": "RISK_MODEL_BUILT",
        }
    passed.append("RISK_MODEL_BUILT")

    expected_value = row.get("expected_value_r", row.get("ev_r"))
    try:
        expected_value = float(expected_value)
    except (TypeError, ValueError):
        expected_value = None
    if expected_value is not None and expected_value <= 0:
        return {
            "stage": canonical_stage("NON_POSITIVE_EV"),
            "reason": canonical_reason(rejected or "NON_POSITIVE_EV"),
            "passed": passed,
            "rejected_at": "CONTEXTUAL_EV_CALCULATED",
            "expected_value_r": expected_value,
        }
    if expected_value is not None:
        passed.append("CONTEXTUAL_EV_CALCULATED")

    if rejected:
        return {
            "stage": canonical_reason(rejected) if canonical_reason(rejected) in REJECTION_STAGES else "PORTFOLIO_CHECKED",
            "reason": canonical_reason(rejected),
            "passed": passed,
            "rejected_at": "PORTFOLIO_CHECKED",
        }

    quantity = row.get("quantity", row.get("qty"))
    try:
        sized = float(quantity) > 0
    except (TypeError, ValueError):
        sized = False
    if not sized:
        return {
            "stage": canonical_stage("INSUFFICIENT_CAPITAL"),
            "reason": "SIZE_NOT_PLANNED",
            "passed": passed,
            "rejected_at": "SIZE_PLANNED",
        }
    passed.append("SIZE_PLANNED")
    passed.append("ACTIONABLE")
    return {
        "stage": "ACTIONABLE",
        "reason": None,
        "passed": passed,
        "rejected_at": None,
        "expected_value_r": expected_value,
    }


def canonical_stage(reason: Any) -> str:
    """Return the canonical rejection stage for a reason."""

    mapped = canonical_reason(reason)
    return mapped if mapped in REJECTION_STAGES else "UNCLASSIFIED"


def stage_order(stage: str) -> int:
    """Sort key: progress stages ascending, rejections after all progress."""

    text = str(stage or "").strip().upper()
    if text in PROGRESS_STAGES:
        return PROGRESS_STAGES.index(text)
    return len(PROGRESS_STAGES) + (REJECTION_STAGES.index(text) if text in REJECTION_STAGES else 0)


def summarise(rows: list[Mapping[str, Any]]) -> dict[str, Any]:
    """Classify a scan payload into stage counts plus per-candidate detail."""

    classified = []
    counts: dict[str, int] = {}
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
    classified.sort(key=lambda item: stage_order(item["stage"]), reverse=True)
    return {
        "candidates": classified,
        "stage_counts": counts,
        "actionable": sum(1 for c in classified if c["stage"] == "ACTIONABLE"),
        "progress_stages": list(PROGRESS_STAGES),
        "rejection_stages": list(REJECTION_STAGES),
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
