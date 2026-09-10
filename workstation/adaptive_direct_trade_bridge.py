from __future__ import annotations

from datetime import datetime, timezone
from threading import RLock
from typing import Any

from omni.trading_intelligence.adaptive_opportunity_policy import ADAPTIVE_OPPORTUNITY_POLICY


_LOCK = RLock()
_INSTALLED = False


def _learning_state() -> dict[str, Any]:
    try:
        from omni.trading_intelligence.trade_learning_engine import learning_engine

        value = learning_engine.status()
        return dict(value) if isinstance(value, dict) else {}
    except Exception:
        return {}


def _allowed_sides(profile: str) -> tuple[str, ...]:
    return ("LONG",) if str(profile or "").strip().lower() == "investment" else ("LONG", "SHORT")


def _adaptive_decision(row: dict[str, Any], profile: str | None = None) -> dict[str, Any]:
    return ADAPTIVE_OPPORTUNITY_POLICY.evaluate(
        row,
        learning_state=_learning_state(),
        allowed_sides=_allowed_sides(profile or str(row.get("profile") or "intraday")),
    )


def _adaptive_live_entry(candidate: dict[str, Any]) -> tuple[float | None, str | None]:
    """Validate a current paper entry by re-estimating edge at the live mark.

    V12 intentionally removes the legacy fixed 1.30 live-R:R and percentage
    drift cutoffs from execution authority. The mark must still be valid and
    remain strictly inside the verified stop/target envelope. The current R:R
    is then fed back through the adaptive expected-value policy; if the edge has
    decayed, the trade is rejected rather than chased.
    """

    from workstation.paper_trading_desk import live_mark_loader

    try:
        decision_entry = float(candidate["entry"])
        stop = float(candidate["stop"])
        target = float(candidate["target"])
    except (KeyError, TypeError, ValueError):
        return None, "INVALID_RISK_LEVELS"

    mark = live_mark_loader(str(candidate.get("symbol") or ""))
    if mark is None:
        return None, "LIVE_MARK_UNAVAILABLE"
    try:
        mark = float(mark)
    except (TypeError, ValueError):
        return None, "INVALID_MARK"
    if decision_entry <= 0 or mark <= 0:
        return None, "INVALID_MARK"

    side = str(
        (candidate.get("adaptive_decision") or {}).get("side")
        if isinstance(candidate.get("adaptive_decision"), dict)
        else candidate.get("candidate_side") or candidate.get("side") or ""
    ).upper()
    if side == "LONG":
        if not (stop < mark < target):
            return None, "LIVE_MARK_OUTSIDE_SETUP"
    elif side == "SHORT":
        if not (target < mark < stop):
            return None, "LIVE_MARK_OUTSIDE_SETUP"
    else:
        return None, "NO_DIRECTIONAL_EDGE"

    current_risk = abs(mark - stop)
    current_reward = abs(target - mark)
    if current_risk <= 0 or current_reward <= 0:
        return None, "INVALID_RISK_LEVELS"

    live_row = dict(candidate)
    live_row["entry"] = mark
    live_row["risk_reward"] = current_reward / current_risk
    live_row["candidate_side"] = side
    live_row["side"] = side
    profile = str(live_row.get("profile") or "intraday")
    live_decision = _adaptive_decision(live_row, profile)
    candidate["live_risk_reward"] = live_row["risk_reward"]
    candidate["live_adaptive_decision"] = live_decision
    if live_decision.get("executable") is not True:
        return None, "LIVE_ADAPTIVE_EDGE_DECAYED"
    candidate["adaptive_decision"] = live_decision
    candidate["risk_reward"] = live_row["risk_reward"]
    return mark, None


