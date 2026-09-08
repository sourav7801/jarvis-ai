from __future__ import annotations

from copy import deepcopy
from math import isfinite
from typing import Any, Iterable, Mapping


GEOMETRY_VERSION = "VERIFIED_RISK_GEOMETRY_V14_1"


def _f(value: Any, default: float | None = None) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return number if isfinite(number) else default


def _positive(value: Any) -> float | None:
    number = _f(value)
    return number if number is not None and number > 0.0 else None


def _side(row: Mapping[str, Any]) -> str:
    for value in (row.get("candidate_side"), row.get("side")):
        token = str(value or "").strip().upper()
        if token in {"LONG", "SHORT"}:
            return token
    return "WAIT"


def _valid_geometry(side: str, entry: Any, stop: Any, target: Any) -> bool:
    e = _positive(entry)
    s = _positive(stop)
    t = _positive(target)
    if e is None or s is None or t is None:
        return False
    if side == "LONG":
        return s < e < t
    if side == "SHORT":
        return t < e < s
    return False


def _evidence_side(item: Mapping[str, Any]) -> str:
    decision = item.get("decision") if isinstance(item.get("decision"), Mapping) else {}
    decision_side = str(decision.get("side") or "").strip().upper()
    if decision_side in {"LONG", "SHORT"}:
        return decision_side
    trend = str(item.get("trend") or "").strip().upper()
    return "LONG" if trend == "BULLISH" else "SHORT" if trend == "BEARISH" else "WAIT"


def _profile_priority(
    profile: str,
    evidence: Iterable[Mapping[str, Any]],
    side: str,
) -> list[dict[str, Any]]:
    rows = [dict(item) for item in evidence if isinstance(item, Mapping)]
    profile_token = str(profile or "").strip().lower()
    if profile_token == "5m_only":
        order = ("5m", "10m", "15m", "1h", "4h", "1d")
    elif profile_token == "10m_only":
        order = ("10m", "5m", "15m", "1h", "4h", "1d")
    elif profile_token == "15m_only":
        order = ("15m", "10m", "5m", "1h", "4h", "1d")
    elif profile_token == "swing":
        order = ("4h", "1d", "1h", "15m", "10m", "5m")
    elif profile_token == "investment":
        order = ("1d", "4h", "1h", "15m", "10m", "5m")
    else:
        order = ("15m", "10m", "5m", "1h", "4h", "1d")
    rank = {timeframe: index for index, timeframe in enumerate(order)}
    rows.sort(
        key=lambda item: (
            0 if _evidence_side(item) == side else 1,
            rank.get(str(item.get("timeframe") or ""), len(order)),
        )
    )
    return rows


def _eligible_evidence(row: Mapping[str, Any], side: str) -> list[dict[str, Any]]:
    eligible: list[dict[str, Any]] = []
    for raw in list(row.get("evidence") or []):
        if not isinstance(raw, Mapping):
            continue
        item = dict(raw)
        if item.get("available") is not True:
            continue
        if item.get("fresh") is False:
            continue
        close = _positive(item.get("close"))
        atr = _positive(item.get("atr14"))
        if close is None or atr is None:
            continue
        # Evidence is accepted only from the existing verified completed-bar scan
        # path. The builder never requests or fabricates candles independently.
        complete_bars = int(item.get("complete_bars") or 0)
        if complete_bars < 15:
            continue
        eligible.append(item)
    return _profile_priority(str(row.get("profile") or ""), eligible, side)


def _bounded_risk_distance(entry: float, atr: float, structural_distance: float | None) -> float:
    minimum = max(atr * 0.75, entry * 0.00025)
    maximum = max(atr * 2.50, minimum)
    preferred = atr * 1.20
    if structural_distance is not None and structural_distance > 0.0:
        preferred = max(preferred, structural_distance)
    return max(minimum, min(preferred, maximum))


