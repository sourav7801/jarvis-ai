from __future__ import annotations

from typing import Any, Mapping

from omni.trading_intelligence.option_chain_schema import OptionChainSnapshot, normalize_option_chain
from omni.trading_intelligence.options_execution_intelligence_v151 import OPTIONS_EXECUTION_INTELLIGENCE_V151


SERVICE_VERSION = "OPTIONS_RUNTIME_V15_1"


def _snapshot_from_provider(value: Any, *, underlying: str) -> tuple[OptionChainSnapshot | None, bool, str]:
    if isinstance(value, OptionChainSnapshot):
        return value, False, "PROVIDER_DID_NOT_EXPOSE_VERIFICATION_METADATA"
    if not isinstance(value, Mapping):
        return None, False, "OPTION_CHAIN_PROVIDER_RETURNED_UNSUPPORTED_PAYLOAD"
    raw = dict(value)
    snapshot = raw.get("snapshot")
    if isinstance(snapshot, OptionChainSnapshot):
        verified = raw.get("verified") is True or str(raw.get("data_quality") or "").upper() == "VERIFIED"
        return snapshot, verified, "VERIFIED_PROVIDER_SNAPSHOT" if verified else "OPTION_CHAIN_NOT_VERIFIED"
    contracts = raw.get("contracts") or raw.get("rows") or raw.get("option_chain")
    spot = raw.get("spot") or raw.get("underlying_price")
    timestamp = raw.get("timestamp") or raw.get("generated_at")
    if not contracts or spot is None or timestamp is None:
        return None, False, "OPTION_CHAIN_FIELDS_UNAVAILABLE"
    try:
        normalized = normalize_option_chain(
            contracts,
            underlying=str(raw.get("underlying") or underlying),
            spot=float(spot),
            timestamp=str(timestamp),
            expiry=raw.get("expiry"),
        )
    except Exception as exc:
        return None, False, f"OPTION_CHAIN_NORMALIZATION_FAILED:{type(exc).__name__}"
    verified = raw.get("verified") is True or str(raw.get("data_quality") or "").upper() == "VERIFIED"
    return normalized, verified, "VERIFIED_PROVIDER_SNAPSHOT" if verified else "OPTION_CHAIN_NOT_VERIFIED"


def _instrument_specs(snapshot: OptionChainSnapshot) -> dict[str, dict[str, Any]]:
    from omni.trading_intelligence.instrument_master import instrument_master

    by_symbol: dict[str, dict[str, Any]] = {}
    wanted = {str(contract.symbol or "").upper() for contract in snapshot.contracts if contract.symbol}
    for item in instrument_master.all():
        symbol = str(getattr(item, "symbol", "") or "").upper()
        if not symbol or symbol not in wanted:
            continue
        metadata = dict(getattr(item, "metadata", None) or {})
        verified = metadata.get("verified") is True or str(metadata.get("data_quality") or "").upper() == "VERIFIED"
        lot_size = getattr(item, "lot_size", None)
        tick_size = getattr(item, "tick_size", None)
        if not verified or lot_size is None or tick_size is None:
            continue
        by_symbol[symbol] = {
            "symbol": symbol,
            "provider_symbol": getattr(item, "provider_symbol", None) or symbol,
            "underlying": getattr(item, "underlying", None),
            "expiry": getattr(item, "expiry", None),
            "strike": getattr(item, "strike", None),
            "option_type": getattr(getattr(item, "option_type", None), "value", None),
            "lot_size": float(lot_size),
            "contract_multiplier": float(lot_size),
            "quantity_step": 1.0,
            "tick_size": float(tick_size),
            "currency": getattr(item, "currency", None) or "INR",
            "native_currency": getattr(item, "currency", None) or "INR",
            "valuation_currency": getattr(item, "currency", None) or "INR",
            "source": str(metadata.get("source") or "INSTRUMENT_MASTER"),
            "verified": True,
            "verification_reason": str(metadata.get("verification_reason") or "VERIFIED_INSTRUMENT_MASTER"),
            "cost_model_status": str(metadata.get("cost_model_status") or "UNCONFIGURED"),
        }
    return by_symbol