def install_adaptive_direct_trade_bridge() -> dict[str, Any]:
    """Make legacy paper-control routes use V12 adaptive authority.

    The protected parser and HTTP routes are preserved, but their execution
    authority is redirected to continuous expected value, uncertainty and
    learned paper outcomes. The legacy paper-autonomy singleton is rebound to
    the V12 adaptive singleton inside the current process. No live broker
    capability is imported or created.
    """

    global _INSTALLED
    with _LOCK:
        if _INSTALLED:
            return status()

        from workstation import paper_trade_action_router as router
        from workstation import paper_autonomy_engine as legacy_autonomy_module
        from workstation.adaptive_paper_autonomy_engine import adaptive_paper_autonomy
        from workstation.trading_timeframe_profiles import requested_trading_profile

        legacy_autonomy_module.paper_autonomy = adaptive_paper_autonomy

        if getattr(router, "_v12_adaptive_direct_installed", False):
            _INSTALLED = True
            return status()

        original_consensus = router._consensus_payload
        original_execute = router.execute_paper_trade_request

        def adaptive_consensus(symbol: str, profile: str = "intraday") -> dict[str, Any]:
            payload = dict(original_consensus(symbol, profile))
            payload["legacy_qualified"] = bool(payload.get("qualified"))
            payload["legacy_side"] = payload.get("side")
            payload["profile"] = payload.get("profile") or profile
            decision = _adaptive_decision(payload, profile)
            payload["adaptive_decision"] = decision
            payload["decision_authority"] = "ADAPTIVE_EXPECTED_VALUE_NOT_STATIC_SCORE"
            payload["qualified"] = bool(decision.get("executable"))
            payload["side"] = decision.get("side") if decision.get("executable") else "WAIT"
            payload["paper_only"] = True
            payload["live_execution"] = False
            return payload

        def adaptive_qualified(row: dict[str, Any]) -> bool:
            decision = row.get("adaptive_decision") if isinstance(row.get("adaptive_decision"), dict) else None
            if decision is None:
                decision = _adaptive_decision(row, str(row.get("profile") or "intraday"))
                row["adaptive_decision"] = decision
            return bool(
                row.get("success")
                and decision.get("executable") is True
                and str(decision.get("side") or "").upper() in {"LONG", "SHORT"}
                and row.get("entry") is not None
                and row.get("stop") is not None
                and row.get("target") is not None
            )

        def adaptive_arm(profile: str = "intraday") -> dict[str, Any]:
            from workstation.paper_portfolio_controller import paper_portfolio_controller

            normalized = str(profile or "intraday").strip().lower()
            bucket = "SWING" if normalized == "swing" else "INVESTMENT" if normalized == "investment" else "INTRADAY"
            result = paper_portfolio_controller.start_bucket(bucket, scan_now=True)
            return {
                **dict(result),
                "decision_authority": "ADAPTIVE_EXPECTED_VALUE_NOT_STATIC_SCORE",
                "paper_only": True,
                "live_execution": False,
                "automatic_broker_order": False,
            }

        def adaptive_execute(text: str) -> dict[str, Any]:
            from workstation.paper_trading_desk import paper_desk
            from workstation.paper_market_data import PAPER_MARKET_DATA

            symbols = router.resolve_trade_symbols(text)
            if not symbols:
                return original_execute(text)

            symbol = symbols[0]
            existing = router._already_open(symbol)
            if existing is not None:
                return {
                    "success": True,
                    "action": "paper_trade_existing_position",
                    "symbol": symbol,
                    "position": existing,
                    "speech": f"A paper position in {symbol} is already open. JARVIS did not duplicate exposure.",
                    "decision_authority": "ADAPTIVE_EXPECTED_VALUE_NOT_STATIC_SCORE",
                    "paper_only": True,
                    "live_execution": False,
                }

            profile_spec = requested_trading_profile(text)
            consensus = adaptive_consensus(symbol, profile_spec.name)
            rows = list(consensus.get("decisions") or [])
            best = consensus if adaptive_qualified(consensus) else None
            if best is None:
                autonomy = adaptive_arm(profile_spec.name)
                router._publish_event({
                    "type": "PAPER_TRADE_ARMED",
                    "symbol": symbol,
                    "provider": "JARVIS_V12_ADAPTIVE",
                    "reason": "NO_CURRENT_POSITIVE_EXPECTED_VALUE",
                })
                adaptive = consensus.get("adaptive_decision") or {}
                return {
                    "success": True,
                    "action": "paper_trade_armed",
                    "symbol": symbol,
                    "decisions": rows,
                    "consensus": consensus,
                    "adaptive_decision": adaptive,
                    "autonomy": autonomy,
                    "speech": (
                        f"{symbol} has no current positive adaptive paper edge. "
                        f"Legacy score {float(consensus.get('score') or 0.0):.1f} is only an observation, not a gate. "
                        f"Expected value is {float(adaptive.get('expected_value_r') or 0.0):+.3f}R with "
                        f"{float(adaptive.get('confidence') or 0.0) * 100:.1f}% confidence. "
                        "Adaptive scanning remains armed."
                    ),
                    "paper_only": True,
                    "live_execution": False,
                }

            entry, live_rejection = _adaptive_live_entry(best)
            if entry is None:
                autonomy = adaptive_arm(profile_spec.name)
                return {
                    "success": True,
                    "action": "paper_trade_armed",
                    "symbol": symbol,
                    "candidate": best,
                    "consensus": consensus,
                    "risk_gate": live_rejection,
                    "autonomy": autonomy,
                    "speech": (
                        f"{symbol} had an adaptive candidate, but current-price re-evaluation rejected entry: {live_rejection}. "
                        "JARVIS did not chase the setup; adaptive scanning remains armed."
                    ),
                    "paper_only": True,
                    "live_execution": False,
                }

            adaptive = dict(best.get("adaptive_decision") or {})
            side = str(adaptive.get("side") or best.get("candidate_side") or "").upper()
            if side not in _allowed_sides(profile_spec.name):
                return {
                    "success": True,
                    "action": "paper_trade_risk_rejected",
                    "symbol": symbol,
                    "risk_gate": "SIDE_NOT_ALLOWED",
                    "candidate": best,
                    "paper_only": True,
                    "live_execution": False,
                }

            try:
                instrument_spec = PAPER_MARKET_DATA.instrument_spec(symbol)
            except Exception:
                return {
                    "success": True,
                    "action": "paper_trade_risk_rejected",
                    "symbol": symbol,
                    "candidate": best,
                    "risk_gate": "INSTRUMENT_SPEC_UNAVAILABLE",
                    "speech": "Verified instrument accounting is unavailable. No paper exposure was opened.",
                    "paper_only": True,
                    "live_execution": False,
                }

            valuation_multiplier = 1.0
            if symbol in {"BTC", "ETH", "SOL", "BNB", "XRP"}:
                try:
                    valuation_quote = PAPER_MARKET_DATA.quote(symbol)
                    native_ltp = float(valuation_quote.get("native_ltp") or 0.0)
                    valuation_ltp = float(valuation_quote.get("valuation_ltp") or 0.0)
                    if not valuation_quote.get("success") or native_ltp <= 0 or valuation_ltp <= 0:
                        raise ValueError("crypto valuation reference unavailable")
                    valuation_multiplier = valuation_ltp / native_ltp
                except Exception:
                    return {
                        "success": True,
                        "action": "paper_trade_risk_rejected",
                        "symbol": symbol,
                        "candidate": best,
                        "risk_gate": "VALUATION_FX_UNAVAILABLE",
                        "speech": "The crypto setup is valid, but verified valuation is unavailable. No paper exposure was opened.",
                        "paper_only": True,
                        "live_execution": False,
                    }

            bucket = "SWING" if profile_spec.name == "swing" else "INVESTMENT" if profile_spec.name == "investment" else "INTRADAY"
            allocation = {"INTRADAY": 0.50, "SWING": 0.30, "INVESTMENT": 0.20}[bucket]
            action = str(adaptive.get("action") or "PRIMARY").upper()
            adaptive_risk = max(0.0, float(adaptive.get("risk_multiplier") or 0.0))
            final_risk_multiplier = profile_spec.risk_multiplier * adaptive_risk
            now = datetime.now(timezone.utc)
            result = paper_desk.open_position(
                symbol=symbol,
                side=side,
                entry=float(entry),
                stop=float(best["stop"]),
                target=float(best["target"]),
                quantity=None,
                timeframe=str(best.get("timeframe") or ""),
                strategy="QUANT_ADAPTIVE_EXPECTED_VALUE_V12_DIRECT",
                score=float(best.get("score") or 0.0),
                source="DIRECT_ADAPTIVE_PAPER_COMMAND",
                asset_type=(
                    "CRYPTO" if symbol in {"BTC", "ETH", "SOL", "BNB", "XRP"}
                    else "COMMODITY" if symbol in {"CRUDEOIL", "GOLD", "SILVER", "NATURALGAS"}
                    else "MARKET"
                ),
                external_id=(
                    f"adaptive-direct:{symbol}:{best.get('timeframe')}:{profile_spec.name}:{action}:"
                    f"{now.strftime('%Y%m%dT%H%M%S')}"
                ),
                metadata={
                    "adaptive_decision": adaptive,
                    "adaptive_action": action,
                    "adaptive_expected_value_r": adaptive.get("expected_value_r"),
                    "adaptive_confidence": adaptive.get("confidence"),
                    "adaptive_probability_win": adaptive.get("probability_win"),
                    "adaptive_risk_multiplier": adaptive_risk,
                    "legacy_qualified": best.get("legacy_qualified"),
                    "legacy_score": best.get("score"),
                    "legacy_numeric_gates_are_execution_authority": False,
                    "regime": best.get("regime"),
                    "risk_reward": best.get("risk_reward"),
                    "alignment": best.get("alignment"),
                    "votes": best.get("votes") or [],
                    "decisions": best.get("decisions") or [],
                    "evidence_graph": best.get("evidence_graph") or [],
                    "contradictions": best.get("contradictions") or [],
                    "reasons_not_to_trade": best.get("reasons_not_to_trade") or [],
                    "profile": profile_spec.name,
                    "portfolio_bucket": bucket,
                    "bucket_allocation_fraction": allocation,
                    "command": str(text or "")[:500],
                    "decision_entry": best.get("entry"),
                    "validated_live_entry": entry,
                    "initial_risk": abs(float(entry) - float(best["stop"])),
                    "exit_policy": {
                        "breakeven_at_r": 1.0 if profile_spec.name in {"swing", "investment"} else 0.75,
                        "trailing_at_r": 1.5 if profile_spec.name in {"swing", "investment"} else 1.0,
                        "trailing_distance_r": 0.75 if profile_spec.name in {"swing", "investment"} else 0.50,
                        "trailing_target_r": 1.5 if profile_spec.name in {"swing", "investment"} else 1.0,
                        "scale_out": [
                            {"at_r": 1.0, "fraction": 0.34},
                            {"at_r": 2.0, "fraction": 0.50},
                        ],
                        "max_hold_minutes": 525600 if profile_spec.name == "investment" else 10080 if profile_spec.name == "swing" else 390,
                    },
                },
                risk_multiplier=final_risk_multiplier,
                valuation_multiplier=valuation_multiplier,
                instrument_spec=instrument_spec,
                portfolio_bucket=bucket,
                bucket_allocation_fraction=allocation,
            )

            if not result.get("success"):
                autonomy = adaptive_arm(profile_spec.name)
                return {
                    "success": True,
                    "action": "paper_trade_risk_rejected",
                    "symbol": symbol,
                    "candidate": best,
                    "paper_result": result,
                    "autonomy": autonomy,
                    "speech": (
                        f"{symbol} had positive adaptive expected value, but the persistent portfolio risk layer rejected entry: "
                        f"{result.get('reason')}. Adaptive scanning remains armed."
                    ),
                    "paper_only": True,
                    "live_execution": False,
                }

            adaptive_arm(profile_spec.name)
            router._publish_event({
                "type": "PAPER_POSITION_OPENED",
                "symbol": symbol,
                "provider": "JARVIS_V12_ADAPTIVE",
                "side": result.get("side"),
                "entry": result.get("entry"),
                "stop": result.get("stop"),
                "target": result.get("target"),
                "adaptive_action": action,
                "expected_value_r": adaptive.get("expected_value_r"),
                "confidence": adaptive.get("confidence"),
                "legacy_score": best.get("score"),
            })
            return {
                "success": True,
                "action": "paper_trade_opened",
                "symbol": symbol,
                "candidate": best,
                "consensus": consensus,
                "adaptive_decision": adaptive,
                "position": result,
                "decisions": rows,
                "speech": (
                    f"Adaptive {symbol} paper {action.lower()} opened {side} at {float(result.get('entry') or 0):.4f}; "
                    f"stop {float(result.get('stop') or 0):.4f}, target {float(result.get('target') or 0):.4f}. "
                    f"Expected value {float(adaptive.get('expected_value_r') or 0.0):+.3f}R, "
                    f"confidence {float(adaptive.get('confidence') or 0.0) * 100:.1f}%, "
                    f"legacy score {float(best.get('score') or 0.0):.1f} is observability only. "
                    "The persistent paper risk engine now manages the position."
                ),
                "paper_only": True,
                "live_execution": False,
            }

        router._v12_original_execute_paper_trade_request = original_execute
        router._consensus_payload = adaptive_consensus
        router._qualified = adaptive_qualified
        router._arm_autonomy = adaptive_arm
        router._live_entry = _adaptive_live_entry
        router.execute_paper_trade_request = adaptive_execute
        router._v12_adaptive_direct_installed = True
        _INSTALLED = True
        return status()


def status() -> dict[str, Any]:
    with _LOCK:
        return {
            "success": True,
            "version": "12.0",
            "installed": _INSTALLED,
            "direct_trade_authority": "ADAPTIVE_EXPECTED_VALUE_NOT_STATIC_SCORE",
            "legacy_autonomy_endpoint_redirected": _INSTALLED,
            "legacy_static_score_gate": False if _INSTALLED else None,
            "legacy_static_live_rr_gate": False if _INSTALLED else None,
            "live_entry_revalidated_by_expected_value": _INSTALLED,
            "confidence_scaled_direct_paper_risk": _INSTALLED,
            "persistent_paper_risk_preserved": True,
            "paper_only": True,
            "live_execution": False,
            "automatic_broker_order": False,
        }


__all__ = ["install_adaptive_direct_trade_bridge", "status"]