def _build_from_anchor(row: Mapping[str, Any], anchor: Mapping[str, Any], side: str) -> dict[str, Any]:
    entry = _positive(anchor.get("close"))
    atr = _positive(anchor.get("atr14"))
    if entry is None or atr is None:
        return {
            "success": False,
            "reason": "VERIFIED_CLOSE_OR_ATR_UNAVAILABLE",
            "geometry_version": GEOMETRY_VERSION,
            "paper_only": True,
            "live_execution": False,
        }

    support = _positive(anchor.get("support"))
    resistance = _positive(anchor.get("resistance"))
    buffer = max(atr * 0.10, entry * 0.0001)

    if side == "LONG":
        structural_stop = support - buffer if support is not None and support < entry else None
        structural_distance = entry - structural_stop if structural_stop is not None else None
        risk_distance = _bounded_risk_distance(entry, atr, structural_distance)
        stop = entry - risk_distance
        structural_target = resistance if resistance is not None and resistance > entry else None
        if structural_target is not None and (structural_target - entry) >= risk_distance * 1.25:
            target = structural_target
            target_method = "VERIFIED_RESISTANCE"
        else:
            target = entry + risk_distance * 2.0
            target_method = "ATR_RISK_EXTENSION_2R"
    elif side == "SHORT":
        structural_stop = resistance + buffer if resistance is not None and resistance > entry else None
        structural_distance = structural_stop - entry if structural_stop is not None else None
        risk_distance = _bounded_risk_distance(entry, atr, structural_distance)
        stop = entry + risk_distance
        structural_target = support if support is not None and support < entry else None
        if structural_target is not None and (entry - structural_target) >= risk_distance * 1.25:
            target = structural_target
            target_method = "VERIFIED_SUPPORT"
        else:
            target = entry - risk_distance * 2.0
            target_method = "ATR_RISK_EXTENSION_2R"
    else:
        return {
            "success": False,
            "reason": "NO_DIRECTIONAL_EDGE",
            "geometry_version": GEOMETRY_VERSION,
            "paper_only": True,
            "live_execution": False,
        }

    reward_distance = abs(target - entry)
    risk_distance = abs(entry - stop)
    risk_reward = reward_distance / risk_distance if risk_distance > 0 else 0.0
    if not _valid_geometry(side, entry, stop, target) or risk_reward <= 0.0:
        return {
            "success": False,
            "reason": "DERIVED_GEOMETRY_FAILED_VALIDATION",
            "geometry_version": GEOMETRY_VERSION,
            "paper_only": True,
            "live_execution": False,
        }

    return {
        "success": True,
        "geometry_version": GEOMETRY_VERSION,
        "side": side,
        "entry": float(entry),
        "stop": float(stop),
        "target": float(target),
        "risk_reward": float(risk_reward),
        "risk_distance": float(risk_distance),
        "reward_distance": float(reward_distance),
        "anchor_timeframe": anchor.get("timeframe"),
        "anchor_source": anchor.get("source"),
        "anchor_data_quality": anchor.get("data_quality"),
        "anchor_last_candle_time": anchor.get("last_candle_time"),
        "anchor_complete_bars": anchor.get("complete_bars"),
        "anchor_close": entry,
        "anchor_atr14": atr,
        "anchor_support": support,
        "anchor_resistance": resistance,
        "anchor_direction": _evidence_side(anchor),
        "anchor_direction_matches_candidate": _evidence_side(anchor) == side,
        "stop_method": "VERIFIED_STRUCTURE_PLUS_BOUNDED_ATR",
        "target_method": target_method,
        "derived_from_verified_completed_bar_evidence": True,
        "synthetic_market_data": False,
        "data_fabricated": False,
        "paper_only": True,
        "live_execution": False,
        "automatic_broker_order": False,
    }


def _clear_invalid_risk_token(row: dict[str, Any]) -> bool:
    blockers = [str(item) for item in list(row.get("blockers") or [])]
    reasons = [str(item) for item in list(row.get("reasons_not_to_trade") or [])]
    changed = "INVALID_RISK_LEVELS" in blockers or "INVALID_RISK_LEVELS" in reasons
    row["blockers"] = [item for item in blockers if item != "INVALID_RISK_LEVELS"]
    row["reasons_not_to_trade"] = [item for item in reasons if item != "INVALID_RISK_LEVELS"]
    return changed