def _underlying_decision(symbol: str) -> dict[str, Any]:
    from workstation.quant_terminal_v15_bridge import reasoning_trace

    trace = reasoning_trace(symbol, persist=False)
    best = trace.get("best_sample") if isinstance(trace.get("best_sample"), Mapping) else None
    if not best:
        return {
            "success": False,
            "executable": False,
            "side": "WAIT",
            "expected_value_r": 0.0,
            "reason": "V15_UNDERLYING_REASONING_UNAVAILABLE",
        }
    decision = best.get("decision") if isinstance(best.get("decision"), Mapping) else {}
    return {
        **dict(decision),
        "profile": best.get("profile"),
        "pipeline_stop_reason": best.get("pipeline_stop_reason"),
        "legacy_score_observation": best.get("legacy_score"),
    }


def plan(symbol: str = "NIFTY", *, provider_name: str = "fyers") -> dict[str, Any]:
    canonical = str(symbol or "NIFTY").strip().upper() or "NIFTY"
    provider_key = str(provider_name or "fyers").strip().lower() or "fyers"
    from omni.trading_intelligence.option_chain_provider import option_chain_providers

    provider = option_chain_providers.get(provider_key)
    if provider is None:
        return {
            "success": True,
            "version": "15.1",
            "service": SERVICE_VERSION,
            "underlying": canonical,
            "action": "NO_OPTION_TRADE",
            "executable": False,
            "reason": "OPTION_CHAIN_PROVIDER_UNAVAILABLE",
            "provider": provider_key,
            "registered_providers": list(option_chain_providers.status().get("providers") or []),
            "paper_only": True,
            "live_execution": False,
            "automatic_broker_order": False,
        }
    try:
        raw = provider.snapshot(canonical)
    except Exception as exc:
        return {
            "success": True,
            "version": "15.1",
            "service": SERVICE_VERSION,
            "underlying": canonical,
            "action": "NO_OPTION_TRADE",
            "executable": False,
            "reason": f"OPTION_CHAIN_PROVIDER_ERROR:{type(exc).__name__}",
            "provider": provider_key,
            "paper_only": True,
            "live_execution": False,
            "automatic_broker_order": False,
        }
    snapshot, verified, verification_reason = _snapshot_from_provider(raw, underlying=canonical)
    if snapshot is None:
        return {
            "success": True,
            "version": "15.1",
            "service": SERVICE_VERSION,
            "underlying": canonical,
            "action": "NO_OPTION_TRADE",
            "executable": False,
            "reason": verification_reason,
            "provider": provider_key,
            "paper_only": True,
            "live_execution": False,
            "automatic_broker_order": False,
        }
    specs = _instrument_specs(snapshot)
    decision = _underlying_decision(canonical)
    result = OPTIONS_EXECUTION_INTELLIGENCE_V151.evaluate(
        snapshot,
        decision,
        verified_snapshot=verified,
        verified_specs=specs,
    )
    return {
        **result,
        "provider": provider_key,
        "snapshot_verification_reason": verification_reason,
        "verified_instrument_specs": len(specs),
        "read_only_chain_provider": True,
        "paper_only": True,
        "live_execution": False,
        "automatic_broker_order": False,
    }


def status() -> dict[str, Any]:
    from omni.trading_intelligence.option_chain_provider import option_chain_providers
    from omni.trading_intelligence.options_volatility_synthesis_v13 import OPTIONS_VOLATILITY_SYNTHESIS_V13
    from workstation.options_paper_execution_v151 import OPTIONS_PAPER_EXECUTION_V151

    return {
        "success": True,
        "version": "15.1",
        "service": SERVICE_VERSION,
        "intelligence": OPTIONS_EXECUTION_INTELLIGENCE_V151.status(),
        "paper_execution": OPTIONS_PAPER_EXECUTION_V151.status(),
        "chain_provider_registry": option_chain_providers.status(),
        "volatility_intelligence": OPTIONS_VOLATILITY_SYNTHESIS_V13.status(),
        "read_only_chain_provider_preserved": True,
        "verified_chain_required_for_option_trade": True,
        "verified_lot_size_and_tick_size_required": True,
        "underlying_v15_reasoning_required": True,
        "paper_only": True,
        "live_execution": False,
        "automatic_broker_order": False,
    }


__all__ = ["plan", "status", "SERVICE_VERSION"]