def enrich_scan_row(raw: Mapping[str, Any]) -> dict[str, Any]:
    """Restore executable risk geometry without reviving legacy score authority.

    The legacy Quant consensus may intentionally suppress entry/stop/target when
    its historical qualification gates fail. V14+, however, treats those gates
    as evidence rather than authority. This bridge derives a bounded paper-only
    risk model from the scan's already-verified completed-bar evidence whenever
    direction exists but executable geometry is missing.

    INVALID_RISK_LEVELS is removed only after a geometry object passes strict
    directional validation. All other blockers are preserved untouched.
    """

    row = deepcopy(dict(raw))
    side = _side(row)
    existing_valid = _valid_geometry(side, row.get("entry"), row.get("stop"), row.get("target"))
    if existing_valid:
        cleared = _clear_invalid_risk_token(row)
        row["risk_geometry_v141"] = {
            "success": True,
            "geometry_version": GEOMETRY_VERSION,
            "state": "EXISTING_VALID_GEOMETRY",
            "derived": False,
            "stale_invalid_risk_token_cleared": cleared,
            "paper_only": True,
            "live_execution": False,
        }
        if cleared:
            row["risk_geometry_repaired"] = True
            row["risk_geometry_source"] = GEOMETRY_VERSION
        return row

    if not row.get("success"):
        row["risk_geometry_v141"] = {
            "success": False,
            "geometry_version": GEOMETRY_VERSION,
            "state": "NOT_ATTEMPTED_DATA_UNAVAILABLE",
            "paper_only": True,
            "live_execution": False,
        }
        return row
    if side not in {"LONG", "SHORT"}:
        row["risk_geometry_v141"] = {
            "success": False,
            "geometry_version": GEOMETRY_VERSION,
            "state": "NOT_ATTEMPTED_NO_DIRECTION",
            "reason": "NO_DIRECTIONAL_EDGE",
            "paper_only": True,
            "live_execution": False,
        }
        return row

    evidence = _eligible_evidence(row, side)
    if not evidence:
        row["risk_geometry_v141"] = {
            "success": False,
            "geometry_version": GEOMETRY_VERSION,
            "state": "BLOCKED_VERIFIED_GEOMETRY_INPUT_UNAVAILABLE",
            "reason": "VERIFIED_RISK_GEOMETRY_INPUT_UNAVAILABLE",
            "paper_only": True,
            "live_execution": False,
        }
        return row

    geometry = _build_from_anchor(row, evidence[0], side)
    if not geometry.get("success"):
        row["risk_geometry_v141"] = {**geometry, "state": "DERIVATION_FAILED"}
        return row

    row["entry"] = geometry["entry"]
    row["stop"] = geometry["stop"]
    row["target"] = geometry["target"]
    row["risk_reward"] = geometry["risk_reward"]
    row["risk_model"] = {
        **geometry,
        "source": GEOMETRY_VERSION,
        "legacy_qualification_required": False,
    }
    row["risk_geometry_v141"] = {
        **geometry,
        "state": "DERIVED_VALID_GEOMETRY",
        "derived": True,
    }

    _clear_invalid_risk_token(row)
    row["risk_geometry_repaired"] = True
    row["risk_geometry_source"] = GEOMETRY_VERSION

    setup = dict(row.get("setup") or {})
    setup.update({
        "side": "BULLISH" if side == "LONG" else "BEARISH",
        "entry_reference": geometry["entry"],
        "stop_reference": geometry["stop"],
        "target_reference": geometry["target"],
        "risk_reward_reference": geometry["risk_reward"],
        "status": "V14_1_VERIFIED_DERIVED_RISK_GEOMETRY",
        "timeframe": geometry.get("anchor_timeframe"),
        # V14 positive-EV authority decides executability after this stage.
        "executable_now": False,
        "legacy_qualification_required": False,
    })
    row["setup"] = setup
    return row


def status() -> dict[str, Any]:
    return {
        "success": True,
        "version": "14.1",
        "service": "JARVIS_VERIFIED_RISK_GEOMETRY_V14_1",
        "geometry_version": GEOMETRY_VERSION,
        "legacy_qualified_required": False,
        "invalid_risk_levels_remains_hard_blocker_when_geometry_unavailable": True,
        "verified_completed_bar_evidence_only": True,
        "prefers_candidate_aligned_evidence": True,
        "uses_close": True,
        "uses_atr14": True,
        "uses_support_resistance_when_available": True,
        "data_fabricated": False,
        "paper_only": True,
        "live_execution": False,
        "automatic_broker_order": False,
    }


__all__ = ["GEOMETRY_VERSION", "enrich_scan_row", "status"]
